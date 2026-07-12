"""国际市场数据服务。

提供美股指数、港股指数、黄金、原油、美元指数、人民币汇率等全球主要市场数据。
数据来源：AKShare（免费，实时性好）。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _get_ak():
    """延迟导入 akshare。"""
    import akshare as ak
    return ak


# ============================================================
# 全球指数实时行情
# ============================================================

# 主要国际指数代码映射（东方财富全球指数代码）
GLOBAL_INDICES = {
    # 美股
    "DJI": {"name": "道琼斯", "market": "美股", "symbol": ".DJI"},
    "SPX": {"name": "标普500", "market": "美股", "symbol": ".SPX"},
    "IXIC": {"name": "纳斯达克", "market": "美股", "symbol": ".IXIC"},
    # 港股
    "HSI": {"name": "恒生指数", "market": "港股", "symbol": "HSI"},
    "HSCEI": {"name": "国企指数", "market": "港股", "symbol": "HSCEI"},
    "HSTECH": {"name": "恒生科技", "market": "港股", "symbol": "HSTECH"},
    # 亚太
    "N225": {"name": "日经225", "market": "日本", "symbol": ".N225"},
    "KS11": {"name": "韩国综合", "market": "韩国", "symbol": ".KS11"},
    # 欧洲
    "FTSE": {"name": "英国富时100", "market": "欧洲", "symbol": ".FTSE"},
    "DAX": {"name": "德国DAX", "market": "欧洲", "symbol": ".DAX"},
}

# 主要商品/汇率
GLOBAL_COMMODITIES = {
    "GOLD": {"name": "伦敦金(现货)", "category": "贵金属", "unit": "美元/盎司"},
    "SILVER": {"name": "伦敦银(现货)", "category": "贵金属", "unit": "美元/盎司"},
    "CRUDE_OIL": {"name": "WTI原油", "category": "能源", "unit": "美元/桶"},
    "BRENT_OIL": {"name": "布伦特原油", "category": "能源", "unit": "美元/桶"},
    "USDX": {"name": "美元指数", "category": "汇率", "unit": ""},
    "USDCNY": {"name": "美元/人民币", "category": "汇率", "unit": ""},
    "EURUSD": {"name": "欧元/美元", "category": "汇率", "unit": ""},
    "USDJPY": {"name": "美元/日元", "category": "汇率", "unit": ""},
}


def get_global_indices() -> list[dict]:
    """获取全球主要股票指数实时行情。

    Returns:
        list of {code, name, market, price, change, change_percent, updated_at}
    """
    ak = _get_ak()
    results = []

    try:
        # 使用东方财富全球指数实时行情接口
        df = ak.index_global_spot_em()
        if df is None or df.empty:
            return results

        # 标准化列名（不同版本 akshare 列名可能不同）
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if "代码" in cl or "code" in cl or col == "f12":
                col_map["code"] = col
            elif "名称" in cl or "name" in cl or col == "f14":
                col_map["name"] = col
            elif "最新" in cl or "price" in cl or "收盘" in cl or col == "f2":
                col_map["price"] = col
            elif "涨跌幅" in cl or "pct" in cl or col == "f3":
                col_map["pct"] = col
            elif "涨跌额" in cl or "change" in cl or col == "f4":
                col_map["change"] = col

        for _, row in df.iterrows():
            name = str(row.get(col_map.get("name", ""), ""))
            price = row.get(col_map.get("price", ""), 0)
            pct = row.get(col_map.get("pct", ""), 0)
            change = row.get(col_map.get("change", ""), 0)

            # 筛选我们关注的指数
            for code, info in GLOBAL_INDICES.items():
                if info["name"] in name or name in info["name"]:
                    results.append({
                        "code": code,
                        "name": info["name"],
                        "market": info["market"],
                        "price": _safe_float(price),
                        "change": _safe_float(change),
                        "change_percent": _safe_float(pct),
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    break

        _log_global_market_event("akshare", "success", f"获取 {len(results)} 条全球指数", data_count=len(results))

    except Exception as e:
        logger.warning(f"[GlobalMarket] 全球指数获取失败，尝试备选方案: {e}")
        _log_global_market_event("akshare", "failed", str(e)[:1000])
        # 备选：逐个获取
        results = _fetch_indices_fallback()

    return results


def _fetch_indices_fallback() -> list[dict]:
    """备选方案：通过 Tushare index_global 获取最近交易日的全球指数。"""
    try:
        from app.services.data_sync_service import get_pro
        pro = get_pro()

        # 取最近 5 个交易日，避免非交易日无数据
        for days_ago in range(5):
            trade_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            df = pro.index_global(trade_date=trade_date)
            if df is not None and not df.empty:
                break
        else:
            _log_global_market_event("tushare", "failed", "index_global 最近 5 个交易日均无数据")
            return []

        results = []
        for _, row in df.iterrows():
            ts_code = row.get("ts_code", "")
            results.append({
                "code": ts_code,
                "name": row.get("name", ts_code),
                "market": "全球",
                "price": _safe_float(row.get("close")),
                "change": _safe_float(row.get("change")),
                "change_percent": _safe_float(row.get("pct_chg")),
                "updated_at": str(row.get("trade_date", "")),
            })
        _log_global_market_event("tushare", "success", f"通过 index_global 获取 {len(results)} 条全球指数", data_count=len(results))
        return results
    except Exception as e:
        logger.error(f"[GlobalMarket] 备选方案也失败: {e}")
        _log_global_market_event("tushare", "failed", str(e)[:1000])
        return []


# ============================================================
# 商品期货 & 汇率
# ============================================================


def get_commodities_and_forex() -> list[dict]:
    """获取主要商品期货和汇率数据。

    Returns:
        list of {code, name, category, price, change, change_percent, unit, updated_at}
    """
    ak = _get_ak()
    results = []

    # 1. 贵金属 & 能源（通过现货行情）
    try:
        df_spot = ak.spot_goods_em()
        if df_spot is not None and not df_spot.empty:
            _extract_commodity(df_spot, results)
    except Exception as e:
        logger.warning(f"[GlobalMarket] 现货数据获取失败: {e}")

    # 2. 汇率
    try:
        _fetch_forex(ak, results)
    except Exception as e:
        logger.warning(f"[GlobalMarket] 汇率数据获取失败: {e}")

    return results


def _extract_commodity(df, results: list):
    """从现货行情中提取黄金、白银、原油。"""
    targets = {
        "伦敦金": ("GOLD", "贵金属", "美元/盎司"),
        "伦敦银": ("SILVER", "贵金属", "美元/盎司"),
        "WTI": ("CRUDE_OIL", "能源", "美元/桶"),
        "布伦特": ("BRENT_OIL", "能源", "美元/桶"),
    }

    for _, row in df.iterrows():
        name = str(row.get("名称", row.get("name", "")))
        for keyword, (code, category, unit) in targets.items():
            if keyword in name:
                results.append({
                    "code": code,
                    "name": GLOBAL_COMMODITIES[code]["name"],
                    "category": category,
                    "unit": unit,
                    "price": _safe_float(row.get("最新价", row.get("price", 0))),
                    "change": _safe_float(row.get("涨跌额", row.get("change", 0))),
                    "change_percent": _safe_float(row.get("涨跌幅", row.get("pct_chg", 0))),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                break


def _fetch_forex(ak, results: list):
    """获取主要汇率数据。"""
    try:
        # 美元指数
        df_usdx = ak.currency_boc_safe()
        if df_usdx is not None and not df_usdx.empty:
            # 尝试从数据中提取美元/人民币
            for _, row in df_usdx.iterrows():
                name = str(row.get("货币名称", row.get("name", "")))
                if "美元" in name:
                    rate = _safe_float(row.get("中间价", row.get("中行折算价", 0)))
                    if rate and rate > 0:
                        results.append({
                            "code": "USDCNY",
                            "name": "美元/人民币",
                            "category": "汇率",
                            "unit": "",
                            "price": rate / 100 if rate > 100 else rate,  # 中行汇率可能是百元单位
                            "change": 0,
                            "change_percent": 0,
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })
                        break
    except Exception as e:
        logger.warning(f"[GlobalMarket] 汇率详情获取失败: {e}")

    # 美元指数通过外汇接口
    try:
        df_fx = ak.forex_pair_quote_em()
        if df_fx is not None and not df_fx.empty:
            fx_targets = {
                "美元指数": ("USDX", "汇率", ""),
                "欧元美元": ("EURUSD", "汇率", ""),
                "美元日元": ("USDJPY", "汇率", ""),
            }
            for _, row in df_fx.iterrows():
                name = str(row.get("名称", row.get("name", "")))
                for keyword, (code, category, unit) in fx_targets.items():
                    if keyword in name:
                        results.append({
                            "code": code,
                            "name": GLOBAL_COMMODITIES.get(code, {}).get("name", name),
                            "category": category,
                            "unit": unit,
                            "price": _safe_float(row.get("最新价", row.get("price", 0))),
                            "change": _safe_float(row.get("涨跌额", row.get("change", 0))),
                            "change_percent": _safe_float(row.get("涨跌幅", row.get("pct_chg", 0))),
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })
                        break
    except Exception as e:
        logger.warning(f"[GlobalMarket] 外汇行情获取失败: {e}")


# ============================================================
# 聚合接口：一次返回全部国际市场数据
# ============================================================


def get_global_market_overview() -> dict:
    """获取国际市场全貌（指数 + 商品 + 汇率），供首页展示。

    Returns:
        {
            "indices": [...],       # 全球主要指数
            "commodities": [...],   # 黄金、原油等
            "forex": [...],         # 汇率
            "updated_at": "..."
        }
    """
    indices = get_global_indices()
    commodities_and_forex = get_commodities_and_forex()

    # 分离商品和汇率
    commodities = [item for item in commodities_and_forex if item.get("category") != "汇率"]
    forex = [item for item in commodities_and_forex if item.get("category") == "汇率"]

    return {
        "indices": indices,
        "commodities": commodities,
        "forex": forex,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 辅助函数
# ============================================================


def _safe_float(val) -> float:
    """安全转换为 float。"""
    if val is None:
        return 0.0
    try:
        if pd.isna(val):
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _log_global_market_event(source: str, status: str, message: str, data_count: int | None = None):
    """记录全球市场数据获取日志到数据库。"""
    try:
        from app.db.base import SessionLocal
        from app.models.global_market_log import GlobalMarketLog

        db = SessionLocal()
        try:
            db.add(
                GlobalMarketLog(
                    source=source,
                    status=status,
                    message=message,
                    data_count=data_count,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # 落库失败不能影响主流程
        pass
