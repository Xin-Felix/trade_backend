# AI 晨报功能文档

本文档描述 AI 晨报功能的特有实现。通用架构请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 08:30** 自动生成一份基于市场整体数据的 AI 晨报，每天仅生成一条记录。
- 所有登录用户均可查看今日晨报和历史晨报列表，**无会员/积分限制**。
- 后台管理可查看晨报记录、重新生成、编辑内容。
- 晨报数据基于上一交易日收盘数据 + 国际市场隔夜表现。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 |
|------|------|----------|
| 所有登录用户 | 免费 | 系统每日 08:30 自动生成 |
| 管理员 | 免费 | 后台可手动生成/重新生成/编辑 |

## 3. 数据组装

`build_market_context(report_date)` 组装以下数据：

| 模块 | 数据内容 | 数据来源 |
|------|----------|----------|
| 报告日期 | 当天日期 + 最新交易日标注 | `get_latest_trade_date()` |
| 主要指数 | 上证/深证/创业板最新行情 | Tushare `get_indices()` |
| 国际市场 | 全球指数（恒生/日经/韩国等）+ 商品/汇率 | 本地 `index_global` 表 + Tushare `fut_daily`/`fx_daily` |
| 板块资金流向 | 行业/概念板块 Top5 净流入 | 本地 `sector_moneyflow_*` 表 |
| 涨停梯队 | 连板天梯 + 热门涨停概念 | 本地 `limit_list_d` / `limit_step` 表 |
| 北向资金 | 近 3 个交易日净流入 | 本地 `moneyflow_hsgt` 表 |
| 热点概念 | DC 概念 + THS 热榜 | 本地 `dc_concept` / `ths_hot` 表 |

## 4. AI Prompt 核心要求

角色：盈多多AI晨报主编。

报告结构：
1. 昨日市场回顾（指数表现、涨跌家数、成交额变化、市场情绪）
2. 隔夜国际市场（欧美股市、亚太、商品/黄金/原油、汇率，及对今日A股可能影响）
3. 板块与资金流向（领涨/领跌板块、主力资金、北向资金趋势）
4. 热点与涨停梯队（热门概念、连板天梯、赚钱效应判断）
5. 今日开盘预判与关注（结合内外盘综合判断，2-3 个关注方向 + 1-2 个风险点）
6. 免责声明

约束：
- 总字数 ≤ 1000 字
- 开盘预判必须结合国际市场隔夜表现
- 数据驱动，引用具体数字
- 保持客观中性

## 5. 定时任务

| 配置 | 值 |
|------|-----|
| job_id | `generate_ai_morning_report` |
| 触发时间 | 周一至周五 08:30 |
| 数据基础 | 上一交易日收盘数据 |

## 6. 后台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/ai-morning-reports` | 晨报列表 |
| GET | `/api/v1/admin/ai-morning-reports/{id}` | 晨报详情 |
| PUT | `/api/v1/admin/ai-morning-reports/{id}` | 编辑晨报内容 |
| POST | `/api/v1/admin/ai-morning-reports/generate` | 手动生成 |
| POST | `/api/v1/admin/ai-morning-reports/{id}/regenerate` | 重新生成 |
| POST | `/api/v1/admin/ai-morning-reports/retry-failed` | 重试失败 |

## 7. 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/ai-morning-reports/today` | 任意登录用户 |
| GET | `/api/v1/ai-morning-reports` | 任意登录用户 |

## 8. 文件清单

### 后端
- `app/models/ai_morning_report.py`
- `app/services/ai_morning_report_service.py`
- `app/services/ai_service.py`（`morning_report` prompt）
- `app/services/global_market_service.py`
- `app/services/scheduler_service.py`
- `app/api/v1/endpoints/ai_morning_report.py`
- `app/api/v1/endpoints/ai_morning_report_admin.py`

### 前端
- `trade_admin/src/api/ai-morning-report.ts`
- `trade_admin/src/views/ai-content/morning-report/index.vue`

## 9. 注意事项

- 每天只生成一条晨报，重新生成会覆盖已有记录。
- 晨报 08:30 生成时使用上一交易日数据，需确保前一天盘后同步已完成。
- 国际市场数据从本地 `index_global` 表读取（16:50 同步），不再实时调外部 API，避免阻塞。
