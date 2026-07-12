# AI 每日复盘功能文档

本文档描述 AI 每日复盘功能的特有实现。通用架构、Context Builder、Prompt 设计、DIY 修改等请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 17:00** 自动为所有生效会员生成一份基于其自选股的 AI 复盘报告。
- 积分用户目前仅可在后台/管理端触发为其生成；App 端手动生成是后续规划功能。
- 会员可在 App/用户端查看自己的复盘列表和今日复盘。
- 后台管理可查看所有会员/积分用户的复盘记录、自选股数据源、重新生成、编辑内容。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 | 说明 |
|------|------|----------|------|
| 会员 | 会员权益 | 每日 17:00 自动生成 | VIP/SVIP 档位 features 包含 `ai_daily_review` |
| 非会员积分用户 | 100 积分/天 | 管理端手动触发 | `ai_daily_review` 设置 `required_points: 100`、`consume_mode: per_day` |

具体权限评估逻辑参见 `docs/ai-feature-base.md` 第 6.3 节。

## 3. 数据表

### `daily_reviews`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 自增主键 |
| `user_id` | INTEGER FK → users.id | 用户内部 ID |
| `report_date` | DATE | 复盘日期 |
| `content` | TEXT | AI 生成的复盘内容（Markdown） |
| `status` | VARCHAR(20) | `pending / running / success / failed` |
| `error_message` | TEXT | 失败原因 |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

- 唯一约束：`(user_id, report_date)`，防止同一用户同一天重复生成。
- 迁移文件：`alembic/versions/8f9c7e6d2a41_add_daily_reviews.py`

## 4. 后端实现

### 4.1 关键文件

| 文件 | 作用 |
|------|------|
| `app/models/daily_review.py` | `DailyReview` 模型定义 |
| `app/services/daily_review_service.py` | 复盘生成、查询、重试、编辑核心逻辑 |
| `app/services/ai_service.py` | AI 调用封装，含 `daily_review` system prompt |
| `app/services/scheduler_service.py` | 定时任务注册 `job_generate_daily_reviews` |
| `app/services/scheduler_seed.py` | 默认 17:00 任务配置 |
| `app/services/admin_seed.py` | 后台菜单、会员档位 features、功能权限种子 |
| `app/api/v1/endpoints/daily_review.py` | 用户端接口 |
| `app/api/v1/endpoints/daily_review_admin.py` | 后台管理接口 |
| `app/schemas/daily_review.py` | 请求/响应 schema |
| `app/api/v1/api.py` | 路由注册 |

### 4.2 服务层核心函数

```python
# app/services/daily_review_service.py

# 为单个用户生成复盘（异步）
generate_daily_review_for_user(db, user_id, report_date)

# 同步包装，供定时任务调用
generate_daily_review_for_user_sync(db, user_id, report_date)

# 为所有生效会员批量生成
generate_daily_reviews_for_all_members(report_date=None, skip_non_trading_day=False)

# 获取用户自选股结构化数据（后台查看用）
get_user_watchlist_data(db, user_id)

# 组装 AI 上下文文本
build_watchlist_context(db, user_id)

# 更新复盘内容（管理员编辑）
update_review_content(db, review_id, content)

# 用户端/管理端查询
get_user_reviews(db, user_id, page, page_size)
get_review_detail(db, review_id, user_id=None)
get_admin_reviews(db, user_id, report_date, status, page, page_size)
retry_failed_reviews(db, report_date)
```

### 4.3 AI Prompt

Prompt 定义在 `app/services/ai_service.py` 的 `SYSTEM_PROMPTS["daily_review"]`：

```python
"daily_review": """你是一位专业的A股收盘复盘助手，名叫"盈多多AI"。
你的任务是根据用户当天的自选股表现，生成一份结构化、个性化的每日复盘报告。

输出结构要求：
1. 账户关注概览（用2-3句话概括用户自选股整体表现、涨跌分布）。
2. 重点个股点评（按涨跌幅排序，点评 Top 5 自选股；包含技术面、资金面、所属板块/概念的简要分析）。
3. 明日关注与风险提示（列出1-2个需要关注的事件、数据或技术信号，以及1-2个风险点）。
4. 免责声明：以上分析仅供参考，不构成投资建议。

注意事项：
- 数据驱动，引用具体涨跌幅、PE/PB、换手率等数字。
- 保持客观中性，不直接推荐买卖。
- 语言简洁专业，总字数控制在 600 字以内。
- 若用户没有自选股，则生成一份面向整体市场的通用收盘复盘。
""",
```

