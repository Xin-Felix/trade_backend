# -*- coding: utf-8 -*-
"""市场拥挤度 / 每日复盘 API 路由

从 market_congestion 项目迁移。前端 web-vue 调用的所有接口都在这里。
前端请求路径：/api/v1/mc/...
"""

import logging
import threading
from functools import lru_cache, wraps
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# 简单内存缓存（与原 market_congestion 的 cache.py 等效）
# ---------------------------------------------------------------------------
import hashlib
import json
import time as _time

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 14400  # 4 小时（行情数据盘后才更新，白天不变）


def _cache_key(prefix: str, *args, **kwargs) -> str:
    payload = json.dumps({"a": args, "k": sorted(kwargs.items())}, default=str, sort_keys=True)
    return f"{prefix}:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def cached(prefix: str, ttl: int = _CACHE_TTL):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = _cache_key(prefix, *args, **kwargs)
            with _cache_lock:
                hit = _cache.get(key)
                if hit and _time.time() < hit[0]:
                    return hit[1]
            result = fn(*args, **kwargs)
            if result is not None:
                with _cache_lock:
                    _cache[key] = (_time.time() + ttl, result)
            return result
        return wrapper
    return decorator


def clear_cache():
    with _cache_lock:
        n = len(_cache)
        _cache.clear()
    return n


def warm_cache():
    """预热核心接口缓存（pipeline 完成后或启动时调用）。
    如果 mc_summary 有预计算数据，预热秒完成；否则跳过（等 pipeline 跑完再热）。
    """
    import threading

    def _warm():
        try:
            from app.market.core import database as _db
            # 检查是否有预计算数据，没有就不预热（避免冷启动时全量计算拖慢启动）
            test = _db.read_summary("agg_market_overview")
            if not test:
                logger.info("[Cache] 无预计算数据，跳过预热（等 pipeline 执行后自动预热）")
                return

            logger.info("[Cache] 开始预热核心接口...")
            healthz()
            overview()
            signals()
            updn()
            board_shares()
            board_amounts()
            board_flow()
            board_congestion()
            breadth()
            margin_trend()
            review()
            trend_overview()
            snapshot()
            logger.info("[Cache] 预热完成")
        except Exception as e:
            logger.warning(f"[Cache] 预热部分失败: {e}")

    threading.Thread(target=_warm, daemon=True).start()


# ---------------------------------------------------------------------------
# 核心计算引擎（延迟加载，避免 import 时就连数据库）
# ---------------------------------------------------------------------------
_core = None
_core_lock = threading.Lock()


def _get_core():
    global _core
    if _core is not None:
        return _core
    with _core_lock:
        if _core is not None:
            return _core
        from app.market import core as _c
        _core = _c
        return _core


def _call(fn_name, *args, **kwargs):
    """调用 core 模块的函数，优先读取持久化预计算结果"""
    # 无参数调用时尝试从 mc_summary 读预计算结果（pipeline 产出）
    if not args and not kwargs:
        try:
            from app.market.core import database as _db
            cached = _db.read_summary(f"agg_{fn_name.replace('get_', '')}")
            if cached:
                return cached
        except Exception:
            pass
    core = _get_core()
    fn = getattr(core, fn_name)
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 统一响应
# ---------------------------------------------------------------------------
def ok(data=None, **meta):
    import datetime
    return {
        "code": 0, "msg": "ok",
        "meta": {"generated_at": datetime.datetime.now().isoformat(), **meta},
        "data": data
    }


def _norm_date(d: str | None) -> str | None:
    if not d:
        return None
    return str(d).strip().replace("-", "") or None


# ---------------------------------------------------------------------------
# 元信息
# ---------------------------------------------------------------------------

@router.get("/healthz", summary="数据健康状态")
def healthz():
    core = _get_core()
    dates = core.list_cached_daily_dates()
    latest = dates[-1] if dates else None
    info = core.get_cache_info()
    return ok({
        "ok": latest is not None,
        "latest_trade_date": latest,
        "cached_days": info.get("days", 0),
        "db_size_kb": info.get("size_kb", 0),
    }, trade_date=latest)


