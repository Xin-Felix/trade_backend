# 数据库与数据同步

## 数据模型

| 表 | 说明 |
|---|---|
| `users` | 用户信息 |
| `verification_codes` | 邮箱验证码 |
| `watchlist` | 自选股 |
| `stock_basic` | 股票基础信息（含 industry 行业字段） |
| `stock_daily` | 日 K 线（TimescaleDB 超表） |
| `stock_weekly` | 周 K 线（TimescaleDB 超表） |
| `stock_monthly` | 月 K 线（TimescaleDB 超表） |
| `stock_yearly` | 年 K 线 |
| `stock_daily_basic` | 日线因子 PE/PB/换手率等（TimescaleDB 超表） |
| `stock_fina_indicator` | 财务指标（季度） |
| `stock_intraday` | 分时1分钟K线（主键: ts_code + trade_date + trade_time） |
| `stock_concept` | 概念板块成分股映射 |
| `stock_moneyflow` | 个股日级资金流 |

## stock_intraday 表

全市场分时K线数据，用于分钟级资金流聚合和 iOS 分时走势图。

```sql
CREATE TABLE stock_intraday (
    ts_code     VARCHAR(20),   -- 股票代码
    trade_date  DATE,          -- 交易日期
    trade_time  VARCHAR(5),    -- 时间 HH:MM
    open        NUMERIC(12,4), -- 开盘价
    close       NUMERIC(12,4), -- 收盘价
    high        NUMERIC(12,4), -- 最高价
    low         NUMERIC(12,4), -- 最低价
    volume      NUMERIC(20,0), -- 成交量
    amount      NUMERIC(20,4), -- 成交额(元)
    PRIMARY KEY (ts_code, trade_date, trade_time)
);
```

- 每天约 5500 股 × 241 分钟 ≈ 132 万条
- 仅保留最近 5 个交易日（自动清理）
- 数据源：Tushare 代理 stk_mins 接口
- 采集脚本：`python scripts/sync_intraday.py --days 5`

## 数据库迁移

```bash
alembic upgrade head
```

开发环境首次启动时会自动建表（生产环境建议用 Alembic）。
`stock_intraday` 表在首次采集时自动创建（`CREATE IF NOT EXISTS`）。

### Migration 历史整理（2026-07-11）

已将所有零散 migration 合并为单一初始 migration：

- `alembic/versions/612d2e772bd1_initial_schema.py`

**整理原因：**
1. `084a9b1d34ba` 与 `9967f78c96ce` 重复添加了 `feature_permissions.consume_mode` 列。
2. 旧 migration 链无法从零运行：`d7d13bbbbba6` 会直接 `ALTER TABLE stock_daily` 等表，但这些 stock 表之前没有 migration 创建（此前依赖 `Base.metadata.create_all()`）。

**已存在环境的处理：**

如果某个环境之前已经跑过旧 migration，需要手动将其 `alembic_version` 更新为新的 head，不要重新跑旧 migration：

```sql
UPDATE alembic_version SET version_num = '612d2e772bd1';
```

新环境直接执行 `alembic upgrade head` 即可。

### 新增 Migration

```bash
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

## 数据同步

后端启动时不会自动拉取股票数据。需要手动触发同步任务：

### 日线数据同步

```bash
# 在容器内运行同步脚本
docker compose exec backend python scripts/sync_data.py

# 本地 Python 环境
python scripts/sync_data.py --years 10
```

常用参数：

```bash
python scripts/sync_data.py              # 同步全部（最近10年）
python scripts/sync_data.py --years 5    # 同步最近5年
python scripts/sync_data.py --codes 000001.SZ,600519.SH  # 指定股票
python scripts/sync_data.py --skip-fina --skip-daily-basic  # 跳过某些数据
```

### 分时数据采集

通过 Tushare 代理采集全市场1分钟K线（需在宿主机运行）：

```bash
python scripts/sync_intraday.py              # 采集最近5个交易日（默认）
python scripts/sync_intraday.py --days 1     # 只采集最近1个交易日
python scripts/sync_intraday.py --days 3     # 采集最近3个交易日
```

特性：
- 4 线程并发，每天约 45 分钟完成
- 数据清洗：自动去重 + 缺失分钟插值
- 保留策略：仅保留最近 5 个交易日
- 错误率 < 0.5%

### 权限检测

使用代理 token 刷新所有数据源接口的权限状态：

```bash
python scripts/check_permissions.py
```

建议每天收盘后执行一次增量同步 + 分时采集。

## Tushare 代理配置

项目使用第三方 Tushare 高积分代理，支持 stk_mins 等高级接口：

```bash
# .env
TUSHARE_TOKEN=<原始token>
TUSHARE_PROXY_URL=https://tx.xiaodefa.top/
TUSHARE_PROXY_TOKEN=<代理token>
```

配置后所有 `get_pro()` 调用会优先使用代理。

## 测试账号

开发环境启动时会在 `users` 表中初始化测试账号：

- 邮箱：`1538933906@qq.com`
- 密码：`123456`

若该邮箱已存在，则会将其密码重置为 `123456`，方便 iOS 端一键测试登录。
