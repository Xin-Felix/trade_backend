# AI 晨报功能文档

本文档描述 AI 晨报功能的特有实现。通用架构、Context Builder、Prompt 设计、DIY 修改等请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 08:30** 自动生成一份基于市场整体数据的 AI 晨报，每天仅生成一条记录。
- 所有登录用户均可查看今日晨报和历史晨报列表，**无会员/积分限制**。
- 后台管理可查看晨报记录、重新生成、编辑内容。
- 晨报数据基于上一交易日收盘数据：主要指数、板块资金流向、涨停梯队、北向资金、热点概念等。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 | 说明 |
|------|------|----------|------|
| 所有登录用户 | 免费 | 系统每日 08:30 自动生成 | `ai_morning_report` 功能权限 `required_points: 0`，不设置 `required_tier`，且不在任何会员档位 features 中 |
| 管理员 | 免费 | 后台可手动生成/重新生成/编辑 | 管理端接口受 `require_admin` 保护 |

具体权限评估逻辑参见 `docs/ai-feature-base.md` 第 6.3 节。

## 3. 数据表

### `ai_morning_reports`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 自增主键 |
| `report_date` | DATE | 报告日期（当天日期） |
| `content` | TEXT | AI 生成的晨报内容（Markdown） |
| `status` | VARCHAR(20) | `pending / running / success / failed` |
| `error_message` | TEXT | 失败原因 |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

- 唯一约束：`report_date`，每天只保留一条晨报。
- 迁移文件：`alembic/versions/b25892702575_add_ai_morning_reports.py`

## 4. 后端实现

### 4.1 关键文件

| 文件 | 作用 |
|------|------|
| `app/models/ai_morning_report.py` | `AiMorningReport` 模型定义 |
| `app/services/ai_morning_report_service.py` | 晨报生成、查询、重试、编辑核心逻辑 |
| `app/services/ai_service.py` | AI 调用封装，含 `morning_report` system prompt |
| `app/services/scheduler_service.py` | 定时任务注册 `job_generate_ai_morning_report` |
| `app/services/scheduler_seed.py` | 默认 08:30 任务配置 |
| `app/services/admin_seed.py` | 后台菜单、功能权限种子 |
| `app/api/v1/endpoints/ai_morning_report.py` | 用户端接口（无权限限制，仅登录） |
| `app/api/v1/endpoints/ai_morning_report_admin.py` | 后台管理接口 |
| `app/schemas/ai_morning_report.py` | 请求/响应 schema |
| `app/api/v1/api.py` | 路由注册 |

### 4.2 服务层核心函数

```python
# app/services/ai_morning_report_service.py

# 生成指定日期的晨报（异步）
generate_morning_report(db, report_date)

# 同步包装，供定时任务调用
generate_morning_report_sync(db, report_date)

# 组装市场上下文文本（改数据源时主要改这里）
build_market_context(report_date)

# 更新晨报内容（管理员编辑）
update_morning_report_content(db, report_id, content)

# 用户端/管理端查询
get_morning_report_list(db, page, page_size)
get_morning_report_detail(db, report_id)
get_morning_report_by_date(db, report_date)
retry_failed_morning_report(db, report_date)
```

### 4.3 AI Prompt

Prompt 定义在 `app/services/ai_service.py` 的 `SYSTEM_PROMPTS["morning_report"]`：

```python
"morning_report": """你是盈多多AI晨报主编。请根据提供的前一交易日收盘数据，生成一份市场-wide 的 AI 晨报。

输出结构要求：
1. 昨日市场回顾（主要指数表现、涨跌家数、市场情绪）。
2. 板块与资金流向（领涨/领跌板块、主力资金动向、北向资金）。
3. 热点与涨停梯队（热门概念、连板天梯、涨停家数变化）。
4. 今日关注与风险提示（开盘预判、需关注的事件/数据、风险点）。
5. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 数据驱动，引用具体指数点位、涨跌幅、板块净流入、北向资金等数字。
- 保持客观中性，不直接推荐个股或买卖操作。
- 语言简洁专业，总字数控制在 800 字以内。
""",
```

调用入口：

```python
return await ai_service.analyze(
    prompt=prompt,
    role="morning_report",
    context=context
)
```

### 4.4 数据源

`build_market_context` 会自动获取本地最新交易日，并组装以下数据：

| 数据 | 来源 |
|------|------|
| 主要指数 | `stock_service.get_indices()` |
| 行业板块资金流向 | `stock_service.get_sector_moneyflow_rank(sector_type="industry")` |
| 概念板块资金流向 | `stock_service.get_sector_moneyflow_rank(sector_type="concept")` |
| 涨停梯队 | `limit_up_service.get_limit_up_ladder()` |
| 沪深港通资金 | `stock_service.get_moneyflow_hsgt()` |
| 热点概念 | `DcConcept` / `ThsHot` / `DcHot` 表 |

