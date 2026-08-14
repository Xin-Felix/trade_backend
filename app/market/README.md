# 市场拥挤度 / 每日复盘模块

> 从 `market_congestion` 项目迁移合并而来。后续所有开发都在这里进行。

## 架构

```
app/market/
├── __init__.py          模块说明
├── database.py          数据适配层（读 trade 的表 + 自建 mc_* 表）
├── pipeline.py          管道编排（aggregates + congestion + option）
├── README.md            本文件
└── core/                核心计算逻辑（原 market_congestion/core/）
    ├── config.py        配置（板块映射/信号阈值/tushare token）
    ├── datasource.py    tushare 数据源 + 缓存管理
    ├── database.py      redirect → app.market.database
    ├── metrics.py       指标汇总入口
    ├── market.py        大盘快照/换手率/涨跌走势/板块成交
    ├── breadth.py       市场广度（MA60/NH-NL/上涨占比）
    ├── congestion.py    拥挤度计算
    ├── industry.py      行业排名/走势/资金流入
    ├── margin_mod.py    融资融券
    ├── review.py        每日复盘
    ├── trend.py         趋势信号（EMA+ADX+结构确认）
    ├── screener.py      选股筛选 + 个股K线
    ├── option.py        ETF期权
    ├── history.py       拥挤度历史
    └── utils.py         工具函数
```

## 数据流

```
trade_backend 已有数据（stock_daily/stock_daily_basic 等）
    ↓ 由 trade scheduler 定时同步（sync_daily_kline 16:05 / sync_daily_basic 16:15）
    ↓
app/market/database.py 适配层
    ↓ 读 trade 的表，转成 core/ 期望的格式（YYYYMMDD + amount_yuan）
    ↓
app/market/core/ 计算逻辑
    ↓ 纯计算，返回 dict/list
    ↓
app/api/v1/endpoints/market_congestion.py 路由层
    ↓ 统一响应 {code, msg, meta, data}
    ↓
前端 trade_market_web（/api/v1/mc/...）
```

## API 路由

所有接口前缀：`/api/v1/mc/`

| 接口 | 用途 |
|------|------|
| GET /healthz | 数据健康状态 |
| GET /trade-dates | 交易日列表 |
| GET /config | 客户端配置 |
| GET /market/snapshot | 大盘快照 |
| GET /market/overview | 换手率 |
| GET /market/signals | 综合信号 |
| GET /market/updn | 涨跌走势 |
| GET /board/shares | 板块占比 |
| GET /board/amounts | 板块成交额 |
| GET /board/flow | 板块资金流 |
| GET /board/congestion | 板块拥挤度 |
| GET /industry/crowding | 行业排名 |
| GET /industry/trend | 行业走势 |
| GET /industry/flow | 行业资金 |
| GET /industry/list | 行业列表 |
| GET /breadth | 市场广度 |
| GET /margin/trend | 融资融券 |
| GET /congestion/single | 单日拥挤度 |
| GET /congestion/series | 拥挤度序列 |
| GET /congestion/history | 拥挤度历史 |
| GET /review | 每日复盘 |
| GET /trend/overview | 趋势信号 |
| GET /screener | 选股筛选 |
| GET /kline | 个股K线 |
| GET /option/underlyings | 期权标的 |
| GET /option/analysis | 期权分析 |
| GET /option/signals | 期权信号 |
| GET /option/etf-kline | ETF日K |
| GET /option/etf-minute | ETF分钟K |
| POST /pipeline/trigger | 手动触发管道 |
| POST /cache/clear | 清缓存 |

## 定时任务

通过 trade 的 APScheduler 系统管理，在后台管理面板可配：

| 任务 | 默认时间 | 说明 |
|------|----------|------|
| mc_pipeline | 每天 17:50 | 等日K+日线因子同步完后执行 |

管道步骤：
1. **aggregates** — 计算市场概览/板块/行业/广度/融资/复盘/趋势等指标
2. **congestion** — 预跑 8 组拥挤度（4板块 × 2口径 × 60天）
3. **option** — 刷新期权合约+行情+标的ETF快照

## 自建表

适配层在 trade 的 PostgreSQL 中创建以下 `mc_` 前缀表：

| 表 | 用途 |
|----|------|
| mc_summary | 通用 JSON KV（板块汇总等） |
| mc_margin | 融资余额 |
| mc_stock_kline | 个股/ETF 日K缓存 |
| mc_congestion_history | 拥挤度历史 |
| mc_option_contracts | 期权合约 |
| mc_option_quotes | 期权行情 |
| mc_option_etf_quotes | 标的ETF快照 |
| mc_option_signals | 期权信号 |

## 前端

前端代码在 `/trade_market_web/`，API base URL 已改为 `/api/v1/mc`。

开发：
```bash
cd trade_market_web
npm install
npm run dev  # 开发模式，代理到 http://localhost:8000
```

生产构建：
```bash
npm run build:web  # 产物在 dist/
```

## 开发指南

### 新增接口

1. `app/market/core/` 写计算逻辑
2. `app/api/v1/endpoints/market_congestion.py` 加路由
3. `trade_market_web/src/composables/useApi.js` 加前端调用

### 新增自建表

1. `app/market/database.py` 的 `_DDL` 加建表语句
2. `TABLE_KEYS` 登记主键
3. 加对应的 read/write 函数
