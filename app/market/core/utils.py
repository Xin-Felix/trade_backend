# -*- coding: utf-8 -*-
"""公共工具函数"""

from .config import PCTILE_WINDOW, PCTILE_MIN_PERIODS


def rolling_pctile(values, window=PCTILE_WINDOW, min_periods=PCTILE_MIN_PERIODS):
    """每个点在过去 window 个点中的分位（0~1），不足 min_periods 返回 None"""
    out = []
    for i in range(len(values)):
        seg = values[max(0, i - window + 1):i + 1]
        if len(seg) < min_periods:
            out.append(None)
        else:
            v = seg[-1]
            out.append(sum(1 for x in seg if x <= v) / len(seg))
    return out