### 4.5 定时任务

`app/services/scheduler_service.py`：

```python
def job_generate_ai_morning_report(days: int = 1):
    from app.services.ai_morning_report_service import generate_morning_report_sync
    from app.db.base import SessionLocal
    from datetime import date

    db = SessionLocal()
    try:
        report_date = date.today()
        report = generate_morning_report_sync(db, report_date)
        logger.info(f"[Scheduler] AI 晨报生成完成: {report.status}")
    finally:
        db.close()
```

> 说明：晨报是全局记录（每天一条），`generate_morning_report_sync` 需要调用方传入 `db`，因此 job 中显式创建并关闭 SessionLocal。每日复盘、仓位建议为用户维度，`generate_*_for_all_members` 内部自行管理 session，所以它们的 job 示例中不展示 SessionLocal。

注册：

```python
JOB_REGISTRY = {
    ...
    "generate_ai_morning_report": job_generate_ai_morning_report,
}

JOB_DESCRIPTIONS = {
    ...
    "generate_ai_morning_report": "[AI] 每日自动生成市场晨报",
}
```

默认配置在 `app/services/scheduler_seed.py`：

```python
{
    "job_id": "generate_ai_morning_report",
    "description": "AI 每日市场晨报",
    "trigger_type": "cron",
    "cron_hour": 8,
    "cron_minute": 30,
    "cron_day_of_week": "mon-fri",
    "days": 1,
    "enabled": 1,
}
```

定时任务在 `mon-fri` 运行，内部使用本地最新交易日数据；若本地无最新数据，则生成失败并记录错误。手动触发接口不受影响。

### 4.6 后台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/ai-morning-reports` | 晨报记录列表，支持 `report_date`、`status` |
| GET | `/api/v1/admin/ai-morning-reports/{id}` | 晨报详情 |
| PUT | `/api/v1/admin/ai-morning-reports/{id}` | 编辑晨报内容 |
| POST | `/api/v1/admin/ai-morning-reports/generate` | 手动生成（可指定 `report_date`） |
| POST | `/api/v1/admin/ai-morning-reports/{id}/regenerate` | 重新生成指定晨报 |
| POST | `/api/v1/admin/ai-morning-reports/retry-failed` | 重试失败记录 |

### 4.7 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/ai-morning-reports/today` | 任意登录用户 |
| GET | `/api/v1/ai-morning-reports` | 任意登录用户 |

## 5. 前端实现

前端项目位于 `trade_admin/`。

### 5.1 关键文件

| 文件 | 作用 |
|------|------|
| `trade_admin/src/api/ai-morning-report.ts` | 对接后端接口 |
| `trade_admin/src/views/ai-content/morning-report/index.vue` | 后台管理页面 |

### 5.2 页面功能

- 列表：日期、状态筛选；关键词搜索。
- 操作：生成今日晨报、重试失败、重新生成。
- 详情弹窗：
  - 显示晨报状态
  - 显示 AI 生成的 Markdown 晨报内容
  - 支持点击「编辑内容」进入 Markdown 编辑器，保存后更新后端

## 6. 文件清单

### 后端

- `app/models/ai_morning_report.py`
- `app/models/__init__.py`
- `app/services/ai_morning_report_service.py`
- `app/services/ai_service.py`
- `app/services/scheduler_service.py`
- `app/services/scheduler_seed.py`
- `app/services/admin_seed.py`
- `app/services/stock_service.py`
- `app/services/limit_up_service.py`
- `app/models/analysis.py`
- `app/api/v1/endpoints/ai_morning_report.py`
- `app/api/v1/endpoints/ai_morning_report_admin.py`
- `app/schemas/ai_morning_report.py`
- `app/api/v1/api.py`
- `alembic/versions/b25892702575_add_ai_morning_reports.py`

### 前端

- `trade_admin/src/api/ai-morning-report.ts`
- `trade_admin/src/views/ai-content/morning-report/index.vue`

## 7. 注意事项

- 每天只生成一条晨报，手动重新生成会覆盖已有记录。
- 晨报数据来自本地 `stock_daily` / `stock_daily_basic` / `sector_moneyflow_*` / `limit_*` / `dc_concept` 等表，需确保盘后数据同步已完成。
- 生成时间建议在交易日 08:30，确保使用上一交易日收盘数据。
- 通用架构、Context Builder、Prompt 三层设计、DIY 修改等参见 `docs/ai-feature-base.md`。
