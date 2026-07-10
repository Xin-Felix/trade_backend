#!/usr/bin/env python3
"""全市场分时K线采集脚本（在宿主机运行）。

用法：
    python scripts/sync_intraday.py              # 采集今天
    python scripts/sync_intraday.py 2026-07-10   # 指定日期

注意：此脚本需要在宿主机运行（Docker内因网络问题无法访问东方财富）。
需要能连接到 PostgreSQL 数据库（通过 127.0.0.1:5432）。
"""
import sys
import os
import time

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date


def main():
    trade_date = None
    if len(sys.argv) > 1:
        trade_date = date.fromisoformat(sys.argv[1])

    if trade_date is None:
        trade_date = date.today()

    print(f"=" * 60)
    print(f"  全市场分时K线采集")
    print(f"  日期: {trade_date}")
    print(f"  数据源: 东方财富 (直连，绕过代理)")
    print(f"=" * 60)

    from app.analytics.intraday_sync import sync_all_intraday
    result = sync_all_intraday(trade_date=trade_date)

    print(f"\n完成!")
    print(f"  股票数: {result['total_stocks']}")
    print(f"  数据条数: {result['total_records']}")
    print(f"  耗时: {result['elapsed']}s")


if __name__ == "__main__":
    main()
