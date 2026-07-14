"""国际市场数据服务。

提供美股指数、港股指数、黄金、原油、美元指数、人民币汇率等全球主要市场数据。
数据来源：AKShare（免费，实时性好）。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _get_ak():
    """延迟导入 akshare。"""
    import akshare as ak
    return ak


# ============================================================
# 全球指数实时行情
# ============================================================

# 主要国际指数代码映射（Tushare ts_code，同时作为对外 code）
GLOBAL_INDICES = {
    # 美股
    "DJI": {"name": "道琼斯", "market": "美股", "ts_code": "DJI"},
    "SPX": {"name": "标普500", "market": "美股", "ts_code": "SPX"},
    "IXIC": {"name": "纳斯达克", "market": "美股", "ts_code": "IXIC"},
    # 港股
    "HSI": {"name": "恒生指数", "market": "港股", "ts_code": "HSI"},
    "HSCEI": {"name": "国企指数", "market": "港股", "ts_code": "XIN9"},
    "HSTECH": {"name": "恒生科技", "market": "港股", "ts_code": "HKTECH"},
    # 亚太
    "N225": {"name": "日经225", "market": "日本", "ts_code": "N225"},
    "KS11": {"name": "韩国综合", "market": "韩国", "ts_code": "KS11"},
    # 欧洲
    "FTSE": {"name": "英国富时100", "market": "欧洲", "ts_code": "FTSE"},
    "DAX": {"name": "德国DAX", "market": "欧洲", "ts_code": "GDAXI"},
}

# 反向映射：ts_code -> 对外 code
_TUSHARE_CODE_MAP = {info["ts_code"]: code for code, info in GLOBAL_INDICES.items()}

# 主要商品/汇率
GLOBAL_COMMODITIES = {
    "GOLD": {"name": "伦敦金(现货)", "category": "贵金属", "unit": "美元/盎司"},
    "SILVER": {"name": "伦敦银(现货)", "category": "贵金属", "unit": "美元/盎司"},
    "CRUDE_OIL": {"name": "WTI原油", "category": "能源", "unit": "美元/桶"},
    "BRENT_OIL": {"name": "布伦特原油", "category": "能源", "unit": "美元/桶"},
    "USDX": {"name": "美元指数", "category": "汇率", "unit": ""},
    "USDCNY": {"name": "美元/人民币", "category": "汇率", "unit": ""},
    "EURUSD": {"name": "欧元/美元", "category": "汇率", "unit": ""},
    "USDJPY": {"name": "美元/日元", "category": "汇率", "unit": ""},
}


def get_global_indices() -> list[dict]:
    """获取全球主要股票指数实时行情。

    优先使用 Tushare index_global（付费，稳定），失败后再尝试 akshare。

    Returns:
        list of {code, name, market, price, change, change_percent, updated_at}
    """
    # 1. 优先尝试 Tushare
    results = _fetch_indices_from_tushare()
    if results:
        return results

    # 2. Tushare 无数据时，尝试 akshare
    logger.warning("[GlobalMarket] Tushare 无全球指数数据，尝试 akshare 备选")
    return _fetch_indices_from_akshare()


def _fetch_indices_from_tushare() -> list[dict]:
    """通过 Tushare index_global 获取最近交易日的全球指数。"""
    try:
        from app.services.data_sync_service import get_pro
        pro = get_pro()

        # 取最近 10 个交易日，避免非交易日无数据
        for days_ago in range(10):
            trade_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            df = pro.index_global(trade_date=trade_date)
            if df is not None and not df.empty:
                break
        else:
            _log_global_market_event(
                "tushare", "failed", "index_global 最近 10 个交易日均无数据"
            )
            return []

        results = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            if not ts_code:
                continue
            # 只返回我们关注的指数
            code = _TUSHARE_CODE_MAP.get(ts_code)
            if not code:
                continue
            info = GLOBAL_INDICES[code]
            results.append({
                "code": code,
                "name": info["name"],
                "market": info["market"],
                "price": _safe_float(row.get("close")),
                "change": _safe_float(row.get("change")),
                "change_percent": _safe_float(row.get("pct_chg")),
                "updated_at": str(row.get("trade_date", "")),
            })

        _log_global_market_event(
            "tushare", "success", f"通过 index_global 获取 {len(results)} 条全球指数",
            data_count=len(results)
        )
        return results
    except Exception as e:
        logger.error(f"[GlobalMarket] Tushare 获取失败: {e}")
        _log_global_market_event("tushare", "failed", str(e)[:1000])
        return []


def _fetch_indices_from_akshare() -> list[dict]:
    """通过 akshare index_global_spot_em 获取全球指数实时行情。"""
    ak = _get_ak()
    results = []

    try:
        df = ak.index_global_spot_em()
        if df is None or df.empty:
            _log_global_market_event("akshare", "failed", "index_global_spot_em 返回空数据")
            return results

        # 标准化列名（不同版本 akshare 列名可能不同）
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if "代码" in cl or "code" in cl or col == "f12":
                col_map["code"] = col
            elif "名称" in cl or "name" in cl or col == "f14":
                col_map["name"] = col
            elif "最新" in cl or "price" in cl or "收盘" in cl or col == "f2":
                col_map["price"] = col
            elif "涨跌幅" in cl or "pct" in cl or col == "f3":
                col_map["pct"] = col
            elif "涨跌额" in cl or "change" in cl or col == "f4":
                col_map["change"] = col

        for _, row in df.iterrows():
            name = str(row.get(col_map.get("name", ""), ""))
            price = row.get(col_map.get("price", ""), 0)
            pct = row.get(col_map.get("pct", ""), 0)
            change = row.get(col_map.get("change", ""), 0)

            # 筛选我们关注的指数
            for code, info in GLOBAL_INDICES.items():
                if info["name"] in name or name in info["name"]:
                    results.append({
                        "code": code,
                        "name": info["name"],
                        "market": info["market"],
                        "price": _safe_float(price),
                        "change": _safe_float(change),
                        "change_percent": _safe_float(pct),
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    break

        _log_global_market_event(
            "akshare", "success", f"通过 index_global_spot_em 获取 {len(results)} 条全球指数",
            data_count=len(results)
        )

    except Exception as e:
        logger.warning(f"[GlobalMarket] akshare 全球指数获取失败: {e}")
        _log_global_market_event("akshare", "failed", str(e)[:1000])

    return results


# 保留原函数名作为别名，兼容旧调用
_fetch_indices_fallback = _fetch_indices_from_akshare


def _fetch_indices_fallback() -> list[dict]:
    """备选方案：通过 Tushare index_global 获取最近交易日的全球指数。"""
    try:
        from app.services.data_sync_service import get_pro
        pro = get_pro()

        # 取最近 5 个交易日，避免非交易日无数据
        for days_ago in range(5):
            trade_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            df = pro.index_global(trade_date=trade_date)
            if df is not None and not df.empty:
                break
        else:
            _log_global_market_event("tushare", "failed", "index_global 最近 5 个交易日均无数据")
            return []

        results = []
        for _, row in df.iterrows():
            ts_code = row.get("ts_code", "")
            results.append({
                "code": ts_code,
                "name": row.get("name", ts_code),
                "market": "全球",
                "price": _safe_float(row.get("close")),
                "change": _safe_float(row.get("change")),
                "change_percent": _safe_float(row.get("pct_chg")),
                "updated_at": str(row.get("trade_date", "")),
            })
        _log_global_market_event("tushare", "success", f"通过 index_global 获取 {len(results)} 条全球指数", data_count=len(results))
        return results
    except Exception as e:
        logger.error(f"[GlobalMarket] 备选方案也失败: {e}")
        _log_global_market_event("tushare", "failed", str(e)[:1000])
        return []


# ============================================================
# 商品期货 & 汇率
# ============================================================


def get_commodities_and_forex() -> list[dict]:
    """获取主要商品期货和汇率数据。

    优先使用 Tushare fx_daily 获取外汇数据（稳定），
    商品数据尝试 akshare futures_global_spot_em，
    失败时优雅降级返回空列表。

    Returns:
        list of {code, name, category, price, change, change_percent, unit, updated_at}
    """
    results = []

    # 1. 外汇数据（通过 Tushare fx_daily，稳定可靠）
    try:
        _fetch_forex_from_tushare(results)
    except Exception as e:
        logger.warning(f"[GlobalMarket] Tushare 外汇数据获取失败: {e}")

    # 2. 商品期货（通过 akshare futures_global_spot_em）
    try:
        _fetch_commodities_from_akshare(results)
    except Exception as e:
        logger.warning(f"[GlobalMarket] akshare 商品数据获取失败: {e}")

    return results


def _fetch_forex_from_tushare(results: list):
    """通过 Tushare fx_daily 获取外汇数据。"""
    try:
        from app.services.stock_service import get_pro
        pro = get_pro()
    except RuntimeError:
        return

    fx_pairs = {
        "USDCNH.FXCM": ("USDCNY", "美元/人民币(离岸)", "汇率", ""),
        "EURUSD.FXCM": ("EURUSD", "欧元/美元", "汇率", ""),
        "USDJPY.FXCM": ("USDJPY", "美元/日元", "汇率", ""),
    }

    for ts_code, (code, name, category, unit) in fx_pairs.items():
        try:
            df = pro.fx_daily(ts_code=ts_code, limit=2)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                price = _safe_float(latest.get("bid_close"))
                prev_close = _safe_float(latest.get("bid_open"))
                change = price - prev_close if prev_close else 0
                pct = (change / prev_close * 100) if prev_close else 0
                results.append({
                    "code": code,
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "price": price,
                    "change": round(change, 5),
                    "change_percent": round(pct, 4),
                    "updated_at": str(latest.get("trade_date", "")),
                })
        except Exception:
            continue


def _fetch_commodities_from_akshare(results: list):
    """通过 akshare futures_global_spot_em 获取商品期货数据。"""
    ak = _get_ak()

    try:
        df = ak.futures_global_spot_em()
        if df is None or df.empty:
            return

        # 关键词匹配 → (code, display_name, category, unit)
        targets = [
            ("COMEX黄金", "GOLD", "COMEX黄金(主力)", "贵金属", "美元/盎司"),
            ("COMEX白银", "SILVER", "COMEX白银(主力)", "贵金属", "美元/盎司"),
            ("布伦特原油", "BRENT_OIL", "布伦特原油(主力)", "能源", "美元/桶"),
            ("迷你原油", "CRUDE_OIL", "纽约原油(主力)", "能源", "美元/桶"),
        ]

        found_codes = set()
        for keyword, code, display_name, category, unit in targets:
            if code in found_codes:
                continue
            # 匹配含关键词且有最新价的行，取第一条（最近月合约）
            matched = df[
                df["名称"].str.contains(keyword, na=False)
                & df["最新价"].notna()
                & (df["最新价"] > 0)
            ]
            if matched.empty:
                continue
            row = matched.iloc[0]
            found_codes.add(code)
            results.append({
                "code": code,
                "name": display_name,
                "category": category,
                "unit": unit,
                "price": _safe_float(row.get("最新价")),
                "change": _safe_float(row.get("涨跌额")),
                "change_percent": _safe_float(row.get("涨跌幅")),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
    except Exception as e:
        logger.warning(f"[GlobalMarket] futures_global_spot_em 获取失败: {e}")


# ============================================================
# 聚合接口：一次返回全部国际市场数据
# ============================================================


def get_global_market_overview() -> dict:
    """获取国际市场全貌（指数 + 商品 + 汇率），供首页展示。

    Returns:
        {
            "indices": [...],       # 全球主要指数
            "commodities": [...],   # 黄金、原油等
            "forex": [...],         # 汇率
            "updated_at": "..."
        }
    """
    indices = get_global_indices()
    commodities_and_forex = get_commodities_and_forex()

    # 分离商品和汇率
    commodities = [item for item in commodities_and_forex if item.get("category") != "汇率"]
    forex = [item for item in commodities_and_forex if item.get("category") == "汇率"]

    return {
        "indices": indices,
        "commodities": commodities,
        "forex": forex,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 辅助函数
# ============================================================


def _safe_float(val) -> float:
    """安全转换为 float。"""
    if val is None:
        return 0.0
    try:
        if pd.isna(val):
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _log_global_market_event(source: str, status: str, message: str, data_count: int | None = None):
    """记录全球市场数据获取日志到数据库。"""
    try:
        from app.db.base import SessionLocal
        from app.models.global_market_log import GlobalMarketLog

        db = SessionLocal()
        try:
            db.add(
                GlobalMarketLog(
                    source=source,
                    status=status,
                    message=message,
                    data_count=data_count,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # 落库失败不能影响主流程
        pass
