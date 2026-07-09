"""分析数据同步服务。

负责同步打板/题材/机构/宏观/ETF/可转债等数据分析所需的数据。
每个函数对应一类数据，可独立调用或由调度器触发。
"""

import logging
import time
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from app.db.base import SessionLocal
from app.models.analysis import (
    BrokerRecommend,
    CbBasic,
    CbDaily,
    CnCpi,
    CnPmi,
    CyqPerf,
    DcConcept,
    DcConceptCons,
    DcHot,
    EtfBasic,
    EtfShareSize,
    HkHold,
    IndexDailyBasic,
    IndexWeight,
    LimitListD,
    LimitListThs,
    LimitStep,
    MarginDetail,
    ReportRc,
    SfMonth,
    ShiborLpr,
    StkHolderNumber,
    StkHolderTrade,
    SwDaily,
    ThsHot,
)

logger = logging.getLogger(__name__)


def _get_pro():
    from app.services.data_sync_service import get_pro
    return get_pro()


def _date_str(d: date) -> str:
    return d.strftime("%Y%m%d")


def _bulk_upsert(db, model, records: list[dict], conflict_cols: list[str]):
    """批量 upsert 到 PostgreSQL。"""
    if not records:
        return 0
    stmt = insert(model.__table__).values(records)
    update_cols = {k: stmt.excluded[k] for k in records[0].keys() if k not in conflict_cols and k != "created_at"}
    stmt = stmt.on_conflict_do_update(
        constraint=model.__table__.constraints.__iter__().__next__().name
        if hasattr(model.__table__, "constraints") else None,
        index_elements=conflict_cols,
        set_=update_cols,
    )
    db.execute(stmt)
    return len(records)


def _safe_upsert(db, model, records: list[dict], conflict_cols: list[str]):
    """安全的批量 upsert，使用 index_elements。自动去除同批次内重复行。"""
    if not records:
        return 0
    # 去重：PostgreSQL ON CONFLICT 不允许同一 INSERT 语句中出现重复约束值
    seen = {}
    for r in records:
        key = tuple(r.get(c) for c in conflict_cols)
        seen[key] = r
    records = list(seen.values())
    if not records:
        return 0

    stmt = insert(model.__table__).values(records)
    update_cols = {k: stmt.excluded[k] for k in records[0].keys() if k not in conflict_cols and k != "created_at"}
    if update_cols:
        stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
    db.execute(stmt)
    return len(records)


# ============================================================
# 一、打板/题材/热点
# ============================================================


def sync_limit_list_d(start_date: date = None, end_date: date = None, days: int = 1):
    """同步涨跌停和炸板数据。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.limit_list_d(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "name": row.get("name"),
                        "close": row.get("close"),
                        "pct_chg": row.get("pct_chg"),
                        "amp": row.get("amp"),
                        "fc_ratio": row.get("fc_ratio"),
                        "fl_ratio": row.get("fl_ratio"),
                        "fd_amount": row.get("fd_amount"),
                        "first_time": row.get("first_time"),
                        "last_time": row.get("last_time"),
                        "open_times": row.get("open_times"),
                        "strth": row.get("strth"),
                        "limit": row.get("limit"),
                    })
                _safe_upsert(db, LimitListD, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] limit_list_d: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] limit_list_d 失败: {e}")
        raise
    finally:
        db.close()


def sync_limit_step(start_date: date = None, end_date: date = None, days: int = 1):
    """同步涨停连板天梯。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.limit_step(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "trade_date": d,
                        "step": int(row.get("step", 0)),
                        "ts_code": row.get("ts_code"),
                        "name": row.get("name"),
                        "close": row.get("close"),
                        "pct_chg": row.get("pct_chg"),
                    })
                _safe_upsert(db, LimitStep, records, ["trade_date", "step", "ts_code"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] limit_step: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] limit_step 失败: {e}")
        raise
    finally:
        db.close()


