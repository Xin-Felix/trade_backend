# -*- coding: utf-8 -*-
"""融资余额指标（融资余额 / 流通市值比 + 分位）"""

import os
import json
import time

import pandas as pd

from .config import MARGIN_CACHE_FILE, REQUEST_INTERVAL
from .datasource import get_tushare_pro, list_cached_daily_dates
from . import database as db
from .utils import rolling_pctile
from .market import _load_market_daily

# ==================== 融资余额（融资余额 / 流通市值） ====================

def get_margin_trend():
    """融资余额走势：融资余额 + 融资余额占流通市值比 + 分位。
    数据来源：tushare margin 接口（全市场汇总，按交易所合计）。
    缓存到 margin_daily.json，增量更新。
    返回 {'dates': [...], 'rzye': [亿], 'ratio': [%], 'ratio_pct': [%分位]}"""

    # 加载缓存
    cached = db.read_margin_all()

    if not cached and os.path.exists(MARGIN_CACHE_FILE):
        try:
            with open(MARGIN_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except Exception:
            cached = {}

    # 融券余额缓存
    rqye_cached = db.read_summary('rqye_daily') or {}

    # 增量获取：找出缓存中没有但有 daily_basic 的日期
    market_daily = _load_market_daily()
    all_dates = sorted(market_daily.keys())
    missing = [d for d in all_dates if d not in cached]

    if missing:
        from .datasource import get_tushare_pro
        pro = get_tushare_pro()
        batch_start = missing[0]
        batch_end = missing[-1]
        try:
            import time as _time
            _time.sleep(REQUEST_INTERVAL)
            df_sh = pro.margin(exchange_id='SSE', start_date=batch_start, end_date=batch_end)
            _time.sleep(REQUEST_INTERVAL)
            df_sz = pro.margin(exchange_id='SZSE', start_date=batch_start, end_date=batch_end)
            _time.sleep(REQUEST_INTERVAL)
            df_bj = pro.margin(exchange_id='BSE', start_date=batch_start, end_date=batch_end)

            frames = []
            if df_sh is not None and not df_sh.empty:
                frames.append(df_sh[['trade_date', 'rzye', 'rqye']])
            if df_sz is not None and not df_sz.empty:
                frames.append(df_sz[['trade_date', 'rzye', 'rqye']])
            if df_bj is not None and not df_bj.empty:
                frames.append(df_bj[['trade_date', 'rzye', 'rqye']])

            if frames:
                all_margin = pd.concat(frames, ignore_index=True)
                all_margin['rzye'] = pd.to_numeric(all_margin['rzye'], errors='coerce').fillna(0)
                all_margin['rqye'] = pd.to_numeric(all_margin['rqye'], errors='coerce').fillna(0)
                daily_sum = all_margin.groupby('trade_date').agg({'rzye': 'sum', 'rqye': 'sum'})
                for d in missing:
                    if d in daily_sum.index:
                        cached[d] = float(daily_sum.loc[d, 'rzye'])
                        rqye_cached[d] = float(daily_sum.loc[d, 'rqye'])
        except Exception:
            pass

        new_entries = {d: cached[d] for d in missing if d in cached}
        if new_entries:
            db.write_margin_batch(new_entries)
        # 融券余额存到 summary
        if rqye_cached:
            existing_rq = db.read_summary('rqye_daily') or {}
            existing_rq.update({d: rqye_cached[d] for d in missing if d in rqye_cached})
            db.write_summary('rqye_daily', existing_rq)

    # 构建走势数据
    dates = sorted(d for d in all_dates if d in cached)
    if not dates:
        return {'dates': [], 'rzye': [], 'rqye': [], 'ratio': [], 'ratio_pct': []}

    rzye_yi = []  # 融资余额（亿元）
    rqye_yi = []  # 融券余额（亿元）
    ratio = []    # 融资余额 / 流通市值（%）
    for d in dates:
        rz = cached[d] / 1e8  # 元→亿
        rzye_yi.append(round(rz, 1))
        rq = rqye_cached.get(d, 0) / 1e8
        rqye_yi.append(round(rq, 1))
        mv = market_daily[d]['mv_w'] / 1e4  # 万元→亿元
        r = (rz / mv * 100) if mv > 0 else 0.0
        ratio.append(round(r, 4))

    # 分位
    ratio_pcts = rolling_pctile(ratio)
    ratio_pct_list = [round(p * 100, 1) if p is not None else None for p in ratio_pcts]

    return {
        'dates': dates,
        'rzye': rzye_yi,
        'rqye': rqye_yi,
        'ratio': [round(r, 3) for r in ratio],
        'ratio_pct': ratio_pct_list,
        'latest_rzye': rzye_yi[-1] if rzye_yi else None,
        'latest_rqye': rqye_yi[-1] if rqye_yi else None,
        'latest_ratio': round(ratio[-1], 3) if ratio else None,
        'latest_ratio_pct': ratio_pct_list[-1] if ratio_pct_list else None,
    }


