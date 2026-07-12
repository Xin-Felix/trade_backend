# AI 仓位建议功能文档

本文档描述 AI 仓位建议功能的特有实现。通用架构、Context Builder、Prompt 设计、DIY 修改等请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 19:00** 自动为所有生效会员生成一份基于其持仓的 AI 仓位管理建议。
- 非会员积分用户可在 App 端手动点击生成今日仓位建议（按日扣减积分）。
- 会员可在 App/用户端查看自己的仓位建议列表和今日建议。
- 后台管理可查看所有会员/积分用户的仓位建议记录、持仓数据源、重新生成、编辑内容。
- 若用户没有持仓，则基于其自选股生成一份通用的仓位策略建议。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 | 说明 |
|------|------|----------|------|
| 会员 | 会员权益 | 每日 19:00 自动生成 | VIP/SVIP 档位 features 包含 `ai_position_advice` |
| 非会员积分用户 | 100 积分/天 | App 端手动触发 | `ai_position_advice` 设置 `required_points: 100`、`consume_mode: per_day`，不设置 `required_tier` |

具体权限评估逻辑参见 `docs/ai-feature-base.md` 第 6.3 节。

## 3. 数据表

### `ai_position_advices`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 自增主键 |
| `user_id` | INTEGER FK → users.id | 用户内部 ID |
| `report_date` | DATE | 报告日期 |
| `content` | TEXT | AI 生成的仓位建议内容（Markdown） |
| `status` | VARCHAR(20) | `pending / running / success / failed` |
| `error_message` | TEXT | 失败原因 |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

- 唯一约束：`(user_id, report_date)`，防止同一用户同一天重复生成。
- 迁移文件：`alembic/versions/998f1a99546c_add_ai_position_advices.py`

### 持仓数据源

仓位建议依赖 `portfolio` 表，当前字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | VARCHAR(36) FK → users.public_id | 用户 public_id（与前端、数据同步侧保持一致） |
| `ts_code` | VARCHAR(20) | Tushare 标准代码 |
| `code` | VARCHAR(20) | 原始股票代码 |
| `name` | VARCHAR(100) | 股票名称 |
| `cost_price` | NUMERIC(12,4) | 成本价 |
| `quantity` | NUMERIC(15,4) | 持仓数量（股数） |
| `is_margin` | BOOLEAN | 是否融资持仓 |
| `note` | VARCHAR(500) | 持仓备注 |

- 迁移文件：`alembic/versions/0f84dc4bca24_add_portfolio.py`、`alembic/versions/6fa4fe62d3a8_add_portfolio_cost_price_quantity_margin.py`
- **注意**：`portfolio` 表使用 `users.public_id` 作为用户标识，而 `ai_position_advices` 表使用 `users.id`。服务层在查询和写入时需注意内部 `user_id`（int）与 `public_id`（string）的转换。

## 4. 后端实现

### 4.1 关键文件

| 文件 | 作用 |
|------|------|
| `app/models/ai_position_advice.py` | `AiPositionAdvice` 模型定义 |
| `app/models/portfolio.py` | `Portfolio` 模型定义 |
| `app/services/ai_position_advice_service.py` | 仓位建议生成、查询、重试、编辑核心逻辑 |
| `app/services/portfolio_service.py` | 持仓增删查改 |
| `app/services/ai_service.py` | AI 调用封装，含 `position_advice` system prompt |
| `app/services/scheduler_service.py` | 定时任务注册 `job_generate_ai_position_advices` |
| `app/services/scheduler_seed.py` | 默认 19:00 任务配置 |
| `app/services/admin_seed.py` | 后台菜单、会员档位 features、功能权限种子 |
| `app/api/v1/endpoints/ai_position_advice.py` | 用户端接口（含手动生成） |
| `app/api/v1/endpoints/ai_position_advice_admin.py` | 后台管理接口 |
| `app/schemas/ai_position_advice.py` | 请求/响应 schema |
| `app/api/v1/api.py` | 路由注册 |

### 4.2 服务层核心函数

```python
# app/services/ai_position_advice_service.py

# 为单个用户生成仓位建议（异步）
generate_position_advice_for_user(db, user_id, report_date)

# 同步包装，供定时任务调用
generate_position_advice_for_user_sync(db, user_id, report_date)

# 为所有生效会员批量生成
generate_position_advices_for_all_members(report_date=None, skip_non_trading_day=False)

# 获取用户持仓结构化数据（后台查看用）
get_user_portfolio_data(db, user_id)

# 组装 AI 上下文文本（改数据源时主要改这里）
build_portfolio_context(db, user_id)

# 更新仓位建议内容（管理员编辑）
update_advice_content(db, advice_id, content)

# 用户端/管理端查询
get_user_advices(db, user_id, page, page_size)
get_advice_detail(db, advice_id, user_id=None)
get_admin_advices(db, user_id, report_date, status, page, page_size)
retry_failed_advices(db, report_date)
```

**无持仓时的 fallback**：若用户当前没有持仓，`build_portfolio_context` 会退化为基于其自选股构建上下文，AI 在 Prompt 约束下生成一份通用仓位策略建议（不针对具体个股给出买卖指令）。

### 4.3 AI Prompt

Prompt 定义在 `app/services/ai_service.py` 的 `SYSTEM_PROMPTS["position_advice"]`：