def sync_limit_list_ths(start_date: date = None, end_date: date = None, days: int = 1):
    """同步THS涨跌停榜单。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.limit_list_ths(trade_date=ds)
            time.sleep(0.5)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "name": row.get("name"),
                        "close": row.get("close"),
                        "pct_chg": row.get("pct_chg"),
                        "limit_type": row.get("limit_type"),
                        "first_time": row.get("first_time"),
                        "last_time": row.get("last_time"),
                        "open_times": row.get("open_times"),
                        "lu_limit_order": row.get("lu_limit_order"),
                        "limit_days": row.get("limit_days"),
                    })
                _safe_upsert(db, LimitListThs, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] limit_list_ths: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] limit_list_ths 失败: {e}")
        raise
    finally:
        db.close()


def sync_dc_concept(start_date: date = None, end_date: date = None, days: int = 1):
    """同步DC概念题材列表。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.dc_concept(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    ts_code = row.get("theme_code") or row.get("ts_code")
                    if not ts_code or pd.isna(ts_code):
                        continue
                    records.append({
                        "ts_code": str(ts_code),
                        "trade_date": d,
                        "name": row.get("name"),
                        "z_num": row.get("z_t_num", row.get("z_num")),
                        "d_num": row.get("d_num"),
                        "pct_chg": row.get("pct_change", row.get("pct_chg")),
                        "lead_stock": row.get("lead_stock"),
                        "lead_pct_chg": row.get("lead_stock_pct_change", row.get("lead_pct_chg")),
                    })
                _safe_upsert(db, DcConcept, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] dc_concept: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] dc_concept 失败: {e}")
        raise
    finally:
        db.close()


def sync_ths_hot(days: int = 1):
    """同步THS热榜。"""
    pro = _get_pro()
    trade_date = _date_str(date.today())

    db = SessionLocal()
    total = 0
    try:
        df = pro.ths_hot(trade_date=trade_date)
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "ts_code": row.get("ts_code", row.get("code", "")),
                    "trade_date": date.today(),
                    "data_type": row.get("data_type", "stock"),
                    "rank": row.get("rank"),
                    "name": row.get("name"),
                    "pct_chg": row.get("pct_change", row.get("pct_chg")),
                    "hot": row.get("hot"),
                })
            _safe_upsert(db, ThsHot, records, ["ts_code", "trade_date", "data_type"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] ths_hot: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] ths_hot 失败: {e}")
        raise
    finally:
        db.close()


def sync_dc_hot(days: int = 1):
    """同步DC热榜。"""
    pro = _get_pro()
    trade_date = _date_str(date.today())

    db = SessionLocal()
    total = 0
    try:
        df = pro.dc_hot(trade_date=trade_date)
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "ts_code": row.get("ts_code", row.get("code", "")),
                    "trade_date": date.today(),
                    "market": row.get("market", "A股"),
                    "rank": row.get("rank"),
                    "name": row.get("name"),
                    "pct_chg": row.get("pct_change", row.get("pct_chg")),
                })
            _safe_upsert(db, DcHot, records, ["ts_code", "trade_date", "market"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] dc_hot: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] dc_hot 失败: {e}")
        raise
    finally:
        db.close()


# ============================================================
# 二、机构行为/筹码
# ============================================================


def sync_hk_hold(start_date: date = None, end_date: date = None, days: int = 1):
    """同步沪深股通持股明细（北向资金个股持仓）。

    注：该接口按 trade_date 查询有 T+1~T+2 延迟，所以默认多拉2天。
    """
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days + 2)  # 多拉2天覆盖延迟

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            for ex in ["SH", "SZ"]:
                df = pro.hk_hold(trade_date=ds, exchange=ex)
                time.sleep(0.5)
                if df is not None and not df.empty:
                    records = []
                    for _, row in df.iterrows():
                        ts_code = row.get("ts_code", row.get("code", ""))
                        if not ts_code or pd.isna(ts_code):
                            continue
                        records.append({
                            "ts_code": ts_code,
                            "trade_date": d,
                            "exchange": ex,
                            "vol": row.get("vol"),
                            "ratio": row.get("ratio"),
                        })
                    if records:
                        _safe_upsert(db, HkHold, records, ["ts_code", "trade_date", "exchange"])
                        total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] hk_hold: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] hk_hold 失败: {e}")
        raise
    finally:
        db.close()


