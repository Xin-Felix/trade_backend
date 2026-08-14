# -*- coding: utf-8 -*-
"""选股筛选器 + 个股K线数据"""

import time
import pandas as pd

from .datasource import get_tushare_pro, get_stock_info, get_daily_df, get_daily_basic_df, list_cached_daily_dates
from .config import get_board, REQUEST_INTERVAL
from . import database as db


def screen_stocks(trade_date=None, board=None, industry=None,
                  pct_min=None, pct_max=None,
                  amount_min=None, amount_max=None,
                  exclude_st=True, search=None, limit=200):
    """根据条件筛选股票。
    参数：
      trade_date: YYYYMMDD，默认最新
      board: 板块名（沪深主板/创业板/科创板/北交所），None=全部
      industry: 行业名，None=全部
      pct_min/pct_max: 涨跌幅范围 (%)
      amount_min/amount_max: 成交额范围 (亿元)
      exclude_st: 排除ST
      limit: 最多返回条数
    返回 {'date': str, 'total': int, 'stocks': [{...}]}
    """
    if trade_date is None:
        dates = list_cached_daily_dates()
        if not dates:
            return {'date': None, 'total': 0, 'stocks': []}
        trade_date = dates[-1]
    else:
        # 如果指定的日期没有数据，回退到最近有数据的日期
        df_check, _ = get_daily_df(trade_date)
        if df_check is None or df_check.empty:
            dates = list_cached_daily_dates()
            if not dates:
                return {'date': trade_date, 'total': 0, 'stocks': []}
            # 找到 <= trade_date 的最近日期
            valid = [d for d in dates if d <= trade_date]
            trade_date = valid[-1] if valid else dates[-1]

    df, _ = get_daily_df(trade_date)
    if df is None or df.empty:
        return {'date': trade_date, 'total': 0, 'stocks': []}

    df = df.copy()
    df['board'] = df['ts_code'].apply(get_board)

    # 股票信息
    info = get_stock_info()
    if not info.empty:
        name_map = dict(zip(info['ts_code'], info['name']))
        ind_map = dict(zip(info['ts_code'], info['industry']))
        df['name'] = df['ts_code'].map(name_map).fillna('')
        df['industry'] = df['ts_code'].map(ind_map).fillna('')
    else:
        df['name'] = df['ts_code'].str.split('.').str[0]
        df['industry'] = ''

    # 排除ST
    if exclude_st:
        df = df[~df['name'].str.contains('ST', na=False)]

    # 搜索（名称或代码模糊匹配）
    if search:
        search_lower = search.strip()
        mask = df['ts_code'].str.contains(search_lower, case=False, na=False) | \
               df['name'].str.contains(search_lower, case=False, na=False)
        df = df[mask]

    # 板块筛选
    if board:
        df = df[df['board'] == board]

    # 行业筛选
    if industry:
        df = df[df['industry'] == industry]

    # 涨跌幅筛选
    if pct_min is not None:
        df = df[df['pct_chg'] >= pct_min]
    if pct_max is not None:
        df = df[df['pct_chg'] <= pct_max]

    # 成交额筛选（亿元）
    df['amount_yi'] = df['amount_yuan'] / 1e8
    if amount_min is not None:
        df = df[df['amount_yi'] >= amount_min]
    if amount_max is not None:
        df = df[df['amount_yi'] <= amount_max]

    total = len(df)

    # 按成交额降序
    df = df.nlargest(limit, 'amount_yuan')

    stocks = []
    for _, row in df.iterrows():
        pct = row['pct_chg']
        amt = row['amount_yi']
        cl = row['close']
        stocks.append({
            'ts_code': row['ts_code'],
            'code': row['ts_code'].split('.')[0],
            'name': str(row.get('name', '') or ''),
            'industry': str(row.get('industry', '') or ''),
            'board': row['board'],
            'close': round(float(cl), 2) if pd.notna(cl) else 0,
            'pct_chg': round(float(pct), 2) if pd.notna(pct) else 0,
            'amount_yi': round(float(amt), 2) if pd.notna(amt) else 0,
        })

    return {'date': trade_date, 'total': total, 'stocks': stocks}


def get_stock_kline(ts_code, period='daily', days=120):
    """获取个股K线数据。
    period: 'daily'|'weekly'|'monthly'|'60min'|'30min'|'15min'|'5min'
    days: 获取天数
    返回 {'ts_code': str, 'period': str, 'data': [{date,open,high,low,close,vol,pct_chg}...]}
    """
    try:
        # 分钟级别用 akshare（新浪源，无限频）
        if period in ('60min', '30min', '15min', '5min', '1min'):
            return _get_minute_kline(ts_code, period)

        # 日/周/月K用 tushare + SQLite 缓存
        return _get_period_kline(ts_code, period, days)
    except Exception as e:
        return {'ts_code': ts_code, 'period': period, 'data': [], 'error': str(e)}


