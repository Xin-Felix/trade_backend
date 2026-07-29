# AI 仓位建议功能文档

本文档描述 AI 仓位建议功能的特有实现。通用架构请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 19:00** 自动为所有生效会员生成一份基于其持仓的 AI 仓位管理建议。
- 非会员积分用户可在 App 端手动点击生成今日仓位建议（按日扣减积分）。
- 会员可在 App/用户端查看自己的仓位建议列表和今日建议。
- 后台管理可查看所有会员/积分用户的记录、持仓数据源、重新生成、编辑内容。
- 若用户没有持仓，则基于通用市场数据生成一份策略建议。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 |
|------|------|----------|
| 会员 | 会员权益 | 每日 19:00 自动生成 |
| 非会员积分用户 | 100 积分/天 | App 端手动触发 |

## 3. 数据组装

`build_portfolio_context(db, user_id, market_context=...)` 组装以下数据：

### 3.1 通用市场数据（复用 `daily_review_service.build_market_context()`）

与复盘共享同一份市场上下文（大盘5天K线、国际市场、北向资金、涨跌停、板块资金流向）。
批量生成时只构建一次，传入所有用户复用。

### 3.2 持仓深度数据（每个用户单独查）

| 数据项 | 说明 |
|--------|------|
| 当日行情 | 现价、涨跌幅 |
| 持仓信息 | 成本价、收益率百分比（不暴露金额）、融资标记 |
| 基本面 | PE/PB/换手率/量比 |
| 近 5 天日K | 开高低收 |
| 近 4 周周K | 开高低收 |
| 近 3 天资金流向 | 大单/特大单净流入 |

### 3.3 持仓汇总

- 持仓数量、总收益率百分比、融资占比

## 4. AI Prompt 核心要求

角色：盈多多AI，专业 A 股仓位管理顾问，兼具技术分析和风险管理经验。

报告结构：
1. 持仓概览（总收益率、融资占比、整体风险评估）
2. 重点持仓点评（每只给出：盈亏和趋势判断 + **具体操作倾向**：加仓/持有/减仓/止损 + 融资风险提醒 + 自然融入情绪关怀）
3. 整体仓位策略（总仓位水平建议、行业集中度风险、调仓方向）
4. 免责声明

约束：
- 总字数 ≤ 1200 字
- 只给收益率百分比，不暴露具体金额
- 可以给倾向性建议（加仓/减仓/止损），但不给目标价
- 融资仓位强调杠杆风险
- 语调像靠谱的投顾朋友帮你把脉

## 5. 定时任务

| 配置 | 值 |
|------|-----|
| job_id | `generate_ai_position_advices` |
| 触发时间 | 周一至周五 19:00 |
| 并发控制 | 最多 3 路并发 AI 调用 |
| 市场数据复用 | 预构建一次 `build_market_context()`，所有用户共享 |
| 交易日判断 | 统一使用三层 fallback（stock_daily → TradeCal → weekday） |

## 6. 后台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/ai-position-advices` | 记录列表 |
| GET | `/api/v1/admin/ai-position-advices/{id}` | 详情 |
| PUT | `/api/v1/admin/ai-position-advices/{id}` | 编辑内容 |
| GET | `/api/v1/admin/ai-position-advices/{id}/portfolio-context` | 查看持仓数据源 |
| POST | `/api/v1/admin/ai-position-advices/generate` | 手动生成 |
| POST | `/api/v1/admin/ai-position-advices/{id}/regenerate` | 重新生成 |
| POST | `/api/v1/admin/ai-position-advices/retry-failed` | 重试失败 |

## 7. 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/ai-position-advices/today` | 会员/积分用户 |
| GET | `/api/v1/ai-position-advices` | 会员/积分用户 |
| GET | `/api/v1/ai-position-advices/{id}` | 会员/积分用户 |
| POST | `/api/v1/ai-position-advices/generate` | 会员/积分用户（积分按日扣 100） |

## 8. 与每日复盘的区别

| 维度 | 每日复盘 | 仓位建议 |
|------|----------|----------|
| 定位 | 回顾今天发生了什么 | 指导明天怎么操作 |
| 核心输出 | 分析 + 情绪关怀 | **操作建议**（加仓/减仓/止损） |
| 数据深度 | 5天K线 + 15分钟分时 + 资金流向 | 5天K线 + 4周周K + 资金流向 |
| 字数 | ≤ 1500 字 | ≤ 1200 字 |

## 9. 文件清单

### 后端
- `app/models/ai_position_advice.py`
- `app/models/portfolio.py`
- `app/services/ai_position_advice_service.py`
- `app/services/portfolio_service.py`
- `app/services/ai_service.py`（`position_advice` prompt）
- `app/services/daily_review_service.py`（`build_market_context` 复用）
- `app/services/scheduler_service.py`
- `app/api/v1/endpoints/ai_position_advice.py`
- `app/api/v1/endpoints/ai_position_advice_admin.py`

### 前端
- `trade_admin/src/api/ai-position-advice.ts`
- `trade_admin/src/views/ai-content/position-advice/index.vue`

## 10. 注意事项

- 持仓数据来自 `portfolio` 表（`users.public_id` 标识），仓位建议表用 `users.id` 标识，服务层已处理转换。
- 行情/K线/资金流来自本地表，需确保 19:00 前盘后数据同步已完成。
- `build_market_context()` 会做数据就绪校验，未同步完则 RuntimeError 拒绝生成。
- 全球指数从本地 `index_global` 表读取，商品/汇率用 Tushare `fut_daily`/`fx_daily`，不依赖 akshare。