def sync_stk_holdernumber(days: int = 30):
    """同步股东人数（不定期公布，默认拉最近30天）。"""
    pro = _get_pro()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        df = pro.stk_holdernumber(start_date=_date_str(start_date), end_date=_date_str(end_date))
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                ann = row.get("ann_date")
                if pd.isna(ann) or not ann:
                    continue
                records.append({
                    "ts_code": row.get("ts_code"),
                    "ann_date": pd.to_datetime(str(ann)).date(),
                    "end_date": pd.to_datetime(str(row.get("end_date"))).date() if row.get("end_date") else None,
                    "holder_num": row.get("holder_num"),
                    "holder_num_change": row.get("holder_num_change"),
                    "holder_num_ratio": row.get("holder_num_ratio"),
                })
            _safe_upsert(db, StkHolderNumber, records, ["ts_code", "ann_date"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] stk_holdernumber: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] stk_holdernumber 失败: {e}")
        raise
    finally:
        db.close()


def sync_stk_holdertrade(days: int = 7):
    """同步股东增减持。"""
    pro = _get_pro()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        df = pro.stk_holdertrade(start_date=_date_str(start_date), end_date=_date_str(end_date))
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                ann = row.get("ann_date")
                if pd.isna(ann) or not ann:
                    continue
                records.append({
                    "ts_code": row.get("ts_code"),
                    "ann_date": pd.to_datetime(str(ann)).date(),
                    "holder_name": str(row.get("holder_name", ""))[:200],
                    "holder_type": row.get("holder_type"),
                    "in_de": row.get("in_de"),
                    "change_vol": row.get("change_vol"),
                    "change_ratio": row.get("change_ratio"),
                    "after_share": row.get("after_share"),
                    "after_ratio": row.get("after_ratio"),
                    "avg_price": row.get("avg_price"),
                    "begin_date": pd.to_datetime(str(row.get("begin_date"))).date() if row.get("begin_date") else None,
                    "close_date": pd.to_datetime(str(row.get("close_date"))).date() if row.get("close_date") else None,
                })
            _safe_upsert(db, StkHolderTrade, records, ["ts_code", "ann_date", "holder_name"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] stk_holdertrade: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] stk_holdertrade 失败: {e}")
        raise
    finally:
        db.close()


def sync_cyq_perf(start_date: date = None, end_date: date = None, days: int = 1):
    """同步每日筹码及胜率。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.cyq_perf(trade_date=ds)
            time.sleep(0.5)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "his_low": row.get("his_low"),
                        "his_high": row.get("his_high"),
                        "cost_5pct": row.get("cost_5pct"),
                        "cost_15pct": row.get("cost_15pct"),
                        "cost_50pct": row.get("cost_50pct"),
                        "cost_85pct": row.get("cost_85pct"),
                        "cost_95pct": row.get("cost_95pct"),
                        "weight_avg": row.get("weight_avg"),
                        "winner_rate": row.get("winner_rate"),
                    })
                _safe_upsert(db, CyqPerf, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] cyq_perf: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] cyq_perf 失败: {e}")
        raise
    finally:
        db.close()


def sync_margin_detail(start_date: date = None, end_date: date = None, days: int = 1):
    """同步融资融券明细。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.margin_detail(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "rzye": row.get("rzye"),
                        "rqye": row.get("rqye"),
                        "rzmre": row.get("rzmre"),
                        "rqyl": row.get("rqyl"),
                        "rzche": row.get("rzche"),
                        "rqchl": row.get("rqchl"),
                        "rqmcl": row.get("rqmcl"),
                        "rzrqye": row.get("rzrqye"),
                    })
                _safe_upsert(db, MarginDetail, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] margin_detail: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] margin_detail 失败: {e}")
        raise
    finally:
        db.close()


def sync_broker_recommend(days: int = 1):
    """同步券商月度金股（按月拉取当月）。"""
    pro = _get_pro()
    month = date.today().strftime("%Y%m")

    db = SessionLocal()
    total = 0
    try:
        df = pro.broker_recommend(month=month)
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "month": row.get("month", month),
                    "broker": str(row.get("broker", ""))[:100],
                    "ts_code": row.get("ts_code"),
                    "name": row.get("name"),
                })
            _safe_upsert(db, BrokerRecommend, records, ["month", "broker", "ts_code"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] broker_recommend: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] broker_recommend 失败: {e}")
        raise
    finally:
        db.close()


