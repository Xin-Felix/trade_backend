# 本地开发文档

## 技术栈

- Python 3.12 + FastAPI
- PostgreSQL 16 + TimescaleDB（时序数据）
- SQLAlchemy 2.0 + Alembic
- Tushare Pro（股票数据源）
- Docker + Docker Compose

## 本地 Python 环境

需要本地安装 PostgreSQL + TimescaleDB 和 Redis。

```bash
cd /Users/huangxin/Desktop/trade/trade_backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问：http://127.0.0.1:8000/docs

## Redis 配置

Redis 用于缓存实时分时 K 线等热数据，通过环境变量 `REDIS_URL` 配置：

```bash
# .env
REDIS_URL=redis://127.0.0.1:6379/0
```

- 已配置 `REDIS_URL` 时，数据写入 Redis，默认缓存 30 秒。
- 未配置 `REDIS_URL` 时，自动降级为本地内存缓存（带 TTL），不影响接口使用。
- Docker Compose 已内置 Redis 服务，容器内地址为 `redis://redis:6379/0`。

## 目录结构

```
trade_backend/
├── alembic/                  # 数据库迁移
├── app/
│   ├── main.py               # FastAPI 应用入口
│   ├── api/v1/               # v1 路由
│   │   └── endpoints/        # 认证、天气、股票等接口
│   ├── core/                 # 配置、安全、依赖
│   ├── db/                   # 数据库 Session/Base
│   ├── models/               # SQLAlchemy ORM 模型
│   ├── schemas/              # Pydantic 请求/响应模型
│   ├── services/             # 业务逻辑层
│   └── utils/                # 通用工具
├── tests/                    # 测试
├── docker-compose.yml        # PostgreSQL + Redis + backend 一键启动
├── Dockerfile
├── requirements.txt
└── README.md
```

## 测试

```bash
pytest
```

测试环境默认使用 SQLite 内存数据库 + mock 股票数据，不依赖 PostgreSQL。

## 代码规范

- 路由层只负责接收请求和返回响应，业务逻辑放到 `app/services/`。
- 数据库模型放在 `app/models/`，Pydantic 模型放在 `app/schemas/`。
- 认证依赖使用 `app/core/dependencies.py` 中的 `get_current_user`。

## 注意事项

- `.env` 已加入 `.gitignore`，请勿提交真实密钥。
- 生产环境必须修改 `SECRET_KEY`。
- Tushare Pro 有调用频率限制，全市场同步可能需要较长时间。
- 开发环境可开启 `MOCK_STOCK_DATA=true` 在没有 Tushare token 时调试。
- 分时数据采集脚本 (`scripts/sync_intraday.py`) 需在宿主机运行（使用 `.venv`），Docker 内可能因网络问题无法访问代理。
- Tushare 代理配置在 `.env` 中：`TUSHARE_PROXY_URL` + `TUSHARE_PROXY_TOKEN`，配置后所有 Tushare 调用走代理。
- 权限检测脚本 (`scripts/check_permissions.py`) 使用直接 HTTP POST，不依赖 tushare SDK（避免挂起问题）。
