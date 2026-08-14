# -*- coding: utf-8 -*-
"""数据源层：tushare 接口、SQLite 缓存、缓存管理、股票信息、交易日。
v7: 主存储改为 SQLite（core/database.py），保留 pkl 文件读取作为迁移兼容。"""

import os
import json
import datetime
import time

import pandas as pd

from .config import (
    CACHE_DIR, DAILY_CACHE_DIR, BASIC_CACHE_DIR, ADJ_CACHE_DIR,
    CACHE_KEEP_DAYS, REQUEST_INTERVAL, RETRY_TIMES, RETRY_DELAY,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE, BASIC_UPDATE_HOUR, WARM_DAYS,
    TUSHARE_TOKEN, STOCK_INFO_FILE, SHARES_CACHE_FILE, MARKET_DAILY_FILE,
    INDUSTRY_DAILY_FILE, INDEX_DAILY_FILE, BREADTH_FILE, CONC_DAILY_FILE,
    INDEX_TS_CODE,
)
from . import database as db

# ==================== tushare ====================

_pro = None


def get_tushare_pro():
    """初始化 tushare pro_api（单例）"""
    global _pro
    if _pro is not None:
        return _pro
    try:
        import tushare as ts
    except ImportError:
        raise RuntimeError("未安装 tushare，请先运行: pip install tushare")
    ts.set_token(TUSHARE_TOKEN)
    _pro = ts.pro_api(TUSHARE_TOKEN)
    return _pro


def _fetch_daily(date_str):
    """带重试地获取某日全市场行情"""
    pro = get_tushare_pro()
    last_err = None
    for attempt in range(RETRY_TIMES):
        try:
            return pro.daily(trade_date=date_str)
        except Exception as e:
            last_err = e
            if attempt < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    raise RuntimeError(f"获取 {date_str} 行情失败（已重试{RETRY_TIMES}次）: {last_err}")


# ==================== 按日行情缓存（SQLite 优先） ====================

def _daily_cache_path(date):
    return os.path.join(DAILY_CACHE_DIR, f"{date}.pkl")


def _basic_cache_path(date):
    return os.path.join(BASIC_CACHE_DIR, f"{date}.pkl")


def _adj_cache_path(date):
    return os.path.join(ADJ_CACHE_DIR, f"{date}.pkl")


def _is_today_before_close(date):
    now = datetime.datetime.now()
    if date != now.strftime('%Y%m%d'):
        return False
    return (now.hour, now.minute) < (MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)


def list_cached_daily_dates():
    """已缓存 daily 的日期列表（YYYYMMDD 升序）"""
    dates = db.list_daily_dates()
    if dates:
        return dates
    # fallback: 旧 pkl 文件
    try:
        names = os.listdir(DAILY_CACHE_DIR)
    except Exception:
        return []
    return sorted(n[:-4] for n in names
                  if n.endswith('.pkl') and len(n[:-4]) == 8 and n[:-4].isdigit())


def get_daily_df(date_str):
    """获取某日全市场行情 DataFrame（完整日K字段）。
    优先从 SQLite 读取，不存在则从 tushare 下载并写入 SQLite。
    返回 (df, from_cache)。"""
    # 1. SQLite 查询
    if db.has_daily(date_str):
        df = db.read_daily(date_str)
        if df is not None and not df.empty:
            return df, True

    # 2. fallback: 旧 pkl 文件（兼容未迁移数据）
    path = _daily_cache_path(date_str)
    if os.path.exists(path):
        try:
            df = pd.read_pickle(path)
            if 'high' in df.columns and 'pre_close' in df.columns:
                # 导入到 SQLite
                db.write_daily(date_str, df)
                return df, True
        except Exception:
            pass

    # 3. 从 tushare 下载
    df = _fetch_daily(date_str)
    if df is None or df.empty:
        return None, False

    # 保留完整日K字段
    keep_cols = ['ts_code', 'open', 'high', 'low', 'close', 'pre_close', 'pct_chg', 'vol', 'amount']
    available = [c for c in keep_cols if c in df.columns]
    out = df[available].copy()
    out['amount_yuan'] = pd.to_numeric(out['amount'], errors='coerce') * 1000
    for col in ['open', 'high', 'low', 'close', 'pre_close', 'pct_chg', 'vol']:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')
    out = out.dropna(subset=['amount_yuan'])
    if 'amount' in out.columns:
        out = out.drop(columns=['amount'])

    # 写入 SQLite（盘中不存）
    if not _is_today_before_close(date_str):
        db.write_daily(date_str, out)
    return out, False


