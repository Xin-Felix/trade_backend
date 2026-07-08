# Widgets Studio 后端

基于 FastAPI + PostgreSQL + TimescaleDB 的分层后端服务，提供邮箱验证码登录、股票行情、因子数据等接口。

## 技术栈

- Python 3.12 + FastAPI
- PostgreSQL 16 + TimescaleDB（时序数据）
- SQLAlchemy 2.0 + Alembic
- Tushare Pro（股票数据源）
- Docker + Docker Compose

## 目录结构

```
trade_backend/
├── alembic/                  # 数据库迁移
├── app/
│   ├── main.py               # FastAPI 应用入口
│   ├── api/v1/               # v1 路由
│   │   ├── api.py
│   │   └── endpoints/
│   │       ├── auth.py       # 登录/验证码
│   │       ├── weather.py
│   │       └── stocks.py
│   ├── core/                 # 配置、安全、依赖
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── db/                   # 数据库 Session/Base
│   ├── models/               # SQLAlchemy ORM 模型
│   │   ├── stock.py          # 股票 K 线、因子、财务模型
│   │   ├── user.py
│   │   └── verification_code.py
│   ├── schemas/              # Pydantic 请求/响应模型
│   ├── services/             # 业务逻辑层
│   │   ├── auth_service.py
│   │   ├── data_sync_service.py  # Tushare 数据同步
│   │   ├── email_service.py
│   │   ├── stock_service.py
│   │   └── weather_service.py
│   └── utils/                # 通用工具
├── tests/                    # 测试
├── docker-compose.yml        # PostgreSQL + Redis + backend 一键启动
├── Dockerfile
├── main.py                   # 兼容入口，转发自 app/main.py
├── requirements.txt
└── README.md
```

## 数据模型

| 表 | 说明 |
|---|---|
| `users` | 用户信息 |
| `verification_codes` | 邮箱验证码 |
| `stock_basic` | 股票基础信息 |
| `stock_daily` | 日 K 线（TimescaleDB 超表） |
| `stock_weekly` | 周 K 线（TimescaleDB 超表） |
| `stock_monthly` | 月 K 线（TimescaleDB 超表） |
| `stock_yearly` | 年 K 线 |
| `stock_daily_basic` | 日线因子 PE/PB/换手率等（TimescaleDB 超表） |
| `stock_fina_indicator` | 财务指标（季度） |

## 环境变量

复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

关键配置项：

- `SECRET_KEY`：JWT 密钥，生产环境务必改成随机字符串
- `DATABASE_URL`：PostgreSQL 连接地址
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`：Docker 内数据库配置
- `SMTP_USERNAME` / `SMTP_PASSWORD`：发件邮箱和授权码（验证码邮件用）
- `TUSHARE_TOKEN`：Tushare Pro Token（股票数据源）
- `MOCK_STOCK_DATA`：是否使用 mock 股票数据（无 Tushare token 时方便调试）

## 运行方式

### 方式一：Docker 一键启动（推荐）

```bash
cd /Users/huangxin/Desktop/trade/trade_backend
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN、SMTP 授权码等
docker compose up -d
```

首次启动后，TimescaleDB 扩展会自动启用，应用启动时会自动建表。

访问接口文档：http://127.0.0.1:8000/docs

停止：

```bash
docker compose down
```

### 方式二：本地 Python 环境

需要本地安装 PostgreSQL + TimescaleDB。

```bash
cd /Users/huangxin/Desktop/trade/trade_backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 数据库迁移

```bash
alembic upgrade head
```

## 数据同步

后端启动时不会自动拉取股票数据。需要手动触发同步任务：

```bash
# 方式一：在容器内运行同步脚本
cd /Users/huangxin/Desktop/trade/trade_backend
docker compose exec backend python scripts/sync_data.py

# 方式二：本地 Python 环境
python scripts/sync_data.py --years 10
```

常用参数：

```bash
# 同步全部数据（最近 10 年）
python scripts/sync_data.py

# 同步最近 5 年
python scripts/sync_data.py --years 5

# 只同步指定股票
python scripts/sync_data.py --codes 000001.SZ,600519.SH

# 跳过某些数据
python scripts/sync_data.py --skip-fina --skip-daily-basic
```

建议每天收盘后执行一次增量同步。

## 接口

基础接口：

- `GET /`：服务状态
- `GET /health`：健康检查

v1 接口（前缀 `/api/v1`）：

### 认证

- `POST /auth/email/code`：发送邮箱验证码
- `POST /auth/email/verify`：校验验证码，新用户自动注册并登录
- `POST /auth/login/email`：邮箱密码登录（兼容旧测试账号）
- `POST /auth/login/apple`：Apple 登录（占位）

### 天气

- `GET /weather/beijing`：北京天气

### 股票（均需登录）

- `GET /stocks/quote/{code}`：股票最新行情
- `GET /stocks/klines/{code}`：K 线数据（`period=D/W/M/Y`，`limit=1~500`）
- `GET /stocks/daily-basic/{code}`：日线因子数据（PE/PB/换手率等）
- `GET /stocks/watchlist`：示例自选股

## 测试

```bash
pytest
```

测试环境默认使用 SQLite 内存数据库 + mock 股票数据，不依赖 PostgreSQL。

## 股票代码格式

接口支持以下格式，后端会自动标准化为 Tushare 格式：

- `000001` → `000001.SZ`
- `600519` → `600519.SH`
- `00700` → `00700.HK`
- `000001.SZ`（直接传入）

## 注意事项

- `.env` 已加入 `.gitignore`，请勿提交真实密钥
- 生产环境必须修改 `SECRET_KEY`
- Tushare Pro 有调用频率限制，全市场同步可能需要较长时间
- 开发环境可开启 `MOCK_STOCK_DATA=true` 在没有 Tushare token 时调试
