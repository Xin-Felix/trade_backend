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
│   ├── main.py                  # FastAPI 应用入口 + lifespan
│   ├── api/v1/
│   │   ├── api.py               # 路由汇总注册
│   │   └── endpoints/
│   │       ├── auth.py          # iOS 端认证（邮箱验证码/密码登录）
│   │       ├── admin.py         # 管理后台 API（登录/路由/用户CRUD）
│   │       ├── stocks.py        # 股票数据查询接口
│   │       ├── sync.py          # 手动数据同步触发接口
│   │       ├── scheduler.py     # 定时任务调度管理接口
│   │       ├── weather.py       # 天气（测试用，待删除）
│   │       └── tushare/         # Tushare 代理接口（239个路由）
│   │           ├── __init__.py  # 路由注册汇总
│   │           ├── _base.py     # 公共工具函数
│   │           └── *.py         # 每个接口一个文件
│   ├── core/
│   │   ├── config.py            # Pydantic Settings 配置
│   │   ├── dependencies.py      # FastAPI 依赖（JWT 解析）
│   │   ├── redis.py             # Redis 连接
│   │   └── security.py          # 密码哈希 + JWT 签发
│   ├── db/
│   │   └── base.py              # SQLAlchemy engine/session
│   ├── models/
│   │   ├── user.py              # 用户表
│   │   ├── stock.py             # 所有股票相关表（19+张）
│   │   ├── watchlist.py         # 自选股
│   │   ├── verification_code.py # 邮箱验证码
│   │   └── admin.py             # 后台权限表（菜单/权限/角色关联）
│   ├── schemas/                 # Pydantic 请求/响应模型
│   └── services/
│       ├── auth_service.py      # 认证逻辑
│       ├── admin_service.py     # 后台管理逻辑
│       ├── stock_service.py     # 股票数据查询
│       ├── data_sync_service.py # 数据同步逻辑
│       ├── scheduler_service.py # APScheduler 调度管理
│       ├── watchlist_service.py # 自选股
│       └── email_service.py     # 邮件发送
├── alembic/                     # 数据库迁移
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 数据库模型

### 用户相关
- `users` — 用户表（email/password/role/avatar）
- `verification_codes` — 邮箱验证码
- `watchlist` — 用户自选股

### 后台权限（RBAC）
- `admin_menus` — 菜单/路由定义（树形结构，parent_id）
- `admin_permissions` — 按钮级权限定义（code 如 `system:user:add`）
- `role_menus` — 角色 ↔ 菜单关联
- `role_permissions` — 角色 ↔ 权限关联

### 股票数据（TimescaleDB 超表）
- `stock_basic` — 股票基础信息
- `stock_daily` / `stock_weekly` / `stock_monthly` / `stock_yearly` — K线数据
- `stock_daily_basic` — 每日因子（PE/PB/换手率/市值）
- `stock_fina_indicator` — 财务指标（季度）
- `stock_moneyflow` — 个股资金流向
- `sector_moneyflow_industry` / `sector_moneyflow_concept` — 板块资金流
- `moneyflow_hsgt` — 沪深港通资金流
- `index_basic` / `index_daily` — 指数信息和行情
- `stock_limit` — 涨跌停价格
- `top_list` / `top_inst` — 龙虎榜
- `ths_index` / `ths_daily` / `ths_member` — 同花顺指数
- `stock_concept` — 股票概念映射

## API 路由总览

| 前缀 | 模块 | 说明 |
|------|------|------|
| `/api/v1/auth` | auth | iOS 端认证（验证码/密码登录） |
| `/api/v1/admin` | admin | 管理后台（登录/路由/用户管理） |
| `/api/v1/stocks` | stocks | 股票数据查询（K线/资金流/自选股等） |
| `/api/v1/sync` | sync | 手动触发数据同步 |
| `/api/v1/scheduler` | scheduler | 定时任务调度管理 |
| `/api/v1/ts/*` | tushare | Tushare Pro 数据代理（239个接口） |

## 认证机制

- JWT Bearer Token，通过 `Authorization: Bearer <token>` 传递
- Token 有效期 7 天（可配置）
- 管理后台额外支持 refresh token（30天有效）

## 调度系统

基于 APScheduler 的后台定时任务，提供 REST API 管理：

预定义任务：
- `sync_daily_kline` — 日K线
- `sync_daily_basic` — 日线因子
- `sync_sector_moneyflow` — 板块资金流
- `sync_stock_moneyflow` — 个股资金流
- `sync_index_daily` — 指数日线
- `sync_moneyflow_hsgt` — 沪深港通
- `sync_stock_limit` — 涨跌停
- `sync_all` — 综合同步（以上全部）

支持 cron 和 interval 两种触发方式。