def get_daily_basic_df(date_str):
    """获取某日全市场流通市值 DataFrame（ts_code + circ_mv，单位万元）。
    返回 (df, from_cache)；权限不足/无数据返回 (None, False)。"""
    # 1. SQLite
    if db.has_basic(date_str):
        df = db.read_basic(date_str)
        if df is not None and not df.empty:
            return df, True

    # 2. fallback: 旧 pkl
    path = _basic_cache_path(date_str)
    if os.path.exists(path):
        try:
            df = pd.read_pickle(path)
            db.write_basic(date_str, df)
            return df, True
        except Exception:
            pass

    # 3. 从 tushare 下载
    pro = get_tushare_pro()
    last_err = None
    df = None
    for attempt in range(RETRY_TIMES):
        try:
            df = pro.daily_basic(trade_date=date_str, fields='trade_date,ts_code,circ_mv')
            break
        except Exception as e:
            last_err = e
            if attempt < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    if df is None or df.empty:
        return None, False

    out = df[['ts_code', 'circ_mv']].copy()
    out['circ_mv'] = pd.to_numeric(out['circ_mv'], errors='coerce')
    out = out.dropna(subset=['circ_mv'])

    now = datetime.datetime.now()
    cacheable = not (date_str == now.strftime('%Y%m%d') and now.hour < BASIC_UPDATE_HOUR)
    if cacheable:
        db.write_basic(date_str, out)
    return out, False


def get_adj_factor_df(date_str):
    """获取某日全市场复权因子 DataFrame（ts_code + adj_factor）。
    返回 (df, from_cache)；失败返回 (None, False)。"""
    # 1. SQLite
    if db.has_adj(date_str):
        df = db.read_adj(date_str)
        if df is not None and not df.empty:
            return df, True

    # 2. fallback: 旧 pkl
    path = _adj_cache_path(date_str)
    if os.path.exists(path):
        try:
            df = pd.read_pickle(path)
            db.write_adj(date_str, df)
            return df, True
        except Exception:
            pass

    # 3. 从 tushare 下载
    pro = get_tushare_pro()
    last_err = None
    df = None
    for attempt in range(RETRY_TIMES):
        try:
            df = pro.adj_factor(trade_date=date_str, fields='ts_code,adj_factor')
            break
        except Exception as e:
            last_err = e
            if attempt < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    if df is None or df.empty:
        return None, False

    out = df[['ts_code', 'adj_factor']].copy()
    out['adj_factor'] = pd.to_numeric(out['adj_factor'], errors='coerce')
    out = out.dropna(subset=['adj_factor'])

    now = datetime.datetime.now()
    cacheable = not (date_str == now.strftime('%Y%m%d') and now.hour < BASIC_UPDATE_HOUR)
    if cacheable:
        db.write_adj(date_str, out)
    return out, False


def get_index_daily(days=400):
    """获取指数日线（中证全指），本地缓存，最新日期落后于 daily 缓存时自动更新。
    返回 DataFrame(trade_date, close) 升序；失败返回空 DataFrame。"""
    cached = None
    if os.path.exists(INDEX_DAILY_FILE):
        try:
            cached = pd.read_pickle(INDEX_DAILY_FILE)
        except Exception:
            cached = None

    latest_daily = list_cached_daily_dates()
    need_refresh = cached is None or cached.empty
    if not need_refresh and latest_daily:
        need_refresh = cached['trade_date'].max() < latest_daily[-1]

    if not need_refresh:
        return cached

    try:
        pro = get_tushare_pro()
        start = (datetime.datetime.now() - datetime.timedelta(days=int(days * 1.6))).strftime('%Y%m%d')
        df = pro.index_daily(ts_code=INDEX_TS_CODE, start_date=start)
        if df is None or df.empty:
            return cached if cached is not None else pd.DataFrame()
        out = df[['trade_date', 'close']].copy()
        out['close'] = pd.to_numeric(out['close'], errors='coerce')
        out = out.dropna().sort_values('trade_date').reset_index(drop=True)
        try:
            out.to_pickle(INDEX_DAILY_FILE)
        except Exception:
            pass
        return out
    except Exception:
        return cached if cached is not None else pd.DataFrame()


# ==================== 缓存管理 ====================

