# Ying+ 后端

基于 FastAPI + PostgreSQL + TimescaleDB 的分层后端服务，提供邮箱验证码登录、股票行情、因子数据等接口。

## 快速开始

```bash
cd /Users/huangxin/Desktop/trade/trade_backend
cp .env.example .env
# 编辑 .env 填入必要配置
docker compose up -d
```

服务启动后访问：http://127.0.0.1:8000/docs

## 文档索引

- [API 接口文档](docs/api.md)
- [部署文档](docs/deployment.md)
- [本地开发文档](docs/development.md)
- [数据库与数据同步](docs/database.md)

## 技术栈

- Python 3.12 + FastAPI
- PostgreSQL 16 + TimescaleDB
- SQLAlchemy 2.0 + Alembic
- Tushare Pro（股票数据源）
- Docker + Docker Compose

## 常用命令

```bash
# 运行测试
pytest

# 数据库迁移
alembic upgrade head

# 同步股票数据（容器内）
docker compose exec backend python scripts/sync_data.py
```

## 注意事项

- `.env` 已加入 `.gitignore`，请勿提交真实密钥。
- 生产环境必须修改 `SECRET_KEY`。
- 测试账号：`1538933906@qq.com` / `123456`，开发环境启动时自动创建/重置。
