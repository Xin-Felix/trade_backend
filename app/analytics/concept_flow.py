"""概念板块分钟级资金流聚合。

核心逻辑：
1. 从 stock_concept 获取概念-成分股映射
2. 从 stock_intraday 获取成分股的分钟 K 线
3. 按概念聚合每分钟的资金流入/流出
4. 资金流方向判定：分钟 close >= open → 流入，否则 → 流出

输出格式：
- 分钟级：每个概念每分钟一条 {concept_id, time, net_inflow, total_amount, up_count, down_count}
- 日级汇总：每个概念全天总净流入排名

用途：iOS 概念资金流动态走势动画
"""

import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import text

from app.db.base import SessionLocal

logger = logging.getLogger(__name__)


def compute_concept_minute_flow(
    trade_date: Optional[date] = None,
    concept_ids: Optional[list[str]] = None,
    top_n_concepts: int = 30,
) -> list[dict]:
    """计算概念板块分钟级资金流走势。

    基于 stock_intraday 表：close >= open 为流入，否则为流出，金额为 amount。

    Returns:
        [{concept_id, concept_name, minutes: [{time, net_inflow, inflow, outflow, up_count, down_count}]}]
    """
    if trade_date is None:
        trade_date = date.today()

    db = SessionLocal()
    try:
        # 1. 获取概念-成分股映射
        concept_stocks = _get_concept_stocks(db, concept_ids, top_n_concepts)
        if not concept_stocks:
            logger.warning("[ConceptFlow] 无概念映射数据")
            return []

        # 2. 收集所有需要的股票代码
        all_codes = set()
        for info in concept_stocks.values():
            all_codes.update(s["ts_code"] for s in info["stocks"])

        logger.info(f"[ConceptFlow] {len(concept_stocks)} 个概念, {len(all_codes)} 只股票")

        # 3. 从 stock_intraday 获取分钟 K 线
        minute_data = _fetch_intraday_from_db(db, all_codes, trade_date)
        if not minute_data:
            logger.warning(f"[ConceptFlow] {trade_date} 无分时数据，尝试 moneyflow 日级数据")
            return _fallback_daily_flow(db, concept_stocks, trade_date)

        logger.info(f"[ConceptFlow] 获取到 {len(minute_data)} 只股票的分时数据")

        # 4. 按概念聚合每分钟
        results = _aggregate_minute_flow(concept_stocks, minute_data)
        logger.info(f"[ConceptFlow] 生成 {len(results)} 个概念的分钟资金流")

        return results
    finally:
        db.close()


def get_concept_flow_summary(
    trade_date: Optional[date] = None,
    top_n: int = 20,
) -> list[dict]:
    """获取概念资金流日内汇总（每个概念的全天净流入排名）。

    Returns:
        [{concept_id, concept_name, net_inflow, inflow, outflow, stock_count, up_count, down_count}, ...]
        按 net_inflow 降序
    """
    if trade_date is None:
        trade_date = date.today()

    db = SessionLocal()
    try:
        concept_stocks = _get_concept_stocks(db, None, top_n)
        if not concept_stocks:
            return []

        all_codes = set()
        for info in concept_stocks.values():
            all_codes.update(s["ts_code"] for s in info["stocks"])

        # 优先用 stock_intraday 分时数据聚合
        minute_data = _fetch_intraday_from_db(db, all_codes, trade_date)
        if minute_data:
            return _summarize_from_intraday(concept_stocks, minute_data)

        # fallback: 用 stock_moneyflow 日级数据
        return _fallback_daily_summary(db, concept_stocks, trade_date)
    finally:
        db.close()


