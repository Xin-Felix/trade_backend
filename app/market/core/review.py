# -*- coding: utf-8 -*-
"""每日复盘（趋势概览）"""

import pandas as pd

from .datasource import list_cached_daily_dates
from . import database as db
from .config import get_board
from .utils import rolling_pctile
from .market import _load_market_daily, _load_conc_daily, get_market_signals, get_board_congestion_trend
from .breadth import _compute_breadth

# ==================== 每日复盘（趋势概览） ====================

def get_daily_review(target_date=None):
    """每日复盘数据：汇总各关键指标的最新值 + 近60天走势 + 日变化 + 信号变化追踪 + 板块热力。
    target_date: YYYYMMDD 格式，缺省取最近有数据的一天。支持翻看历史。
    返回结构供前端 ReviewPage 一次性渲染。"""

    # --- 确定目标日期 ---
    all_dates = sorted(list_cached_daily_dates())
    if not all_dates:
        return {'error': '暂无缓存数据'}

    if target_date:
        # 找到 <= target_date 的最近一天
        earlier = [d for d in all_dates if d <= target_date]
        if not earlier:
            return {'error': f'{target_date} 之前无数据'}
        date = earlier[-1]
    else:
        date = all_dates[-1]

    date_idx = all_dates.index(date)
    prev_date = all_dates[date_idx - 1] if date_idx > 0 else None

    # --- 换手率 + 分位走势 ---
    market_daily = _load_market_daily()
    m_dates = sorted(market_daily.keys())
    turnovers = [market_daily[d]['amt_w'] / market_daily[d]['mv_w']
                 if market_daily[d]['mv_w'] > 0 else 0.0 for d in m_dates]
    turnover_pcts = rolling_pctile(turnovers)

    # 目标日在 market_daily 中的位置
    turnover_today = turnover_prev = turnover_pct_today = turnover_pct_prev = None
    if date in market_daily:
        mi = m_dates.index(date)
        turnover_today = turnovers[mi]
        turnover_pct_today = turnover_pcts[mi]
        if mi > 0:
            turnover_prev = turnovers[mi - 1]
            turnover_pct_prev = turnover_pcts[mi - 1]

    # --- 成交集中度 + 分位走势 ---
    conc = _load_conc_daily()
    conc_dates = sorted(conc.keys())
    conc_values = [conc[d] for d in conc_dates]
    conc_pcts = rolling_pctile(conc_values) if conc_values else []

    conc_today = conc_prev = conc_pct_today = conc_pct_prev = None
    if date in conc:
        ci = conc_dates.index(date)
        conc_today = conc_values[ci]
        conc_pct_today = conc_pcts[ci]
        if ci > 0:
            conc_prev = conc_values[ci - 1]
            conc_pct_prev = conc_pcts[ci - 1]

    # --- 市场广度 ---
    breadth = _compute_breadth()
    above60_today = above60_prev = None
    up_ratio_today = up_ratio_prev = None
    median_chg_today = median_chg_prev = None
    breadth_dates = []
    breadth_above60 = []
    breadth_up_ratio = []
    breadth_median = []

    if breadth is not None and not breadth.empty:
        breadth_dates = breadth['date'].tolist()
        breadth_above60 = [round(v * 100, 1) if pd.notna(v) else None for v in breadth['above60']]
        breadth_up_ratio = [round(v * 100, 1) if pd.notna(v) else None for v in breadth['up_ratio_ma10']]
        breadth_median = [round(float(v), 2) if pd.notna(v) else None for v in breadth['chg_median_ma10']]

        if date in breadth_dates:
            bi = breadth_dates.index(date)
            row = breadth.iloc[bi]
            above60_today = float(row['above60']) if pd.notna(row['above60']) else None
            up_ratio_today = float(row['up_ratio_ma10']) if pd.notna(row['up_ratio_ma10']) else None
            median_chg_today = float(row['chg_median_ma10']) if pd.notna(row['chg_median_ma10']) else None
            if bi > 0:
                prev_row = breadth.iloc[bi - 1]
                above60_prev = float(prev_row['above60']) if pd.notna(prev_row['above60']) else None
                up_ratio_prev = float(prev_row['up_ratio_ma10']) if pd.notna(prev_row['up_ratio_ma10']) else None
                median_chg_prev = float(prev_row['chg_median_ma10']) if pd.notna(prev_row['chg_median_ma10']) else None

    # --- 信号快照（目标日） ---
    # 简化：取当前信号（get_market_signals 基于全量数据最新值计算）
    # 对于历史日期，信号只能近似（因为分位是基于完整历史计算的）
    signals_data = get_market_signals()

    # --- 信号近5天变化追踪 ---
    # 用简化方式：给出关键分位指标近5天的值
    recent_n = min(5, date_idx + 1)
    recent_dates = all_dates[date_idx - recent_n + 1: date_idx + 1]

    signals_history = []
    for rd in recent_dates:
        day_info = {'date': rd, 'turnover_pct': None, 'conc_pct': None, 'above60': None}
        if rd in market_daily:
            ri = m_dates.index(rd)
            day_info['turnover_pct'] = round(turnover_pcts[ri] * 100, 1) if turnover_pcts[ri] is not None else None
        if rd in conc:
            ri = conc_dates.index(rd)
            day_info['conc_pct'] = round(conc_pcts[ri] * 100, 1) if conc_pcts[ri] is not None else None
        if breadth is not None and rd in breadth_dates:
            ri = breadth_dates.index(rd)
            v = breadth.iloc[ri]['above60']
            day_info['above60'] = float(round(float(v) * 100, 1)) if pd.notna(v) else None
        signals_history.append(day_info)

    # --- 板块热力（各板块分位今日 vs 昨日） ---
    board_cong = get_board_congestion_trend()
    board_heatmap = {}
    if board_cong and board_cong.get('dates'):
        bc_dates = board_cong['dates']
        if date in bc_dates:
            bci = bc_dates.index(date)
            for b, bdata in board_cong['boards'].items():
                pctile_today = bdata['pctile'][bci] if bci < len(bdata['pctile']) else None
                pctile_prev = bdata['pctile'][bci - 1] if bci > 0 and (bci - 1) < len(bdata['pctile']) else None
                share_today = bdata['share'][bci] if bci < len(bdata['share']) else None
                board_heatmap[b] = {
                    'pctile': pctile_today,
                    'pctile_prev': pctile_prev,
                    'pctile_chg': round(pctile_today - pctile_prev, 1) if pctile_today is not None and pctile_prev is not None else None,
                    'share': share_today,
                }

    # --- 构建走势数据（取近60天） ---
    trend_start = max(0, date_idx - 59)
    trend_dates = all_dates[trend_start: date_idx + 1]

    # 换手率分位走势
    trend_turnover_pct = []
    for td in trend_dates:
        if td in market_daily:
            ti = m_dates.index(td)
            v = turnover_pcts[ti]
            trend_turnover_pct.append(float(round(v * 100, 1)) if v is not None else None)
        else:
            trend_turnover_pct.append(None)

    # 集中度分位走势
    trend_conc_pct = []
    for td in trend_dates:
        if td in conc:
            ti = conc_dates.index(td)
            v = conc_pcts[ti]
            trend_conc_pct.append(float(round(v * 100, 1)) if v is not None else None)
        else:
            trend_conc_pct.append(None)

    # 广度（站上MA60占比）走势
    trend_above60 = []
    for td in trend_dates:
        if breadth is not None and td in breadth_dates:
            ti = breadth_dates.index(td)
            v = breadth.iloc[ti]['above60']
            trend_above60.append(float(round(float(v) * 100, 1)) if pd.notna(v) else None)
        else:
            trend_above60.append(None)

    # 涨跌幅中位数走势
    trend_median = []
    for td in trend_dates:
        if breadth is not None and td in breadth_dates:
            ti = breadth_dates.index(td)
            v = breadth.iloc[ti]['chg_median_ma10']
            trend_median.append(float(round(float(v), 2)) if pd.notna(v) else None)
        else:
            trend_median.append(None)

    # 上涨家数占比走势
    trend_up_ratio = []
    for td in trend_dates:
        if breadth is not None and td in breadth_dates:
            ti = breadth_dates.index(td)
            v = breadth.iloc[ti]['up_ratio_ma10']
            trend_up_ratio.append(float(round(float(v) * 100, 1)) if pd.notna(v) else None)
        else:
            trend_up_ratio.append(None)

    # --- 日变化摘要（自动文字生成） ---
    def _delta_text(name, today, prev, unit='%', mult=100, decimals=1):
        if today is None:
            return None
        today_v = round(today * mult, decimals)
        if prev is not None:
            prev_v = round(prev * mult, decimals)
            delta = round(today_v - prev_v, decimals)
            arrow = '↑' if delta > 0 else ('↓' if delta < 0 else '→')
            return f"{name} {today_v}{unit}（{arrow}{abs(delta)}{unit}）"
        return f"{name} {today_v}{unit}"

    summary_texts = []
    t = _delta_text('换手率分位', turnover_pct_today, turnover_pct_prev, '%', 100, 1)
    if t:
        summary_texts.append(t)
    t = _delta_text('集中度分位', conc_pct_today, conc_pct_prev, '%', 100, 1)
    if t:
        summary_texts.append(t)
    t = _delta_text('站上MA60', above60_today, above60_prev, '%', 100, 1)
    if t:
        summary_texts.append(t)
    t = _delta_text('上涨占比(10日)', up_ratio_today, up_ratio_prev, '%', 100, 1)
    if t:
        summary_texts.append(t)
    t = _delta_text('涨跌幅中位数(10日)', median_chg_today, median_chg_prev, '%', 1, 2)
    if t:
        summary_texts.append(t)

    # 定性判断
    assessment = ''
    warn_count = signals_data.get('warning_count', 0) if signals_data and not signals_data.get('error') else 0
    if warn_count >= 3:
        assessment = '⚠️ 预警层多项触发，风险较高，注意控制仓位'
    elif turnover_pct_today is not None and above60_today is not None:
        if turnover_pct_today > 0.8 and above60_today < 0.5:
            assessment = '⚠️ 换手率高位但广度走弱，二八分化明显，谨慎追高'
        elif turnover_pct_today < 0.3 and above60_today > 0.6:
            assessment = '市场活跃度低但个股趋势良好，可能是温和上涨阶段'
        elif turnover_pct_today > 0.7:
            assessment = '市场交易活跃，关注是否进入过热区间'
        elif turnover_pct_today < 0.2:
            assessment = '市场极度冷清，可能接近阶段性底部'
        else:
            assessment = '市场状态正常，各项指标无明显异常'
    else:
        assessment = '数据不足，无法给出定性判断'

    # --- 组装返回 ---
    return {
        'date': date,
        'prev_date': prev_date,
        'all_dates': all_dates,  # 前端翻页用
        # 指标摘要（卡片用）
        'summary': {
            'turnover_pct': round(turnover_pct_today * 100, 1) if turnover_pct_today is not None else None,
            'turnover_pct_prev': round(turnover_pct_prev * 100, 1) if turnover_pct_prev is not None else None,
            'conc_pct': round(conc_pct_today * 100, 1) if conc_pct_today is not None else None,
            'conc_pct_prev': round(conc_pct_prev * 100, 1) if conc_pct_prev is not None else None,
            'above60': round(above60_today * 100, 1) if above60_today is not None else None,
            'above60_prev': round(above60_prev * 100, 1) if above60_prev is not None else None,
            'up_ratio': round(up_ratio_today * 100, 1) if up_ratio_today is not None else None,
            'up_ratio_prev': round(up_ratio_prev * 100, 1) if up_ratio_prev is not None else None,
            'median_chg': round(float(median_chg_today), 2) if median_chg_today is not None else None,
            'median_chg_prev': round(float(median_chg_prev), 2) if median_chg_prev is not None else None,
            'warning_count': warn_count,
            'warning_total': signals_data.get('warning_total', 7) if signals_data and not signals_data.get('error') else 7,
            'signal': signals_data.get('signal', '未知') if signals_data and not signals_data.get('error') else '未知',
            'level': signals_data.get('level', 'ok') if signals_data and not signals_data.get('error') else 'ok',
        },
        # 走势数据（近60天）
        'trend': {
            'dates': trend_dates,
            'turnover_pct': trend_turnover_pct,
            'conc_pct': trend_conc_pct,
            'above60': trend_above60,
            'up_ratio': trend_up_ratio,
            'median_chg': trend_median,
        },
        # 信号近5天变化
        'signals_history': signals_history,
        # 板块热力
        'board_heatmap': board_heatmap,
        # 文字摘要
        'summary_texts': summary_texts,
        'assessment': assessment,
    }