```python
"position_advice": """你是一位专业的 A 股仓位管理顾问，名叫"盈多多AI"。
请根据用户当前持仓（以及可选的自选股），生成一份结构化的仓位建议报告。

输出结构要求：
1. 持仓概览（用2-3句话概括当前持仓数量、行业/概念分布、整体风险暴露）。
2. 重点持仓点评（按持仓市值/涨跌幅排序，点评 Top 5；给出加/减/持有的倾向性建议及理由）。
3. 仓位调整建议（总体仓位水平建议、需要警惕的风险信号、可关注的加仓方向）。
4. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 只提供仓位管理建议，不直接给出买卖指令或目标价。
- 数据驱动，引用具体涨跌幅、PE/PB、换手率、资金流向等数字。
- 保持客观中性，提示风险，不做收益承诺。
- 语言简洁专业，总字数控制在 600 字以内。
- 若用户没有持仓，则基于其自选股生成一份通用的仓位策略建议。
""",
```

调用入口：

```python
return await ai_service.analyze(
    prompt=prompt,
    role="position_advice",
    context=context
)
```

### 4.4 定时任务

`app/services/scheduler_service.py`：

```python
def job_generate_ai_position_advices(days: int = 1):
    from app.services.ai_position_advice_service import generate_position_advices_for_all_members
    from datetime import date

    report_date = date.today()
    generate_position_advices_for_all_members(report_date=report_date, skip_non_trading_day=True)
```

注册：

```python
JOB_REGISTRY = {
    ...
    "generate_ai_position_advices": job_generate_ai_position_advices,
}

JOB_DESCRIPTIONS = {
    ...
    "generate_ai_position_advices": "[AI] 每日自动生成会员仓位建议",
}
```

默认配置在 `app/services/scheduler_seed.py`：

```python
{
    "job_id": "generate_ai_position_advices",
    "description": "AI 每日会员仓位建议",
    "trigger_type": "cron",
    "cron_hour": 19,
    "cron_minute": 0,
    "cron_day_of_week": "mon-fri",
    "days": 1,
    "enabled": 1,
}
```

仅交易日执行逻辑参见 `docs/ai-feature-base.md` 第 6.2 节。

### 4.5 后台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/ai-position-advices` | 仓位建议记录列表，支持 `report_date`、`status`、`keyword`、`user_public_id` |
| GET | `/api/v1/admin/ai-position-advices/{id}` | 仓位建议详情 |
| PUT | `/api/v1/admin/ai-position-advices/{id}` | 编辑仓位建议内容 |
| GET | `/api/v1/admin/ai-position-advices/{id}/portfolio-context` | 查看该建议用户的持仓数据 |
| GET | `/api/v1/admin/ai-position-advices/users/available` | 已生成仓位建议的用户下拉列表 |
| POST | `/api/v1/admin/ai-position-advices/generate` | 手动生成（可指定 `user_public_id`） |
| POST | `/api/v1/admin/ai-position-advices/{id}/regenerate` | 重新生成指定建议 |
| POST | `/api/v1/admin/ai-position-advices/retry-failed` | 重试失败记录 |

### 4.6 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/ai-position-advices/today` | 会员/积分用户 |
| GET | `/api/v1/ai-position-advices` | 会员/积分用户 |
| GET | `/api/v1/ai-position-advices/{id}` | 会员/积分用户 |
| POST | `/api/v1/ai-position-advices/generate` | 会员/积分用户（积分用户会按日扣 100 积分） |

## 5. 前端实现

前端项目位于 `trade_admin/`。

### 5.1 关键文件

| 文件 | 作用 |
|------|------|
| `trade_admin/src/api/ai-position-advice.ts` | 对接后端接口 |
| `trade_admin/src/views/ai-content/position-advice/index.vue` | 后台管理页面 |

### 5.2 页面功能

- 列表：日期、状态、会员用户筛选；关键词搜索。
- 操作：全部生成、重试失败、为选中用户生成、重新生成。
- 详情弹窗：
  - 显示用户基本信息和状态
  - 显示「用户持仓数据」表格（代码、现价、涨跌幅、成本、持仓量、市值、浮盈/亏、盈亏%、融资标识）
  - 显示 AI 生成的 Markdown 仓位建议内容
  - 支持点击「编辑内容」进入 Markdown 编辑器，保存后更新后端

## 6. 文件清单

### 后端

- `app/models/ai_position_advice.py`
- `app/models/portfolio.py`
- `app/models/__init__.py`
- `app/services/ai_position_advice_service.py`
- `app/services/portfolio_service.py`
- `app/services/ai_service.py`
- `app/services/scheduler_service.py`
- `app/services/scheduler_seed.py`
- `app/services/admin_seed.py`
- `app/api/v1/endpoints/ai_position_advice.py`
- `app/api/v1/endpoints/ai_position_advice_admin.py`
- `app/schemas/ai_position_advice.py`
- `app/api/v1/api.py`
- `alembic/versions/998f1a99546c_add_ai_position_advices.py`
- `alembic/versions/0f84dc4bca24_add_portfolio.py`
- `alembic/versions/6fa4fe62d3a8_add_portfolio_cost_price_quantity_margin.py`

### 前端

- `trade_admin/src/api/ai-position-advice.ts`
- `trade_admin/src/views/ai-content/position-advice/index.vue`

## 7. 注意事项

- 持仓数据来自 `portfolio` 表，行情数据来自本地 `stock_daily` / `stock_daily_basic` 表，需确保盘后数据同步已完成（建议 19:00 之后生成）。
- `portfolio` 表以 `users.public_id` 为用户标识，`ai_position_advices` 表以 `users.id` 为用户标识，服务层需做好转换。
- 通用架构、Context Builder、Prompt 三层设计、DIY 修改等参见 `docs/ai-feature-base.md`。
