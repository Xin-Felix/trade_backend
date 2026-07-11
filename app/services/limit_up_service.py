"""涨停板天梯聚合服务。

整合 limit_cpt_list（涨停板块统计）、limit_step（连板天梯）、
limit_list_d（涨跌停明细）和 stock_concept（概念映射），
为 iOS 端提供可直接渲染的涨停板数据。
"""

from datetime import date, datetime

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.analysis import LimitCptList, LimitListD, LimitStep
from app.models.stock import StockBasic, StockConcept


def _format_time(t) -> str | None:
    """把 Tushare 时间格式 HHMMSS 转成 HH:MM。"""
    if t is None:
        return None
    s = str(t).strip()
    if not s or s.lower() == "nan":
        return None
    s = s.zfill(6)
    return f"{s[:2]}:{s[2:4]}"


def _normalize_code_for_lookup(code: str) -> str:
    """把代码里的后缀去掉，方便和 stock_concept 等表匹配。"""
    return code.split(".")[0] if "." in code else code


def get_limit_up_ladder(trade_date: date | None = None, top_n_concepts: int = 30) -> dict:
    """获取涨停板天梯聚合数据。

    Returns:
        {
            "trade_date": "YYYYMMDD",
            "concept_tags": [{name, count, pct_change, cons_count, rank}, ...],
            "ladder": [
                {"step": 8, "label": "8板", "stocks": [...]},
                {"step": 1, "label": "首板", "stocks": [...]},
            ],
            "opened_limit": [{ts_code, name, first_time, open_times, pct_chg, concept_tags}, ...],
        }
    """
    db = SessionLocal()
    try:
        target_date = trade_date
        if target_date is None:
            latest = db.execute(
                select(LimitListD.trade_date)
                .order_by(LimitListD.trade_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            target_date = latest or date.today()

        # 1. 热门涨停概念标签
        concept_rows = db.execute(
            select(LimitCptList)
            .where(LimitCptList.trade_date == target_date)
            .order_by(LimitCptList.rank.asc())
            .limit(top_n_concepts)
        ).scalars().all()

        concept_tags = []
        hot_concept_names = set()
        for r in concept_rows:
            hot_concept_names.add(r.name)
            concept_tags.append({
                "name": r.name,
                "count": r.up_nums,
                "cons_count": r.cons_nums,
                "pct_change": float(r.pct_chg) if r.pct_chg is not None else None,
                "rank": r.rank,
            })

        # 2. 涨停个股明细（U=涨停）
        limit_up_rows = db.execute(
            select(LimitListD)
            .where(LimitListD.trade_date == target_date)
            .where(LimitListD.limit == "U")
        ).scalars().all()

        # 3. 炸板个股明细（Z=炸板）
        opened_rows = db.execute(
            select(LimitListD)
            .where(LimitListD.trade_date == target_date)
            .where(LimitListD.limit == "Z")
        ).scalars().all()

        # 4. 连板天梯 step 映射
        step_rows = db.execute(
            select(LimitStep)
            .where(LimitStep.trade_date == target_date)
        ).scalars().all()
        step_map = {r.ts_code: r.step for r in step_rows}

        # 5. 股票基础信息（名称兜底）
        ts_codes = {r.ts_code for r in limit_up_rows} | {r.ts_code for r in opened_rows}
        name_map = {}
        if ts_codes:
            basic_rows = db.execute(
                select(StockBasic.ts_code, StockBasic.name)
                .where(StockBasic.ts_code.in_(ts_codes))
            ).all()
            name_map = {r.ts_code: r.name for r in basic_rows}

        # 6. 个股概念标签（只保留热门涨停概念）
        pure_codes = {_normalize_code_for_lookup(c) for c in ts_codes}
        concept_map: dict[str, list[str]] = {c: [] for c in ts_codes}
        if pure_codes and hot_concept_names:
            stock_concept_rows = db.execute(
                select(StockConcept.ts_code, StockConcept.concept_name)
                .where(StockConcept.ts_code.in_(ts_codes))
                .where(StockConcept.concept_name.in_(hot_concept_names))
            ).all()
            for r in stock_concept_rows:
                if r.concept_name not in concept_map[r.ts_code]:
                    concept_map[r.ts_code].append(r.concept_name)

        def _build_stock_item(row: LimitListD) -> dict:
            name = row.name or name_map.get(row.ts_code)
            return {
                "ts_code": row.ts_code,
                "name": name,
                "close": float(row.close) if row.close is not None else None,
                "pct_chg": float(row.pct_chg) if row.pct_chg is not None else None,
                "first_time": _format_time(row.first_time),
                "last_time": _format_time(row.last_time),
                "open_times": row.open_times,
                "concept_tags": concept_map.get(row.ts_code, [])[:2],
            }

        # 7. 按连板天数分组
        ladder_groups: dict[int, list[dict]] = {}
        for row in limit_up_rows:
            step = step_map.get(row.ts_code, 1) or 1
            ladder_groups.setdefault(step, []).append(_build_stock_item(row))

        ladder = []
        for step in sorted(ladder_groups.keys(), reverse=True):
            label = "首板" if step == 1 else f"{step}板"
            ladder.append({
                "step": step,
                "label": label,
                "stocks": ladder_groups[step],
            })

        # 8. 炸板列表
        opened_limit = [_build_stock_item(r) for r in opened_rows]

        return {
            "trade_date": target_date.strftime("%Y%m%d"),
            "concept_tags": concept_tags,
            "ladder": ladder,
            "opened_limit": opened_limit,
        }
    finally:
        db.close()
