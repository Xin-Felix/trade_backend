# -*- coding: utf-8 -*-
"""拥挤度计算（单日/批量）"""

import datetime
import time

from .config import BOARD_MAP, REQUEST_INTERVAL, get_board
from .datasource import get_daily_df, get_daily_basic_df, get_stock_names, get_trade_days_in_range
from . import database as db


def _get_new_stock_codes(trade_date, days_threshold=22):
    """获取在 trade_date 之前上市不足 days_threshold 个交易日的股票代码集合。"""
    # 用预加载的首次出现日期+累计天数来快速判断
    stock_days = _get_stock_day_counts()
    new_codes = set()
    for ts_code, dates_list in stock_days.items():
        # 用二分查找该股票截至 trade_date 出现了多少天
        import bisect
        idx = bisect.bisect_right(dates_list, trade_date)
        if idx < days_threshold:
            new_codes.add(ts_code)
    return new_codes


# 全局缓存：每只股票出现的日期列表（升序）
_stock_day_counts = None


def _get_stock_day_counts():
    """一次性加载每只股票的全部出现日期（升序排列）。"""
    global _stock_day_counts
    if _stock_day_counts is not None:
        return _stock_day_counts
    conn = db.get_conn()
    rows = conn.execute("SELECT ts_code, date FROM daily ORDER BY ts_code, date").fetchall()
    from collections import defaultdict
    result = defaultdict(list)
    for ts_code, date in rows:
        result[ts_code].append(date)
    _stock_day_counts = dict(result)
    return _stock_day_counts


# 批量计算缓存
_new_stock_cache = {}


def _get_new_stock_codes_cached(trade_date, days_threshold=22):
    """带缓存的新股判断（批量计算时复用同一天的查询结果）"""
    key = (trade_date, days_threshold)
    if key not in _new_stock_cache:
        _new_stock_cache[key] = _get_new_stock_codes(trade_date, days_threshold)
    return _new_stock_cache[key]


def _compute_from_df(df, board, date_str, top_percent, with_top_stocks=True, denominator='board', exclude_new=False):
    """从当日全市场行情 DataFrame 计算拥挤度（单日/批量共用）

    denominator: 'board' = 除以所选板块总成交额（板块内部集中度）
                 'market' = 除以全市场总成交额（板块头部占全市场比重）
    """
    df = df.copy()
    df['board'] = df['ts_code'].apply(get_board)

    # 排除新股（上市不足1个月）
    if exclude_new:
        new_codes = _get_new_stock_codes_cached(date_str)
        df = df[~df['ts_code'].isin(new_codes)]
        if df.empty:
            raise RuntimeError(f"排除新股后 {date_str} 无数据")

    market_total = float(df['amount_yuan'].sum())

    target_board = BOARD_MAP.get(board)
    if target_board is not None:
        df = df[df['board'] == target_board]
        if df.empty:
            raise RuntimeError(f"该板块在 {date_str} 无数据: {board}")

    total_amount = float(df['amount_yuan'].sum())
    total_stocks = len(df)
    top_n = max(1, int(total_stocks * top_percent / 100))
    top_df = df.nlargest(top_n, 'amount_yuan')
    top_amount = float(top_df['amount_yuan'].sum())

    denom_amount = market_total if denominator == 'market' else total_amount
    congestion = top_amount / denom_amount if denom_amount > 0 else 0.0

    top_stocks = []
    if with_top_stocks:
        names = get_stock_names()
        for _, row in top_df.iterrows():
            code = row['ts_code'].split('.')[0]
            top_stocks.append({
                '代码': code,
                '名称': names.get(row['ts_code'], code),
                '板块': row['board'],
                '成交额': float(row['amount_yuan']),
            })

    now = datetime.datetime.now()
    return {
        'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date': date_str,
        'time': now.strftime('%H:%M:%S'),
        'board': board,
        'top_percent': top_percent,
        'denominator': denominator,
        'congestion': congestion,
        'congestion_pct': f"{congestion * 100:.2f}%",
        'top_n': top_n,
        'total_stocks': total_stocks,
        'top_amount': top_amount,
        'top_amount_yi': top_amount / 1e8,
        'total_amount': total_amount,
        'total_amount_yi': total_amount / 1e8,
        'market_amount_yi': market_total / 1e8,
        'top_stocks': top_stocks,
    }


def _find_latest_trade_date():
    """往前最多找 10 天，返回最近一个有行情的交易日"""
    now = datetime.datetime.now()
    for offset in range(0, 10):
        date_str = (now - datetime.timedelta(days=offset)).strftime('%Y%m%d')
        try:
            df, _ = get_daily_df(date_str)
            if df is not None and not df.empty:
                return date_str
        except Exception:
            continue
    return None


def calc_market_congestion(board='全部A股', trade_date=None, top_percent=5, denominator='board', exclude_new=False):
    """单日拥挤度计算"""
    actual_date = trade_date if trade_date else _find_latest_trade_date()
    if actual_date is None:
        raise RuntimeError("无法获取数据")

    df, from_cache = get_daily_df(actual_date)
    if df is None or df.empty:
        raise RuntimeError(f"无法获取 {actual_date} 的数据")

    result = _compute_from_df(df, board, actual_date, top_percent,
                              with_top_stocks=True, denominator=denominator,
                              exclude_new=exclude_new)
    result['from_cache'] = from_cache
    try:
        get_daily_basic_df(actual_date)
    except Exception:
        pass
    return result


def batch_calc_market_congestion(board='全部A股', top_percent=5,
                                 start_date=None, end_date=None,
                                 denominator='board',
                                 exclude_new=False,
                                 progress_callback=None):
    """批量计算日期范围内每个交易日的拥挤度"""
    global _new_stock_cache
    _new_stock_cache = {}  # 清除缓存
    now = datetime.datetime.now()
    if end_date is None:
        end_date = now.strftime('%Y%m%d')
    if start_date is None:
        start_date = (now - datetime.timedelta(days=60)).strftime('%Y%m%d')

    target_days = get_trade_days_in_range(start_date, end_date)
    if not target_days:
        raise RuntimeError("所选日期范围内无交易日")

    results = []
    total = len(target_days)

    for i, date_str in enumerate(target_days):
        try:
            df, from_cache = get_daily_df(date_str)
            if df is None or df.empty:
                if progress_callback:
                    progress_callback(i + 1, total, date_str, '无数据', False)
                continue

            result = _compute_from_df(df, board, date_str, top_percent,
                                      with_top_stocks=False, denominator=denominator,
                                      exclude_new=exclude_new)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total, date_str, result['congestion_pct'], from_cache)

            basic_from_cache = True
            try:
                _, basic_from_cache = get_daily_basic_df(date_str)
            except Exception:
                pass

            if not from_cache or not basic_from_cache:
                time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, total, date_str, f"错误: {str(e)[:30]}", False)
            continue

    return results
