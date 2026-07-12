"""H5 页面管理接口。

提供后台管理所需的 CRUD，以及面向 App WebView 的公开读取接口。
"""

import bleach
import markdown
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.h5_page import H5Page
from app.schemas.h5_page import (
    H5PageCreateRequest,
    H5PageDetailResponse,
    H5PageListResponse,
    H5PageOperationResponse,
    H5PagePublishRequest,
    H5PagePublicResponse,
    H5PageUpdateRequest,
)
from app.schemas.user import User

router = APIRouter()

# 允许在富文本中保留的基础标签和属性
_ALLOWED_TAGS = bleach.ALLOWED_TAGS | {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "pre",
    "code",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "a",
    "img",
    "div",
    "span",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
_ALLOWED_ATTRIBUTES = {
    **bleach.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "title", "width", "height"],
    "div": ["class", "style"],
    "span": ["class", "style"],
    "p": ["class", "style"],
    "h1": ["class", "style"],
    "h2": ["class", "style"],
    "h3": ["class", "style"],
    "h4": ["class", "style"],
    "h5": ["class", "style"],
    "h6": ["class", "style"],
    "table": ["class", "style"],
    "th": ["class", "style"],
    "td": ["class", "style"],
}


def _to_dict(page: H5Page) -> dict:
    return {
        "id": page.id,
        "slug": page.slug,
        "title": page.title,
        "content_type": page.content_type,
        "content": page.content,
        "is_published": page.is_published == 1,
        "created_at": page.created_at.strftime("%Y-%m-%d %H:%M:%S") if page.created_at else "",
        "updated_at": page.updated_at.strftime("%Y-%m-%d %H:%M:%S") if page.updated_at else "",
    }


def _render_html(page: H5Page) -> str:
    """根据内容类型渲染 HTML。"""
    if page.content_type == "markdown":
        html = markdown.markdown(
            page.content,
            extensions=["extra", "nl2br", "toc", "fenced_code"],
        )
    else:
        html = page.content or ""
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, strip=True)


@router.get("", response_model=H5PageListResponse)
async def list_h5_pages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="搜索标题/slug"),
    is_published: int | None = Query(None, description="发布状态: 1/0"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取 H5 页面列表（分页 + 搜索）。"""
    query = db.query(H5Page)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(H5Page.title.ilike(like), H5Page.slug.ilike(like))
        )
    if is_published is not None:
        query = query.filter(H5Page.is_published == (1 if is_published else 0))

    total = query.count()
    items = (
        query.order_by(H5Page.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return H5PageListResponse(
        data={
            "list": [_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("", response_model=H5PageDetailResponse)
async def create_h5_page(
    payload: H5PageCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建 H5 页面。"""
    existing = db.query(H5Page).filter(H5Page.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"页面标识已存在: {payload.slug}")

    page = H5Page(
        slug=payload.slug,
        title=payload.title,
        content_type=payload.content_type,
        content=payload.content,
        is_published=1 if payload.is_published else 0,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return H5PageDetailResponse(data=_to_dict(page))


@router.get("/{page_id}", response_model=H5PageDetailResponse)
async def get_h5_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取 H5 页面详情。"""
    page = db.query(H5Page).filter(H5Page.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    return H5PageDetailResponse(data=_to_dict(page))


@router.put("/{page_id}", response_model=H5PageDetailResponse)
async def update_h5_page(
    page_id: int,
    payload: H5PageUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新 H5 页面。"""
    page = db.query(H5Page).filter(H5Page.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")

    data = payload.model_dump(exclude_none=True)
    if "is_published" in data:
        data["is_published"] = 1 if data["is_published"] else 0

    for field, value in data.items():
        setattr(page, field, value)

    db.commit()
    db.refresh(page)
    return H5PageDetailResponse(data=_to_dict(page))


@router.put("/{page_id}/publish", response_model=H5PageOperationResponse)
async def publish_h5_page(
    page_id: int,
    payload: H5PagePublishRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发布/下架 H5 页面。"""
    page = db.query(H5Page).filter(H5Page.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")

    page.is_published = 1 if payload.is_published else 0
    db.commit()
    label = "发布" if payload.is_published else "下架"
    return H5PageOperationResponse(message=f"{label}成功")


@router.delete("/{page_id}", response_model=H5PageOperationResponse)
async def delete_h5_page(
    page_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除 H5 页面。"""
    page = db.query(H5Page).filter(H5Page.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")

    db.delete(page)
    db.commit()
    return H5PageOperationResponse(message="删除成功")


# ---------------------------------------------------------------------------
# 公开接口（供 App WebView 调用，无需登录）
# ---------------------------------------------------------------------------


@router.get("/public/{slug}", response_model=H5PagePublicResponse)
async def get_public_h5_page(
    slug: str,
    db: Session = Depends(get_db),
):
    """按 slug 获取已发布的 H5 页面内容。"""
    page = (
        db.query(H5Page)
        .filter(H5Page.slug == slug, H5Page.is_published == 1)
        .first()
    )
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在或未发布")

    return H5PagePublicResponse(
        data={
            "slug": page.slug,
            "title": page.title,
            "content_type": page.content_type,
            "content": page.content,
            "rendered_html": _render_html(page),
        }
    )
