"""后台管理 API 端点。

提供适配 vue-pure-admin 前端所需的登录、刷新 token、获取动态路由等接口。
以及用户管理 CRUD。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    AsyncRoutesResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.schemas.admin_user import (
    UserListItem,
    UserListResponse,
    UserListData,
    UserOperationResponse,
    UserResetPasswordRequest,
    UserUpdateRequest,
)
from app.schemas.user import User
from app.services import admin_service

router = APIRouter()


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    """后台管理员登录（适配 vue-pure-admin 前端格式）。"""
    try:
        return admin_service.admin_login(db, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """刷新 access token。"""
    try:
        return admin_service.admin_refresh_token(db, payload.refreshToken)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get("/async-routes", response_model=AsyncRoutesResponse)
async def get_async_routes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的动态路由/菜单（根据角色过滤）。"""
    db_user = db.query(UserModel).filter(UserModel.public_id == user.id).first()
    role = db_user.role if db_user else "user"
    routes = admin_service.get_async_routes(db, role)
    return AsyncRoutesResponse(data=routes)


# ---------------------------------------------------------------------------
# 用户管理 CRUD
# ---------------------------------------------------------------------------


@router.get("/users", response_model=UserListResponse)
async def get_user_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="邮箱/名称搜索"),
    role: str | None = Query(None, description="角色筛选"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户列表（分页 + 搜索）。"""
    query = db.query(UserModel)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(UserModel.email.ilike(like), UserModel.name.ilike(like)))
    if role:
        query = query.filter(UserModel.role == role)

    total = query.count()
    users = query.order_by(UserModel.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        UserListItem(
            id=u.public_id,
            email=u.email,
            name=u.name,
            avatar=u.avatar,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "",
            updated_at=u.updated_at.strftime("%Y-%m-%d %H:%M:%S") if u.updated_at else "",
        )
        for u in users
    ]

    return UserListResponse(data=UserListData(list=items, total=total, page=page, page_size=page_size))


@router.put("/users/{user_id}", response_model=UserOperationResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑用户信息（角色/名称/状态）。"""
    db_user = db.query(UserModel).filter(UserModel.public_id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if payload.role is not None:
        db_user.role = payload.role
    if payload.name is not None:
        db_user.name = payload.name
    if payload.is_active is not None:
        db_user.is_active = payload.is_active

    db.commit()
    return UserOperationResponse(message="更新成功")


@router.put("/users/{user_id}/reset-password", response_model=UserOperationResponse)
async def reset_user_password(
    user_id: str,
    payload: UserResetPasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重置用户密码。"""
    db_user = db.query(UserModel).filter(UserModel.public_id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    db_user.hashed_password = get_password_hash(payload.password)
    db.commit()
    return UserOperationResponse(message="密码重置成功")


# ---------------------------------------------------------------------------
# 菜单管理 CRUD
# ---------------------------------------------------------------------------

from app.models.admin import AdminMenu, RoleMenu
from app.schemas.admin_menu import (
    MenuCreateRequest,
    MenuItemResponse,
    MenuTreeResponse,
    MenuUpdateRequest,
    OperationResponse,
    RoleItem,
    RoleListResponse,
    RoleMenuUpdateRequest,
)


def _build_menu_tree_list(menus: list[AdminMenu]) -> list[MenuItemResponse]:
    """将扁平菜单构建为嵌套树（用于管理页面展示）。"""
    menu_map: dict[int, MenuItemResponse] = {}
    roots: list[MenuItemResponse] = []

    for m in menus:
        item = MenuItemResponse(
            id=m.id,
            parent_id=m.parent_id,
            path=m.path,
            name=m.name,
            component=m.component,
            redirect=m.redirect,
            title=m.title,
            icon=m.icon,
            menu_type=m.menu_type,
            rank=m.rank,
            show_link=m.show_link,
            keep_alive=m.keep_alive,
            children=[],
        )
        menu_map[m.id] = item

    for m in menus:
        node = menu_map[m.id]
        if m.parent_id == 0:
            roots.append(node)
        else:
            parent = menu_map.get(m.parent_id)
            if parent:
                parent.children.append(node)

    return roots


@router.get("/menus", response_model=MenuTreeResponse)
async def get_menu_tree(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取菜单树（管理页面用，返回全部菜单）。"""
    menus = db.query(AdminMenu).order_by(AdminMenu.rank.asc(), AdminMenu.id.asc()).all()
    tree = _build_menu_tree_list(menus)
    return MenuTreeResponse(data=tree)


@router.post("/menus", response_model=OperationResponse)
async def create_menu(
    payload: MenuCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增菜单。"""
    menu = AdminMenu(
        parent_id=payload.parent_id,
        path=payload.path,
        name=payload.name,
        component=payload.component,
        redirect=payload.redirect,
        title=payload.title,
        icon=payload.icon,
        menu_type=payload.menu_type,
        rank=payload.rank,
        show_link=payload.show_link,
        keep_alive=payload.keep_alive,
    )
    db.add(menu)
    db.commit()
    return OperationResponse(message="创建成功")


@router.put("/menus/{menu_id}", response_model=OperationResponse)
async def update_menu(
    menu_id: int,
    payload: MenuUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑菜单。"""
    menu = db.query(AdminMenu).filter(AdminMenu.id == menu_id).first()
    if menu is None:
        raise HTTPException(status_code=404, detail="菜单不存在")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(menu, field, value)

    db.commit()
    return OperationResponse(message="更新成功")


@router.delete("/menus/{menu_id}", response_model=OperationResponse)
async def delete_menu(
    menu_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除菜单（同时删除子菜单和角色关联）。"""
    # 递归收集所有子菜单 ID
    all_ids = [menu_id]
    queue = [menu_id]
    while queue:
        pid = queue.pop(0)
        children = db.query(AdminMenu.id).filter(AdminMenu.parent_id == pid).all()
        for (cid,) in children:
            all_ids.append(cid)
            queue.append(cid)

    # 删除角色关联
    db.query(RoleMenu).filter(RoleMenu.menu_id.in_(all_ids)).delete(synchronize_session=False)
    # 删除菜单
    db.query(AdminMenu).filter(AdminMenu.id.in_(all_ids)).delete(synchronize_session=False)
    db.commit()
    return OperationResponse(message="删除成功")


# ---------------------------------------------------------------------------
# 角色管理 CRUD
# ---------------------------------------------------------------------------

from app.models.admin import AdminRole
from app.schemas.admin_menu import RoleCreateRequest, RoleUpdateRequest


@router.get("/roles", response_model=RoleListResponse)
async def get_role_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取角色列表（含已分配的菜单 ID 和用户数）。"""
    from sqlalchemy import func

    all_roles = db.query(AdminRole).order_by(AdminRole.id.asc()).all()
    roles = []
    for r in all_roles:
        user_count = db.query(func.count(UserModel.id)).filter(UserModel.role == r.code).scalar() or 0
        menu_ids = [rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role == r.code).all()]
        roles.append(RoleItem(
            role=r.code,
            name=r.name,
            description=r.description,
            user_count=user_count,
            menu_ids=menu_ids,
        ))

    return RoleListResponse(data=roles)


@router.post("/roles", response_model=OperationResponse)
async def create_role(
    payload: RoleCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增角色。"""
    existing = db.query(AdminRole).filter(AdminRole.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色标识已存在")

    db.add(AdminRole(code=payload.code, name=payload.name, description=payload.description))
    db.commit()
    return OperationResponse(message="创建成功")


@router.put("/roles/{role}", response_model=OperationResponse)
async def update_role(
    role: str,
    payload: RoleUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑角色。"""
    db_role = db.query(AdminRole).filter(AdminRole.code == role).first()
    if db_role is None:
        raise HTTPException(status_code=404, detail="角色不存在")

    if payload.name is not None:
        db_role.name = payload.name
    if payload.description is not None:
        db_role.description = payload.description

    db.commit()
    return OperationResponse(message="更新成功")


@router.delete("/roles/{role}", response_model=OperationResponse)
async def delete_role(
    role: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除角色（不允许删除 admin）。"""
    if role == "admin":
        raise HTTPException(status_code=400, detail="不允许删除管理员角色")

    db_role = db.query(AdminRole).filter(AdminRole.code == role).first()
    if db_role is None:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 检查是否有用户在使用该角色
    from sqlalchemy import func
    user_count = db.query(func.count(UserModel.id)).filter(UserModel.role == role).scalar() or 0
    if user_count > 0:
        raise HTTPException(status_code=400, detail=f"该角色下还有 {user_count} 个用户，请先转移用户")

    # 删除角色菜单关联
    db.query(RoleMenu).filter(RoleMenu.role == role).delete(synchronize_session=False)
    # 删除角色
    db.delete(db_role)
    db.commit()
    return OperationResponse(message="删除成功")


@router.put("/roles/{role}/menus", response_model=OperationResponse)
async def update_role_menus(
    role: str,
    payload: RoleMenuUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新角色的菜单权限（全量替换）。"""
    db.query(RoleMenu).filter(RoleMenu.role == role).delete(synchronize_session=False)
    for menu_id in payload.menu_ids:
        db.add(RoleMenu(role=role, menu_id=menu_id))
    db.commit()
    return OperationResponse(message="权限更新成功")
