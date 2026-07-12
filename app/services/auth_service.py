import random
import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.models.user import User as UserModel
from app.models.verification_code import VerificationCode
from app.schemas.token import TokenResponse
from app.schemas.user import User


def authenticate_email(db: Session, email: str, password: str) -> TokenResponse:
    """邮箱密码登录：校验 bcrypt 哈希密码并返回 JWT。"""
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if user is None or user.hashed_password is None or not verify_password(password, user.hashed_password):
        raise ValueError("邮箱或密码错误")

    access_token = create_access_token({"sub": user.public_id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.public_id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(id=user.public_id, email=user.email, name=user.name),
    )


def create_user(db: Session, email: str, password: str | None = None, name: str | None = None) -> UserModel:
    """创建用户（注册用），密码使用 bcrypt 哈希。"""
    if db.query(UserModel).filter(UserModel.email == email).first():
        raise ValueError("邮箱已存在")

    user = UserModel(
        email=email,
        hashed_password=get_password_hash(password) if password else None,
        name=name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_apple(identity_token: str, user_id: str) -> TokenResponse:
    """
    Apple 登录（占位）。
    真实流程：
    1. 用 Apple 公钥验证 identity_token
    2. 根据 sub（user_id）查找或创建用户
    3. 返回自己的 JWT
    """
    # TODO: 验证 Apple identity token
    user = User(id=user_id, email="apple_user@example.com", name="Apple User")
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.id})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


CODE_TTL_MINUTES = 5
MAX_ACTIVE_CODES = 3


def generate_verification_code(length: int = 6) -> str:
    """生成纯数字验证码。"""
    return "".join(random.choices(string.digits, k=length))


def create_verification_code(db: Session, email: str, purpose: str = "login") -> str:
    """为指定邮箱创建验证码，过期前限制未使用验证码数量。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=CODE_TTL_MINUTES)
    active_count = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.used_at.is_(None),
            VerificationCode.expires_at > datetime.now(timezone.utc),
            VerificationCode.created_at > cutoff,
        )
        .count()
    )
    if active_count >= MAX_ACTIVE_CODES:
        raise ValueError("请求过于频繁，请稍后再试")

    code = generate_verification_code()
    record = VerificationCode(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
    )
    db.add(record)
    db.commit()
    return code


def verify_email_code(db: Session, email: str, code: str, purpose: str = "login") -> UserModel:
    """
    校验邮箱验证码。
    - 验证码必须未使用且未过期
    - 校验成功后标记为已使用
    - 如果用户不存在则自动创建（注册）
    """
    record = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.email == email,
            VerificationCode.code == code,
            VerificationCode.purpose == purpose,
            VerificationCode.used_at.is_(None),
            VerificationCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if record is None:
        raise ValueError("验证码错误或已过期")

    record.used_at = datetime.now(timezone.utc)
    db.commit()

    user = db.query(UserModel).filter(UserModel.email == email).first()
    if user is None:
        random_password = secrets.token_urlsafe(32)
        user = create_user(db, email=email, password=random_password, name=email.split("@")[0])

    return user


def issue_token_for_user(user: UserModel) -> TokenResponse:
    """为已有用户签发 JWT。"""
    access_token = create_access_token({"sub": user.public_id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.public_id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(id=user.public_id, email=user.email, name=user.name),
    )


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    """用 refresh token 换取新的 access token 和 refresh token。"""
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        public_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if public_id is None or token_type != "refresh":
            raise ValueError("无效的 refresh token")
    except JWTError as exc:
        raise ValueError("无效的 refresh token") from exc

    user = db.query(UserModel).filter(UserModel.public_id == public_id).first()
    if user is None:
        raise ValueError("用户不存在")
    if not user.is_active:
        raise ValueError("用户已被禁用")

    access_token = create_access_token({"sub": user.public_id, "email": user.email})
    new_refresh_token = create_refresh_token({"sub": user.public_id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=User(id=user.public_id, email=user.email, name=user.name),
    )
