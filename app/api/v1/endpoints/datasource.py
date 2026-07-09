"""数据源管理接口，查看和管理所有已注册的 Tushare 接口信息。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.data_source import DataSource
from app.schemas.user import User

router = APIRouter()


@router.get("/list")
async def list_data_sources(
    category: str = Query("", description="按分类筛选"),
    keyword: str = Query("", description="搜索关键词（接口名/标题）"),
    has_local_table: int | None = Query(None, description="是否有本地表: 1/0"),
    has_permission: int | None = Query(None, description="是否有调用权限: 1/0"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取数据源列表（分页+筛选）。"""
    query = db.query(DataSource)

    if category:
        query = query.filter(DataSource.category.ilike(f"%{category}%"))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            DataSource.api_name.ilike(like) | DataSource.title.ilike(like)
        )
    if has_local_table is not None:
        query = query.filter(DataSource.has_local_table == has_local_table)
    if has_permission is not None:
        query = query.filter(DataSource.has_permission == has_permission)

    total = query.count()
    items = query.order_by(DataSource.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "data": {
            "list": [_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/categories")
async def list_categories(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取所有分类列表。"""
    rows = db.query(DataSource.category).distinct().all()
    categories = sorted(set(r[0] for r in rows))
    return {"success": True, "data": categories}


def _to_dict(ds: DataSource) -> dict:
    return {
        "id": ds.id,
        "api_name": ds.api_name,
        "title": ds.title,
        "category": ds.category,
        "description": ds.description,
        "proxy_path": ds.proxy_path,
        "doc_url": ds.doc_url,
        "has_local_table": ds.has_local_table == 1,
        "local_table_name": ds.local_table_name,
        "enabled": ds.enabled == 1,
        "has_permission": ds.has_permission,
        "permission_msg": ds.permission_msg,
    }


@router.post("/check-permission")
async def check_all_permissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """触发权限检测（后台执行，逐个调 Tushare 接口检查权限）。"""
    import threading
    from app.services.datasource_permission import check_permissions_async
    t = threading.Thread(target=check_permissions_async, daemon=True)
    t.start()
    return {"success": True, "message": "权限检测已开始，请稍后刷新查看结果"}


@router.post("/check-permission/{api_name}")
async def check_single_permission(
    api_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """检测单个接口权限。"""
    from app.services.datasource_permission import check_single_api
    result = check_single_api(api_name)
    return {"success": True, "data": result}
