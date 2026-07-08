from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.auth import EmailCodeRequest, EmailCodeVerifyRequest, EmailLoginRequest
from app.schemas.token import TokenResponse
from app.services import auth_service, email_service

router = APIRouter()


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
