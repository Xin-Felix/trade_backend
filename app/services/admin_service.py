"""后台管理服务层。

处理管理员登录、权限查询、菜单获取等逻辑。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models.admin import AdminMenu, AdminPermission, RoleMenu, RolePermission
from app.models.user import User as UserModel
from app.schemas.admin import (
    AdminLoginData,
    AdminLoginResponse,
    RefreshTokenData,
    RefreshTokenResponse,
)
from app.services import oss_service


def admin_login(db: Session, username: str, password: str) -> AdminLoginResponse:
    """管理员登录。

    支持用邮箱作为 username 登录，校验密码和角色。
    """
    user = (
        db.query(UserModel)
        .filter(UserModel.email == username, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise ValueError("用户不存在")
    if not user.hashed_password or not verify_password(password, user.hashed_password):
        raise ValueError("密码错误")
    if user.role not in ("admin",):
        raise ValueError("无管理员权限")
    if not user.is_active:
        raise ValueError("账号已被禁用")

    # 生成 token
    access_token = create_access_token({"sub": user.public_id, "email": user.email, "role": user.role})
    refresh_token = create_access_token(
        {"sub": user.public_id, "type": "refresh"},
        expires_delta=timedelta(days=30),
    )
    expires = (datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)).strftime(
        "%Y/%m/%d %H:%M:%S"
    )

    # 获取按钮级权限
    permissions = _get_role_permissions(db, user.role)

    return AdminLoginResponse(
        data=AdminLoginData(
            avatar=oss_service.resolve_avatar_url(user.avatar) or "",
            username=user.email,
            nickname=user.name or user.email.split("@")[0],
            roles=[user.role],
            permissions=permissions,
            access_token=access_token,
            refresh_token=refresh_token,
            expires=expires,
        )
    )


def admin_refresh_token(db: Session, refresh_token: str) -> RefreshTokenResponse:
    """刷新 access token。"""
    from jose import JWTError, jwt

    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        public_id = payload.get("sub")
        token_type = payload.get("type")
        if not public_id or token_type != "refresh":
            raise ValueError("无效的 refresh token")
    except JWTError:
        raise ValueError("无效的 refresh token")

    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise ValueError("用户不存在")

    new_access_token = create_access_token({"sub": user.public_id, "email": user.email, "role": user.role})
    new_refresh_token = create_access_token(
        {"sub": user.public_id, "type": "refresh"},
        expires_delta=timedelta(days=30),
    )
    expires = (datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)).strftime(
        "%Y/%m/%d %H:%M:%S"
    )

    return RefreshTokenResponse(
        data=RefreshTokenData(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires=expires,
        )
    )


def get_async_routes(db: Session, role: str) -> list[dict]:
    """根据角色获取动态路由/菜单树。

    admin 角色返回所有菜单，其他角色根据 role_menus 表过滤。
    """
    if role == "admin":
        menus = db.query(AdminMenu).order_by(AdminMenu.rank.asc(), AdminMenu.id.asc()).all()
    else:
        menu_ids = [
            rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role == role).all()
        ]
        if not menu_ids:
            return []
        menus = (
            db.query(AdminMenu)
            .filter(AdminMenu.id.in_(menu_ids))
            .order_by(AdminMenu.rank.asc(), AdminMenu.id.asc())
            .all()
        )

    return _build_menu_tree(menus)


def _build_menu_tree(menus: list[AdminMenu]) -> list[dict]:
    """将扁平菜单列表构建为前端需要的嵌套树结构。"""
    menu_map: dict[int, dict] = {}
    roots: list[dict] = []

    for m in menus:
        import json

        extra = {}
        if m.extra_meta:
            try:
                extra = json.loads(m.extra_meta)
            except (json.JSONDecodeError, TypeError):
                pass

        meta = {
            "title": m.title,
            "icon": m.icon,
        }
        if m.show_link == 0:
            meta["showLink"] = False
        if m.keep_alive == 1:
            meta["keepAlive"] = True
        if extra:
            meta.update(extra)

        node = {
            "path": m.path,
            "meta": meta,
        }
        if m.name:
            node["name"] = m.name
        if m.component:
            node["component"] = m.component
        if m.redirect:
            node["redirect"] = m.redirect

        node["children"] = []
        menu_map[m.id] = node

    # 构建树
    for m in menus:
        node = menu_map[m.id]
        if m.parent_id == 0:
            roots.append(node)
        else:
            parent = menu_map.get(m.parent_id)
            if parent:
                parent["children"].append(node)

    # 清理空 children
    def clean_children(nodes: list[dict]):
        for n in nodes:
            if not n["children"]:
                del n["children"]
            else:
                clean_children(n["children"])

    clean_children(roots)
    return roots


def ensure_last_admin_protected(
    db: Session,
    user: UserModel,
    new_role: str | None = None,
    new_is_active: int | None = None,
) -> None:
    """禁止将最后一位管理员降权或禁用。"""
    if user.role != "admin":
        return

    # 仍然是 admin 且保持启用，无需保护
    if (new_role is None or new_role == "admin") and (new_is_active is None or new_is_active == 1):
        return

    other_admins = (
        db.query(UserModel)
        .filter(
            UserModel.id != user.id,
            UserModel.role == "admin",
            UserModel.is_active == 1,
            UserModel.is_deleted == 0,
        )
        .count()
    )
    if other_admins == 0:
        raise ValueError("系统中至少需要保留一位管理员")


def _get_role_permissions(db: Session, role: str) -> list[str]:
    """获取角色的所有按钮级权限标识。"""
    if role == "admin":
        return ["*:*:*"]

    perm_ids = [
        rp.permission_id for rp in db.query(RolePermission).filter(RolePermission.role == role).all()
    ]
    if not perm_ids:
        return []

    perms = db.query(AdminPermission).filter(AdminPermission.id.in_(perm_ids)).all()
    return [p.code for p in perms]
