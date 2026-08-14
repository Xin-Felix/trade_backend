# 市场拥挤度 / 每日复盘 — 开发文档

> **最后更新**：2026-08-13
> **位置**：`trade_backend/app/market/`（已从独立项目合并到 trade）
> **前端**：`trade_market_web/`

---

## 架构

```
浏览器（localhost:5173 开发 / 生产构建后托管）
        │ HTTP
        ▼
trade_backend FastAPI（/api/v1/mc × 34 个接口）
        │ SQLAlchemy engine（共享 trade 的数据库）
        ▼
PostgreSQL + TimescaleDB（Docker volume）
        ▲
trade scheduler（APScheduler，盘后定时同步 tushare 数据）
        ▲
mc_pipeline（17:50 触发，基于已同步的行情数据计算各类指标）
```

## 数据流

```
tushare API
    ↓ sync_daily_kline (16:05) / sync_daily_basic (16:15)
    ↓
stock_daily / stock_daily_basic 表（trade 已有）
    ↓ PostgreSQL 视图 daily / daily_basic / cached_dates（字段适配）
    ↓
app/market/core/ 计算逻辑
    ↓ 纯计算，返回 dict/list
    ↓
/api/v1/mc/* 路由 → 前端
```

---

## 目录结构

```
trade_backend/app/market/
├── __init__.py          模块入口
├── database.py          ★ 数据适配层（视图创建 + 兼容接口）
├── pipeline.py          管道编排（aggregates + congestion + option）
├── DEV_DOC.md           本文件
├── README.md            快速参考
└── core/                核心计算逻辑
    ├── __init__.py      导出所有公开函数
    ├── config.py        配置（板块映射/信号阈值/tushare token 从 trade settings 读）
    ├── database.py      redirect → app.market.database
    ├── datasource.py    tushare 数据源 + 缓存管理 + 预热
    ├── metrics.py       指标汇总入口（re-export）
    ├── market.py        大盘快照 / 换手率 / 涨跌走势 / 板块成交额
    ├── industry.py      行业排名 / 走势 / 资金流入
    ├── breadth.py       市场广度（MA60/NH-NL/上涨占比）
    ├── congestion.py    拥挤度计算（单日/批量/排除新股）
    ├── margin_mod.py    融资融券余额
    ├── review.py        每日复盘（趋势仪表盘）
    ├── trend.py         趋势信号（EMA+ADX+结构确认，5指数并发）
    ├── screener.py      选股筛选 + 个股K线
    ├── option.py        ETF期权：合约/行情/分析/K线/信号
    ├── history.py       拥挤度计算历史
    └── utils.py         公共工具（rolling_pctile）

trade_market_web/              Vue 3 前端
├── src/
│   ├── composables/
│   │   ├── useApi.js          API 调用（全走 /api/v1/mc/...）
│   │   ├── http.js            fetch 封装（API base = /api/v1/mc）
│   │   ├── useChart.js        ECharts 组合式函数
│   │   └── utils.js           工具函数
│   ├── pages/                 8 个页面组件
│   ├── components/            NavBar + StatusBar
│   └── stores/app.js          Pinia 全局状态
├── vite.config.js             /api 代理到 localhost:8000
└── package.json
```

---

## 数据库

### trade 已有的表（行情数据由 trade scheduler 同步）

| 表 | 用途 | 量级 |
|----|------|------|
| stock_daily | 全市场日K (TimescaleDB hypertable) | 135万/年 |
| stock_daily_basic | PE/PB/换手率/市值 | 135万/年 |

### 视图层（app/market/database.py 启动时创建）

| 视图 | 映射 | 说明 |
|------|------|------|
| daily | stock_daily | 字段适配（trade_date→date TEXT, amount千元→amount_yuan元） |
| daily_basic | stock_daily_basic | ts_code + circ_mv |
| cached_dates | DISTINCT trade_date | 兼容 has_daily/has_basic 查询 |
| summary | mc_summary | 通用 JSON KV |
| margin | mc_margin | 融资余额 |

### mc_ 前缀表（market_congestion 独有）

| 表 | 用途 | 主键 |
|----|------|------|
| mc_summary | 通用 JSON KV（板块汇总等） | key |
| mc_margin | 融资余额 | date |
| mc_stock_kline | 个股/ETF 日K缓存 | (ts_code, date) |
| mc_congestion_history | 拥挤度历史 | (date, board, top_percent, denominator) |
| mc_option_contracts | 期权合约 | option_code |
| mc_option_quotes | 期权行情 | option_code |
| mc_option_etf_quotes | 标的ETF快照 | code |
| mc_option_signals | 期权信号 | UNIQUE(date, code, signal_key) |
| adj_factor | 复权因子（暂空） | (date, ts_code) |

