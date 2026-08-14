# -*- coding: utf-8 -*-
"""趋势信号模块：将 ETF 期权趋势策略的信号层应用到主要指数上。

信号三层结构：
  第1层 方向闸门（周线）：收盘价相对周EMA20 + 周EMA10方向
  第2层 趋势强度（日线）：ADX(14)>30 + DI差>10 + ATR比率>0.8
  第3层 结构确认（日线）：EMA10/EMA20/EMA50 排列

输出：每个标的的当前信号状态 + 历史走势图数据
"""

import os
import datetime
import time
import pandas as pd
import numpy as np

from .datasource import get_tushare_pro
from .config import CACHE_DIR

# 跟踪的标的（使用 tushare 指数代码）
TREND_TARGETS = {
    '沪深300': '000300.SH',
    '中证500': '000905.SH',
    '创业板指': '399006.SZ',
    '上证50': '000016.SH',
    '科创50': '000688.SH',
}

TREND_CACHE_DIR = os.path.join(CACHE_DIR, 'trend')
os.makedirs(TREND_CACHE_DIR, exist_ok=True)


def _get_index_data(name, ts_code, days=500):
    """获取指数日线数据，优先读本地缓存，落后时增量更新。
    返回 DataFrame(trade_date, open, high, low, close) 升序。"""
    cache_file = os.path.join(TREND_CACHE_DIR, f'{ts_code.replace(".", "_")}.pkl')

    cached = None
    if os.path.exists(cache_file):
        try:
            cached = pd.read_pickle(cache_file)
        except Exception:
            cached = None

    # 判断是否需要更新：缓存文件修改时间超过 4 小时则刷新
    need_refresh = cached is None or cached.empty or len(cached) < 60
    if not need_refresh:
        mtime = os.path.getmtime(cache_file)
        age_hours = (time.time() - mtime) / 3600
        need_refresh = age_hours > 4

    if not need_refresh and cached is not None:
        return cached.tail(days).reset_index(drop=True)

    # 从 tushare 拉取
    try:
        pro = get_tushare_pro()
        start = (datetime.datetime.now() - datetime.timedelta(days=int(days * 1.6))).strftime('%Y%m%d')
        df = pro.index_daily(ts_code=ts_code, start_date=start,
                             fields='trade_date,open,high,low,close')
        if df is None or df.empty:
            return cached.tail(days).reset_index(drop=True) if cached is not None and not cached.empty else None
        for col in ('open', 'high', 'low', 'close'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna().sort_values('trade_date').reset_index(drop=True)
        # 保存缓存
        try:
            df.to_pickle(cache_file)
        except Exception:
            pass
        return df.tail(days).reset_index(drop=True)
    except Exception:
        if cached is not None and not cached.empty:
            return cached.tail(days).reset_index(drop=True)
        return None


# ==================== 技术指标计算 ====================


def _ema(series, period):
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def _adx(high, low, close, period=14):
    """计算 ADX、+DI、-DI"""
    n = len(close)
    if n < period * 2:
        return pd.Series([None] * n), pd.Series([None] * n), pd.Series([None] * n)

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    # Wilder smoothing
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)

    # DX → ADX
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx, plus_di, minus_di