def get_cache_info():
    """返回缓存统计（优先用 SQLite 信息）"""
    info = db.get_db_info()
    if info['days'] > 0:
        return info
    # fallback: 旧文件统计
    days, size = set(), 0
    for folder in (DAILY_CACHE_DIR, BASIC_CACHE_DIR, ADJ_CACHE_DIR):
        try:
            for name in os.listdir(folder):
                if name.endswith('.pkl') and len(name[:-4]) == 8:
                    days.add(name[:-4])
                    size += os.path.getsize(os.path.join(folder, name))
        except Exception:
            pass
    return {'days': len(days), 'size_kb': size // 1024}


def clear_cache():
    """清空全部缓存（SQLite + 旧文件）"""
    db.clear_db()
    removed = 0
    extra = [SHARES_CACHE_FILE, MARKET_DAILY_FILE, INDUSTRY_DAILY_FILE,
             INDEX_DAILY_FILE, BREADTH_FILE, CONC_DAILY_FILE]
    for folder in (DAILY_CACHE_DIR, BASIC_CACHE_DIR, ADJ_CACHE_DIR):
        try:
            for name in os.listdir(folder):
                if name.endswith('.pkl'):
                    os.remove(os.path.join(folder, name))
                    removed += 1
        except Exception:
            pass
    for path in extra:
        try:
            os.remove(path)
            removed += 1
        except Exception:
            pass
    return removed


# ==================== 股票信息表（名称 + 行业） ====================

STOCK_BASIC_KEEP_DAYS = 7
_stock_info = None
_stock_names = None


def get_stock_info():
    """返回 DataFrame {ts_code, name, industry}；获取失败返回空 DataFrame"""
    global _stock_info
    if _stock_info is not None:
        return _stock_info

    try:
        if os.path.exists(STOCK_INFO_FILE):
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(STOCK_INFO_FILE))
            if (datetime.datetime.now() - mtime).days < STOCK_BASIC_KEEP_DAYS:
                _stock_info = pd.read_pickle(STOCK_INFO_FILE)
                return _stock_info
    except Exception:
        pass

    info = pd.DataFrame(columns=['ts_code', 'name', 'industry'])
    try:
        pro = get_tushare_pro()
        info = pro.stock_basic(exchange='', list_status='L',
                               fields='ts_code,name,industry')
    except Exception:
        pass

    _stock_info = info
    if not info.empty:
        try:
            info.to_pickle(STOCK_INFO_FILE)
        except Exception:
            pass
    return info


def get_stock_names():
    """返回 {ts_code: 名称} 映射；获取失败返回空 dict"""
    global _stock_names
    if _stock_names is not None:
        return _stock_names
    info = get_stock_info()
    _stock_names = dict(zip(info['ts_code'], info['name'])) if not info.empty else {}
    return _stock_names


# ==================== 交易日 ====================

def fetch_trade_dates():
    """获取近一年交易日，返回 ([显示格式 YYYY-MM-DD], [原始格式 YYYYMMDD])，新的在前"""
    pro = get_tushare_pro()
    today = datetime.datetime.now()
    start_dt = (today - datetime.timedelta(days=365)).strftime('%Y%m%d')
    end_dt = today.strftime('%Y%m%d')
    df = pro.trade_cal(exchange='SSE', start_date=start_dt, end_date=end_dt)
    trade_days = sorted(df[df['is_open'] == 1]['cal_date'].tolist(), reverse=True)
    display_list = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in trade_days]
    return display_list, trade_days


def get_trade_days_in_range(start_date, end_date):
    """获取日期范围内的交易日（YYYYMMDD 升序）"""
    pro = get_tushare_pro()
    cal_df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
    days = sorted(cal_df[cal_df['is_open'] == 1]['cal_date'].tolist())
    return days


# ==================== 缓存预热 ====================

def warm_basic_cache(progress_callback=None):
    """全量预热近一年数据：为每个交易日补全 daily、daily_basic、adj_factor。
    数据写入 SQLite。首次较慢，之后每天只增量补最近日期。
    返回 (新下载数, 总交易日数)。"""
    now = datetime.datetime.now()
    start = (now - datetime.timedelta(days=WARM_DAYS)).strftime('%Y%m%d')
    end = now.strftime('%Y%m%d')
    try:
        dates = get_trade_days_in_range(start, end)
    except Exception:
        dates = list_cached_daily_dates()
    total = len(dates)
    downloaded = 0

    for i, d in enumerate(dates):
        made_request = False
        # daily
        if not db.has_daily(d):
            try:
                _, cached = get_daily_df(d)
                if not cached:
                    downloaded += 1
                    made_request = True
            except Exception:
                pass
        # daily_basic
        if not db.has_basic(d):
            try:
                df, _ = get_daily_basic_df(d)
                if df is not None:
                    downloaded += 1
                    made_request = True
            except Exception:
                pass
        # adj_factor
        if not db.has_adj(d):
            try:
                df, _ = get_adj_factor_df(d)
                if df is not None:
                    downloaded += 1
                    made_request = True
            except Exception:
                pass
        if progress_callback:
            progress_callback(i + 1, total, d, not made_request)
        if made_request:
            time.sleep(REQUEST_INTERVAL)
    return downloaded, total