def _get_minute_kline(ts_code, period):
    """从 akshare 获取分钟K线（新浪源）"""
    import akshare as ak

    # ts_code 格式: 300308.SZ → sz300308
    code = ts_code.split('.')[0]
    suffix = ts_code.split('.')[1].lower() if '.' in ts_code else 'sz'
    symbol = suffix + code

    period_map = {'60min': '60', '30min': '30', '15min': '15', '5min': '5', '1min': '1'}
    freq = period_map.get(period, '60')

    df = ak.stock_zh_a_minute(symbol=symbol, period=freq)
    if df is None or df.empty:
        return {'ts_code': ts_code, 'period': period, 'data': []}

    # 分时(1min)只取当天数据，其他取最近5天
    if period == '1min':
        # 取最后一个交易日的数据
        last_date = str(df['day'].iloc[-1])[:10]
        df = df[df['day'].astype(str).str.startswith(last_date)]
    else:
        bars_per_day = int(240 / int(freq))
        df = df.tail(bars_per_day * 5)

    data = []
    for _, row in df.iterrows():
        day_str = str(row['day'])
        # 分时显示 "HH:MM"，其他显示 "MM-DD HH:MM"
        if period == '1min':
            date_label = day_str[11:16] if len(day_str) >= 16 else day_str
        else:
            date_label = day_str[5:16] if len(day_str) >= 16 else day_str
        data.append({
            'date': date_label,
            'open': round(float(row['open']), 2),
            'high': round(float(row['high']), 2),
            'low': round(float(row['low']), 2),
            'close': round(float(row['close']), 2),
            'vol': round(float(row['volume']) / 100, 0),  # 股→手
            'pct_chg': 0,
        })
    return {'ts_code': ts_code, 'period': period, 'data': data}


def _get_period_kline(ts_code, period, days):
    """从 tushare 获取日/周/月K线，日K缓存到 SQLite"""
    import datetime
    pro = get_tushare_pro()
    start = (datetime.datetime.now() - datetime.timedelta(days=int(days * 2))).strftime('%Y%m%d')

    # 日K：先查 SQLite 缓存
    if period == 'daily':
        cached = _read_stock_daily_cache(ts_code, start)
        if cached is not None and len(cached) >= days * 0.8:
            return {'ts_code': ts_code, 'period': period, 'data': cached[-days:]}

    time.sleep(REQUEST_INTERVAL)
    if period == 'weekly':
        df = pro.weekly(ts_code=ts_code, start_date=start, adj='qfq',
                       fields='trade_date,open,high,low,close,vol,pct_chg')
    elif period == 'monthly':
        df = pro.monthly(ts_code=ts_code, start_date=start, adj='qfq',
                        fields='trade_date,open,high,low,close,vol,pct_chg')
    else:
        # 日K用 pro_bar 获取前复权数据
        import tushare as ts
        df = ts.pro_bar(ts_code=ts_code, start_date=start, adj='qfq')

    if df is None or df.empty:
        return {'ts_code': ts_code, 'period': period, 'data': []}

    for col in ('open', 'high', 'low', 'close', 'vol', 'pct_chg'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close']).sort_values('trade_date').reset_index(drop=True)

    data = []
    for _, row in df.iterrows():
        data.append({
            'date': row['trade_date'],
            'open': round(float(row['open']), 2),
            'high': round(float(row['high']), 2),
            'low': round(float(row['low']), 2),
            'close': round(float(row['close']), 2),
            'vol': round(float(row['vol']), 0),
            'pct_chg': round(float(row['pct_chg']), 2) if pd.notna(row['pct_chg']) else 0,
        })

    # 日K写入缓存
    if period == 'daily' and data:
        _write_stock_daily_cache(ts_code, data)

    return {'ts_code': ts_code, 'period': period, 'data': data[-days:]}


def _read_stock_daily_cache(ts_code, start_date):
    """读取个股日K缓存（stock_kline 表由 database.py 统一建）"""
    rows = db.read_stock_kline(ts_code, start_date)
    return rows or None


def _write_stock_daily_cache(ts_code, data):
    """写入个股日K缓存"""
    db.write_stock_kline(ts_code, data)


def get_all_industries():
    """返回所有行业列表"""
    info = get_stock_info()
    if info.empty:
        return []
    return sorted(info['industry'].dropna().unique().tolist())
