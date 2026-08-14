from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, set_request_id
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.user import User as UserModel
from app.services.admin_seed import (
    seed_admin_menus,
    seed_h5_pages,
    seed_membership_data,
    seed_sector_default_configs,
)
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

    # 初始化市场拥挤度模块的自有表
    from app.market.database import init_db as mc_init_db
    mc_init_db()

    # 确保 market 模块依赖的 PostgreSQL 视图存在（daily/daily_basic/cached_dates）
    # 这些视图映射 stock_daily / stock_daily_basic 表为 market/core 期望的旧格式
    from sqlalchemy import text as _text
    with engine.connect() as _conn:
        try:
            # 视图依赖 stock_daily 和 stock_daily_basic 表（上面 create_all 已创建）
            _conn.execute(_text("""
                CREATE OR REPLACE VIEW daily AS
                SELECT TO_CHAR(trade_date, 'YYYYMMDD') as date, ts_code,
                    open::double precision, high::double precision, low::double precision,
                    close::double precision, pre_close::double precision, pct_chg::double precision,
                    vol::double precision, (amount * 1000)::double precision as amount_yuan
                FROM stock_daily
            """))
            _conn.execute(_text("""
                CREATE OR REPLACE VIEW daily_basic AS
                SELECT TO_CHAR(trade_date, 'YYYYMMDD') as date, ts_code, circ_mv::double precision
                FROM stock_daily_basic
            """))
            _conn.execute(_text("""
                CREATE OR REPLACE VIEW cached_dates AS
                SELECT TO_CHAR(trade_date, 'YYYYMMDD') as date, 1 as has_daily,
                    CASE WHEN EXISTS (SELECT 1 FROM stock_daily_basic b WHERE b.trade_date = d.trade_date LIMIT 1)
                    THEN 1 ELSE 0 END as has_basic, 1 as has_adj
                FROM (SELECT DISTINCT trade_date FROM stock_daily) d
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS adj_factor (
                    date TEXT NOT NULL, ts_code TEXT NOT NULL, adj_factor DOUBLE PRECISION DEFAULT 1.0,
                    PRIMARY KEY (date, ts_code))
            """))
            # mc_summary / mc_margin 等辅助表
            _conn.execute(_text("CREATE TABLE IF NOT EXISTS mc_summary (key TEXT PRIMARY KEY, value TEXT)"))
            _conn.execute(_text("CREATE TABLE IF NOT EXISTS mc_margin (date TEXT PRIMARY KEY, rzye DOUBLE PRECISION)"))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_stock_kline (
                    ts_code TEXT NOT NULL, date TEXT NOT NULL,
                    open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
                    close DOUBLE PRECISION, vol DOUBLE PRECISION, pct_chg DOUBLE PRECISION,
                    PRIMARY KEY (ts_code, date))
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_option_contracts (
                    option_code TEXT PRIMARY KEY, underlying_code TEXT NOT NULL,
                    option_name TEXT, exchange TEXT, option_type TEXT,
                    strike DOUBLE PRECISION, expire_date TEXT, updated_at TEXT)
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_option_quotes (
                    option_code TEXT NOT NULL, underlying_code TEXT NOT NULL,
                    option_type TEXT, strike DOUBLE PRECISION, price DOUBLE PRECISION,
                    change_pct DOUBLE PRECISION, volume INTEGER, open_interest INTEGER,
                    iv DOUBLE PRECISION, delta DOUBLE PRECISION, gamma DOUBLE PRECISION,
                    theta DOUBLE PRECISION, vega DOUBLE PRECISION,
                    buy_price DOUBLE PRECISION, buy_vol INTEGER,
                    sell_price DOUBLE PRECISION, sell_vol INTEGER,
                    expire_date TEXT, updated_at TEXT,
                    PRIMARY KEY (option_code))
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_option_etf_quotes (
                    code TEXT PRIMARY KEY, name TEXT, price DOUBLE PRECISION,
                    prev_close DOUBLE PRECISION, open DOUBLE PRECISION,
                    high DOUBLE PRECISION, low DOUBLE PRECISION,
                    volume BIGINT, change_pct DOUBLE PRECISION, updated_at TEXT)
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_option_signals (
                    id SERIAL PRIMARY KEY, ts TEXT, date TEXT, underlying_code TEXT,
                    signal_key TEXT, level TEXT, name TEXT, label TEXT, detail TEXT)
            """))
            _conn.execute(_text("""
                CREATE TABLE IF NOT EXISTS mc_congestion_history (
                    date TEXT NOT NULL, board TEXT NOT NULL, top_percent REAL NOT NULL,
                    denominator TEXT NOT NULL, congestion REAL,
                    PRIMARY KEY (date, board, top_percent, denominator))
            """))
            # summary / margin 视图兼容
            _conn.execute(_text("CREATE OR REPLACE VIEW summary AS SELECT * FROM mc_summary"))
            _conn.execute(_text("CREATE OR REPLACE VIEW margin AS SELECT * FROM mc_margin"))
            _conn.commit()
        except Exception as e:
            _conn.rollback()
            import logging
            logging.getLogger(__name__).warning(f"市场视图/表初始化部分失败（首次部署可忽略）: {e}")

    # 开发环境初始化测试账号，方便 iOS 端快速验证
    # 密码可通过环境变量 DEV_TEST_USER_PASSWORD 覆盖
    # 通过环境变量 ENABLE_DEV_TEST_USER 控制，生产环境建议设置为 false
    if getenv("ENABLE_DEV_TEST_USER", "true").lower() == "true":
        db = SessionLocal()
        try:
            test_email = "1538933906@qq.com"
            test_password = getenv("DEV_TEST_USER_PASSWORD") or "123456"
            try:
                create_user(db, email=test_email, password=test_password, name="Test User")
                # 将测试用户设为管理员
                user = db.query(UserModel).filter(UserModel.email == test_email).first()
                if user is not None:
                    user.role = "admin"
                    db.commit()
            except ValueError as exc:
                if "邮箱已存在" not in str(exc):
                    raise
                # 用户已存在时重置测试账号密码，确保 iOS 测试登录始终可用
                user = db.query(UserModel).filter(UserModel.email == test_email).first()
                if user is not None:
                    user.hashed_password = get_password_hash(test_password)
                    user.role = "admin"
                    db.commit()
        finally:
            db.close()

    db = SessionLocal()
    try:
        # 初始化后台管理菜单数据
        seed_admin_menus(db)

        # 初始化会员档位和功能权限
        seed_membership_data(db)

        # 初始化 H5 页面示例数据
        seed_h5_pages(db)

        # 初始化分时资金流向默认配置
        seed_sector_default_configs(db)

        # 初始化定时任务配置
        seed_scheduler_jobs(db)

        # 初始化数据源注册表
        seed_data_sources(db)
    finally:
        db.close()

    # 启动后异步预热行情缓存（不阻塞请求）
    from app.api.v1.endpoints.market_congestion import warm_cache
    warm_cache()

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

# 配置统一日志：开发环境文本格式，生产环境可开启 JSON 格式
configure_logging(level=getenv("LOG_LEVEL", "INFO"), json_format=getenv("LOG_JSON", "false").lower() == "true")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """为每个请求生成 request_id，注入日志上下文并返回响应头。"""
    rid = set_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
    finally:
        # 请求结束后不主动清理 ContextVar，后续异步任务仍可能需要；
        # 新请求会覆盖自己的 request_id。
        pass


# 允许 iOS App 跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改成你的 App 域名
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# 统一异常响应格式
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/")
async def root():
    return {"message": "Ying+ API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
