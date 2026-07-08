from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.user import User as UserModel
from app.services.auth_service import create_user

# 导入所有模型，确保 Base.metadata 能创建表
import app.models  # noqa: F401


_HYPERTABLES = [
    "stock_daily",
    "stock_weekly",
    "stock_monthly",
    "stock_daily_basic",
]


def _ensure_timescale_hypertables():
    """启用 TimescaleDB 扩展并将时序表转换为超表（仅 PostgreSQL）。"""
    # 非 PostgreSQL 数据库跳过
    if engine.dialect.name != "postgresql":
        return

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.commit()

        for table in _HYPERTABLES:
            result = conn.execute(
                text(
                    "SELECT 1 FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = :table_name"
                ),
                {"table_name": table},
            ).scalar()
            if result is None:
                conn.execute(
                    text(
                        f"SELECT create_hypertable('{table}', 'trade_date', if_not_exists => TRUE)"
                    )
                )
                conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表（开发环境用，生产环境建议用 alembic）
    Base.metadata.create_all(bind=engine)
    _ensure_timescale_hypertables()

    # 开发环境初始化测试账号，方便 iOS 端快速验证
    db = SessionLocal()
    try:
        try:
            create_user(db, email="1538933906@qq.com", password="123456", name="Test User")
        except ValueError as exc:
            if "邮箱已存在" not in str(exc):
                raise
            # 用户已存在时重置测试账号密码，确保 iOS 测试登录始终可用
            user = db.query(UserModel).filter(UserModel.email == "1538933906@qq.com").first()
            if user is not None:
                user.hashed_password = get_password_hash("123456")
                db.commit()
    finally:
        db.close()

    yield


app = FastAPI(
    title=settings.app_name,
    description="个人信息仪表盘后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

# 允许 iOS App 跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改成你的 App 域名
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Ying+ API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
