"""菜单管理和角色管理的请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 菜单管理
# ---------------------------------------------------------------------------

class MenuItemResponse(BaseModel):
    """菜单项（含 children 嵌套）"""
    id: int
    parent_id: int
    path: str
    name: Optional[str] = None
    component: Optional[str] = None
    redirect: Optional[str] = None
    title: str
    icon: Optional[str] = None
    menu_type: int
    rank: int
    show_link: int
    keep_alive: int
    children: list["MenuItemResponse"] = []


class MenuTreeResponse(BaseModel):
    success: bool = True
    data: list[MenuItemResponse]


class MenuCreateRequest(BaseModel):
    parent_id: int = 0
    path: str
    name: Optional[str] = None
    component: Optional[str] = None
    redirect: Optional[str] = None
    title: str
    icon: Optional[str] = None
    menu_type: int = 1
    rank: int = 0
    show_link: int = 1
    keep_alive: int = 0


class MenuUpdateRequest(BaseModel):
    parent_id: Optional[int] = None
    path: Optional[str] = None
    name: Optional[str] = None
    component: Optional[str] = None
    redirect: Optional[str] = None
    title: Optional[str] = None
    icon: Optional[str] = None
    menu_type: Optional[int] = None
    rank: Optional[int] = None
    show_link: Optional[int] = None
    keep_alive: Optional[int] = None


# ---------------------------------------------------------------------------
# 角色管理
# ---------------------------------------------------------------------------

class RoleItem(BaseModel):
    """角色项"""
    role: str
    name: str
    description: str | None = None
    user_count: int
    menu_ids: list[int]


class RoleListResponse(BaseModel):
    success: bool = True
    data: list[RoleItem]


class RoleCreateRequest(BaseModel):
    """新增角色"""
    code: str
    name: str
    description: str | None = None


class RoleUpdateRequest(BaseModel):
    """编辑角色"""
    name: str | None = None
    description: str | None = None


class RoleMenuUpdateRequest(BaseModel):
    """分配角色菜单权限"""
    menu_ids: list[int]


class OperationResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"


MenuItemResponse.model_rebuild()
MenuTreeResponse.model_rebuild()