---

## 前端页面

| # | Tab | 路由 | 内容 |
|---|-----|------|------|
| 1 | 总览 | /overview | 综合评估+快照+涨跌走势+换手率+板块成交额 |
| 2 | 复盘 | /review | 仪表盘+多指标对比+信号追踪+板块热力 |
| 3 | 拥挤度 | /congestion | 日历+趋势图+板块拥挤度 |
| 4 | 行业资金 | /industry | 排名+走势+流入+板块占比 |
| 5 | 市场健康 | /health | 广度三线+融资融券概览+余额走势 |
| 6 | 趋势 | /trend | 三层信号卡片+EMA走势+ADX |
| 7 | 选股 | /screener | 筛选+K线(蜡烛/分时/MA/成交量) |
| 8 | 期权 | /option | T型报价+标的K线+信号列表+微笑+持仓量+曲面 |

---

## 定时任务

通过 trade 的 APScheduler 管理，在管理后台 **"数据管理 → 数据中心"** 可查看/配置/手动触发。

| 任务 | 默认时间 | 依赖 | 说明 |
|------|----------|------|------|
| sync_daily_kline | 16:05 | tushare | 拉日K线 |
| sync_daily_basic | 16:15 | tushare | 拉日线因子 |
| **mc_pipeline** | **17:50** | 上述两个完成 | 计算拥挤度/指标/期权 |

mc_pipeline 的三个步骤：
1. **aggregates** — 市场概览/板块/行业/广度/融资/复盘/趋势
2. **congestion** — 预跑 8 组拥挤度（4板块 × 2口径 × 60天）
3. **option** — 期权合约+行情+标的ETF（akshare + 新浪）

手动触发：
```bash
# 通过 API
curl -X POST http://127.0.0.1:8000/api/v1/mc/pipeline/trigger

# 只跑某一步
curl -X POST 'http://127.0.0.1:8000/api/v1/mc/pipeline/trigger?only=aggregates'
```

---

## 数据源

| 数据 | 来源 | 频率 |
|------|------|------|
| 全市场日K (OHLCV) | tushare `daily` | 每交易日 16:05（trade scheduler） |
| 流通市值/换手率 | tushare `daily_basic` | 每交易日 16:15 |
| 融资余额 | tushare `margin` | mc_pipeline 内拉取 |
| 期权合约 | akshare | mc_pipeline 每次 |
| 期权行情+Greeks | 新浪 hq.sinajs.cn | mc_pipeline 每次 |
| 标的ETF价格 | 新浪快照 | mc_pipeline 每次 |
| ETF 日K | tushare `pro_bar(asset='FD')` | mc_pipeline 每次 |
| 交易日历 | tushare `trade_cal` | 首次请求时 |

---

## 开发指南

### 新增接口

1. `app/market/core/` 写计算逻辑（纯函数，不碰 HTTP）
2. `app/api/v1/endpoints/market_congestion.py` 加路由
3. `trade_market_web/src/composables/useApi.js` 加前端调用

### 新增 mc_ 表

1. `app/market/database.py` 的 `_DDL` 加建表语句
2. `TABLE_KEYS` 登记主键
3. 加对应的 read/write 函数

### 本地开发

```bash
cd /Users/huangxin/Desktop/trade

# 启动后端
docker compose up -d

# 前端开发
cd trade_market_web && npm run dev     # http://localhost:5173

# 管理后台
cd trade_admin && npm run dev          # http://127.0.0.1:8848
```

### 日常操作

```bash
cd /Users/huangxin/Desktop/trade

# 看后端日志
docker compose logs -f backend

# 重启后端（改了代码后）
docker compose up -d --build backend

# 进 PG 查数据
docker exec -it trade-postgres-1 psql -U yingplus_user -d yingplus

# 手动跑 mc 管道
curl -X POST http://127.0.0.1:8000/api/v1/mc/pipeline/trigger
```

---

## 注意事项

- **tushare token** 在 `trade_backend/.env` 的 `TUSHARE_TOKEN`
- **新浪接口** 必须带 `Referer: finance.sina.com.cn` + GBK 解码
- **期权 IV 单位**：小数（0.224），前端展示 ×100
- **ETF K线** 必须 `pro_bar(asset='FD')`，不传 `asset` 返回 None
- **ETF 分钟K** 服务器上为空（需要本机日进斗金数据库）

---

## TODO

- [ ] 告警接入（mc_pipeline 失败通知）
- [ ] 期权分钟K 服务端采集（TDX 7709 / 东财）
- [ ] 策略执行器（DSL 白名单算子 → pandas 掩码）
- [ ] 手机端响应式适配
- [ ] mc 前端集成到 trade_admin（或独立域名部署）
