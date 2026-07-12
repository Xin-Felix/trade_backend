from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    role: str = "user"
    is_active: bool = True


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class UserUpdate(BaseModel):
    """用户可修改的个人信息字段。"""
    name: Optional[str] = None
    avatar: Optional[str] = None


class PasswordUpdate(BaseModel):
    """修改密码。"""
    old_password: str
    new_password: str
