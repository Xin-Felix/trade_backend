# 数据库与数据同步

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

## 数据库迁移

```bash
alembic upgrade head
```

开发环境首次启动时会自动建表（生产环境建议用 Alembic）。

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

## 测试账号

开发环境启动时会在 `users` 表中初始化测试账号：

- 邮箱：`1538933906@qq.com`
- 密码：`123456`

若该邮箱已存在，则会将其密码重置为 `123456`，方便 iOS 端一键测试登录。
