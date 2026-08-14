# -*- coding: utf-8 -*-
"""数据库适配层 redirect

core/ 下的模块通过 `from . import database as db` 引用本文件。
实际实现在 app/market/database.py，这里直接从那里导入所有函数。
"""

from app.market.database import *  # noqa: F401,F403
from app.market.database import (
    get_conn, get_db_info, get_cache_info, backend_info, init_db,
    read_sql, upsert_rows, upsert_df,
    list_daily_dates, has_daily, read_daily, write_daily,
    has_basic, read_basic, write_basic,
    has_adj, read_adj, write_adj,
    read_margin_all, write_margin_batch,
    read_summary, write_summary,
    read_stock_kline, write_stock_kline,
    read_option_contracts, write_option_contracts, count_option_contracts_by_underlying,
    read_option_quotes, write_option_quotes,
    read_option_etf_quote, write_option_etf_quotes,
    read_option_signals, write_option_signals,
    read_congestion_history, write_congestion_history, clear_congestion_history,
    option_contracts_fresh,
)