def sync_report_rc(days: int = 3):
    """同步券商盈利预测。"""
    pro = _get_pro()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        df = pro.report_rc(start_date=_date_str(start_date), end_date=_date_str(end_date))
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                rd = row.get("report_date")
                if pd.isna(rd) or not rd:
                    continue
                records.append({
                    "ts_code": row.get("ts_code"),
                    "report_date": pd.to_datetime(str(rd)).date(),
                    "org_name": str(row.get("org_name", ""))[:200],
                    "name": row.get("name"),
                    "rating": row.get("rating"),
                    "target_price": row.get("target_price"),
                    "target_price_change": row.get("target_price_change"),
                    "eps_current": row.get("eps_current", row.get("eps2")),
                    "eps_next": row.get("eps_next", row.get("eps3")),
                })
            # 去重：同一批数据里可能有重复的(ts_code, report_date, org_name)
            seen = {}
            for r in records:
                key = (r["ts_code"], r["report_date"], r["org_name"])
                seen[key] = r
            records = list(seen.values())

            _safe_upsert(db, ReportRc, records, ["ts_code", "report_date", "org_name"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] report_rc: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] report_rc 失败: {e}")
        raise
    finally:
        db.close()


# ============================================================
# 三、宏观/行业趋势
# ============================================================


def sync_index_weight(days: int = 1):
    """同步指数成分和权重（月度数据，拉取当月）。"""
    pro = _get_pro()
    # 用当月第一天和最后一天
    today = date.today()
    start = today.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    db = SessionLocal()
    total = 0
    try:
        for idx_code in ["000300.SH", "000905.SH", "000016.SH"]:  # 沪深300/中证500/上证50
            df = pro.index_weight(index_code=idx_code, start_date=_date_str(start), end_date=_date_str(end))
            time.sleep(0.5)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    td = row.get("trade_date")
                    if pd.isna(td) or not td:
                        continue
                    records.append({
                        "index_code": idx_code,
                        "con_code": row.get("con_code"),
                        "trade_date": pd.to_datetime(str(td)).date(),
                        "weight": row.get("weight"),
                    })
                _safe_upsert(db, IndexWeight, records, ["index_code", "con_code", "trade_date"])
                total += len(records)
        db.commit()
        logger.info(f"[Sync] index_weight: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] index_weight 失败: {e}")
        raise
    finally:
        db.close()