def _atr(high, low, close, period=14):
    """ATR"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def _resample_weekly(df):
    """日线转周线（按自然周聚合）"""
    df = df.copy()
    df['trade_date_dt'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date_dt')
    weekly = df.resample('W-FRI').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'trade_date': 'last',
    }).dropna(subset=['close'])
    return weekly.reset_index(drop=True)


# ==================== 信号计算 ====================


def _compute_signals(name, ts_code, days=250):
    """计算单个标的的趋势信号 + 走势数据。"""
    df = _get_index_data(name, ts_code, days=max(days, 400))
    if df is None or len(df) < 100:
        return None

    # === 日线指标 ===
    close = df['close']
    high = df['high']
    low = df['low']

    ema10 = _ema(close, 10)
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    adx_s, plus_di, minus_di = _adx(high, low, close, 14)
    atr_s = _atr(high, low, close, 14)
    atr_ratio_s = (atr_s / close) / (atr_s / close).rolling(250, min_periods=60).median()

    # === 周线闸门 ===
    weekly = _resample_weekly(df)
    if len(weekly) < 25:
        w_gate = 'neutral'
    else:
        w_close = weekly['close']
        w_ema20 = _ema(w_close, 20)
        w_ema10 = _ema(w_close, 10)
        last_wc = w_close.iloc[-1]
        last_we20 = w_ema20.iloc[-1]
        ema10_rising = w_ema10.iloc[-1] > w_ema10.iloc[-2]
        ema10_falling = w_ema10.iloc[-1] < w_ema10.iloc[-2]

        if last_wc > last_we20 and ema10_rising:
            w_gate = 'long'
        elif last_wc < last_we20 and ema10_falling:
            w_gate = 'short'
        else:
            w_gate = 'neutral'

    # === 日线第2层：趋势强度 ===
    latest_adx = float(adx_s.iloc[-1]) if pd.notna(adx_s.iloc[-1]) else 0
    latest_di_spread = abs(float(plus_di.iloc[-1]) - float(minus_di.iloc[-1])) if pd.notna(plus_di.iloc[-1]) else 0
    latest_atr_ratio = float(atr_ratio_s.iloc[-1]) if pd.notna(atr_ratio_s.iloc[-1]) else 0

    trend_strong = latest_adx > 30 and latest_di_spread > 10 and latest_atr_ratio > 0.8

    # === 日线第3层：结构确认 ===
    lc = float(close.iloc[-1])
    le10 = float(ema10.iloc[-1])
    le20 = float(ema20.iloc[-1])
    le50 = float(ema50.iloc[-1])

    if lc > le50 and le10 > le20:
        structure = 'long'
    elif lc < le50 and le10 < le20:
        structure = 'short'
    else:
        structure = 'neutral'

    # === 综合信号 ===
    strength = 0
    if w_gate != 'neutral':
        strength += 1
    if trend_strong:
        strength += 1
    if structure != 'neutral':
        strength += 1

    if w_gate == 'long' and trend_strong and structure == 'long':
        signal = 'long'
    elif w_gate == 'short' and trend_strong and structure == 'short':
        signal = 'short'
    else:
        signal = 'neutral'

    # === 历史信号序列 ===
    signal_series = []
    for i in range(len(df)):
        if i < 50:
            signal_series.append(0)
            continue
        c = float(close.iloc[i])
        e10 = float(ema10.iloc[i])
        e20 = float(ema20.iloc[i])
        e50 = float(ema50.iloc[i])
        adx_v = float(adx_s.iloc[i]) if pd.notna(adx_s.iloc[i]) else 0
        if c > e50 and e10 > e20 and adx_v > 30:
            signal_series.append(1)
        elif c < e50 and e10 < e20 and adx_v > 30:
            signal_series.append(-1)
        else:
            signal_series.append(0)

    # 截取最近展示天数
    show_n = min(len(df), days)
    idx_start = len(df) - show_n

    return {
        'name': name,
        'ts_code': ts_code,
        'signal': signal,
        'gate': w_gate,
        'adx': round(latest_adx, 1),
        'di_spread': round(latest_di_spread, 1),
        'atr_ratio': round(latest_atr_ratio, 2),
        'structure': structure,
        'strength': strength,
        'latest_close': round(lc, 2),
        'latest_date': df['trade_date'].iloc[-1],
        # 走势数据
        'dates': df['trade_date'].iloc[idx_start:].tolist(),
        'closes': [round(float(v), 2) for v in close.iloc[idx_start:].tolist()],
        'ema10': [round(float(v), 2) for v in ema10.iloc[idx_start:].tolist()],
        'ema20': [round(float(v), 2) for v in ema20.iloc[idx_start:].tolist()],
        'ema50': [round(float(v), 2) for v in ema50.iloc[idx_start:].tolist()],
        'adx_series': [round(float(v), 1) if pd.notna(v) else None for v in adx_s.iloc[idx_start:].tolist()],
        'signal_series': signal_series[idx_start:],
    }


# ==================== 对外接口 ====================


def get_trend_overview():
    """获取所有跟踪标的的趋势信号概览 + 走势数据。
    使用线程池并发获取（2个并发，避免 tushare 限流）。
    返回 {'targets': [{ ... }, ...]}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []

    def _task(item):
        name, ts_code = item
        return _compute_signals(name, ts_code, days=250)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_task, item): item[0]
                   for item in TREND_TARGETS.items()}
        for future in as_completed(futures):
            try:
                r = future.result()
                if r:
                    results.append(r)
            except Exception:
                pass

    # 按 TREND_TARGETS 定义顺序排列
    order = list(TREND_TARGETS.keys())
    results.sort(key=lambda x: order.index(x['name']) if x['name'] in order else 99)
    return {'targets': results}
