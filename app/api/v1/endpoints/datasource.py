"""数据源管理接口。

统一管理所有接入的数据源（Tushare / AKShare / 自定义），
提供列表查询、分类统计、概览摘要和权限检测功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer as SAInteger
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.data_source import DataSource
from app.schemas.user import User

router = APIRouter()


# ============================================================
# 查询接口
# ============================================================


@router.get("/list")
async def list_data_sources(
    provider: str = Query("", description="按提供商筛选: tushare/akshare/custom"),
    category: str = Query("", description="按分类筛选"),
    keyword: str = Query("", description="搜索关键词（接口名/标题/描述）"),
    has_local_table: int | None = Query(None, description="是否有本地表: 1/0"),
    has_permission: int | None = Query(None, description="是否有调用权限: 1/0/-1"),
    enabled: int | None = Query(None, description="是否启用: 1/0"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取数据源列表（分页+筛选）。

    支持按 provider、分类、关键词等多维度筛选。
    """
    query = db.query(DataSource)

    if provider:
        query = query.filter(DataSource.provider == provider)
    if category:
        query = query.filter(DataSource.category.ilike(f"%{category}%"))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            DataSource.api_name.ilike(like)
            | DataSource.title.ilike(like)
            | DataSource.description.ilike(like)
        )
    if has_local_table is not None:
        query = query.filter(DataSource.has_local_table == has_local_table)
    if has_permission is not None:
        query = query.filter(DataSource.has_permission == has_permission)
    if enabled is not None:
        query = query.filter(DataSource.enabled == enabled)

    total = query.count()
    items = (
        query.order_by(DataSource.provider.asc(), DataSource.category.asc(), DataSource.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "data": {
            "list": [_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/overview")
async def datasource_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """数据源概览统计。

    返回各 provider 的接口数量、分类数、本地表数、权限统计等。
    """
    # 按 provider 统计
    provider_stats = (
        db.query(
            DataSource.provider,
            sql_func.count(DataSource.id).label("total"),
            sql_func.sum(DataSource.has_local_table).label("local_table_count"),
            sql_func.sum(
                sql_func.cast(DataSource.has_permission == 1, SAInteger)
            ).label("permitted_count"),
            sql_func.sum(
                sql_func.cast(DataSource.enabled == 1, SAInteger)
            ).label("enabled_count"),
        )
        .group_by(DataSource.provider)
        .all()
    )

    providers = []
    for row in provider_stats:
        providers.append({
            "provider": row.provider,
            "total": row.total,
            "local_table_count": int(row.local_table_count or 0),
            "permitted_count": int(row.permitted_count or 0),
            "enabled_count": int(row.enabled_count or 0),
        })

    # 总计
    total = db.query(sql_func.count(DataSource.id)).scalar()
    total_local = db.query(sql_func.count(DataSource.id)).filter(DataSource.has_local_table == 1).scalar()

    return {
        "success": True,
        "data": {
            "total": total,
            "total_local_tables": total_local,
            "providers": providers,
        },
    }


@router.get("/providers")
async def list_providers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取所有数据源提供商列表。"""
    rows = db.query(DataSource.provider).distinct().all()
    return {"success": True, "data": sorted(r[0] for r in rows)}


@router.get("/categories")
async def list_categories(
    provider: str = Query("", description="按提供商筛选"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取所有分类列表（可按 provider 筛选）。"""
    query = db.query(DataSource.category).distinct()
    if provider:
        query = query.filter(DataSource.provider == provider)
    rows = query.all()
    categories = sorted(set(r[0] for r in rows))
    return {"success": True, "data": categories}


@router.get("/doc/{provider}/{api_name}")
async def get_api_doc(
    provider: str,
    api_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取单个接口的详细文档信息。"""
    ds = (
        db.query(DataSource)
        .filter(DataSource.provider == provider, DataSource.api_name == api_name)
        .first()
    )
    if not ds:
        raise HTTPException(status_code=404, detail=f"未找到接口: {provider}/{api_name}")
    return {"success": True, "data": _to_dict(ds)}


# ============================================================
# 权限检测
# ============================================================


@router.post("/check-permission")
async def check_all_permissions(
    provider: str = Query("tushare", description="要检测的 provider"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """触发权限检测（后台执行）。

    目前仅支持 tushare 的权限检测。
    """
    if provider != "tushare":
        return {"success": True, "message": f"暂不支持 {provider} 的权限检测"}

    import threading
    from app.services.datasource_permission import check_permissions_async
    t = threading.Thread(target=check_permissions_async, daemon=True)
    t.start()
    return {"success": True, "message": "权限检测已开始，请稍后刷新查看结果"}


@router.post("/check-permission/{api_name}")
async def check_single_permission(
    api_name: str,
    provider: str = Query("tushare", description="provider"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """检测单个接口权限。"""
    if provider != "tushare":
        return {"success": True, "data": {"has_permission": -1, "message": f"暂不支持 {provider} 的权限检测"}}

    from app.services.datasource_permission import check_single_api
    result = check_single_api(api_name)
    return {"success": True, "data": result}


# ============================================================
# 辅助函数
# ============================================================


def _to_dict(ds: DataSource) -> dict:
    """将 DataSource ORM 对象转为 API 响应字典。"""
    return {
        "id": ds.id,
        "provider": ds.provider,
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
