from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.db.base import get_db
from app.models.user import User as UserModel
from app.schemas.user import User
from app.services import oss_service


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization Header 中解析 JWT，并查询数据库返回当前用户。

    该函数统一完成：token 校验、用户存在性校验、用户状态校验。
    数据库查询操作放到线程池执行，避免阻塞事件循环。
    所有需要当前用户的接口都应通过 Depends(get_current_user) 获取。
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        public_id: str = payload.get("sub")
        email: str = payload.get("email")
        if public_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    db_user = await run_in_threadpool(
        lambda: db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用"
        )

    return User(
        id=db_user.public_id,
        email=db_user.email,
        name=db_user.name,
        avatar=oss_service.resolve_avatar_url(db_user.avatar),
        role=db_user.role,
        is_active=bool(db_user.is_active),
    )


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> None:
    """校验当前用户是否为管理员，非管理员抛出 403。

    用户角色已由 get_current_user 提供，此处不再查询数据库。
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )


def require_feature(feature_code: str, consume: bool = True):
    """FastAPI 依赖工厂：校验并消费功能权限（积分/会员/每日免费额度）。

    用法：
        @router.post("/chat")
        async def ai_chat(
            body: ChatRequest,
            user: User = Depends(require_feature("ai_chat", consume=True)),
        ):
            ...
    """
    async def _checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        db_user = await run_in_threadpool(
            lambda: db.query(UserModel)
            .filter(UserModel.public_id == user.id, UserModel.is_deleted == 0)
            .first()
        )
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在"
            )

        from app.services import membership_service

        result = await run_in_threadpool(
            membership_service.check_and_consume,
            db,
            db_user,
            feature_code,
            consume,
        )
        if not result["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "feature_code": feature_code,
                    "reason": result["reason"],
                    "required_points": result.get("required_points", 0),
                    "required_tier": result.get("required_tier"),
                    "balance": result.get("balance", 0),
                },
            )

        # 如果是积分消费或免费额度计数，在这里统一 commit，
        # 因为很多只读接口自身不会 commit。
        if consume and result.get("commit_needed"):
            await run_in_threadpool(db.commit)

        return user

    return _checker