def sync_index_dailybasic(start_date: date = None, end_date: date = None, days: int = 1):
    """同步大盘指数每日指标。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.index_dailybasic(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "total_mv": row.get("total_mv"),
                        "float_mv": row.get("float_mv"),
                        "total_share": row.get("total_share"),
                        "float_share": row.get("float_share"),
                        "free_share": row.get("free_share"),
                        "turnover_rate": row.get("turnover_rate"),
                        "turnover_rate_f": row.get("turnover_rate_f"),
                        "pe": row.get("pe"),
                        "pe_ttm": row.get("pe_ttm"),
                        "pb": row.get("pb"),
                    })
                _safe_upsert(db, IndexDailyBasic, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] index_dailybasic: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] index_dailybasic 失败: {e}")
        raise
    finally:
        db.close()


def sync_sw_daily(start_date: date = None, end_date: date = None, days: int = 1):
    """同步申万日线行情。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        df = pro.sw_daily(start_date=_date_str(start_date), end_date=_date_str(end_date))
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                td = row.get("trade_date")
                if pd.isna(td) or not td:
                    continue
                records.append({
                    "ts_code": row.get("ts_code"),
                    "trade_date": pd.to_datetime(str(td)).date(),
                    "name": row.get("name"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "change": row.get("change"),
                    "pct_chg": row.get("pct_chg"),
                    "vol": row.get("vol"),
                    "amount": row.get("amount"),
                })
            _safe_upsert(db, SwDaily, records, ["ts_code", "trade_date"])
            total = len(records)
        db.commit()
        logger.info(f"[Sync] sw_daily: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] sw_daily 失败: {e}")
        raise
    finally:
        db.close()


def sync_cn_cpi(days: int = 1):
    """同步CPI数据。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.cn_cpi()
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                m = row.get("month")
                if pd.isna(m) or not m:
                    continue
                records.append({
                    "month": str(m),
                    "nt_val": row.get("nt_val"),
                    "nt_yoy": row.get("nt_yoy"),
                    "nt_mom": row.get("nt_mom"),
                    "nt_accu": row.get("nt_accu"),
                    "town_val": row.get("town_val"),
                    "town_yoy": row.get("town_yoy"),
                    "town_mom": row.get("town_mom"),
                    "town_accu": row.get("town_accu"),
                    "cnt_val": row.get("cnt_val"),
                    "cnt_yoy": row.get("cnt_yoy"),
                    "cnt_mom": row.get("cnt_mom"),
                    "cnt_accu": row.get("cnt_accu"),
                })
            _safe_upsert(db, CnCpi, records, ["month"])
        db.commit()
        logger.info(f"[Sync] cn_cpi 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] cn_cpi 失败: {e}")
        raise
    finally:
        db.close()


def sync_cn_pmi(days: int = 1):
    """同步PMI数据。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.cn_pmi()
        time.sleep(0.3)
        if df is not None and not df.empty:
            # Tushare 返回编码字段，做映射
            col_map = {
                "MONTH": "month",
                "PMI010000": "pmi",          # 制造业PMI
                "PMI010100": "pmi_mp",       # 生产
                "PMI010200": "pmi_no",       # 新订单
                "PMI010800": "pmi_rmd",      # 原材料库存
                "PMI010500": "pmi_emp",      # 从业人员
                "PMI010600": "pmi_del",      # 供应商配送时间
                "PMI030000": "npmi",         # 非制造业PMI
                "PMI020100": "npmi_bact",    # 商务活动
                "PMI020200": "npmi_no",      # 新订单(非)
            }
            records = []
            for _, row in df.iterrows():
                m = row.get("MONTH", row.get("month"))
                if pd.isna(m) or not m:
                    continue
                rec = {"month": str(m)}
                for src_col, dst_col in col_map.items():
                    if dst_col == "month":
                        continue
                    val = row.get(src_col)
                    rec[dst_col] = val if not pd.isna(val) else None
                records.append(rec)
            _safe_upsert(db, CnPmi, records, ["month"])
        db.commit()
        logger.info(f"[Sync] cn_pmi 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] cn_pmi 失败: {e}")
        raise
    finally:
        db.close()


def sync_shibor_lpr(days: int = 1):
    """同步LPR利率。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.shibor_lpr()
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                d = row.get("date")
                if pd.isna(d) or not d:
                    continue
                records.append({
                    "date": pd.to_datetime(str(d)).date(),
                    "lpr_1y": row.get("1y", row.get("lpr_1y")),
                    "lpr_5y": row.get("5y", row.get("lpr_5y")),
                })
            _safe_upsert(db, ShiborLpr, records, ["date"])
        db.commit()
        logger.info(f"[Sync] shibor_lpr 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] shibor_lpr 失败: {e}")
        raise
    finally:
        db.close()


def sync_sf_month(days: int = 1):
    """同步社融增量。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.sf_month()
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                m = row.get("month")
                if pd.isna(m) or not m:
                    continue
                records.append({
                    "month": str(m),
                    "rmbfe": row.get("rmbfe"),
                    "trust_loan": row.get("trust_loan"),
                    "entrust_loan": row.get("entrust_loan"),
                    "undiscounted_ba": row.get("undiscounted_ba"),
                    "cb": row.get("cb"),
                    "stk": row.get("stk"),
                    "govbond": row.get("govbond"),
                    "sf": row.get("sf"),
                })
            _safe_upsert(db, SfMonth, records, ["month"])
        db.commit()
        logger.info(f"[Sync] sf_month 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] sf_month 失败: {e}")
        raise
    finally:
        db.close()


# ============================================================
# 四、ETF/可转债
# ============================================================


def sync_etf_basic(days: int = 1):
    """同步ETF基本信息。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.etf_basic()
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "ts_code": row.get("ts_code"),
                    "name": row.get("name"),
                    "management": row.get("management"),
                    "custodian": row.get("custodian"),
                    "fund_type": row.get("fund_type"),
                    "found_date": pd.to_datetime(str(row.get("found_date"))).date() if row.get("found_date") and not pd.isna(row.get("found_date")) else None,
                    "due_date": pd.to_datetime(str(row.get("due_date"))).date() if row.get("due_date") and not pd.isna(row.get("due_date")) else None,
                    "list_date": pd.to_datetime(str(row.get("list_date"))).date() if row.get("list_date") and not pd.isna(row.get("list_date")) else None,
                    "delist_date": pd.to_datetime(str(row.get("delist_date"))).date() if row.get("delist_date") and not pd.isna(row.get("delist_date")) else None,
                    "issue_amount": row.get("issue_amount"),
                    "m_fee": row.get("m_fee"),
                    "c_fee": row.get("c_fee"),
                    "benchmark": str(row.get("benchmark", ""))[:500] if row.get("benchmark") else None,
                    "status": row.get("status"),
                    "invest_type": row.get("invest_type"),
                    "market": row.get("market"),
                })
            _safe_upsert(db, EtfBasic, records, ["ts_code"])
        db.commit()
        logger.info(f"[Sync] etf_basic 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] etf_basic 失败: {e}")
        raise
    finally:
        db.close()


def sync_etf_share_size(start_date: date = None, end_date: date = None, days: int = 1):
    """同步ETF份额规模。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.etf_share_size(trade_date=ds)
            time.sleep(0.5)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "fd_share": row.get("fd_share"),
                        "fd_nav": row.get("fd_nav"),
                        "market_cap": row.get("market_cap"),
                        "close": row.get("close"),
                    })
                _safe_upsert(db, EtfShareSize, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] etf_share_size: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] etf_share_size 失败: {e}")
        raise
    finally:
        db.close()


