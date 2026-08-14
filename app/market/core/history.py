# -*- coding: utf-8 -*-
"""拥挤度计算历史

原先存桌面版的 history.json，服务端化后落 Postgres 的 congestion_history 表。
用途：拥挤度页的趋势图（多组「板块 × 前N% × 口径」曲线叠加）。

按 (date, board, top_percent, denominator) 去重覆盖，所以不再需要
原来那套「读全表 → 插到头部 → 截断 365 条 → 写回」的逻辑。
"""

from . import database as db


def load_history(start_date: str = None, end_date: str = None) -> list[dict]:
    """返回历史记录（新的在前）"""
    return db.read_congestion_history(start_date, end_date)


def save_history(record: dict) -> None:
    """写入单条计算结果"""
    if record:
        db.write_congestion_history([record])


def save_history_batch(records: list[dict]) -> None:
    """批量写入"""
    if records:
        db.write_congestion_history(records)


def clear_history() -> None:
    db.clear_congestion_history()
