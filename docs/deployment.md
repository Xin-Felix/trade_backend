# 部署文档

## 环境变量

复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | JWT 密钥，生产环境务必改成随机字符串（至少 32 字节） |
| `DATABASE_URL` | PostgreSQL 连接地址 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Docker 内数据库配置 |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | 发件邮箱和授权码（验证码邮件用） |
| `TUSHARE_TOKEN` | Tushare Pro Token（股票数据源） |
| `MOCK_STOCK_DATA` | 是否使用 mock 股票数据（无 Tushare token 时方便调试） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT 过期时间（分钟），默认 7 天 |

## Docker 一键启动（推荐）

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

## 生产环境注意事项

1. 必须修改 `SECRET_KEY`，不要使用默认的 `your-secret-key-change-in-production`。
2. `CORS` 当前配置为 `allow_origins=["*"]`，生产环境应改成你的 App 域名。
3. 建议使用 Alembic 管理数据库迁移，而不是依赖启动时的 `create_all`。
4. 使用环境变量注入敏感配置，不要提交 `.env` 文件。