调用入口：

```python
return await ai_service.analyze(
    prompt=prompt,
    role="daily_review",
    context=context
)
```

### 4.4 定时任务

`app/services/scheduler_service.py`：

```python
def job_generate_daily_reviews(days: int = 1):
    from app.services.daily_review_service import generate_daily_reviews_for_all_members
    from datetime import date

    report_date = date.today()
    generate_daily_reviews_for_all_members(report_date=report_date, skip_non_trading_day=True)
```

注册：

```python
JOB_REGISTRY = {
    ...
    "generate_daily_reviews": job_generate_daily_reviews,
}

JOB_DESCRIPTIONS = {
    ...
    "generate_daily_reviews": "[AI] 每日自动生成会员复盘",
}
```

默认配置在 `app/services/scheduler_seed.py`：

```python
{
    "job_id": "generate_daily_reviews",
    "description": "AI 每日会员复盘",
    "trigger_type": "cron",
    "cron_hour": 17,
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
| GET | `/api/v1/admin/daily-reviews` | 复盘记录列表，支持 `report_date`、`status`、`keyword`、`user_public_id` |
| GET | `/api/v1/admin/daily-reviews/{id}` | 复盘详情 |
| PUT | `/api/v1/admin/daily-reviews/{id}` | 编辑复盘内容 |
| GET | `/api/v1/admin/daily-reviews/{id}/watchlist` | 查看该复盘用户的自选股数据 |
| GET | `/api/v1/admin/daily-reviews/users/available` | 已生成复盘的用户下拉列表 |
| POST | `/api/v1/admin/daily-reviews/generate` | 手动生成（可指定 `user_public_id`） |
| POST | `/api/v1/admin/daily-reviews/{id}/regenerate` | 重新生成指定复盘 |
| POST | `/api/v1/admin/daily-reviews/retry-failed` | 重试失败记录 |

### 4.6 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/daily-reviews/today` | 会员/积分用户 |
| GET | `/api/v1/daily-reviews` | 会员/积分用户 |
| GET | `/api/v1/daily-reviews/{id}` | 会员/积分用户 |

## 5. 前端实现

前端项目位于 `trade_admin/`。

### 5.1 关键文件

| 文件 | 作用 |
|------|------|
| `trade_admin/src/api/daily-review.ts` | 对接后端接口 |
| `trade_admin/src/views/daily-review/index.vue` | 后台管理页面 |

### 5.2 页面功能

- 列表：日期、状态、会员用户筛选；关键词搜索。
- 操作：全部生成、重试失败、为选中用户生成、重新生成。
- 详情弹窗：
  - 显示用户基本信息和状态
  - 显示「用户自选股数据」表格（代码、现价、涨跌幅、PE、PB、换手）
  - 显示 AI 生成的 Markdown 复盘内容
  - 支持点击「编辑内容」进入 Markdown 编辑器，保存后更新后端

## 6. 文件清单

### 后端

- `app/models/daily_review.py`
- `app/models/__init__.py`
- `app/services/daily_review_service.py`
- `app/services/ai_service.py`
- `app/services/scheduler_service.py`
- `app/services/scheduler_seed.py`
- `app/services/admin_seed.py`
- `app/api/v1/endpoints/daily_review.py`
- `app/api/v1/endpoints/daily_review_admin.py`
- `app/schemas/daily_review.py`
- `app/api/v1/api.py`
- `alembic/versions/8f9c7e6d2a41_add_daily_reviews.py`

### 前端

- `trade_admin/src/api/daily-review.ts`
- `trade_admin/src/views/daily-review/index.vue`

## 7. 注意事项

- 自选股数据来自本地 `stock_daily` / `stock_daily_basic` 表，需确保盘后数据同步已完成（建议 17:00 之后生成）。
- 通用架构、Context Builder、Prompt 三层设计、DIY 修改等参见 `docs/ai-feature-base.md`。
