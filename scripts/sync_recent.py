"""快速增量同步最近几天的数据（日/周/月K线 + 日线因子 + 板块资金流等）。

用法：
    python scripts/sync_recent.py          # 同步最近 5 天
    python scripts/sync_recent.py --days 3 # 同步最近 3 天
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _log(message: str):
    print(message, flush=True)


from app.db.base import SessionLocal
from app.services.data_sync_service import (
    get_pro,
    sync_daily_basic,
    sync_index_daily,
    sync_klines,
    sync_moneyflow_hsgt,
    sync_sector_moneyflow,
    sync_stock_limit,
    sync_stock_moneyflow,
    sync_top_inst,
    sync_top_list,
    _get_trade_dates,
    _sync_klines_by_date,
    _sync_daily_basic_by_date,
)


def main():
    parser = argparse.ArgumentParser(description="快速增量同步最近几天的 Tushare 数据")
    parser.add_argument("--days", type=int, default=5, help="同步最近多少天，默认 5")
    args = parser.parse_args()

    end_date = date.today()
    start_date = end_date - timedelta(days=args.days)

    _log(f"=== 增量同步 {start_date} ~ {end_date} ===\n")

    db = SessionLocal()
    try:
        # 1. 日 K 线
        _log("[1] 同步日 K 线...")
        count = _sync_klines_by_date(db, "D", start_date, end_date)
        _log(f"    完成，共 {count} 条\n")

        # 2. 周 K 线
        _log("[2] 同步周 K 线...")
        count = _sync_klines_by_date(db, "W", start_date, end_date)
        _log(f"    完成，共 {count} 条\n")

        # 3. 月 K 线
        _log("[3] 同步月 K 线...")
        count = _sync_klines_by_date(db, "M", start_date, end_date)
        _log(f"    完成，共 {count} 条\n")

        # 4. 日线因子
        _log("[4] 同步日线因子...")
        count = _sync_daily_basic_by_date(db, start_date, end_date)
        _log(f"    完成，共 {count} 条\n")

        db.commit()
    finally:
        db.close()

    # 5. 板块资金流
    _log("[5] 同步板块资金流（行业）...")
    count = sync_sector_moneyflow(sector_type="industry", start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    _log("[6] 同步板块资金流（概念）...")
    count = sync_sector_moneyflow(sector_type="concept", start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    # 6. 个股资金流
    _log("[7] 同步个股资金流...")
    count = sync_stock_moneyflow(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    # 7. 沪深港通
    _log("[8] 同步沪深港通...")
    count = sync_moneyflow_hsgt(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    # 8. 指数日线
    _log("[9] 同步指数日线...")
    count = sync_index_daily(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    # 9. 涨跌停
    _log("[10] 同步涨跌停...")
    count = sync_stock_limit(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    # 10. 龙虎榜
    _log("[11] 同步龙虎榜...")
    count = sync_top_list(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    _log("[12] 同步龙虎榜机构...")
    count = sync_top_inst(start_date=start_date, end_date=end_date)
    _log(f"    完成，共 {count} 条\n")

    _log("=== 增量同步完成 ===")


if __name__ == "__main__":
    main()
