# -*- coding: utf-8 -*-
"""市场广度（上涨家数占比 / 站上MA60占比 / 新高新低）"""

import os
import pandas as pd

from .config import BREADTH_FILE
from .datasource import list_cached_daily_dates
from . import database as db

# ==================== 市场广度（上涨家数占比 / 站上MA60占比 / 新高新低） ====================
#
# 价格类指标一律用 收盘价 × 复权因子（后复权），否则除权日产生假信号（文档·注意事项7）。

BREADTH_VERSION = 2   # 算法版本：复权改造后旧缓存作废


def _compute_breadth():
    """从缓存行情计算市场广度（需要 close/pct_chg + 复权因子）。
    缓存结果，daily 缓存天数、最新日期或算法版本变化时重算。
    优化：批量从 SQLite 读取数据，避免逐天 DataFrame 构建。"""
    dates = list_cached_daily_dates()
    if not dates:
        return None

    if os.path.exists(BREADTH_FILE):
        try:
            cache = pd.read_pickle(BREADTH_FILE)
            meta = cache.attrs.get('meta', {})
            if (meta.get('n_days') == len(dates) and meta.get('max_date') == dates[-1]
                    and meta.get('ver') == BREADTH_VERSION):
                return cache
        except Exception:
            pass

    # 批量读取所有数据（单次 SQL JOIN，仅取需要的字段）
    all_df = db.read_sql(
        "SELECT d.date, d.ts_code, d.close, d.pct_chg, a.adj_factor "
        "FROM daily d LEFT JOIN adj_factor a ON d.date = a.date AND d.ts_code = a.ts_code "
        "WHERE d.date IN (SELECT date FROM cached_dates WHERE has_daily=1) "
        "ORDER BY d.ts_code, d.date"
    )

    if all_df.empty:
        return None

    all_df['adj_factor'] = all_df['adj_factor'].fillna(1.0)
    all_df['adj_close'] = all_df['close'] * all_df['adj_factor']

    g_close = all_df.groupby('ts_code')['adj_close']
    # 60 日均线（后复权）
    all_df['ma60'] = g_close.transform(lambda s: s.rolling(60, min_periods=40).mean())
    # 250 日新高/新低（后复权，文档口径；缓存不足时 min_periods 兜底）
    all_df['hh'] = g_close.transform(lambda s: s.rolling(250, min_periods=60).max())
    all_df['ll'] = g_close.transform(lambda s: s.rolling(250, min_periods=60).min())

    def _day_agg(g):
        up = (g['pct_chg'] > 0).mean()
        med = g['pct_chg'].median()
        ma_valid = g['ma60'].notna()
        above60 = (g.loc[ma_valid, 'adj_close'] > g.loc[ma_valid, 'ma60']).mean() if ma_valid.any() else None
        hh_valid = g['hh'].notna()
        nh = int((g.loc[hh_valid, 'adj_close'] >= g.loc[hh_valid, 'hh']).sum()) if hh_valid.any() else 0
        nl = int((g.loc[hh_valid, 'adj_close'] <= g.loc[hh_valid, 'll']).sum()) if hh_valid.any() else 0
        return pd.Series({'up_ratio': up, 'chg_median': med, 'above60': above60, 'nh': nh, 'nl': nl})

    breadth = all_df.groupby('date').apply(_day_agg, include_groups=False).reset_index()
    breadth = breadth.sort_values('date').reset_index(drop=True)
    breadth['up_ratio_ma10'] = breadth['up_ratio'].rolling(10, min_periods=3).mean()
    breadth['chg_median_ma10'] = breadth['chg_median'].rolling(10, min_periods=3).mean()
    breadth['nhnl'] = breadth['nh'] - breadth['nl']
    breadth.attrs['meta'] = {'n_days': len(dates), 'max_date': dates[-1], 'ver': BREADTH_VERSION}
    try:
        breadth.to_pickle(BREADTH_FILE)
    except Exception:
        pass
    return breadth


def get_breadth():
    """市场广度走势数据（图表用）"""
    breadth = _compute_breadth()
    if breadth is None or breadth.empty:
        return {'dates': [], 'up_ratio10': [], 'above60': [], 'nhnl': [], 'chg_med10': []}
    dates = breadth['date'].tolist()
    return {
        'dates': dates,
        'up_ratio10': [round(v * 100, 1) if pd.notna(v) else None for v in breadth['up_ratio_ma10']],
        'above60': [round(v * 100, 1) if pd.notna(v) else None for v in breadth['above60']],
        'nhnl': [int(v) for v in breadth['nhnl']],
        'chg_med10': [round(float(v), 2) if pd.notna(v) else None for v in breadth['chg_median_ma10']],
    }


