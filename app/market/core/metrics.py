# -*- coding: utf-8 -*-
"""指标计算层（薄 re-export 层，实际逻辑拆分到子模块）

子模块：
  utils.py       公共工具（rolling_pctile）
  congestion.py  拥挤度（单日/批量计算）
  market.py      大盘相关（换手率/快照/涨跌走势/板块占比/板块走势/资金流入/集中度/综合信号）
  industry.py    行业相关（行业拥挤度排名/走势/资金流入）
  breadth.py     市场广度（上涨占比/MA60/NH-NL）
  margin_mod.py  融资余额
  review.py      每日复盘
"""

from .utils import rolling_pctile
from .congestion import calc_market_congestion, batch_calc_market_congestion
from .market import (
    get_board_shares, get_board_amounts, get_board_flow, get_board_congestion_trend,
    get_market_overview, get_daily_snapshot, get_market_signals,
    get_updn_trend,
    _load_market_daily, _load_conc_daily,
)
from .industry import get_industry_crowding, get_industry_trend, get_industry_flow
from .breadth import get_breadth, _compute_breadth
from .margin_mod import get_margin_trend
from .review import get_daily_review
