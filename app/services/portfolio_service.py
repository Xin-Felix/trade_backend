"""持仓服务：增删查改，按标记时间排序。"""

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.portfolio import Portfolio
from app.schemas.portfolio import PortfolioItem


class PortfolioLimitExceededError(Exception):
    """持仓数量超过上限。"""

    def __init__(self, limit: int = 10):
        self.limit = limit
        super().__init__(f"持仓最多可添加 {limit} 只，建议精简票池后再添加")


def _normalize_code(code: str) -> str:
    """标准化为 Tushare 格式。"""
    code = code.strip().upper()
    if "." in code:
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith("0") or code.startswith("3"):
        return f"{code}.SZ"
    if code.startswith("8") or code.startswith("4"):
        return f"{code}.BJ"
    if code.isdigit() and len(code) >= 5:
        return f"{code}.HK"
    return code


def _portfolio_item_from_row(row: Portfolio) -> PortfolioItem:
    """从 ORM 行构造 PortfolioItem Schema。"""
    return PortfolioItem(
        code=row.code,
        name=row.name,
        ts_code=row.ts_code,
        cost_price=float(row.cost_price) if row.cost_price is not None else None,
        quantity=float(row.quantity) if row.quantity is not None else None,
        is_margin=bool(row.is_margin) if row.is_margin is not None else False,
        note=row.note,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def get_portfolio(user_id: str) -> list[PortfolioItem]:
    """获取用户持仓列表，按标记时间升序排列。"""
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Portfolio)
                .where(Portfolio.user_id == user_id, Portfolio.is_deleted == 0)
                .order_by(Portfolio.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [_portfolio_item_from_row(r) for r in rows]
    finally:
        db.close()


def add_to_portfolio(
    user_id: str,
    code: str,
    name: str,
    cost_price: float | None = None,
    quantity: float | None = None,
    is_margin: bool | None = None,
    note: str | None = None,
    limit: int = 10,
) -> PortfolioItem:
    """添加持仓；已存在（含已软删除）则恢复或更新；达到上限时抛出异常。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        # 查询包含已软删除记录，便于恢复
        existing = db.execute(
            select(Portfolio).where(
                Portfolio.user_id == user_id,
                Portfolio.ts_code == ts_code,
            )
        ).scalar_one_or_none()

        if existing:
            if existing.is_deleted == 1:
                existing.is_deleted = 0
            if note is not None:
                existing.note = note
            if cost_price is not None:
                existing.cost_price = cost_price
            if quantity is not None:
                existing.quantity = quantity
            if is_margin is not None:
                existing.is_margin = is_margin
            db.commit()
            db.refresh(existing)
            return _portfolio_item_from_row(existing)

        # 检查数量上限（仅统计未删除）
        count = db.execute(
            select(func.count(Portfolio.id)).where(
                Portfolio.user_id == user_id,
                Portfolio.is_deleted == 0,
            )
        ).scalar()
        if count is not None and count >= limit:
            raise PortfolioLimitExceededError(limit)

        item = Portfolio(
            user_id=user_id,
            ts_code=ts_code,
            code=code.strip(),
            name=name.strip(),
            cost_price=cost_price,
            quantity=quantity,
            is_margin=is_margin if is_margin is not None else False,
            note=note,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        return _portfolio_item_from_row(item)
    finally:
        db.close()


def update_portfolio(
    user_id: str,
    code: str,
    cost_price: float | None = None,
    quantity: float | None = None,
    is_margin: bool | None = None,
    note: str | None = None,
) -> PortfolioItem | None:
    """部分更新持仓信息；找不到返回 None。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        existing = db.execute(
            select(Portfolio).where(
                Portfolio.user_id == user_id,
                Portfolio.ts_code == ts_code,
                Portfolio.is_deleted == 0,
            )
        ).scalar_one_or_none()

        if existing is None:
            return None

        if note is not None:
            existing.note = note
        if cost_price is not None:
            existing.cost_price = cost_price
        if quantity is not None:
            existing.quantity = quantity
        if is_margin is not None:
            existing.is_margin = is_margin

        db.commit()
        db.refresh(existing)
        return _portfolio_item_from_row(existing)
    finally:
        db.close()


def remove_from_portfolio(user_id: str, code: str) -> bool:
    """软删除持仓，返回是否成功删除。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        item = db.execute(
            select(Portfolio).where(
                Portfolio.user_id == user_id,
                Portfolio.ts_code == ts_code,
                Portfolio.is_deleted == 0,
            )
        ).scalar_one_or_none()

        if item is None:
            return False

        item.is_deleted = 1
        db.commit()
        return True
    finally:
        db.close()


def is_in_portfolio(user_id: str, code: str) -> bool:
    """判断某只股票是否在用户持仓中。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        item = db.execute(
            select(Portfolio.id).where(
                Portfolio.user_id == user_id,
                Portfolio.ts_code == ts_code,
                Portfolio.is_deleted == 0,
            )
        ).scalar_one_or_none()
        return item is not None
    finally:
        db.close()
