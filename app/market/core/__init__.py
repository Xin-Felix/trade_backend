# -*- coding: utf-8 -*-
"""市场拥挤度核心计算包

从 market_congestion/core/ 搬运而来。
database.py 是适配层（redirect 到 app.market.database），
读取 trade_backend 已有的 stock_daily / stock_daily_basic 等表。
"""

from .config import *  # noqa: F401,F403
from .config import get_board
from .datasource import (
    get_tushare_pro, get_daily_df, get_daily_basic_df, get_index_daily,
    list_cached_daily_dates, get_cache_info, clear_cache,
    get_stock_info, get_stock_names, fetch_trade_dates, get_trade_days_in_range,
    warm_basic_cache,
)
from .metrics import (
    calc_market_congestion, batch_calc_market_congestion,
    rolling_pctile, get_board_shares, get_board_amounts, get_board_flow, get_board_congestion_trend,
    get_industry_flow, get_market_overview, get_daily_snapshot,
    get_industry_crowding, get_industry_trend, get_breadth, get_market_signals,
    get_daily_review, get_margin_trend, get_updn_trend,
)
from .history import (
    load_history, save_history, save_history_batch, clear_history,
)
from .trend import get_trend_overview
from .screener import screen_stocks, get_stock_kline, get_all_industries
from .option import (
    get_option_underlyings, get_option_analysis, get_option_signals,
    get_etf_kline, get_etf_minute_kline,
    refresh_option_data, migrate_from_watcher_db,
)