def sync_cb_basic(days: int = 1):
    """同步可转债基础信息。"""
    pro = _get_pro()
    db = SessionLocal()
    try:
        df = pro.cb_basic()
        time.sleep(0.3)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "ts_code": row.get("ts_code"),
                    "bond_full_name": row.get("bond_full_name"),
                    "bond_short_name": row.get("bond_short_name"),
                    "stk_code": row.get("stk_code"),
                    "stk_short_name": row.get("stk_short_name"),
                    "issue_size": row.get("issue_size"),
                    "par_value": row.get("par_value"),
                    "conv_price": row.get("conv_price"),
                    "conv_start_date": pd.to_datetime(str(row.get("conv_start_date"))).date() if row.get("conv_start_date") and not pd.isna(row.get("conv_start_date")) else None,
                    "conv_end_date": pd.to_datetime(str(row.get("conv_end_date"))).date() if row.get("conv_end_date") and not pd.isna(row.get("conv_end_date")) else None,
                    "maturity_date": pd.to_datetime(str(row.get("maturity_date"))).date() if row.get("maturity_date") and not pd.isna(row.get("maturity_date")) else None,
                    "list_date": pd.to_datetime(str(row.get("list_date"))).date() if row.get("list_date") and not pd.isna(row.get("list_date")) else None,
                    "delist_date": pd.to_datetime(str(row.get("delist_date"))).date() if row.get("delist_date") and not pd.isna(row.get("delist_date")) else None,
                    "exchange": row.get("exchange"),
                })
            _safe_upsert(db, CbBasic, records, ["ts_code"])
        db.commit()
        logger.info(f"[Sync] cb_basic 完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] cb_basic 失败: {e}")
        raise
    finally:
        db.close()


def sync_cb_daily(start_date: date = None, end_date: date = None, days: int = 1):
    """同步可转债日线行情。"""
    pro = _get_pro()
    if not start_date:
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    total = 0
    try:
        d = start_date
        while d <= end_date:
            ds = _date_str(d)
            df = pro.cb_daily(trade_date=ds)
            time.sleep(0.3)
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "ts_code": row.get("ts_code"),
                        "trade_date": d,
                        "close": row.get("close"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "pre_close": row.get("pre_close"),
                        "change": row.get("change"),
                        "pct_chg": row.get("pct_chg"),
                        "vol": row.get("vol"),
                        "amount": row.get("amount"),
                    })
                _safe_upsert(db, CbDaily, records, ["ts_code", "trade_date"])
                total += len(records)
            d += timedelta(days=1)
        db.commit()
        logger.info(f"[Sync] cb_daily: {total} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"[Sync] cb_daily 失败: {e}")
        raise
    finally:
        db.close()
