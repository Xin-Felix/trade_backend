"""数据浏览 API。

提供通用的数据库表浏览功能，支持按表名查看数据、分页、简单筛选。
仅管理员可用。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import engine, get_db
from app.schemas.user import User

router = APIRouter()

# 允许浏览的表（白名单，避免泄露敏感数据）
_BROWSABLE_TABLES = {
    "stock_basic": "股票基础信息",
    "stock_daily": "日K线",
    "stock_weekly": "周K线",
    "stock_monthly": "月K线",
    "stock_yearly": "年K线",
    "stock_daily_basic": "日线因子(PE/PB等)",
    "stock_fina_indicator": "财务指标",
    "stock_moneyflow": "个股资金流向",
    "moneyflow_hsgt": "沪深港通资金",
    "sector_moneyflow_industry": "行业板块资金流",
    "sector_moneyflow_concept": "概念板块资金流",
    "index_basic": "指数基础信息",
    "index_daily": "指数日线",
    "stock_limit": "涨跌停",
    "top_list": "龙虎榜明细",
    "top_inst": "龙虎榜机构",
    "ths_index": "同花顺指数",
    "ths_daily": "同花顺指数日线",
    "ths_member": "同花顺成分股",
    "stock_concept": "股票概念映射",
    "users": "用户表",
    "watchlist": "自选股",
}


@router.get("/tables")
async def get_table_list(user: User = Depends(get_current_user)):
    """获取可浏览的数据表列表及行数统计。"""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    tables = []
    for table_name, label in _BROWSABLE_TABLES.items():
        if table_name not in existing_tables:
            continue
        tables.append({
            "name": table_name,
            "label": label,
        })

    return {"success": True, "data": tables}


@router.get("/tables/{table_name}")
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    ts_code: str | None = Query(None, description="按 ts_code 筛选"),
    trade_date: str | None = Query(None, description="按 trade_date 筛选 (YYYYMMDD)"),
    keyword: str | None = Query(None, description="通用关键词搜索"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查看指定表的数据。"""
    if table_name not in _BROWSABLE_TABLES:
        raise HTTPException(status_code=400, detail=f"不允许浏览表: {table_name}")

    # 获取表的列信息
    insp = inspect(engine)
    if table_name not in insp.get_table_names():
        raise HTTPException(status_code=404, detail="表不存在")

    columns_info = insp.get_columns(table_name)
    column_names = [c["name"] for c in columns_info]

    # 构建查询
    where_clauses = []
    params = {}

    if ts_code and "ts_code" in column_names:
        where_clauses.append("ts_code = :ts_code")
        params["ts_code"] = ts_code

    if trade_date and "trade_date" in column_names:
        where_clauses.append("trade_date = :trade_date")
        # 支持 YYYYMMDD 格式转为日期
        params["trade_date"] = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

    if keyword:
        # 在文本类列中搜索（取前几个 varchar 列）
        text_cols = [c["name"] for c in columns_info if "VARCHAR" in str(c["type"]).upper() or "TEXT" in str(c["type"]).upper()]
        if text_cols:
            or_parts = [f"{col}::text ILIKE :keyword" for col in text_cols[:3]]
            where_clauses.append(f"({' OR '.join(or_parts)})")
            params["keyword"] = f"%{keyword}%"

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # 获取总数
    count_sql = f"SELECT COUNT(*) FROM {table_name}{where_sql}"
    with engine.connect() as conn:
        total = conn.execute(text(count_sql), params).scalar() or 0

    # 获取数据（按主键/第一列降序）
    # 确定排序列
    pk_constraint = insp.get_pk_constraint(table_name)
    pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []
    order_col = pk_cols[0] if pk_cols else column_names[0]

    # 对于时序表优先按 trade_date 降序
    if "trade_date" in column_names:
        order_col = "trade_date"

    offset = (page - 1) * page_size
    data_sql = f"SELECT * FROM {table_name}{where_sql} ORDER BY {order_col} DESC LIMIT :limit OFFSET :offset"
    params["limit"] = page_size
    params["offset"] = offset

    with engine.connect() as conn:
        result = conn.execute(text(data_sql), params)
        rows = [dict(row._mapping) for row in result]

    # 序列化（处理日期等类型）
    import decimal
    from datetime import date, datetime

    def serialize(val):
        if val is None:
            return None
        if isinstance(val, (date, datetime)):
            return val.isoformat()
        if isinstance(val, decimal.Decimal):
            return float(val)
        return val

    serialized_rows = [{k: serialize(v) for k, v in row.items()} for row in rows]

    return {
        "success": True,
        "data": {
            "columns": column_names,
            "rows": serialized_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "table_name": table_name,
            "label": _BROWSABLE_TABLES[table_name],
        },
    }


@router.get("/stock-dict")
async def get_stock_dict(
    q: str | None = Query(None, description="搜索关键词（代码/名称/拼音）"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    """获取股票字典（ts_code + name），支持模糊搜索。

    前端用于数据浏览页的 ts_code 筛选下拉框。
    """
    from sqlalchemy import or_, select
    from app.models.stock import StockBasic

    with engine.connect() as conn:
        query = select(StockBasic.ts_code, StockBasic.name, StockBasic.cnspell)

        if q:
            like = f"%{q}%"
            # 前缀匹配优先
            prefix = f"{q}%"
            query = query.where(
                or_(
                    StockBasic.ts_code.ilike(prefix),
                    StockBasic.symbol.ilike(prefix),
                    StockBasic.name.ilike(like),
                    StockBasic.cnspell.ilike(prefix),
                )
            )

        query = query.limit(limit)
        result = conn.execute(query)
        items = [
            {"value": row.ts_code, "label": f"{row.ts_code} {row.name or ''}"}
            for row in result
        ]

    return {"success": True, "data": items}
