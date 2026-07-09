"""Tushare 代理接口 - 公共工具函数。

所有 Tushare 代理接口共用的工具函数放在这里，
包括获取 Pro API 实例、DataFrame 转 list[dict] 等。
"""

from datetime import date


def get_pro():
    """获取 Tushare Pro API 实例（单例复用 token）。"""
    from app.core.config import settings
    import tushare as ts
    ts.set_token(settings.tushare_token)
    return ts.pro_api()


def df_to_list(df) -> list[dict]:
    """把 pandas DataFrame 转成 list[dict]，NaN 转为 None。"""
    if df is None or df.empty:
        return []
    return df.where(df.notnull(), None).to_dict(orient="records")


def today() -> str:
    """返回今天日期字符串 YYYYMMDD。"""
    return date.today().strftime("%Y%m%d")


def normalize_code(code: str) -> str:
    """标准化股票代码为 Tushare 格式（如 000001 -> 000001.SZ）。"""
    from app.services.stock_service import _normalize_code
    return _normalize_code(code)
