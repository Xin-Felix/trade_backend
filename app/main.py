from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.user import User as UserModel
from app.services.admin_seed import seed_admin_menus
from app.services.auth_service import create_user
from app.services.datasource_seed import seed_data_sources
from app.services.scheduler_seed import seed_scheduler_jobs

# 导入所有模型，确保 Base.metadata 能创建表
import app.models  # noqa: F401


_HYPERTABLES = [
    "stock_daily",
    "stock_weekly",
    "stock_monthly",
    "stock_daily_basic",
    "stock_moneyflow",
    "index_daily",
    "stock_limit",
    "top_list",
    "top_inst",
    "ths_daily",
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

    # 启动定时调度器
    from app.services.scheduler_service import shutdown_scheduler, start_scheduler
    start_scheduler()

    # 开发环境初始化测试账号，方便 iOS 端快速验证
    db = SessionLocal()
    try:
        try:
            create_user(db, email="1538933906@qq.com", password="123456", name="Test User")
            # 将测试用户设为管理员
            user = db.query(UserModel).filter(UserModel.email == "1538933906@qq.com").first()
            if user is not None:
                user.role = "admin"
                db.commit()
        except ValueError as exc:
            if "邮箱已存在" not in str(exc):
                raise
            # 用户已存在时重置测试账号密码，确保 iOS 测试登录始终可用
            user = db.query(UserModel).filter(UserModel.email == "1538933906@qq.com").first()
            if user is not None:
                user.hashed_password = get_password_hash("123456")
                user.role = "admin"
                db.commit()

        # 初始化后台管理菜单数据
        seed_admin_menus(db)

        # 初始化定时任务配置
        seed_scheduler_jobs(db)

        # 初始化数据源注册表
        seed_data_sources(db)
    finally:
        db.close()

    yield

    # 关闭定时调度器
    shutdown_scheduler()


app = FastAPI(
    title="盈多多 Ying+ API",
    description="""盈多多（Ying+）AI 投资工作台后端服务。

## 主要模块

### 认证 (Auth)
- 邮箱验证码登录/注册
- Apple Sign In
- 用户信息查询与修改

### 数据源管理 (DataSource)
- 多 Provider 数据源注册（Tushare / AKShare / 自定义）
- 接口权限检测
- 分类概览与统计

### 数据同步 (Sync)
- 日K线、日线因子、板块资金流
- 龙虎榜、同花顺板块
- 北向资金、涨跌停
- 概念映射

### 调度管理 (Scheduler)
- 定时任务配置（Cron / Interval）
- 任务执行日志
- 手动触发

### 股票 (Stocks)
- 个股行情、分时K线
- 所属板块、概念映射
- 资金流向

### Tushare 代理 (Tushare Proxy)
- 200+ 接口透传代理
- 统一鉴权与限流

### 数据浏览 (Data Browser)
- 本地数据表查询
- 任意表分页浏览
""",
    version="1.0.0",
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
