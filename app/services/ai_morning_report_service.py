"""AI 晨报服务层。

每日开盘前基于市场整体数据生成一份市场-wide 的 AI 晨报。
"""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ai_morning_report import AiMorningReport
from app.models.analysis import DcConcept, DcHot, ThsHot
from app.services import ai_service, stock_service
from app.services.limit_up_service import get_limit_up_ladder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 交易日辅助
# ---------------------------------------------------------------------------


def get_latest_trade_date(db: Session) -> date | None:
    """获取本地数据库中最新的交易日（基于 stock_daily 表）。"""
    from app.models.stock import StockDaily

    latest = db.query(func.max(StockDaily.trade_date)).scalar()
    return latest


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_or_create_report(db: Session, report_date: date) -> AiMorningReport:
    """获取或创建指定日期的晨报记录。"""
    report = (
        db.query(AiMorningReport)
        .filter(AiMorningReport.report_date == report_date)
        .first()
    )
    if report is None:
        report = AiMorningReport(report_date=report_date, status="pending")
        db.add(report)
        db.commit()
        db.refresh(report)
    return report


def _fmt_date(d: date | None) -> str:
    return d.strftime("%Y%m%d") if d else ""


def _get_hot_concepts(db: Session, trade_date: date, limit: int = 5) -> list[dict]:
    """获取指定交易日的热门概念（按涨家数倒序）。"""
    rows = (
        db.execute(
            select(DcConcept)
            .where(DcConcept.trade_date == trade_date)
            .order_by(DcConcept.z_num.desc(), DcConcept.pct_chg.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "name": r.name,
            "z_num": r.z_num,
            "d_num": r.d_num,
            "pct_chg": float(r.pct_chg) if r.pct_chg is not None else None,
            "lead_stock": r.lead_stock,
            "lead_pct_chg": float(r.lead_pct_chg) if r.lead_pct_chg is not None else None,
        }
        for r in rows
    ]


def _get_ths_hot_concepts(db: Session, trade_date: date, limit: int = 5) -> list[dict]:
    """获取 THS 热门概念榜。"""
    rows = (
        db.execute(
            select(ThsHot)
            .where(ThsHot.trade_date == trade_date, ThsHot.data_type == "concept")
            .order_by(ThsHot.rank.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "name": r.name,
            "rank": r.rank,
            "pct_chg": float(r.pct_chg) if r.pct_chg is not None else None,
            "hot": float(r.hot) if r.hot is not None else None,
        }
        for r in rows
    ]


def _get_dc_hot_stocks(db: Session, trade_date: date, limit: int = 5) -> list[dict]:
    """获取 DC 热榜 A 股。"""
    rows = (
        db.execute(
            select(DcHot)
            .where(DcHot.trade_date == trade_date, DcHot.market == "A股")
            .order_by(DcHot.rank.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "name": r.name,
            "rank": r.rank,
            "pct_chg": float(r.pct_chg) if r.pct_chg is not None else None,
        }
        for r in rows
    ]


def _build_index_section() -> str:
    """构建主要指数片段。"""
    indices = stock_service.get_indices()
    if not indices:
        return "主要指数：暂无数据。"
    lines = ["主要指数："]
    for item in indices:
        lines.append(
            f"- {item.get('name')}：{item.get('value')}（{item.get('change'):+.2f}%）"
        )
    return "\n".join(lines)


def _build_sector_section(trade_date: date) -> str:
    """构建板块资金流向片段。"""
    lines = ["板块资金流向（按净流入排序）："]
    try:
        industry = stock_service.get_sector_moneyflow_rank(
            sector_type="industry", trade_date=_fmt_date(trade_date), limit=5
        )
        if industry.get("sectors"):
            lines.append("行业板块净流入 Top 5：")
            for s in industry["sectors"][:5]:
                lines.append(
                    f"- {s.get('name')}：净流入 {s.get('net_amount')} 亿元，"
                    f"涨跌幅 {s.get('pct_change')}%，领涨股 {s.get('lead_stock')}"
                )
    except Exception as exc:
        logger.warning(f"[AiMorningReport] 行业板块资金获取失败: {exc}")

    try:
        concept = stock_service.get_sector_moneyflow_rank(
            sector_type="concept", trade_date=_fmt_date(trade_date), limit=5
        )
        if concept.get("sectors"):
            lines.append("概念板块净流入 Top 5：")
            for s in concept["sectors"][:5]:
                lines.append(
                    f"- {s.get('name')}：净流入 {s.get('net_amount')} 亿元，"
                    f"涨跌幅 {s.get('pct_change')}%，领涨股 {s.get('lead_stock')}"
                )
    except Exception as exc:
        logger.warning(f"[AiMorningReport] 概念板块资金获取失败: {exc}")

    return "\n".join(lines) if len(lines) > 1 else "板块资金流向：暂无数据。"


def _build_limit_up_section(trade_date: date) -> str:
    """构建涨停梯队片段。"""
    try:
        data = get_limit_up_ladder(trade_date=trade_date, top_n_concepts=10)
        if not data.get("ladder"):
            return "涨停梯队：暂无数据。"

        lines = [
            f"涨停梯队（交易日 {data.get('trade_date')}）：",
            "热门涨停概念：" + ", ".join(
                f"{c.get('name')}({c.get('count')}只)" for c in data.get("concept_tags", [])[:5]
            ),
        ]
        for group in data["ladder"][:5]:
            stocks = ", ".join(s.get("name") for s in group.get("stocks", [])[:5])
            lines.append(f"- {group.get('label')}：{stocks}")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"[AiMorningReport] 涨停梯队获取失败: {exc}")
        return "涨停梯队：暂无数据。"


def _build_hsgt_section(trade_date: date) -> str:
    """构建北向资金片段。"""
    try:
        start = (trade_date - timedelta(days=5)).strftime("%Y%m%d")
        end = trade_date.strftime("%Y%m%d")
        rows = stock_service.get_moneyflow_hsgt(start_date=start, end_date=end, limit=3)
        if not rows:
            return "沪深港通资金流向：暂无数据。"
        lines = ["沪深港通资金流向（最近 3 个交易日，单位：亿元）："]
        for r in rows:
            lines.append(
                f"- {r.get('trade_date')}：北向 {r.get('north_money')}, "
                f"沪股通 {r.get('hgt')}, 深股通 {r.get('sgt')}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"[AiMorningReport] 北向资金获取失败: {exc}")
        return "沪深港通资金流向：暂无数据。"


def _build_hot_concepts_section(db: Session, trade_date: date) -> str:
    """构建热点概念片段。"""
    lines = ["热点概念："]
    dc_concepts = _get_hot_concepts(db, trade_date, limit=5)
    if dc_concepts:
        for c in dc_concepts:
            lines.append(
                f"- {c.get('name')}：涨家数 {c.get('z_num')}，跌家数 {c.get('d_num')}，"
                f"涨跌幅 {c.get('pct_chg')}%，领涨股 {c.get('lead_stock')}"
            )
    else:
        lines.append("暂无 DC 概念热点数据。")

    ths = _get_ths_hot_concepts(db, trade_date, limit=5)
    if ths:
        lines.append("THS 热门概念榜：")
        for c in ths:
            lines.append(
                f"- {c.get('name')}（热度 {c.get('hot')}，涨跌幅 {c.get('pct_chg')}%）"
            )

    return "\n".join(lines)


async def build_market_context(report_date: date) -> str:
    """基于最新可用交易日收盘数据组装市场上下文文本。"""
    db = SessionLocal()
    try:
        trade_date = get_latest_trade_date(db)
        if trade_date is None:
            return "暂无本地市场数据。"

        parts = [
            f"报告日期：{report_date.isoformat()}（使用最新交易日 {trade_date.isoformat()} 收盘数据）",
            _build_index_section(),
            _build_global_market_section(),
            _build_sector_section(trade_date),
            _build_limit_up_section(trade_date),
            _build_hsgt_section(trade_date),
            _build_hot_concepts_section(db, trade_date),
        ]
        return "\n\n".join(parts)
    finally:
        db.close()


def _build_global_market_section() -> str:
    """构建国际市场片段（欧美盘对今日A股的影响参考）。"""
    lines = ["国际市场（隔夜）："]
    try:
        from app.services import global_market_service

        indices = global_market_service.get_global_indices()
        if indices:
            for item in indices:
                pct = item.get("change_percent", 0)
                lines.append(
                    f"- {item.get('name')}（{item.get('market')}）: "
                    f"{item.get('price')} ({pct:+.2f}%)"
                )
        commodities = global_market_service.get_commodities_and_forex()
        if commodities:
            for item in commodities:
                pct = item.get("change_percent", 0)
                lines.append(
                    f"- {item.get('name')}: {item.get('price')} ({pct:+.2f}%)"
                )
    except Exception as exc:
        lines.append(f"国际市场数据获取失败：{exc}")
    return "\n".join(lines) if len(lines) > 1 else "国际市场：暂无数据。"


async def _generate_morning_report_content(report_date: date, context: str) -> dict:
    """调用 AI 生成晨报内容，返回 {"summary": ..., "content": ...}。"""
    prompt = (
        f"请生成 {report_date.isoformat()} 的 AI 晨报。\n"
        f"请基于以下市场数据，给出结构化、客观中性的开盘前晨报。"
    )
    return await ai_service.analyze_json(
        prompt=prompt, role="morning_report", context=context, schema=ai_service.AiReportOutput
    )


def _run_async(coro):
    """在同步上下文中运行异步协程，兼容 APScheduler 线程环境。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------


async def generate_morning_report(db: Session, report_date: date, force: bool = False) -> AiMorningReport:
    """生成指定日期的晨报（异步）。

    Args:
        force: 为 True 时强制重新生成，即使状态为 running 也会覆盖。
    """
    report = _get_or_create_report(db, report_date)
    if not force and report.status == "running":
        logger.info(f"[AiMorningReport] {report_date} 晨报正在生成中，跳过")
        return report

    report.status = "running"
    db.commit()

    try:
        context = await build_market_context(report_date)
        result = await _generate_morning_report_content(report_date, context)
        report.summary = result.get("summary")
        report.content = result.get("content")
        report.status = "success"
        report.error_message = None
    except Exception as exc:
        report.status = "failed"
        report.error_message = str(exc)[:2000]
        logger.exception(f"[AiMorningReport] 生成 {report_date} 晨报失败")
    finally:
        db.commit()
        db.refresh(report)

    return report


def generate_morning_report_sync(db: Session, report_date: date, force: bool = False) -> AiMorningReport:
    """生成指定日期的晨报（同步包装，供定时任务使用）。"""
    return _run_async(generate_morning_report(db, report_date, force=force))


# ---------------------------------------------------------------------------
# 查询与重试
# ---------------------------------------------------------------------------


def get_morning_report_list(
    db: Session, page: int = 1, page_size: int = 20
) -> tuple[list[AiMorningReport], int]:
    """查询晨报列表（按日期倒序）。"""
    query = db.query(AiMorningReport)
    total = query.count()
    items = (
        query.order_by(AiMorningReport.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_morning_report_detail(db: Session, report_id: int) -> AiMorningReport | None:
    """获取晨报详情。"""
    return db.query(AiMorningReport).filter(AiMorningReport.id == report_id).first()


def get_morning_report_by_date(db: Session, report_date: date) -> AiMorningReport | None:
    """按日期获取晨报。"""
    return db.query(AiMorningReport).filter(AiMorningReport.report_date == report_date).first()


def update_morning_report_content(
    db: Session, report_id: int, content: str, summary: str | None = None
) -> AiMorningReport | None:
    """管理员手工编辑晨报内容。"""
    report = db.query(AiMorningReport).filter(AiMorningReport.id == report_id).first()
    if report is None:
        return None
    report.content = content
    if summary is not None:
        report.summary = summary
    report.status = "success"
    report.error_message = None
    db.commit()
    db.refresh(report)
    return report


def retry_failed_morning_report(db: Session, report_date: date | None = None) -> dict:
    """重试指定日期的失败晨报。"""
    if report_date is None:
        report_date = date.today()

    failed_report = (
        db.query(AiMorningReport)
        .filter(AiMorningReport.report_date == report_date, AiMorningReport.status == "failed")
        .first()
    )

    if failed_report is None:
        return {"total": 0, "success": 0, "still_failed": 0}

    try:
        result = generate_morning_report_sync(db, report_date)
        if result.status == "success":
            return {"total": 1, "success": 1, "still_failed": 0}
        return {"total": 1, "success": 0, "still_failed": 1}
    except Exception:
        logger.exception(f"[AiMorningReport] 重试晨报 {failed_report.id} 失败")
        return {"total": 1, "success": 0, "still_failed": 1}