def get_concept_minute_trend(
    concept_id: str,
    trade_date: Optional[date] = None,
) -> dict:
    """获取单个概念的分钟级资金流走势（用于 iOS 动画折线图）。

    Returns:
        {concept_id, concept_name, trade_date, stock_count, minutes: [{time, net_inflow, inflow, outflow, ...}]}
    """
    if trade_date is None:
        trade_date = date.today()

    db = SessionLocal()
    try:
        concept_stocks = _get_concept_stocks(db, [concept_id], 1)
        if not concept_stocks or concept_id not in concept_stocks:
            return {"concept_id": concept_id, "concept_name": "", "trade_date": trade_date.isoformat(), "stock_count": 0, "minutes": []}

        info = concept_stocks[concept_id]
        stock_codes = set(s["ts_code"] for s in info["stocks"])

        minute_data = _fetch_intraday_from_db(db, stock_codes, trade_date)
        if not minute_data:
            return {"concept_id": concept_id, "concept_name": info["name"], "trade_date": trade_date.isoformat(), "stock_count": len(info["stocks"]), "minutes": []}

        # 聚合分钟数据
        minutes = _aggregate_single_concept_minutes(info["stocks"], minute_data)

        return {
            "concept_id": concept_id,
            "concept_name": info["name"],
            "trade_date": trade_date.isoformat(),
            "stock_count": len(info["stocks"]),
            "matched_count": len([c for c in stock_codes if c in minute_data]),
            "minutes": minutes,
        }
    finally:
        db.close()