@router.get("/trade-dates", summary="交易日列表")
def trade_dates():
    core = _get_core()
    display_list, _ = core.fetch_trade_dates()
    latest = core.list_cached_daily_dates()
    return ok({"dates": display_list}, trade_date=latest[-1] if latest else None)


@router.get("/config", summary="客户端配置")
def client_config():
    from app.market.core import config as cfg
    return ok({
        "warn_threshold": cfg.WARN_THRESHOLD,
        "turnover_pct_line": cfg.TURNOVER_PCT_LINE,
        "conc_pct_line": cfg.CONC_PCT_LINE,
        "above60_line": cfg.ABOVE60_LINE,
        "bias_pct_line": cfg.BIAS_PCT_LINE,
        "nhnl_div_ratio": cfg.NHNL_DIV_RATIO,
        "board_options": cfg.BOARD_OPTIONS,
        "threshold_options": cfg.THRESHOLD_OPTIONS,
    })


# ---------------------------------------------------------------------------
# 总览页
# ---------------------------------------------------------------------------

@router.get("/market/snapshot", summary="大盘快照")
@cached("snapshot")
def snapshot(date: str | None = Query(None)):
    return _call("get_daily_snapshot", _norm_date(date))


@router.get("/market/overview", summary="全市场换手率")
@cached("market_overview")
def overview():
    return _call("get_market_overview")


@router.get("/market/signals", summary="综合市场信号")
@cached("market_signals")
def signals(date: str | None = Query(None)):
    return _call("get_market_signals", _norm_date(date))


@router.get("/market/updn", summary="涨跌走势")
@cached("updn_trend")
def updn(exclude_st: bool = Query(False), exclude_board: str | None = Query(None)):
    return _call("get_updn_trend", exclude_st=exclude_st, exclude_board=exclude_board or None)


# ---------------------------------------------------------------------------
# 板块
# ---------------------------------------------------------------------------

@router.get("/board/shares", summary="板块成交额占比")
@cached("board_shares")
def board_shares():
    return _call("get_board_shares")


@router.get("/board/amounts", summary="板块绝对成交额")
@cached("board_amounts")
def board_amounts():
    return _call("get_board_amounts")


@router.get("/board/flow", summary="板块资金净流入")
@cached("board_flow")
def board_flow():
    return _call("get_board_flow")


@router.get("/board/congestion", summary="板块拥挤度走势")
@cached("board_congestion")
def board_congestion():
    return _call("get_board_congestion_trend")


# ---------------------------------------------------------------------------
# 行业
# ---------------------------------------------------------------------------

@router.get("/industry/crowding", summary="行业拥挤度排名")
@cached("industry_crowding")
def industry_crowding(date: str | None = Query(None)):
    return _call("get_industry_crowding", _norm_date(date))


@router.get("/industry/trend", summary="行业走势")
@cached("industry_trend")
def industry_trend(industries: list[str] | None = Query(None)):
    return _call("get_industry_trend", list(industries) if industries else None)


@router.get("/industry/flow", summary="行业资金流入")
@cached("industry_flow")
def industry_flow(industries: list[str] | None = Query(None)):
    return _call("get_industry_flow", list(industries) if industries else None)


@router.get("/industry/list", summary="行业列表")
@cached("all_industries")
def all_industries():
    return _call("get_all_industries")


# ---------------------------------------------------------------------------
# 市场健康
# ---------------------------------------------------------------------------

@router.get("/breadth", summary="市场广度")
@cached("breadth")
def breadth():
    return _call("get_breadth")


@router.get("/margin/trend", summary="融资融券趋势")
@cached("margin_trend")
def margin_trend():
    return _call("get_margin_trend")


# ---------------------------------------------------------------------------
# 拥挤度
# ---------------------------------------------------------------------------

@router.get("/congestion/single", summary="单日拥挤度")
def congestion_single(
    board: str = Query("全部A股"),
    date: str | None = Query(None),
    top: int = Query(5),
    denom: str = Query("market"),
    exclude_new: bool = Query(False),
):
    result = _call("calc_market_congestion",
                   board=board, trade_date=_norm_date(date),
                   top_percent=top, denominator=denom, exclude_new=exclude_new)
    if result and result.get("date"):
        try:
            _call("save_history", result)
        except Exception:
            pass
    return ok(result, trade_date=(result or {}).get("date"))


