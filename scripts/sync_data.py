"""Tushare 数据同步脚本。

用法：
    python scripts/sync_data.py
    python scripts/sync_data.py --years 5
    python scripts/sync_data.py --codes 000001.SZ,600519.SH --periods D,W,M
"""

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _log(message: str):
    print(message, flush=True)


from app.services.data_sync_service import (
    sync_daily_basic,
    sync_fina_indicator,
    sync_klines,
    sync_sector_moneyflow,
    sync_stock_basic,
)


def main():
    parser = argparse.ArgumentParser(description="同步 Tushare 数据到 PostgreSQL")
    parser.add_argument("--years", type=int, default=10, help="同步最近多少年数据，默认 10")
    parser.add_argument("--codes", type=str, default=None, help="指定股票代码，逗号分隔，默认全市场")
    parser.add_argument(
        "--periods",
        type=str,
        default="D,W,M,Y",
        help="同步哪些 K 线周期，逗号分隔，默认 D,W,M,Y",
    )
    parser.add_argument("--skip-basic", action="store_true", help="跳过同步股票基础信息")
    parser.add_argument("--skip-kline", action="store_true", help="跳过同步 K 线")
    parser.add_argument("--skip-daily-basic", action="store_true", help="跳过同步日线因子")
    parser.add_argument("--skip-fina", action="store_true", help="跳过同步财务指标")
    parser.add_argument("--skip-sector-moneyflow", action="store_true", help="跳过同步板块资金流")
    parser.add_argument(
        "--sector-types",
        type=str,
        default="industry,concept",
        help="同步哪些板块资金流类型，逗号分隔，默认 industry,concept",
    )
    args = parser.parse_args()

    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]

    periods = [p.strip().upper() for p in args.periods.split(",") if p.strip()]

    results = {}

    if not args.skip_basic:
        _log("[1/4] 同步股票基础信息...")
        results["stock_basic"] = sync_stock_basic()
        _log(f"      完成，共 {results['stock_basic']} 条")

    if not args.skip_kline:
        for period in periods:
            _log(f"[2/4] 同步 {period} K 线...")
            if codes:
                count = 0
                for code in codes:
                    count += sync_klines(ts_code=code, period=period, years=args.years)
            else:
                count = sync_klines(period=period, years=args.years)
            results[f"kline_{period}"] = count
            _log(f"      完成，共 {count} 条")

    if not args.skip_daily_basic:
        _log("[3/4] 同步日线因子...")
        if codes:
            count = 0
            for code in codes:
                count += sync_daily_basic(ts_code=code, years=args.years)
        else:
            count = sync_daily_basic(years=args.years)
        results["daily_basic"] = count
        _log(f"      完成，共 {count} 条")

    if not args.skip_fina:
        _log("[4/4] 同步财务指标...")
        if codes:
            count = 0
            for code in codes:
                count += sync_fina_indicator(ts_code=code, years=args.years)
        else:
            count = sync_fina_indicator(years=args.years)
        results["fina_indicator"] = count
        _log(f"      完成，共 {count} 条")

    if not args.skip_sector_moneyflow:
        sector_types = [s.strip().lower() for s in args.sector_types.split(",") if s.strip()]
        for sector_type in sector_types:
            _log(f"[5] 同步 {sector_type} 板块资金流...")
            count = sync_sector_moneyflow(sector_type=sector_type)
            results[f"sector_moneyflow_{sector_type}"] = count
            _log(f"      完成，共 {count} 条")

    _log("\n同步结果：")
    for key, value in results.items():
        _log(f"  {key}: {value}")


if __name__ == "__main__":
    main()
