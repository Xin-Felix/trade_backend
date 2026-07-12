"""自选股服务：增删查，按加入时间排序。"""

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.watchlist import Watchlist
from app.schemas.watchlist import WatchlistItem


class WatchlistLimitExceededError(Exception):
    """自选股数量超过上限。"""

    def __init__(self, limit: int = 20):
        self.limit = limit
        super().__init__(f"自选股最多可添加 {limit} 只，建议精简票池后再添加")


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


def get_watchlist(user_id: str) -> list[WatchlistItem]:
    """获取用户自选股列表，按加入时间升序排列。"""
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Watchlist)
                .where(Watchlist.user_id == user_id, Watchlist.is_deleted == 0)
                .order_by(Watchlist.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            WatchlistItem(
                code=r.code,
                name=r.name,
                ts_code=r.ts_code,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]
    finally:
        db.close()


def add_to_watchlist(user_id: str, code: str, name: str, limit: int = 20) -> WatchlistItem:
    """添加自选股；已存在（含已软删除）则恢复或忽略；达到上限时抛出异常。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        # 查询包含已软删除记录，便于恢复
        existing = db.execute(
            select(Watchlist).where(
                Watchlist.user_id == user_id,
                Watchlist.ts_code == ts_code,
            )
        ).scalar_one_or_none()

        if existing:
            if existing.is_deleted == 1:
                existing.is_deleted = 0
                existing.name = name.strip()
                existing.code = code.strip()
                db.commit()
                db.refresh(existing)
            return WatchlistItem(
                code=existing.code,
                name=existing.name,
                ts_code=existing.ts_code,
                created_at=existing.created_at.isoformat() if existing.created_at else "",
            )

        # 检查数量上限（仅统计未删除）
        count = db.execute(
            select(func.count(Watchlist.id)).where(
                Watchlist.user_id == user_id,
                Watchlist.is_deleted == 0,
            )
        ).scalar()
        if count is not None and count >= limit:
            raise WatchlistLimitExceededError(limit)

        item = Watchlist(
            user_id=user_id,
            ts_code=ts_code,
            code=code.strip(),
            name=name.strip(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        return WatchlistItem(
            code=item.code,
            name=item.name,
            ts_code=item.ts_code,
            created_at=item.created_at.isoformat() if item.created_at else "",
        )
    finally:
        db.close()


def remove_from_watchlist(user_id: str, code: str) -> bool:
    """软删除自选股，返回是否成功删除。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        item = db.execute(
            select(Watchlist).where(
                Watchlist.user_id == user_id,
                Watchlist.ts_code == ts_code,
                Watchlist.is_deleted == 0,
            )
        ).scalar_one_or_none()

        if item is None:
            return False

        item.is_deleted = 1
        db.commit()
        return True
    finally:
        db.close()


def is_in_watchlist(user_id: str, code: str) -> bool:
    """判断某只股票是否在用户自选股中。"""
    ts_code = _normalize_code(code)
    db = SessionLocal()
    try:
        item = db.execute(
            select(Watchlist.id).where(
                Watchlist.user_id == user_id,
                Watchlist.ts_code == ts_code,
                Watchlist.is_deleted == 0,
            )
        ).scalar_one_or_none()
        return item is not None
    finally:
        db.close()