@router.get("/congestion/series", summary="拥挤度序列")
@cached("congestion_series", ttl=3600)
def congestion_series(
    board: str = Query("全部A股"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    top: int = Query(5),
    denom: str = Query("market"),
    exclude_new: bool = Query(False),
):
    results = _call("batch_calc_market_congestion",
                    board=board, top_percent=top,
                    start_date=_norm_date(start), end_date=_norm_date(end),
                    denominator=denom, exclude_new=exclude_new, progress_callback=None)
    if results:
        try:
            _call("save_history_batch", results)
        except Exception:
            pass
    return {"results": results or []}


@router.get("/congestion/history", summary="拥挤度历史")
def congestion_history(start: str | None = Query(None), end: str | None = Query(None)):
    data = _call("load_history", _norm_date(start), _norm_date(end))
    return ok(data)


# ---------------------------------------------------------------------------
# 复盘 / 趋势
# ---------------------------------------------------------------------------

@router.get("/review", summary="每日复盘")
@cached("review")
def review(date: str | None = Query(None)):
    return _call("get_daily_review", _norm_date(date))


@router.get("/trend/overview", summary="趋势信号")
@cached("trend_overview")
def trend_overview():
    return _call("get_trend_overview")


# ---------------------------------------------------------------------------
# 选股
# ---------------------------------------------------------------------------

@router.get("/screener", summary="选股筛选")
def screener(
    date: str | None = Query(None),
    board: str | None = Query(None),
    industry: str | None = Query(None),
    pct_min: float | None = Query(None),
    pct_max: float | None = Query(None),
    amount_min: float | None = Query(None),
    amount_max: float | None = Query(None),
    exclude_st: bool = Query(True),
    search: str | None = Query(None),
    limit: int = Query(200),
):
    data = _call("screen_stocks",
                 trade_date=_norm_date(date), board=board or None,
                 industry=industry or None, pct_min=pct_min, pct_max=pct_max,
                 amount_min=amount_min, amount_max=amount_max,
                 exclude_st=exclude_st, search=search or None, limit=limit)
    return ok(data, trade_date=(data or {}).get("date"))


@router.get("/kline", summary="个股K线")
def kline(
    code: str = Query(...),
    period: str = Query("daily"),
    days: int = Query(120),
):
    return ok(_call("get_stock_kline", code, period=period, days=days))


# ---------------------------------------------------------------------------
# 期权
# ---------------------------------------------------------------------------

@router.get("/option/underlyings", summary="期权标的列表")
@cached("option_underlyings")
def option_underlyings():
    return _call("get_option_underlyings")


@router.get("/option/analysis", summary="期权分析")
@cached("option_analysis", ttl=60)
def option_analysis(code: str = Query(...)):
    return _call("get_option_analysis", code)


@router.get("/option/signals", summary="期权信号")
def option_signals(code: str | None = Query(None), limit: int = Query(50)):
    return ok(_call("get_option_signals", code, limit))


@router.get("/option/etf-kline", summary="ETF日K")
@cached("etf_kline")
def etf_kline(code: str = Query(...), days: int = Query(120)):
    return _call("get_etf_kline", code, days)


@router.get("/option/etf-minute", summary="ETF分钟K")
def etf_minute(code: str = Query(...), period: int = Query(1)):
    return ok(_call("get_etf_minute_kline", code, period))


# ---------------------------------------------------------------------------
# 管道管理
# ---------------------------------------------------------------------------

@router.post("/pipeline/trigger", summary="手动触发数据管道")
def trigger_pipeline(only: str | None = Query(None)):
    """手动触发 market congestion pipeline"""
    from app.market.pipeline import run_pipeline
    result = run_pipeline(force=True, only=only)
    return ok(result)


@router.post("/cache/clear", summary="清缓存")
def clear_cache_api():
    n = clear_cache()
    return ok({"cleared": n})
