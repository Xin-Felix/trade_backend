"""每日一言接口。

提供后台管理所需的 CRUD，以及面向 App 首页的公开读取接口。
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db.base import get_db
from app.models.daily_quote import DailyQuote
from app.schemas.daily_quote import (
    DailyQuoteCreateRequest,
    DailyQuoteDetailResponse,
    DailyQuoteListResponse,
    DailyQuoteOperationResponse,
    DailyQuotePublicResponse,
    DailyQuotePublishRequest,
    DailyQuoteUpdateRequest,
)

router = APIRouter()


def _format_date(d: date | None) -> str | None:
    return d.strftime("%Y-%m-%d") if d else None


def _to_dict(quote: DailyQuote) -> dict:
    return {
        "id": quote.id,
        "content": quote.content,
        "author": quote.author,
        "display_date": _format_date(quote.display_date),
        "is_published": quote.is_published == 1,
        "created_at": quote.created_at.strftime("%Y-%m-%d %H:%M:%S") if quote.created_at else "",
        "updated_at": quote.updated_at.strftime("%Y-%m-%d %H:%M:%S") if quote.updated_at else "",
    }


def _get_today_quote(db: Session) -> DailyQuote:
    """按指定日期 > 自动轮播的规则返回当日语录。"""
    today = date.today()

    # 1. 先看今天有没有指定日期的语录
    override = (
        db.query(DailyQuote)
        .filter(DailyQuote.display_date == today, DailyQuote.is_published == 1)
        .order_by(DailyQuote.id.asc())
        .first()
    )
    if override:
        return override

    # 2. 否则从自动轮播池中按日期取模
    pool = (
        db.query(DailyQuote)
        .filter(DailyQuote.is_published == 1, DailyQuote.display_date.is_(None))
        .order_by(DailyQuote.id.asc())
        .all()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="暂无今日语录")

    days_since_epoch = (today - date(1970, 1, 1)).days
    return pool[days_since_epoch % len(pool)]


# ---------------------------------------------------------------------------
# 公开接口（App 首页调用，无需登录）
# ---------------------------------------------------------------------------


@router.get("/today", response_model=DailyQuotePublicResponse)
async def get_today_quote(db: Session = Depends(get_db)):
    """获取今日语录。"""
    quote = _get_today_quote(db)
    return DailyQuotePublicResponse(
        data={
            "id": quote.id,
            "content": quote.content,
            "author": quote.author,
        }
    )


# ---------------------------------------------------------------------------
# 后台管理接口
# ---------------------------------------------------------------------------


@router.get("", response_model=DailyQuoteListResponse)
async def list_daily_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="搜索内容/作者"),
    is_published: int | None = Query(None, description="发布状态: 1/0"),
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取每日一言列表（分页 + 搜索）。"""
    query = db.query(DailyQuote)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(DailyQuote.content.ilike(like), DailyQuote.author.ilike(like))
        )
    if is_published is not None:
        query = query.filter(DailyQuote.is_published == (1 if is_published else 0))

    total = query.count()
    items = (
        query.order_by(DailyQuote.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return DailyQuoteListResponse(
        data={
            "list": [_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("", response_model=DailyQuoteDetailResponse)
async def create_daily_quote(
    payload: DailyQuoteCreateRequest,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建每日一言。"""
    quote = DailyQuote(
        content=payload.content,
        author=payload.author,
        display_date=payload.display_date,
        is_published=1 if payload.is_published else 0,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return DailyQuoteDetailResponse(data=_to_dict(quote))


@router.get("/{quote_id}", response_model=DailyQuoteDetailResponse)
async def get_daily_quote(
    quote_id: int,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取每日一言详情。"""
    quote = db.query(DailyQuote).filter(DailyQuote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="语录不存在")
    return DailyQuoteDetailResponse(data=_to_dict(quote))


@router.put("/{quote_id}", response_model=DailyQuoteDetailResponse)
async def update_daily_quote(
    quote_id: int,
    payload: DailyQuoteUpdateRequest,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新每日一言。"""
    quote = db.query(DailyQuote).filter(DailyQuote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="语录不存在")

    data = payload.model_dump(exclude_unset=True)
    if "is_published" in data:
        data["is_published"] = 1 if data["is_published"] else 0
    if "author" in data:
        author = data["author"]
        if author is None or (isinstance(author, str) and not author.strip()):
            data["author"] = None

    for field, value in data.items():
        setattr(quote, field, value)

    db.commit()
    db.refresh(quote)
    return DailyQuoteDetailResponse(data=_to_dict(quote))


@router.put("/{quote_id}/publish", response_model=DailyQuoteOperationResponse)
async def publish_daily_quote(
    quote_id: int,
    payload: DailyQuotePublishRequest,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """上架/下架每日一言。"""
    quote = db.query(DailyQuote).filter(DailyQuote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="语录不存在")

    quote.is_published = 1 if payload.is_published else 0
    db.commit()
    label = "上架" if payload.is_published else "下架"
    return DailyQuoteOperationResponse(message=f"{label}成功")


@router.delete("/{quote_id}", response_model=DailyQuoteOperationResponse)
async def delete_daily_quote(
    quote_id: int,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除每日一言。"""
    quote = db.query(DailyQuote).filter(DailyQuote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="语录不存在")

    db.delete(quote)
    db.commit()
    return DailyQuoteOperationResponse(message="删除成功")
