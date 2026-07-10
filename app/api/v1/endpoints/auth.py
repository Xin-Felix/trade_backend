from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.schemas.auth import EmailCodeRequest, EmailCodeVerifyRequest, EmailLoginRequest
from app.schemas.token import TokenResponse
from app.schemas.user import PasswordUpdate, User, UserUpdate
from app.services import auth_service, email_service

router = APIRouter()


# ============================================================
# 登录 / 注册
# ============================================================


@router.post("/login/email", response_model=TokenResponse)
async def login_email(
    payload: EmailLoginRequest,
    db: Session = Depends(get_db),
):
    try:
        return auth_service.authenticate_email(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


@router.post("/login/apple", response_model=TokenResponse)
async def login_apple(identity_token: str, user_id: str):
    return auth_service.authenticate_apple(identity_token, user_id)


@router.post("/email/code", status_code=status.HTTP_204_NO_CONTENT)
async def send_email_code(payload: EmailCodeRequest, db: Session = Depends(get_db)):
    """发送邮箱验证码到用户邮箱；SMTP 未配置时打印到日志。"""
    try:
        code = auth_service.create_verification_code(db, payload.email, purpose=payload.purpose or "login")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    email_service.send_login_code_email(payload.email, code)
    return None


@router.post("/email/verify", response_model=TokenResponse)
async def verify_email_code(payload: EmailCodeVerifyRequest, db: Session = Depends(get_db)):
    """校验邮箱验证码，新用户自动注册并直接登录。"""
    try:
        user = auth_service.verify_email_code(db, payload.email, payload.code, purpose=payload.purpose or "login")
        return auth_service.issue_token_for_user(user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ============================================================
# 用户信息
# ============================================================


@router.get("/me")
async def get_current_user_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取当前登录用户的完整信息。"""
    from app.models.user import User as UserModel

    db_user = db.query(UserModel).filter(UserModel.public_id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 头像：如果存的是 OSS object_key，生成签名 URL
    avatar_url = _resolve_avatar_url(db_user.avatar)

    return {
        "success": True,
        "data": {
            "id": db_user.public_id,
            "email": db_user.email,
            "name": db_user.name,
            "avatar": avatar_url,
            "role": db_user.role,
            "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
        },
    }


@router.put("/me")
async def update_current_user(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """修改当前用户的个人信息（昵称、头像）。"""
    from app.models.user import User as UserModel

    db_user = db.query(UserModel).filter(UserModel.public_id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if payload.name is not None:
        db_user.name = payload.name
    if payload.avatar is not None:
        db_user.avatar = payload.avatar

    db.commit()
    db.refresh(db_user)

    return {
        "success": True,
        "data": {
            "id": db_user.public_id,
            "email": db_user.email,
            "name": db_user.name,
            "avatar": _resolve_avatar_url(db_user.avatar),
            "role": db_user.role,
        },
    }


@router.put("/me/password")
async def update_password(
    payload: PasswordUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """修改当前用户密码。需要提供旧密码验证。"""
    from app.core.security import get_password_hash, verify_password
    from app.models.user import User as UserModel

    db_user = db.query(UserModel).filter(UserModel.public_id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 验证旧密码
    if not db_user.hashed_password or not verify_password(payload.old_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码不正确")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

    db_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    return {"success": True, "message": "密码修改成功"}


# ============================================================
# 辅助函数
# ============================================================


def _resolve_avatar_url(avatar: str | None) -> str | None:
    """将 avatar 字段解析为可访问的 URL。

    - 如果是 http/https 开头（外部 URL），直接返回
    - 如果是 OSS object_key（如 avatars/2026/07/xxx.jpg），拼接公共访问 URL
    - 如果为空，返回 None
    """
    if not avatar:
        return None
    if avatar.startswith("http://") or avatar.startswith("https://"):
        return avatar
    # 当作 OSS object_key，拼接公共读 URL（Bucket 已设为公共读）
    from app.core.config import settings
    domain = settings.oss_custom_domain or f"{settings.oss_bucket_name}.oss-cn-hangzhou.aliyuncs.com"
    return f"https://{domain}/{avatar}"
