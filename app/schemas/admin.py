"""后台管理 API 请求/响应模型。

适配 vue-pure-admin 前端所需的数据格式。
"""

from typing import Optional

from pydantic import BaseModel


class AdminLoginRequest(BaseModel):
    """后台登录请求"""
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    """后台登录响应（适配 vue-pure-admin 格式）"""
    success: bool = True
    data: "AdminLoginData"


class AdminLoginData(BaseModel):
    avatar: str = ""
    username: str
    nickname: str = ""
    roles: list[str]
    permissions: list[str]
    access_token: str
    refresh_token: str
    expires: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    success: bool = True
    data: "RefreshTokenData"


class RefreshTokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires: str


class AsyncRoutesResponse(BaseModel):
    success: bool = True
    data: list[dict]


# Pydantic v2 model rebuild for forward references
AdminLoginResponse.model_rebuild()
RefreshTokenResponse.model_rebuild()
