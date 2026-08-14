# -*- coding: utf-8 -*-
"""大盘相关指标：板块占比、换手率、快照、涨跌走势、资金流入、集中度、综合信号"""

import os
import json
import time

import pandas as pd

from .config import (
    BOARD_SHARE_ORDER, SHARES_CACHE_FILE, MARKET_DAILY_FILE, CONC_DAILY_FILE,
    PCTILE_WINDOW, PCTILE_MIN_PERIODS, REQUEST_INTERVAL, get_board,
    WARN_THRESHOLD, TURNOVER_PCT_LINE, CONC_PCT_LINE, ABOVE60_LINE,
    BIAS_PCT_LINE, NHNL_DIV_RATIO,
)
from .datasource import (
    get_daily_df, get_daily_basic_df, get_index_daily,
    get_stock_info, get_tushare_pro,
    list_cached_daily_dates,
)
from . import database as db
from .utils import rolling_pctile
from .breadth import _compute_breadth

# ==================== 板块成交占比 ====================

def get_board_shares():
    """基于已缓存的每日行情（不触发下载），计算各板块成交额占全市场比例走势。
    返回 {'dates': [YYYYMMDD...], 'boards': {板块: [占比%...]}}
    优化：对缺失日期使用批量 SQL + Python 分组，避免逐天读取全表。"""
    cached_shares = db.read_summary('board_shares') or {}

    if not cached_shares and os.path.exists(SHARES_CACHE_FILE):
        try:
            with open(SHARES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_shares = json.load(f)
        except Exception:
            cached_shares = {}

    all_dates = list_cached_daily_dates()
    missing = [d for d in all_dates if d not in cached_shares]

    if missing:
        conn = db.get_conn()
        batch_size = 500
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = f"SELECT date, ts_code, amount_yuan FROM daily WHERE date IN ({placeholders})"
            rows = conn.execute(sql, batch).fetchall()
            # 按日期分组计算板块成交额
            from collections import defaultdict
            day_board_amt = defaultdict(lambda: defaultdict(float))
            for date_str, ts_code, amount_yuan in rows:
                board = get_board(ts_code)
                day_board_amt[date_str][board] += (amount_yuan or 0) / 1e8
            for d_str, board_amts in day_board_amt.items():
                cached_shares[d_str] = {b: float(board_amts.get(b, 0.0)) for b in BOARD_SHARE_ORDER}
        db.write_summary('board_shares', cached_shares)

    dates = [d for d in all_dates if d in cached_shares]
    boards = {b: [] for b in BOARD_SHARE_ORDER}
    for d in dates:
        row = cached_shares.get(d, {})
        total = sum(row.get(b, 0.0) for b in BOARD_SHARE_ORDER)
        for b in BOARD_SHARE_ORDER:
            pct = (row.get(b, 0.0) / total * 100) if total > 0 else 0.0
            boards[b].append(round(pct, 2))
    return {'dates': dates, 'boards': boards}


def get_board_amounts():
    """各板块每日绝对成交额（亿元）走势 + 全市场合计。
    返回 {'dates': [...], 'boards': {板块: [亿元...]}, 'total': [亿元...]}"""
    cached_shares = db.read_summary('board_shares') or {}
    all_dates = sorted(cached_shares.keys())
    if not all_dates:
        return {'dates': [], 'boards': {}, 'total': []}

    boards = {b: [] for b in BOARD_SHARE_ORDER if b != '其他'}
    total = []
    for d in all_dates:
        row = cached_shares.get(d, {})
        day_total = sum(row.get(b, 0.0) for b in BOARD_SHARE_ORDER)
        total.append(round(day_total, 1))
        for b in boards:
            boards[b].append(round(row.get(b, 0.0), 1))
    return {'dates': all_dates, 'boards': boards, 'total': total}


# ==================== 大盘拥挤度（换手率分位 + 量能偏离） ====================

def _load_market_daily():
    """增量汇总每日全市场成交额/流通市值：{date: {'amt_w', 'mv_w'}}（万元）
    优化：对缺失日期使用批量 SQL 聚合，避免逐天 Python merge。"""
    # 优先从 SQLite summary
    data = db.read_summary('market_daily') or {}

    # fallback: 旧 json 文件
    if not data and os.path.exists(MARKET_DAILY_FILE):
        try:
            with open(MARKET_DAILY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

    # 找出需要计算的日期
    all_dates = list_cached_daily_dates()
    missing = [d for d in all_dates if d not in data]

    if missing:
        # 批量 SQL 聚合：直接在数据库中 JOIN + GROUP BY
        conn = db.get_conn()
        # 分批处理避免 SQL 变量过多（SQLite 变量上限 999）
        batch_size = 500
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = f"""
                SELECT d.date,
                       SUM(d.amount_yuan) / 10000.0 AS amt_w,
                       SUM(b.circ_mv) AS mv_w
                FROM daily d
                INNER JOIN daily_basic b ON d.date = b.date AND d.ts_code = b.ts_code
                WHERE d.date IN ({placeholders})
                GROUP BY d.date
            """
            rows = conn.execute(sql, batch).fetchall()
            for row in rows:
                date_str, amt_w, mv_w = row
                if amt_w and mv_w:
                    data[date_str] = {'amt_w': float(amt_w), 'mv_w': float(mv_w)}

        db.write_summary('market_daily', data)

    return data


def get_market_overview():
    """大盘拥挤度概览：全市场换手率、换手率分位、量能偏离度"""
    data = _load_market_daily()
    dates = sorted(data.keys())
    if not dates:
        return {'n_days': 0}

    turnovers = [data[d]['amt_w'] / data[d]['mv_w'] if data[d]['mv_w'] > 0 else 0.0
                 for d in dates]
    pctiles = rolling_pctile(turnovers)

    latest_date = dates[-1]
    latest_turnover = turnovers[-1]
    latest_pct = pctiles[-1]
    ma20 = sum(turnovers[-20:]) / len(turnovers[-20:])
    vol_dev = latest_turnover / ma20 if ma20 > 0 else None

    return {
        'date': latest_date,
        'n_days': len(dates),
        'turnover': latest_turnover,            # 全市场换手率（0~1）
        'turnover_pct': latest_pct,             # 换手率分位（0~1），数据不足为 None
        'vol_dev': vol_dev,                     # 量能偏离度
        'total_amount_yi': data[latest_date]['amt_w'] / 1e4,   # 亿元
        'total_mv_yi': data[latest_date]['mv_w'] / 1e4,        # 亿元
        # 走势图数据
        'dates': dates,
        'turnover_series': [round(t * 100, 3) for t in turnovers],
        'pctile_series': [round(p * 100, 1) if p is not None else None for p in pctiles],
    }


# ==================== 当日大盘快照（涨跌停/涨跌家数/指数） ====================

def get_daily_snapshot(trade_date=None):
    """当日大盘快照数据：涨跌停家数、上涨/下跌/平盘家数、成交额、指数等。
    trade_date 为 YYYYMMDD，缺省取最近有数据的一天。
    返回 dict，前端总览页直接渲染。"""
    if trade_date is None:
        dates = list_cached_daily_dates()
        if not dates:
            return {'error': '暂无数据'}
        trade_date = dates[-1]

    try:
        df, _ = get_daily_df(trade_date)
    except Exception:
        df = None
    if df is None or df.empty:
        return {'error': f'{trade_date} 无数据'}

    pct = df['pct_chg']
    total = len(df)
    up_count = int((pct > 0).sum())
    down_count = int((pct < 0).sum())
    flat_count = int((pct == 0).sum())

    # 涨停/跌停判断（A股主板/创业板/科创板涨跌幅限制不同）
    # 简化处理：涨幅 >= 9.8% 视为涨停，跌幅 <= -9.8% 视为跌停（覆盖10%/20%板）
    limit_up = int((pct >= 9.8).sum())
    limit_down = int((pct <= -9.8).sum())
    # 20cm 板（创业板/科创板）：涨幅 >= 19.5%
    limit_up_20 = int((pct >= 19.5).sum())
    limit_down_20 = int((pct <= -19.5).sum())

    # 成交额
    total_amount_yi = float(df['amount_yuan'].sum()) / 1e8

    # 涨跌幅统计
    avg_pct = float(pct.mean())
    median_pct = float(pct.median())

    # 涨幅分布
    pct_gt5 = int((pct >= 5).sum())    # 涨幅>5%
    pct_gt3 = int((pct >= 3).sum())    # 涨幅>3%
    pct_lt_5 = int((pct <= -5).sum())  # 跌幅>5%
    pct_lt_3 = int((pct <= -3).sum())  # 跌幅>3%

    # 炸板率（盘中曾触及涨停但收盘未涨停）
    zha_ban_rate = None
    zha_ban_count = 0
    touched_limit_count = 0
    if 'high' in df.columns and 'pre_close' in df.columns:
        # 从缓存计算（完整日K数据）
        limit_price = df['pre_close'] * 1.095
        touched = df[df['high'] >= limit_price]
        touched_limit_count = len(touched)
        if touched_limit_count > 0:
            closed_limit = touched[touched['pct_chg'] >= 9.5]
            zha_ban_count = touched_limit_count - len(closed_limit)
            zha_ban_rate = round(zha_ban_count / touched_limit_count * 100, 1)
    else:
        # 旧缓存无 high/pre_close，尝试实时获取
        try:
            pro = get_tushare_pro()
            full_df = pro.daily(trade_date=trade_date, fields='ts_code,close,pre_close,high,pct_chg')
            if full_df is not None and not full_df.empty:
                full_df['limit_price'] = full_df['pre_close'] * 1.095
                touched = full_df[full_df['high'] >= full_df['limit_price']]
                touched_limit_count = len(touched)
                if touched_limit_count > 0:
                    closed_limit = touched[touched['pct_chg'] >= 9.5]
                    zha_ban_count = touched_limit_count - len(closed_limit)
                    zha_ban_rate = round(zha_ban_count / touched_limit_count * 100, 1)
        except Exception:
            pass

    # 指数数据（中证全指）
    idx = get_index_daily()
    idx_close = idx_pct = idx_name = None
    if idx is not None and not idx.empty:
        idx_name = '中证全指'
        last_row = idx[idx['trade_date'] == trade_date]
        if not last_row.empty:
            idx_close = float(last_row['close'].iloc[0])
        # 计算指数涨跌幅（用最近两天）
        idx_sorted = idx.sort_values('trade_date')
        idx_dates = idx_sorted['trade_date'].tolist()
        if trade_date in idx_dates:
            i = idx_dates.index(trade_date)
            if i > 0:
                prev_close = float(idx_sorted.iloc[i - 1]['close'])
                if prev_close > 0:
                    idx_pct = round((idx_close - prev_close) / prev_close * 100, 2)

    return {
        'date': trade_date,
        'total_stocks': total,
        'up_count': up_count,
        'down_count': down_count,
        'flat_count': flat_count,
        'limit_up': limit_up,
        'limit_down': limit_down,
        'limit_up_20': limit_up_20,
        'limit_down_20': limit_down_20,
        'total_amount_yi': round(total_amount_yi, 1),
        'avg_pct': round(avg_pct, 2),
        'median_pct': round(median_pct, 2),
        'pct_gt5': pct_gt5,
        'pct_gt3': pct_gt3,
        'pct_lt_5': pct_lt_5,
        'pct_lt_3': pct_lt_3,
        'zha_ban_rate': zha_ban_rate,
        'zha_ban_count': zha_ban_count,
        'touched_limit_count': touched_limit_count,
        'idx_name': idx_name,
        'idx_close': idx_close,
        'idx_pct': idx_pct,
    }


# ==================== 板块资金流入（累计净流入趋势） ====================

BOARD_FLOW_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'cache', 'board_flow.json')


def get_board_flow():
    """各板块每日成交额累计净流入趋势（从0开始）。
    算法：每个板块每天的成交额（亿元）减去该板块整个时间段的日均成交额，
    然后逐日累加。线往上 = 资金持续高于平均水平流入，线往下 = 低于平均水平（资金流出）。
    返回 {'dates': [...], 'boards': {板块: [累计值...]}}"""
    cached_shares = db.read_summary('board_shares') or {}

    if not cached_shares and os.path.exists(SHARES_CACHE_FILE):
        try:
            with open(SHARES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_shares = json.load(f)
        except Exception:
            cached_shares = {}

    dates = sorted(list_cached_daily_dates())
    if not dates:
        return {'dates': [], 'boards': {}}

    # 补全 board_shares 缓存中没有的日期
    dirty = False
    for d in dates:
        if d not in cached_shares:
            try:
                daily, _ = get_daily_df(d)
                if daily is None:
                    continue
                df = daily.copy()
                df['board'] = df['ts_code'].apply(get_board)
                grp = df.groupby('board')['amount_yuan'].sum() / 1e8
                cached_shares[d] = {b: float(grp.get(b, 0.0)) for b in BOARD_SHARE_ORDER}
                dirty = True
            except Exception:
                continue

    if dirty:
        db.write_summary('board_shares', cached_shares)

    # 收集各板块每日成交额（亿元）
    boards_daily = {b: [] for b in BOARD_SHARE_ORDER}
    valid_dates = []
    for d in dates:
        row = cached_shares.get(d)
        if not row:
            continue
        valid_dates.append(d)
        for b in BOARD_SHARE_ORDER:
            boards_daily[b].append(row.get(b, 0.0))

    if not valid_dates:
        return {'dates': [], 'boards': {}}

    # 计算累计净流入：第一天为0，后续每天与前一天的差值（环比增量）逐日累加
    # 曲线上升 = 成交额在增长（资金持续流入），曲线下降 = 成交额在萎缩（资金流出）
    result_boards = {}
    for b in BOARD_SHARE_ORDER:
        series = boards_daily[b]
        cum = 0.0
        cum_series = [0.0]  # 第一天从0开始
        for i in range(1, len(series)):
            cum += (series[i] - series[i - 1])
            cum_series.append(round(cum, 2))
        result_boards[b] = cum_series

    return {'dates': valid_dates, 'boards': result_boards}


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

def get_board_congestion_trend():
    """各板块每日成交额占全市场的比例（%）及其历史分位。
    衡量资金在不同板块间的分配变化。
    返回 {'dates': [...], 'boards': {板块: {'share': [%...], 'pctile': [%...]}}}"""
    cached_shares = db.read_summary('board_shares') or {}

    if not cached_shares and os.path.exists(SHARES_CACHE_FILE):
        try:
            with open(SHARES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_shares = json.load(f)
        except Exception:
            cached_shares = {}

    dates = sorted(list_cached_daily_dates())
    if not dates:
        return {'dates': [], 'boards': {}}

    # 补全缓存
    dirty = False
    for d in dates:
        if d not in cached_shares:
            try:
                daily, _ = get_daily_df(d)
                if daily is None:
                    continue
                df = daily.copy()
                df['board'] = df['ts_code'].apply(get_board)
                grp = df.groupby('board')['amount_yuan'].sum() / 1e8
                cached_shares[d] = {b: float(grp.get(b, 0.0)) for b in BOARD_SHARE_ORDER}
                dirty = True
            except Exception:
                continue
    if dirty:
        db.write_summary('board_shares', cached_shares)

    # 收集每日各板块占比
    valid_dates = []
    boards_share = {b: [] for b in BOARD_SHARE_ORDER if b != '其他'}
    for d in dates:
        row = cached_shares.get(d)
        if not row:
            continue
        total = sum(row.get(b, 0.0) for b in BOARD_SHARE_ORDER)
        if total <= 0:
            continue
        valid_dates.append(d)
        for b in boards_share:
            boards_share[b].append(round(row.get(b, 0.0) / total * 100, 2))

    if not valid_dates:
        return {'dates': [], 'boards': {}}

    # 计算滚动分位
    result = {}
    for b in boards_share:
        shares = boards_share[b]
        pctiles = rolling_pctile(shares)
        result[b] = {
            'share': shares,
            'pctile': [round(p * 100, 1) if p is not None else None for p in pctiles],
        }

    return {'dates': valid_dates, 'boards': result}


# ==================== 前 5% 集中度走势（信号用） ====================

def _load_conc_daily():
    """全市场前 5% 成交额集中度：{date: ratio}（÷全市场口径）
    优化：批量 SQL 计算。"""
    data = db.read_summary('conc_daily') or {}

    if not data and os.path.exists(CONC_DAILY_FILE):
        try:
            with open(CONC_DAILY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

    all_dates = list_cached_daily_dates()
    missing = [d for d in all_dates if d not in data]

    if missing:
        conn = db.get_conn()
        batch_size = 500
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            # 获取每天的总成交额和股票数
            sql_total = f"SELECT date, SUM(amount_yuan) as total, COUNT(*) as cnt FROM daily WHERE date IN ({placeholders}) GROUP BY date"
            totals = {r[0]: (r[1], r[2]) for r in conn.execute(sql_total, batch).fetchall()}
            # 获取每天前5%股票的成交额（用子查询按日排名）
            for d in batch:
                if d not in totals or not totals[d][0]:
                    continue
                total_amt, cnt = totals[d]
                top_n = max(1, int(cnt * 0.05))
                sql_top = "SELECT SUM(amount_yuan) FROM (SELECT amount_yuan FROM daily WHERE date=? ORDER BY amount_yuan DESC LIMIT ?)"
                row = conn.execute(sql_top, (d, top_n)).fetchone()
                if row and row[0]:
                    data[d] = row[0] / total_amt
        db.write_summary('conc_daily', data)

    return data


# ==================== 综合市场信号（文档 6.6 + 8.3 信号字典） ====================

def get_market_signals(trade_date=None):
    """根据各指标计算最近市场状态：
    预警层 6 项（≥3 项触发 → 预警），确认层（跌破MA60 / MA20死叉MA60 → 离场确认）。
    trade_date: 可选 YYYYMMDD，指定则计算截至该日的信号状态。
    使用纪律（文档·注意9）：预警层只收紧止盈，离场一律以确认层为准。"""
    signals = []
    confirms = []

    # ---- 换手率分位 ----
    ov = get_market_overview()
    # 如果指定了日期，从 overview 的时序数据中截取
    if trade_date and ov.get('dates'):
        all_dates = ov['dates']
        try:
            cut_idx = next(i for i, d in enumerate(all_dates) if d >= trade_date)
            cut_idx = min(cut_idx + 1, len(all_dates))
        except StopIteration:
            cut_idx = len(all_dates)
        pctile_series = ov.get('pctile_series', [])
        tp = pctile_series[cut_idx - 1] / 100 if cut_idx > 0 and cut_idx <= len(pctile_series) and pctile_series[cut_idx - 1] is not None else None
    else:
        tp = ov.get('turnover_pct')
    signals.append({
        'key': 'turnover_pct',
        'name': f"换手率分位 > {TURNOVER_PCT_LINE:.0%}",
        'value': tp,
        'value_text': f"{tp * 100:.0f}%" if tp is not None else '样本不足',
        'triggered': bool(tp is not None and tp > TURNOVER_PCT_LINE),
        'desc': '全市场过热（2015、2024.10 验证）',
    })

    # ---- 成交集中度分位 ----
    conc = _load_conc_daily()
    conc_dates = sorted(conc.keys())
    if trade_date:
        conc_dates = [d for d in conc_dates if d <= trade_date]
    conc_pct = None
    if conc_dates:
        series = [conc[d] for d in conc_dates]
        conc_pct = rolling_pctile(series)[-1]
    signals.append({
        'key': 'conc_pct',
        'name': f"成交集中度分位 > {CONC_PCT_LINE:.0%}",
        'value': conc_pct,
        'value_text': f"{conc_pct * 100:.0f}%" if conc_pct is not None else '样本不足',
        'triggered': bool(conc_pct is not None and conc_pct > CONC_PCT_LINE),
        'desc': '前5%股票成交占比分位，抱团极致则脆弱（2021.2 验证）',
    })

    # ---- 广度：站上MA60占比 / 上涨家数占比 / 涨跌幅中位数 / NH-NL 顶背离 ----
    breadth = _compute_breadth()
    above60 = up10 = med10 = None
    nhnl_latest = nhnl_max60 = None
    if breadth is not None and not breadth.empty:
        bdf = breadth
        if trade_date:
            bdf = breadth[breadth['date'] <= trade_date]
        if not bdf.empty:
            last = bdf.iloc[-1]
            above60 = last['above60'] if pd.notna(last['above60']) else None
            up10 = last['up_ratio_ma10'] if pd.notna(last['up_ratio_ma10']) else None
            med10 = last['chg_median_ma10'] if pd.notna(last['chg_median_ma10']) else None
            nhnl_latest = int(last['nhnl'])
            nhnl_max60 = int(bdf['nhnl'].tail(60).max())
    signals.append({
        'key': 'above60',
        'name': f"站上MA60占比 < {ABOVE60_LINE:.0%}",
        'value': above60,
        'value_text': f"{above60 * 100:.0f}%" if above60 is not None else '样本不足',
        'triggered': bool(above60 is not None and above60 < ABOVE60_LINE),
        'desc': '多数股票不跟涨（2015.5、2018.1 验证）',
    })
    signals.append({
        'key': 'up_ratio10',
        'name': '上涨家数占比(10日) < 50%',
        'value': up10,
        'value_text': f"{up10 * 100:.0f}%" if up10 is not None else '样本不足',
        'triggered': bool(up10 is not None and up10 < 0.5),
        'desc': '指数涨但上涨家数占比跌破一半 → 二八分化',
    })
    signals.append({
        'key': 'chg_median',
        'name': '涨跌幅中位数(10日) < 0',
        'value': med10,
        'value_text': f"{med10:.2f}%" if med10 is not None else '样本不足',
        'triggered': bool(med10 is not None and med10 < 0),
        'desc': '权重护盘假象：中位数为负说明多数股票在跌（2021 抱团期验证）',
    })

    # ---- 指数趋势：BIAS60 分位 / 跌破MA60 / 死叉 / NHNL 顶背离 ----
    idx = get_index_daily()
    below_ma60 = dead_cross = idx_new_high = False
    bias_pct = None
    idx_close = idx_ma60 = None
    if idx is not None and not idx.empty:
        if trade_date:
            idx = idx[idx['trade_date'] <= trade_date]
        if len(idx) >= 61:
            closes = idx['close'].tolist()
            ma20 = sum(closes[-20:]) / 20
            ma60 = sum(closes[-60:]) / 60
            ma20_prev = sum(closes[-21:-1]) / 20
            ma60_prev = sum(closes[-61:-1]) / 60
            idx_close = closes[-1]
            idx_ma60 = ma60
        below_ma60 = idx_close < ma60
        dead_cross = ma20 < ma60 and ma20_prev >= ma60_prev
        idx_new_high = idx_close >= max(closes[-250:])
        # BIAS60 序列及其分位
        ma60_series = pd.Series(closes).rolling(60).mean()
        bias_series = (pd.Series(closes) / ma60_series - 1).dropna().tolist()
        if bias_series:
            bias_pct = rolling_pctile(bias_series)[-1]

    signals.append({
        'key': 'bias_pct',
        'name': f"BIAS60 分位 > {BIAS_PCT_LINE:.0%}",
        'value': bias_pct,
        'value_text': f"{bias_pct * 100:.0f}%" if bias_pct is not None else '样本不足',
        'triggered': bool(bias_pct is not None and bias_pct > BIAS_PCT_LINE),
        'desc': '指数偏离 60 日线过多，短期透支（2015.5、2024.10.8 验证）',
    })
    signals.append({
        'key': 'nhnl_div',
        'name': 'NH-NL 顶背离',
        'value': bool(idx_new_high and nhnl_latest is not None
                      and nhnl_max60 is not None
                      and nhnl_latest < nhnl_max60 * NHNL_DIV_RATIO),
        'value_text': (f"NHNL {nhnl_latest} / 峰值 {nhnl_max60}" if nhnl_latest is not None
                       else '样本不足'),
        'triggered': bool(idx_new_high and nhnl_latest is not None
                          and nhnl_max60 is not None
                          and nhnl_latest < nhnl_max60 * NHNL_DIV_RATIO),
        'desc': '指数新高但创新高家数不足峰值一半（2007/2015/2021 大顶验证）',
    })
    confirms.append({
        'key': 'below_ma60',
        'name': '指数跌破 MA60',
        'value': below_ma60,
        'value_text': (f"收盘 {idx_close:.0f} < MA60 {idx_ma60:.0f}" if idx_close and idx_ma60 else '样本不足'),
        'triggered': bool(below_ma60),
        'desc': '中证全指收盘跌破 60 日均线',
    })
    confirms.append({
        'key': 'dead_cross',
        'name': 'MA20 死叉 MA60',
        'value': dead_cross,
        'value_text': '是' if dead_cross else '否',
        'triggered': bool(dead_cross),
        'desc': '20 日均线下穿 60 日均线（当日发生）',
    })

    warning = sum(1 for s in signals if s['triggered'])
    confirm_exit = any(c['triggered'] for c in confirms)
    if warning >= WARN_THRESHOLD and confirm_exit:
        signal, level = '减仓 / 离场', 'danger'
    elif warning >= WARN_THRESHOLD:
        signal, level = '预警：收紧止盈，不加仓', 'warn'
    elif warning >= 2:
        signal, level = '注意：风险信号增多', 'caution'
    else:
        signal, level = '正常', 'ok'

    return {
        'date': trade_date or ov.get('date'),
        'n_days': ov.get('n_days', 0),
        'warning_count': warning,
        'warning_total': len(signals),
        'confirm_exit': confirm_exit,
        'signal': signal,
        'level': level,
        'signals': signals,
        'confirms': confirms,
    }


# ==================== 涨跌家数走势 + 多指数 ====================

UPDN_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'cache', 'updn_daily.json')


def get_updn_trend(exclude_st=False, exclude_board=None):
    """近一年每天的涨/跌/平家数走势 + 炸板率 + 主要指数当日涨跌。
    支持筛选：exclude_st=True 排除ST股；exclude_board='创业板' 排除某板块。
    缓存按板块/ST分类存储，前端筛选时在已缓存数据上做加减。"""

    # 加载缓存（v2：按板块+ST分类）
    cached = db.read_summary('updn_daily') or {}

    if not cached and os.path.exists(UPDN_CACHE_FILE):
        try:
            with open(UPDN_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except Exception:
            cached = {}

    # 检查缓存版本（v2 有 'boards' 字段）
    if cached and not any(isinstance(v, dict) and 'boards' in v for v in cached.values()):
        cached = {}  # 旧格式，清空重算

    dates = list_cached_daily_dates()
    info = get_stock_info()
    st_codes = set(info[info['name'].str.contains('ST', na=False)]['ts_code'].tolist()) if not info.empty else set()

    missing = [d for d in dates if d not in cached]
    if missing:
        conn = db.get_conn()
        # 批量读取所有缺失日期的必要字段
        batch_size = 500
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = f"SELECT date, ts_code, pct_chg, high, pre_close FROM daily WHERE date IN ({placeholders})"
            rows = conn.execute(sql, batch).fetchall()
            # 按日期分组处理
            from collections import defaultdict
            day_rows = defaultdict(list)
            for row in rows:
                day_rows[row[0]].append(row)

            for d in batch:
                if d not in day_rows or not day_rows[d]:
                    continue
                day_data = {'boards': {}, 'st': {}, 'total': {}}
                up = flat = down = 0
                st_up = st_flat = st_down = st_count = 0
                board_stats = {b: {'up': 0, 'flat': 0, 'down': 0, 'count': 0} for b in ['沪深主板', '创业板', '科创板', '北交所']}
                touched_count = 0
                closed_limit_count = 0

                for _, ts_code, pct_chg, high, pre_close in day_rows[d]:
                    pct_chg = pct_chg or 0
                    board = get_board(ts_code)
                    is_st = ts_code in st_codes

                    if pct_chg > 0:
                        up += 1
                    elif pct_chg == 0:
                        flat += 1
                    else:
                        down += 1

                    if is_st:
                        st_count += 1
                        if pct_chg > 0: st_up += 1
                        elif pct_chg == 0: st_flat += 1
                        else: st_down += 1

                    if board in board_stats:
                        board_stats[board]['count'] += 1
                        if pct_chg > 0: board_stats[board]['up'] += 1
                        elif pct_chg == 0: board_stats[board]['flat'] += 1
                        else: board_stats[board]['down'] += 1

                    # 炸板率
                    if high and pre_close and pre_close > 0:
                        limit_price = pre_close * 1.095
                        if high >= limit_price:
                            touched_count += 1
                            if pct_chg >= 9.5:
                                closed_limit_count += 1

                day_data['total'] = {'up': up, 'flat': flat, 'down': down, 'count': up + flat + down}
                day_data['st'] = {'up': st_up, 'flat': st_flat, 'down': st_down, 'count': st_count}
                day_data['boards'] = board_stats
                if touched_count > 0:
                    day_data['zha_ban_rate'] = round((touched_count - closed_limit_count) / touched_count * 100, 1)
                else:
                    day_data['zha_ban_rate'] = 0.0
                cached[d] = day_data

        db.write_summary('updn_daily', cached)

    sorted_dates = sorted(d for d in dates if d in cached)
    if not sorted_dates:
        return {'dates': [], 'up': [], 'flat': [], 'down': [], 'zha_ban_rate': [], 'indices': {}}

    # 根据筛选条件计算
    up_list, flat_list, down_list, zha_ban_list = [], [], [], []
    for d in sorted_dates:
        c = cached[d]
        up = c['total']['up']
        flat = c['total']['flat']
        down = c['total']['down']

        if exclude_st:
            up -= c['st']['up']
            flat -= c['st']['flat']
            down -= c['st']['down']

        if exclude_board and exclude_board in c.get('boards', {}):
            bd = c['boards'][exclude_board]
            up -= bd['up']
            flat -= bd['flat']
            down -= bd['down']

        up_list.append(up)
        flat_list.append(flat)
        down_list.append(down)
        zha_ban_list.append(c.get('zha_ban_rate'))

    # 主要指数当日涨跌
    indices = {}
    try:
        pro = get_tushare_pro()
        latest_date = sorted_dates[-1]
        idx_codes = {
            '上证指数': '000001.SH',
            '深证成指': '399001.SZ',
            '创业板指': '399006.SZ',
            '科创50': '000688.SH',
        }
        for name, code in idx_codes.items():
            try:
                df_idx = pro.index_daily(ts_code=code, start_date=latest_date, end_date=latest_date)
                if df_idx is not None and not df_idx.empty:
                    row = df_idx.iloc[0]
                    indices[name] = {
                        'close': round(float(row['close']), 2),
                        'pct_chg': round(float(row['pct_chg']), 2),
                    }
            except Exception:
                continue
    except Exception:
        pass

    return {
        'dates': sorted_dates,
        'up': up_list,
        'flat': flat_list,
        'down': down_list,
        'zha_ban_rate': zha_ban_list,
        'indices': indices,
    }



