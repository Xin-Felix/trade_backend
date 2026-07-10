# Ying+ 后端架构文档

## 项目概述

基于 FastAPI + PostgreSQL/TimescaleDB 的个人股票数据分析后端，配套 iOS App 和 Web 管理后台。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.111.0 |
| ORM | SQLAlchemy | 2.0.30 |
| 数据库 | PostgreSQL + TimescaleDB | 16 |
| 缓存 | Redis | 7 |
| 数据迁移 | Alembic | 1.13.1 |
| 股票数据源 | Tushare Pro / akshare | 1.4.13 / 1.18.35 |
| 定时调度 | APScheduler | 3.10.4 |
| 认证 | JWT (python-jose) | - |
| 部署 | Docker Compose | - |

## 目录结构

```
trade_backend/
├── app/
│   ├── main.py                  # FastAPI 入口 + lifespan（建表/种子/调度器）
│   ├── api/v1/
│   │   ├── api.py               # 路由注册汇总
│   │   └── endpoints/
│   │       ├── auth.py          # iOS 认证（验证码/密码）
│   │       ├── admin.py         # 管理后台（登录/路由/用户/菜单/角色）
│   │       ├── stocks.py        # 股票查询（iOS App）
│   │       ├── sync.py          # 手动同步 + 数据状态（写日志）
│   │       ├── scheduler.py     # 定时任务管理 + 执行日志查询
│   │       ├── datasource.py    # 数据源管理 + 权限检测
│   │       ├── data_browser.py  # 数据浏览
│   │       └── tushare/         # Tushare 代理（239个路由）
│   ├── core/
│   │   ├── config.py            # Settings（DB/JWT/SMTP/Redis/Tushare）
│   │   ├── dependencies.py      # get_current_user（JWT解析）
│   │   ├── redis.py             # Redis 连接
│   │   └── security.py          # bcrypt + JWT
│   ├── db/base.py               # engine/session（pool_size=10）
│   ├── models/
│   │   ├── user.py              # users 表
│   │   ├── stock.py             # 原始股票表（19张）
│   │   ├── analysis.py          # 分析数据表（25张）
│   │   ├── watchlist.py         # 自选股
│   │   ├── verification_code.py # 验证码
│   │   ├── admin.py             # RBAC（菜单/权限/角色）
│   │   ├── scheduler.py         # 定时任务配置
│   │   ├── scheduler_log.py     # 执行日志
│   │   └── data_source.py       # 数据源注册（239条）
│   ├── schemas/                 # Pydantic 模型
│   └── services/
│       ├── auth_service.py      # 认证
│       ├── admin_service.py     # 后台管理
│       ├── admin_seed.py        # 菜单+角色种子
│       ├── stock_service.py     # 股票查询
│       ├── data_sync_service.py # 原始数据同步
│       ├── analysis_sync_service.py # 分析数据同步
│       ├── scheduler_service.py # APScheduler（14个任务+日志记录）
│       ├── scheduler_seed.py    # 定时任务种子
│       ├── datasource_seed.py   # 数据源种子（239条+本地表标记）
│       ├── datasource_permission.py # 权限检测
│       ├── watchlist_service.py # 自选股
│       └── email_service.py     # 邮件
├── alembic/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 数据库（44+ 张表）

### 用户
- `users` — email/password/role/avatar/public_id
- `verification_codes` — 邮箱验证码
- `watchlist` — 自选股

### RBAC
- `admin_menus` — 菜单树（parent_id）
- `admin_permissions` — 按钮权限
- `admin_roles` — 角色
- `role_menus` / `role_permissions` — 关联

### 调度
- `scheduler_jobs` — 任务配置（trigger_type/cron/interval/days/enabled）
- `scheduler_logs` — 执行日志（定时+手动统一记录）

### 数据源
- `data_sources` — 239条接口元信息（has_local_table/has_permission/permission_msg）

### 原始股票数据（TimescaleDB 超表）
stock_basic / stock_daily / stock_weekly / stock_monthly / stock_yearly /
stock_daily_basic / stock_fina_indicator / stock_moneyflow /
sector_moneyflow_industry / sector_moneyflow_concept / moneyflow_hsgt /
index_basic / index_daily / stock_limit / top_list / top_inst /
ths_index / ths_daily / ths_member / stock_concept

### 分析数据（25张）
**打板题材：** limit_list_d / limit_step / limit_list_ths / dc_concept / dc_concept_cons / ths_hot / dc_hot
**机构筹码：** hk_hold / stk_holdernumber / stk_holdertrade / cyq_perf / margin_detail / broker_recommend / report_rc
**宏观行业：** index_weight / index_dailybasic / sw_daily / cn_cpi / cn_pmi / shibor_lpr / sf_month
**ETF/可转债：** etf_basic / etf_share_size / cb_basic / cb_daily_local

## API 路由

| 前缀 | 说明 |
|------|------|
| /api/v1/auth | iOS 认证 |
| /api/v1/admin | 后台管理 |
| /api/v1/stocks | 股票查询 |
| /api/v1/sync | 手动同步+数据状态 |
| /api/v1/scheduler | 定时任务+日志 |
| /api/v1/datasource | 数据源管理 |
| /api/v1/data | 数据浏览 |
| /api/v1/ts/* | Tushare 代理 |

### 关键接口

**调度管理：**
- GET /scheduler/jobs — 任务列表
- POST /scheduler/jobs — 创建/更新配置
- PUT /scheduler/jobs/{id}/toggle — 启用/禁用
- POST /scheduler/jobs/{id}/run — 立即执行
- DELETE /scheduler/jobs/{id} — 删除
- GET /scheduler/logs?job_id=&status= — 执行日志（分页+筛选）

**数据同步（手动触发，也写日志）：**
- GET /sync/status — 所有表数据概况
- POST /sync/recent — 综合同步
- POST /sync/{type} — 按类型同步

**数据源：**
- GET /datasource/list — 接口列表（分页+筛选）
- GET /datasource/categories — 分类列表
- POST /datasource/check-permission — 批量权限检测

## 定时任务（14个）

| 任务ID | 描述 | 默认时间 |
|--------|------|---------|
| sync_daily_kline | 日K线 | 17:00 |
| sync_daily_basic | 日线因子 | 17:10 |
| sync_sector_moneyflow | 板块资金流 | 17:20 |
| sync_stock_moneyflow | 个股资金流 | 17:30 |
| sync_index_daily | 指数日线 | 17:40 |
| sync_moneyflow_hsgt | 沪深港通 | 17:50 |
| sync_stock_limit | 涨跌停 | 18:00 |
| sync_all | 综合同步（默认禁用） | 19:00 |
| sync_limit_data | 打板数据 | 16:30 |
| sync_concept_hot | 题材热点 | 16:40 |
| sync_institution | 机构数据 | 18:30 |
| sync_research | 研报数据 | 20:00 |
| sync_macro | 宏观数据 | 20:30 |
| sync_etf_cb | ETF/可转债 | 18:10 |

## 日志机制

统一写入 `scheduler_logs` 表：
- **定时任务**：APScheduler 触发时自动记录，job_id 如 `sync_daily_kline`
- **手动同步**：通过 `/api/v1/sync/*` 触发时也记录，job_id 如 `manual_daily_kline`
- **字段**：status(success/failed/running) / message / duration_seconds / started_at / finished_at

## 启动流程

1. 建表 → 2. TimescaleDB超表 → 3. 启动调度器(恢复DB配置) → 4. 种子菜单 → 5. 种子任务配置 → 6. 种子数据源 → 7. 测试账号

## 常用命令

```bash
docker compose up -d          # 启动
docker restart yingplus_backend  # 重启后端
docker logs -f yingplus_backend  # 看日志
alembic upgrade head          # 迁移
```
