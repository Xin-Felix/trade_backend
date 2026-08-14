# -*- coding: utf-8 -*-
"""市场拥挤度数据管道

从 market_congestion/server/app/pipeline/run_daily.py 迁移而来。
复用 trade_backend 的 scheduler 触发，不再自己管定时。

步骤：
  1. aggregates  —— 各类汇总指标（行情数据已由 trade scheduler 同步，不需要再拉）
  2. congestion  —— 预跑 8 组拥挤度
  3. option      —— 期权合约+行情+标的快照
"""

import logging
import time

logger = logging.getLogger(__name__)

STEPS = ("aggregates", "congestion", "option")


def _get_core():
    from app.market import core
    return core


# ---------------------------------------------------------------------------
# 各步骤
# ---------------------------------------------------------------------------

def step_aggregates() -> dict:
    """重算全部汇总指标并持久化到 mc_summary"""
    import json as _json
    from app.market.core import (
        get_market_overview, get_daily_snapshot, get_market_signals,
        get_updn_trend, get_board_shares, get_board_amounts,
        get_board_flow, get_board_congestion_trend,
        get_breadth, get_margin_trend, get_daily_review,
        get_trend_overview, get_industry_crowding, get_industry_trend,
        get_industry_flow, get_all_industries,
    )
    from app.market.core import database as db

    done = []
    tasks = [
        ("market_overview", get_market_overview),
        ("snapshot", lambda: get_daily_snapshot(None)),
        ("market_signals", lambda: get_market_signals(None)),
        ("updn_trend", lambda: get_updn_trend(exclude_st=False, exclude_board=None)),
        ("board_shares", get_board_shares),
        ("board_amounts", get_board_amounts),
        ("board_flow", get_board_flow),
        ("board_congestion", get_board_congestion_trend),
        ("breadth", get_breadth),
        ("margin_trend", get_margin_trend),
        ("review", lambda: get_daily_review(None)),
        ("trend_overview", get_trend_overview),
    ]
    for name, fn in tasks:
        t0 = time.perf_counter()
        try:
            result = fn()
            cost = (time.perf_counter() - t0) * 1000
            logger.info("  %s 完成 %.0fms", name, cost)
            done.append(name)
            # 持久化到 mc_summary（供下次冷启动直接读取）
            if result is not None:
                try:
                    db.write_summary(f"agg_{name}", result)
                except Exception:
                    pass
        except Exception:
            logger.exception("  %s 失败", name)

    # 行业
    try:
        r1 = get_industry_crowding(None)
        r2 = get_industry_trend(None)
        r3 = get_industry_flow(None)
        r4 = get_all_industries()
        done.append("industry")
        logger.info("  industry 完成")
        try:
            db.write_summary("agg_industry_crowding", r1)
            db.write_summary("agg_industry_trend", r2)
            db.write_summary("agg_industry_flow", r3)
            db.write_summary("agg_all_industries", r4)
        except Exception:
            pass
    except Exception:
        logger.exception("  industry 失败")

    return {"done": done, "count": len(done)}


def step_congestion() -> dict:
    """预跑拥挤度全部组合"""
    from app.market.core import (
        batch_calc_market_congestion, list_cached_daily_dates, save_history_batch,
    )

    boards = ["全部A股", "沪深主板", "创业板", "科创板"]
    denoms = ["market", "board"]
    top_percent = 5
    days = 60

    dates = list_cached_daily_dates()
    if not dates:
        return {"warmed": 0, "reason": "本地无行情数据"}

    end = dates[-1]
    start = dates[max(0, len(dates) - days)]

    warmed = 0
    for denom in denoms:
        for board in boards:
            try:
                results = batch_calc_market_congestion(
                    board=board, top_percent=top_percent,
                    start_date=start, end_date=end,
                    denominator=denom, exclude_new=False,
                    progress_callback=None,
                )
                if results:
                    save_history_batch(results)
                warmed += 1
            except Exception:
                logger.exception("预热拥挤度失败 board=%s denom=%s", board, denom)

    return {"warmed": warmed, "start": start, "end": end}


def step_option() -> dict:
    """刷新期权合约+行情+标的快照"""
    from app.market.core import (
        refresh_option_data, get_option_underlyings, get_option_analysis,
    )

    refresh_option_data(None)
    underlyings = get_option_underlyings()
    for u in underlyings or []:
        try:
            get_option_analysis(u["code"])
        except Exception:
            logger.exception("  期权分析失败 %s", u.get("code"))
    return {"underlyings": len(underlyings or [])}


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

def run_pipeline(force: bool = False, only: str | None = None) -> dict:
    """执行管道

    Args:
        force: 是否强制执行（忽略交易日判断）
        only: 只跑某一步 (aggregates/congestion/option)
    """
    from app.api.v1.endpoints.market_congestion import clear_cache, warm_cache

    started = time.perf_counter()
    logger.info("=" * 60)
    logger.info("MC pipeline 开始")

    # 交易日判断（非强制模式）
    if not force:
        try:
            core = _get_core()
            from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            _, raw_dates = core.fetch_trade_dates()
            if today not in set(raw_dates or []):
                logger.info("今天不是交易日，跳过")
                return {"skipped": True, "reason": "non_trade_day"}
        except Exception:
            logger.exception("交易日判断失败，按交易日处理")

    # 先清缓存
    clear_cache()

    steps_to_run = [only] if only else list(STEPS)
    runners = {
        "aggregates": step_aggregates,
        "congestion": step_congestion,
        "option": step_option,
    }

    results = {}
    failed = []

    for name in steps_to_run:
        if name not in runners:
            continue
        logger.info("[%s] 开始", name)
        t0 = time.perf_counter()
        try:
            results[name] = runners[name]()
            logger.info("[%s] 完成 %.1fs", name, time.perf_counter() - t0)
        except Exception:
            logger.exception("[%s] 失败", name)
            failed.append(name)

    cost = time.perf_counter() - started
    logger.info("MC pipeline 完成，耗时 %.0fs，失败: %s", cost, failed or "无")
    logger.info("=" * 60)

    # pipeline 完成后预热缓存
    warm_cache()

    return {"ok": not failed, "failed": failed, "results": results, "cost_s": round(cost, 1)}
