#!/usr/bin/env python3
"""全市场分时K线采集脚本。

用法：
    python scripts/sync_intraday.py              # 采集最近5个交易日
    python scripts/sync_intraday.py --days 3     # 采集最近3个交易日
    python scripts/sync_intraday.py --days 1     # 只采集最近1个交易日

数据源：Tushare 代理（stk_mins 接口，4 线程并发）。
只保留最近5个交易日的数据，更早的自动清理。
"""
import sys
import os
import argparse

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="全市场分时K线采集")
    parser.add_argument("--days", type=int, default=5, help="采集最近几个交易日（默认5）")
    args = parser.parse_args()

    from app.analytics.intraday_sync import sync_all_intraday
    result = sync_all_intraday(days=args.days)

    print(f"\n完成!")
    print(f"  股票数: {result['total_stocks']}")
    print(f"  数据条数: {result['total_records']}")
    print(f"  耗时: {result['elapsed']}s")


if __name__ == "__main__":
    main()
