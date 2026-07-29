"""数据同步接口。

保留数据表概况查询和概念同步（概念同步逻辑较特殊，不纳入 scheduler 通用任务）。
手动同步操作统一通过 /scheduler/jobs/{job_id}/run 触发。
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/status")
async def get_sync_status(
    user: User = Depends(get_current_user),
) -> dict:
    """获取所有本地表的数据概况（行数、最新日期、最后更新时间）。"""
    from sqlalchemy import text
    from app.db.base import SessionLocal

    # 定义需要展示的表及其日期字段
    tables_config = [
        {"table": "stock_basic", "title": "股票列表", "date_col": None, "category": "基础数据"},
        {"table": "stock_daily", "title": "日K线", "date_col": "trade_date", "category": "行情数据"},
        {"table": "stock_weekly", "title": "周K线", "date_col": "trade_date", "category": "行情数据"},
        {"table": "stock_monthly", "title": "月K线", "date_col": "trade_date", "category": "行情数据"},
        {"table": "stock_daily_basic", "title": "日线因子", "date_col": "trade_date", "category": "行情数据"},
        {"table": "stock_limit", "title": "涨跌停价格", "date_col": "trade_date", "category": "行情数据"},
        {"table": "stock_fina_indicator", "title": "财务指标", "date_col": "end_date", "category": "财务数据"},
        {"table": "stock_moneyflow", "title": "个股资金流", "date_col": "trade_date", "category": "资金流向"},
        {"table": "moneyflow_hsgt", "title": "沪深港通资金流", "date_col": "trade_date", "category": "资金流向"},
        {"table": "sector_moneyflow_industry", "title": "行业板块资金流", "date_col": "trade_date", "category": "资金流向"},
        {"table": "sector_moneyflow_concept", "title": "概念板块资金流", "date_col": "trade_date", "category": "资金流向"},
        {"table": "index_basic", "title": "指数基础", "date_col": None, "category": "指数数据"},
        {"table": "index_daily", "title": "指数日线", "date_col": "trade_date", "category": "指数数据"},
        {"table": "index_global", "title": "全球指数", "date_col": "trade_date", "category": "指数数据"},
        {"table": "top_list", "title": "龙虎榜", "date_col": "trade_date", "category": "龙虎榜"},
        {"table": "top_inst", "title": "龙虎榜机构", "date_col": "trade_date", "category": "龙虎榜"},
        {"table": "ths_index", "title": "同花顺指数", "date_col": None, "category": "板块题材"},
        {"table": "ths_daily", "title": "同花顺指数日线", "date_col": "trade_date", "category": "板块题材"},
        {"table": "ths_member", "title": "同花顺成分股", "date_col": None, "category": "板块题材"},
        {"table": "stock_concept", "title": "概念映射", "date_col": None, "category": "板块题材"},
        # 分析数据表
        {"table": "limit_list_d", "title": "涨跌停/炸板", "date_col": "trade_date", "category": "打板数据"},
        {"table": "limit_step", "title": "连板天梯", "date_col": "trade_date", "category": "打板数据"},
        {"table": "limit_list_ths", "title": "THS涨跌停榜", "date_col": "trade_date", "category": "打板数据"},
        {"table": "dc_concept", "title": "DC概念题材", "date_col": "trade_date", "category": "板块题材"},
        {"table": "ths_hot", "title": "THS热榜", "date_col": "trade_date", "category": "热点数据"},
        {"table": "dc_hot", "title": "DC热榜", "date_col": "trade_date", "category": "热点数据"},
        {"table": "hk_hold", "title": "北向持仓", "date_col": "trade_date", "category": "机构数据"},
        {"table": "stk_holdernumber", "title": "股东人数", "date_col": "ann_date", "category": "机构数据"},
        {"table": "stk_holdertrade", "title": "股东增减持", "date_col": "ann_date", "category": "机构数据"},
        {"table": "cyq_perf", "title": "筹码胜率", "date_col": "trade_date", "category": "机构数据"},
        {"table": "margin_detail", "title": "融资融券明细", "date_col": "trade_date", "category": "机构数据"},
        {"table": "broker_recommend", "title": "券商金股", "date_col": None, "category": "研报数据"},
        {"table": "report_rc", "title": "盈利预测", "date_col": "report_date", "category": "研报数据"},
        {"table": "index_weight", "title": "指数权重", "date_col": "trade_date", "category": "宏观数据"},
        {"table": "index_dailybasic", "title": "指数估值", "date_col": "trade_date", "category": "宏观数据"},
        {"table": "sw_daily", "title": "申万行业日线", "date_col": "trade_date", "category": "宏观数据"},
        {"table": "cn_cpi", "title": "CPI", "date_col": None, "category": "宏观数据"},
        {"table": "cn_pmi", "title": "PMI", "date_col": None, "category": "宏观数据"},
        {"table": "shibor_lpr", "title": "LPR利率", "date_col": None, "category": "宏观数据"},
        {"table": "sf_month", "title": "社融增量", "date_col": None, "category": "宏观数据"},
        {"table": "etf_basic", "title": "ETF基础", "date_col": None, "category": "ETF/可转债"},
        {"table": "etf_share_size", "title": "ETF份额", "date_col": "trade_date", "category": "ETF/可转债"},
        {"table": "cb_basic", "title": "可转债基础", "date_col": None, "category": "ETF/可转债"},
        {"table": "cb_daily_local", "title": "可转债行情", "date_col": "trade_date", "category": "ETF/可转债"},
        # 分时数据
        {"table": "stock_intraday", "title": "分时K线", "date_col": "trade_date", "category": "盘中数据"},
        # AI 生成数据
        {"table": "market_pulse", "title": "市场温度", "date_col": "trade_date", "category": "AI数据"},
    ]

    db = SessionLocal()
    results = []
    try:
        for cfg in tables_config:
            tbl = cfg["table"]
            try:
                # 查行数
                row_count = db.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()

                # 查最新日期
                latest_date = None
                if cfg["date_col"]:
                    latest_date = db.execute(
                        text(f"SELECT MAX({cfg['date_col']}) FROM {tbl}")
                    ).scalar()
                    if latest_date:
                        latest_date = str(latest_date)

                # 查最后更新时间
                last_updated = None
                try:
                    last_updated = db.execute(
                        text(f"SELECT MAX(updated_at) FROM {tbl}")
                    ).scalar()
                    if last_updated:
                        last_updated = last_updated.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    db.rollback()
                    try:
                        last_updated = db.execute(
                            text(f"SELECT MAX(created_at) FROM {tbl}")
                        ).scalar()
                        if last_updated:
                            last_updated = last_updated.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        db.rollback()

                results.append({
                    "table": tbl,
                    "title": cfg["title"],
                    "category": cfg["category"],
                    "row_count": row_count,
                    "latest_date": latest_date,
                    "last_updated": last_updated,
                    "sync_status": _get_sync_status(cfg, latest_date),
                })
            except Exception:
                db.rollback()
                results.append({
                    "table": tbl,
                    "title": cfg["title"],
                    "category": cfg["category"],
                    "row_count": 0,
                    "latest_date": None,
                    "last_updated": None,
                    "sync_status": "无数据",
                })
    finally:
        db.close()

    return {"success": True, "data": results}


def _get_sync_status(cfg: dict, latest_date) -> str:
    """判断数据同步状态。"""
    from datetime import date, datetime, timedelta, timezone

    # 中国时间
    cn_tz = timezone(timedelta(hours=8))
    today = datetime.now(cn_tz).date()
    weekday = today.weekday()  # 0=周一

    if not latest_date:
        return "无数据"

    # 解析日期
    try:
        if isinstance(latest_date, str):
            latest = date.fromisoformat(latest_date)
        else:
            latest = latest_date
    except (ValueError, TypeError):
        return "未知"

    # 没有日期列的表不需要判断（如 stock_basic）
    if cfg.get("date_col") is None:
        return "正常"

    # 计算最新交易日应该是哪天
    # 周一~周五且当前时间 > 16:30 → 最新应为今天
    # 周一~周五且当前时间 < 16:30 → 最新应为昨天/上一个交易日
    # 周六/周日 → 最新应为周五
    now_time = datetime.now(cn_tz).time()
    from datetime import time as dtime
    data_ready_time = dtime(16, 30)

    if weekday >= 5:
        # 周末：最新应该是周五
        expected = today - timedelta(days=weekday - 4)
    elif now_time >= data_ready_time:
        # 工作日 16:30 后：最新应该是今天
        expected = today
    else:
        # 工作日 16:30 前：最新应该是上一个交易日
        if weekday == 0:  # 周一早上
            expected = today - timedelta(days=3)  # 上周五
        else:
            expected = today - timedelta(days=1)

    if latest >= expected:
        return "已同步"
    elif (expected - latest).days <= 1:
        return "同步中"
    else:
        return f"滞后{(expected - latest).days}天"


# ============================================================
# 概念同步（保留，逻辑较特殊）
# ============================================================


def _run_sync_concepts():
    """后台任务：同步全部概念板块及其成分股到 stock_concept 表。"""
    import time
    import logging

    from sqlalchemy.dialects.postgresql import insert
    from app.db.base import SessionLocal
    from app.models.stock import StockConcept
    from app.services.stock_service import get_pro

    logger = logging.getLogger(__name__)
    pro = get_pro()

    df_concepts = pro.ths_index(exchange="A", type="N",
        fields="ts_code,name,count,exchange,list_date,type")
    if df_concepts is None or df_concepts.empty:
        logger.warning("sync_concepts: 获取概念列表为空")
        return

    logger.info(f"sync_concepts: 共 {len(df_concepts)} 个概念板块，开始逐个拉取成分股...")

    db = SessionLocal()
    total_inserted = 0
    try:
        for idx, row in df_concepts.iterrows():
            concept_code = row["ts_code"]
            concept_name = row["name"]

            try:
                df_members = pro.ths_member(ts_code=concept_code)
            except Exception as e:
                logger.warning(f"sync_concepts: 拉取概念 {concept_code}({concept_name}) 成分失败: {e}")
                time.sleep(0.3)
                continue

            if df_members is None or df_members.empty:
                time.sleep(0.2)
                continue

            records = []
            for _, member_row in df_members.iterrows():
                con_code = member_row.get("con_code")
                if not con_code or str(con_code).strip() == "" or con_code == concept_code:
                    continue
                con_code = str(con_code).strip()
                con_name = member_row.get("con_name")
                if con_name and not isinstance(con_name, str):
                    con_name = str(con_name)
                records.append({
                    "concept_id": concept_code,
                    "concept_name": concept_name,
                    "ts_code": con_code,
                    "name": con_name if con_name else None,
                    "in_date": None,
                    "out_date": None,
                })

            if records:
                seen = {}
                for r in records:
                    key = (r["concept_id"], r["ts_code"])
                    seen[key] = r
                records = list(seen.values())

            if records:
                try:
                    stmt = insert(StockConcept.__table__).values(records)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uix_stock_concept",
                        set_={
                            "concept_name": stmt.excluded.concept_name,
                            "name": stmt.excluded.name,
                        }
                    )
                    db.execute(stmt)
                    db.commit()
                    total_inserted += len(records)
                except Exception as e:
                    db.rollback()
                    logger.warning(f"sync_concepts: 插入概念 {concept_code} 失败: {str(e)[:100]}")

            time.sleep(0.35)

            if (idx + 1) % 50 == 0:
                logger.info(f"sync_concepts: 已处理 {idx + 1}/{len(df_concepts)} 个概念，累计 {total_inserted} 条记录")

        logger.info(f"sync_concepts: 完成！共处理 {len(df_concepts)} 个概念，{total_inserted} 条映射记录")
    except Exception as e:
        logger.error(f"sync_concepts: 同步异常: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/concept")
async def sync_concept_endpoint(
    user: User = Depends(get_current_user),
) -> dict:
    """同步全部概念板块成分股映射（耗时较长，独立线程执行）。"""
    import threading
    threading.Thread(target=_run_sync_concepts, daemon=True).start()
    return {"success": True, "data": {"status": "started", "message": "正在后台同步全部概念板块成分股，预计需要几分钟"}}