def get_stock_intraday_flow(
    ts_code: str,
    trade_date: Optional[date] = None,
) -> dict:
    """获取单只股票的分时资金流走势。

    Returns:
        {ts_code, trade_date, minutes: [{time, net_inflow, inflow, outflow, close, volume}]}
    """
    if trade_date is None:
        trade_date = date.today()

    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT trade_time, open, close, high, low, volume, amount
                FROM stock_intraday
                WHERE ts_code = :code AND trade_date = :td
                ORDER BY trade_time
            """),
            {"code": ts_code, "td": trade_date},
        ).fetchall()

        minutes = []
        cumulative_net = 0.0
        for row in rows:
            trade_time, open_p, close_p, high_p, low_p, vol, amt = row
            open_f = float(open_p) if open_p else 0
            close_f = float(close_p) if close_p else 0
            amount_f = float(amt) if amt else 0

            # close >= open → 资金流入，否则流出
            if close_f >= open_f:
                inflow = amount_f
                outflow = 0.0
            else:
                inflow = 0.0
                outflow = amount_f
            net = inflow - outflow
            cumulative_net += net

            minutes.append({
                "time": trade_time,
                "close": close_f,
                "volume": int(vol) if vol else 0,
                "amount": round(amount_f, 2),
                "inflow": round(inflow, 2),
                "outflow": round(outflow, 2),
                "net_inflow": round(net, 2),
                "cumulative_net": round(cumulative_net, 2),
            })

        return {
            "ts_code": ts_code,
            "trade_date": trade_date.isoformat(),
            "total_minutes": len(minutes),
            "minutes": minutes,
        }
    finally:
        db.close()


def compute_industry_minute_flow(
    trade_date: Optional[date] = None,
    industry_ids: Optional[list[str]] = None,
    top_n_industries: int = 30,
) -> list[dict]:
    """计算行业板块分钟级资金流走势。

    复用概念资金流聚合逻辑，行业映射来自 ths_index(type='I') + ths_member。
    输出字段名与 compute_concept_minute_flow 保持一致，便于前端通用。
    """
    if trade_date is None:
        trade_date = date.today()

    db = SessionLocal()
    try:
        industry_stocks = _get_industry_stocks(db, industry_ids, top_n_industries)
        if not industry_stocks:
            logger.warning("[IndustryFlow] 无行业映射数据")
            return []

        all_codes = set()
        for info in industry_stocks.values():
            all_codes.update(s["ts_code"] for s in info["stocks"])

        logger.info(f"[IndustryFlow] {len(industry_stocks)} 个行业, {len(all_codes)} 只股票")

        minute_data = _fetch_intraday_from_db(db, all_codes, trade_date)
        if not minute_data:
            logger.warning(f"[IndustryFlow] {trade_date} 无分时数据，尝试 moneyflow 日级数据")
            return _fallback_daily_flow(db, industry_stocks, trade_date)

        logger.info(f"[IndustryFlow] 获取到 {len(minute_data)} 只股票的分时数据")

        results = _aggregate_minute_flow(industry_stocks, minute_data)
        logger.info(f"[IndustryFlow] 生成 {len(results)} 个行业的分钟资金流")

        return results
    finally:
        db.close()


# ============================================================
# 内部函数
# ============================================================


def _get_concept_stocks(db, concept_ids: Optional[list[str]], top_n: int) -> dict:
    """获取概念-成分股映射。

    Returns:
        {concept_id: {"name": "概念名", "stocks": [{"ts_code": "000001.SZ", "name": "平安银行"}, ...]}}
    """
    if concept_ids:
        placeholders = ",".join([f"'{c}'" for c in concept_ids])
        sql = f"SELECT concept_id, concept_name, ts_code, name FROM stock_concept WHERE concept_id IN ({placeholders})"
    else:
        # 默认热门概念列表（排除过于宽泛的融资融券/沪深港通/成份股等）
        default_ids = [
            "885728.TI",  # 人工智能
            "885756.TI",  # 芯片概念
            "885431.TI",  # 新能源汽车
            "886100.TI",  # DeepSeek概念
            "885921.TI",  # 储能
            "885700.TI",  # 军工
            "885531.TI",  # 光伏概念
            "886069.TI",  # 人形机器人
            "885517.TI",  # 机器人概念
            "886067.TI",  # 低空经济
            "885806.TI",  # 华为概念
            "885800.TI",  # 消费电子概念
        ]
        ids_to_use = default_ids[:top_n]
        placeholders = ",".join([f"'{c}'" for c in ids_to_use])
        sql = f"SELECT concept_id, concept_name, ts_code, name FROM stock_concept WHERE concept_id IN ({placeholders})"

    rows = db.execute(text(sql)).fetchall()
    if not rows:
        return {}

    concept_map = {}
    for row in rows:
        cid = row[0]
        if cid not in concept_map:
            concept_map[cid] = {"name": row[1], "stocks": []}
        concept_map[cid]["stocks"].append({"ts_code": row[2], "name": row[3]})

    return concept_map


def _get_industry_stocks(db, industry_ids: Optional[list[str]], top_n: int) -> dict:
    """获取行业-成分股映射。

    基于 stock_basic.industry 字段（申万行业分类）。

    Returns:
        {industry_name: {"name": "行业名", "stocks": [{"ts_code": "000001.SZ", "name": "平安银行"}, ...]}}
    """
    if industry_ids:
        # industry_ids 这里实际上是行业名称列表
        placeholders = ",".join([f"'{c}'" for c in industry_ids])
        sql = f"""
            SELECT ts_code, name, industry FROM stock_basic
            WHERE industry IN ({placeholders}) AND industry IS NOT NULL AND industry != ''
        """
    else:
        # 取成分股最多的前 N 个行业
        sql = f"""
            SELECT sb.ts_code, sb.name, sb.industry
            FROM stock_basic sb
            INNER JOIN (
                SELECT industry, COUNT(*) as cnt
                FROM stock_basic
                WHERE industry IS NOT NULL AND industry != ''
                GROUP BY industry
                ORDER BY cnt DESC
                LIMIT {top_n}
            ) top ON sb.industry = top.industry
            WHERE sb.industry IS NOT NULL AND sb.industry != ''
        """

    rows = db.execute(text(sql)).fetchall()
    if not rows:
        return {}

    industry_map = {}
    for row in rows:
        ts_code, name, industry = row
        if industry not in industry_map:
            industry_map[industry] = {"name": industry, "stocks": []}
        industry_map[industry]["stocks"].append({"ts_code": ts_code, "name": name})

    return industry_map


def _fetch_intraday_from_db(db, stock_codes: set, trade_date: date) -> dict:
    """从 stock_intraday 表获取分时数据。

    Returns:
        {ts_code: [{time, open, close, volume, amount}, ...]}
    """
    # 检查是否有当天数据
    count = 0
    try:
        count = db.execute(
            text("SELECT COUNT(*) FROM stock_intraday WHERE trade_date = :td"),
            {"td": trade_date},
        ).scalar() or 0
    except Exception:
        db.rollback()
        return {}

    if count == 0:
        return {}

    # 批量查询所有相关股票的分时数据
    rows = db.execute(
        text("""
            SELECT ts_code, trade_time, open, close, high, low, volume, amount
            FROM stock_intraday
            WHERE trade_date = :td
            ORDER BY ts_code, trade_time
        """),
        {"td": trade_date},
    ).fetchall()

    minute_data = {}
    for row in rows:
        ts_code = row[0]
        if ts_code not in stock_codes:
            continue
        if ts_code not in minute_data:
            minute_data[ts_code] = []
        minute_data[ts_code].append({
            "time": row[1],
            "open": float(row[2]) if row[2] else 0,
            "close": float(row[3]) if row[3] else 0,
            "high": float(row[4]) if row[4] else 0,
            "low": float(row[5]) if row[5] else 0,
            "volume": int(row[6]) if row[6] else 0,
            "amount": float(row[7]) if row[7] else 0,
        })

    return minute_data


def _aggregate_minute_flow(concept_map: dict, minute_data: dict) -> list[dict]:
    """按概念聚合每分钟资金流，返回每个概念的分钟级走势。"""
    results = []

    for concept_id, info in concept_map.items():
        minutes = _aggregate_single_concept_minutes(info["stocks"], minute_data)
        if not minutes:
            continue

        # 计算全天汇总
        total_net = sum(m["net_inflow"] for m in minutes)
        total_inflow = sum(m["inflow"] for m in minutes)
        total_outflow = sum(m["outflow"] for m in minutes)

        results.append({
            "concept_id": concept_id,
            "concept_name": info["name"],
            "stock_count": len(info["stocks"]),
            "matched_count": len([s for s in info["stocks"] if s["ts_code"] in minute_data]),
            "net_inflow": round(total_net, 2),
            "inflow": round(total_inflow, 2),
            "outflow": round(total_outflow, 2),
            "minutes": minutes,
        })

    return results


def _aggregate_single_concept_minutes(stocks: list[dict], minute_data: dict) -> list[dict]:
    """聚合单个概念的分钟级数据。"""
    # 按时间聚合所有成分股
    time_agg = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "up_count": 0, "down_count": 0, "amount": 0.0})

    for stock in stocks:
        ts_code = stock["ts_code"]
        if ts_code not in minute_data:
            continue
        for bar in minute_data[ts_code]:
            t = bar["time"]
            amount = bar["amount"]
            # close >= open → 资金流入
            if bar["close"] >= bar["open"]:
                time_agg[t]["inflow"] += amount
                time_agg[t]["up_count"] += 1
            else:
                time_agg[t]["outflow"] += amount
                time_agg[t]["down_count"] += 1
            time_agg[t]["amount"] += amount

    if not time_agg:
        return []

    # 按时间排序输出
    cumulative_net = 0.0
    minutes = []
    for t in sorted(time_agg.keys()):
        agg = time_agg[t]
        net = agg["inflow"] - agg["outflow"]
        cumulative_net += net
        minutes.append({
            "time": t,
            "net_inflow": round(net, 2),
            "inflow": round(agg["inflow"], 2),
            "outflow": round(agg["outflow"], 2),
            "cumulative_net": round(cumulative_net, 2),
            "total_amount": round(agg["amount"], 2),
            "up_count": agg["up_count"],
            "down_count": agg["down_count"],
        })

    return minutes


def _summarize_from_intraday(concept_map: dict, minute_data: dict) -> list[dict]:
    """基于分时数据生成概念日级汇总排名。"""
    results = []

    for concept_id, info in concept_map.items():
        net_inflow = 0.0
        inflow = 0.0
        outflow = 0.0
        up_count = 0
        down_count = 0
        matched = 0

        for stock in info["stocks"]:
            ts_code = stock["ts_code"]
            if ts_code not in minute_data:
                continue
            matched += 1
            stock_net = 0.0
            for bar in minute_data[ts_code]:
                amount = bar["amount"]
                if bar["close"] >= bar["open"]:
                    inflow += amount
                    stock_net += amount
                else:
                    outflow += amount
                    stock_net -= amount
            net_inflow += stock_net
            if stock_net > 0:
                up_count += 1
            elif stock_net < 0:
                down_count += 1

        if matched == 0:
            continue

        results.append({
            "concept_id": concept_id,
            "concept_name": info["name"],
            "net_inflow": round(net_inflow, 2),
            "inflow": round(inflow, 2),
            "outflow": round(outflow, 2),
            "stock_count": len(info["stocks"]),
            "matched_count": matched,
            "up_count": up_count,
            "down_count": down_count,
        })

    results.sort(key=lambda x: x["net_inflow"], reverse=True)
    return results


def _fallback_daily_flow(db, concept_stocks: dict, trade_date: date) -> list[dict]:
    """降级：用 stock_moneyflow 日级数据。"""
    summary = _fallback_daily_summary(db, concept_stocks, trade_date)
    # 转为与分钟级相同的格式（但没有 minutes 字段）
    return summary


def _fallback_daily_summary(db, concept_stocks: dict, trade_date: date) -> list[dict]:
    """降级汇总：从 stock_moneyflow 表获取日级资金流。"""
    try:
        rows = db.execute(
            text("""
                SELECT ts_code, net_mf_amount,
                       buy_sm_amount, sell_sm_amount,
                       buy_md_amount, sell_md_amount,
                       buy_lg_amount, sell_lg_amount,
                       buy_elg_amount, sell_elg_amount
                FROM stock_moneyflow WHERE trade_date = :td
            """),
            {"td": trade_date},
        ).fetchall()
    except Exception:
        db.rollback()
        return []

    # 构建资金流 map
    flow_map = {}
    for row in rows:
        ts_code = row[0]
        inflow = float((row[2] or 0) + (row[4] or 0) + (row[6] or 0) + (row[8] or 0))
        outflow = float((row[3] or 0) + (row[5] or 0) + (row[7] or 0) + (row[9] or 0))
        flow_map[ts_code] = {"net_inflow": float(row[1] or 0), "inflow": inflow, "outflow": outflow}

    results = []
    for concept_id, info in concept_stocks.items():
        net_inflow = 0.0
        inflow = 0.0
        outflow = 0.0
        up_count = 0
        down_count = 0
        matched = 0

        for stock in info["stocks"]:
            ts_code = stock["ts_code"]
            if ts_code not in flow_map:
                continue
            matched += 1
            data = flow_map[ts_code]
            net_inflow += data["net_inflow"]
            inflow += data["inflow"]
            outflow += data["outflow"]
            if data["net_inflow"] > 0:
                up_count += 1
            elif data["net_inflow"] < 0:
                down_count += 1

        if matched == 0:
            continue

        results.append({
            "concept_id": concept_id,
            "concept_name": info["name"],
            "net_inflow": round(net_inflow, 2),
            "inflow": round(inflow, 2),
            "outflow": round(outflow, 2),
            "stock_count": len(info["stocks"]),
            "matched_count": matched,
            "up_count": up_count,
            "down_count": down_count,
        })

    results.sort(key=lambda x: x["net_inflow"], reverse=True)
    return results
