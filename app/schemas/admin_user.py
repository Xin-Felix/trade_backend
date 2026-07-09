"""用户管理相关的请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel


class UserListQuery(BaseModel):
    """用户列表查询参数"""
    page: int = 1
    page_size: int = 20
    keyword: Optional[str] = None  # 邮箱/名称模糊搜索
    role: Optional[str] = None  # 角色筛选


class UserListItem(BaseModel):
    """用户列表项"""
    id: str  # public_id
    email: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    is_active: int
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    """用户列表响应"""
    success: bool = True
    data: "UserListData"


class UserListData(BaseModel):
    list: list[UserListItem]
    total: int
    page: int
    page_size: int


class UserUpdateRequest(BaseModel):
    """编辑用户请求"""
    role: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[int] = None


class UserResetPasswordRequest(BaseModel):
    """重置用户密码"""
    password: str


class UserOperationResponse(BaseModel):
    """通用操作响应"""
    success: bool = True
    message: str = "操作成功"


UserListResponse.model_rebuild()
