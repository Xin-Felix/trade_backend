# -*- coding: utf-8 -*-
"""行业相关指标：行业拥挤度排名/走势/资金流入"""

import os
import pandas as pd

from .config import INDUSTRY_DAILY_FILE, get_board
from .datasource import (
    get_daily_df, get_daily_basic_df, get_stock_info,
    list_cached_daily_dates,
)
from . import database as db
from .utils import rolling_pctile

# ==================== 行业拥挤度排名 ====================

def _load_industry_daily():
    """增量汇总每日各行业成交额/流通市值：DataFrame(date, industry, amt_w, mv_w)
    优化：对缺失日期使用批量 SQL + Python 分组。"""
    if os.path.exists(INDUSTRY_DAILY_FILE):
        try:
            df = pd.read_pickle(INDUSTRY_DAILY_FILE)
        except Exception:
            df = pd.DataFrame(columns=['date', 'industry', 'amt_w', 'mv_w'])
    else:
        df = pd.DataFrame(columns=['date', 'industry', 'amt_w', 'mv_w'])

    have = set(df['date'].unique()) if not df.empty else set()
    info = get_stock_info()
    if info.empty:
        return df
    ind_map = dict(zip(info['ts_code'], info['industry']))

    all_dates = list_cached_daily_dates()
    missing = [d for d in all_dates if d not in have]

    if missing:
        conn = db.get_conn()
        batch_size = 200  # 行业计算稍复杂，用较小批次
        new_rows = []
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = f"""
                SELECT d.date, d.ts_code, d.amount_yuan, b.circ_mv
                FROM daily d
                INNER JOIN daily_basic b ON d.date = b.date AND d.ts_code = b.ts_code
                WHERE d.date IN ({placeholders})
            """
            rows = conn.execute(sql, batch).fetchall()
            # 按 (date, industry) 聚合
            from collections import defaultdict
            agg = defaultdict(lambda: {'amt': 0.0, 'mv': 0.0})
            for date_str, ts_code, amount_yuan, circ_mv in rows:
                industry = ind_map.get(ts_code)
                if not industry:
                    continue
                key = (date_str, industry)
                agg[key]['amt'] += (amount_yuan or 0) / 1e4
                agg[key]['mv'] += (circ_mv or 0)
            for (date_str, industry), vals in agg.items():
                new_rows.append({'date': date_str, 'industry': industry,
                                 'amt_w': vals['amt'], 'mv_w': vals['mv']})

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True)
            try:
                df.to_pickle(INDUSTRY_DAILY_FILE)
            except Exception:
                pass
    return df


def get_industry_crowding(trade_date=None):
    """行业拥挤度排名：成交额占比 + 占比分位 + 换手率 + 换手率分位。
    trade_date 为 YYYYMMDD，缺省取最近有数据的一天。"""
    df = _load_industry_daily()
    if df.empty:
        return {'date': None, 'n_days': 0, 'rows': []}

    dates = sorted(df['date'].unique())
    if trade_date and trade_date in dates:
        target = trade_date
    elif trade_date:
        earlier = [d for d in dates if d <= trade_date]
        target = earlier[-1] if earlier else dates[-1]
    else:
        target = dates[-1]

    mkt_amt = df.groupby('date')['amt_w'].sum()
    records = []
    for ind, g in df.groupby('industry'):
        g = g.sort_values('date')
        g_dates = g['date'].tolist()
        shares = [(a / mkt_amt[d]) if mkt_amt[d] > 0 else 0.0
                  for a, d in zip(g['amt_w'], g_dates)]
        turnovers = [(a / m) if m > 0 else 0.0
                     for a, m in zip(g['amt_w'], g['mv_w'])]
        share_pcts = rolling_pctile(shares)
        turnover_pcts = rolling_pctile(turnovers)
        if target in g_dates:
            i = g_dates.index(target)
            records.append({
                'industry': ind,
                'share': shares[i],
                'share_pct': share_pcts[i],
                'turnover': turnovers[i],
                'turnover_pct': turnover_pcts[i],
            })

    records.sort(key=lambda r: (r['share_pct'] is not None, r['share_pct'] or 0), reverse=True)
    return {'date': target, 'n_days': len(dates), 'rows': records}


def get_industry_trend(industries=None):
    """指定行业的拥挤度走势（折线图用）：成交额占比% + 占比分位%。
    industries 为空时只返回行业列表和日期轴。
    返回 {'dates', 'industries', 'series': {行业: {'share': [], 'share_pct': []}}}"""
    df = _load_industry_daily()
    if df.empty:
        return {'dates': [], 'industries': [], 'series': {}}

    dates = sorted(df['date'].unique())
    mkt_amt = df.groupby('date')['amt_w'].sum()
    all_industries = sorted(df['industry'].unique().tolist())

    out = {}
    for ind in (industries or []):
        g = df[df['industry'] == ind].sort_values('date')
        if g.empty:
            continue
        g_dates = g['date'].tolist()
        shares = [(a / mkt_amt[d]) if mkt_amt[d] > 0 else 0.0
                  for a, d in zip(g['amt_w'], g_dates)]
        pcts = rolling_pctile(shares)
        share_map = dict(zip(g_dates, shares))
        pct_map = dict(zip(g_dates, pcts))
        out[ind] = {
            'share': [round(share_map[d] * 100, 2) if d in share_map else None for d in dates],
            'share_pct': [round(pct_map[d] * 100, 1)
                          if d in pct_map and pct_map[d] is not None else None for d in dates],
        }
    return {'dates': dates, 'industries': all_industries, 'series': out}


# ==================== 行业资金流入（累计净流入趋势） ====================

def get_industry_flow(industries=None, top_n=10):
    """行业每日成交额累计净流入趋势（从0开始）。
    算法：与 get_board_flow 相同，但按 tushare 行业分类。
    industries=None 时自动取最近一天成交额最高的 top_n 个行业。
    返回 {'dates': [...], 'industries': [...], 'all_industries': [...],
           'series': {行业: [累计值...]}}"""
    ind_df = _load_industry_daily()
    if ind_df.empty:
        return {'dates': [], 'industries': [], 'all_industries': [], 'series': {}}

    dates = sorted(ind_df['date'].unique())
    all_industries = sorted(ind_df['industry'].unique().tolist())

    # 自动选择：最近一天成交额前 top_n 的行业
    if not industries:
        last_date = dates[-1]
        last_day = ind_df[ind_df['date'] == last_date].copy()
        last_day['amt_w'] = pd.to_numeric(last_day['amt_w'], errors='coerce')
        last_day = last_day.nlargest(top_n, 'amt_w')
        industries = last_day['industry'].tolist()

    result_series = {}
    for ind in industries:
        g = ind_df[ind_df['industry'] == ind].sort_values('date')
        if g.empty:
            continue
        # 构建每日成交额映射（万元→亿元）
        g_amt = pd.to_numeric(g['amt_w'], errors='coerce').fillna(0)
        amt_map = dict(zip(g['date'], g_amt / 1e4))
        # 对齐到全局日期轴
        daily_vals = [amt_map.get(d, 0.0) for d in dates]
        # 累计环比增量（从0开始）
        cum = 0.0
        cum_series = [0.0]
        for i in range(1, len(daily_vals)):
            cum += (daily_vals[i] - daily_vals[i - 1])
            cum_series.append(round(cum, 2))
        result_series[ind] = cum_series

    return {
        'dates': dates,
        'industries': industries,
        'all_industries': all_industries,
        'series': result_series,
    }


# ==================== 板块拥挤度走势（各板块成交额占比 + 分位） ====================
