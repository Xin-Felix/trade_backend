"""后台管理权限模型。

采用简单 RBAC：
- admin_roles: 角色定义
- admin_menus: 后台菜单/路由定义
- admin_permissions: 按钮级权限定义
- role_menus: 角色 ↔ 菜单关联
- role_permissions: 角色 ↔ 按钮权限关联
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.db.base import Base


class AdminRole(Base):
    """角色定义表"""

    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, comment="角色标识，如 admin / editor")
    name = Column(String(100), nullable=False, comment="角色名称")
    description = Column(String(255), nullable=True, comment="角色描述")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AdminMenu(Base):
    """后台菜单/路由表"""

    __tablename__ = "admin_menus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, nullable=False, server_default="0", comment="父菜单 ID，0 表示顶级")
    path = Column(String(255), nullable=False, comment="路由路径")
    name = Column(String(100), nullable=True, comment="路由 name（唯一标识）")
    component = Column(String(255), nullable=True, comment="前端组件路径")
    redirect = Column(String(255), nullable=True, comment="重定向地址")
    title = Column(String(100), nullable=False, comment="菜单标题")
    icon = Column(String(100), nullable=True, comment="菜单图标")
    menu_type = Column(Integer, nullable=False, server_default="1", comment="类型: 0=目录 1=菜单 2=按钮")
    rank = Column(Integer, nullable=False, server_default="0", comment="排序（越小越靠前）")
    show_link = Column(Integer, nullable=False, server_default="1", comment="是否显示: 1=是 0=否")
    keep_alive = Column(Integer, nullable=False, server_default="0", comment="是否缓存: 1=是 0=否")
    extra_meta = Column(Text, nullable=True, comment="额外 meta 配置（JSON）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AdminPermission(Base):
    """按钮级权限定义"""

    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    menu_id = Column(
        Integer,
        ForeignKey("admin_menus.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属菜单 ID",
    )
    code = Column(String(100), nullable=False, unique=True, comment="权限标识，如 system:user:add")
    name = Column(String(100), nullable=False, comment="权限名称")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class RoleMenu(Base):
    """角色 ↔ 菜单关联"""

    __tablename__ = "role_menus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(
        String(20),
        ForeignKey("admin_roles.code", ondelete="CASCADE"),
        nullable=False,
        comment="角色标识: admin / user",
    )
    menu_id = Column(
        Integer,
        ForeignKey("admin_menus.id", ondelete="CASCADE"),
        nullable=False,
        comment="菜单 ID",
    )


class RolePermission(Base):
    """角色 ↔ 按钮权限关联"""

    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(
        String(20),
        ForeignKey("admin_roles.code", ondelete="CASCADE"),
        nullable=False,
        comment="角色标识: admin / user",
    )
    permission_id = Column(
        Integer,
        ForeignKey("admin_permissions.id", ondelete="CASCADE"),
        nullable=False,
        comment="权限 ID",
    )
