# AI 功能通用底座文档

本文档汇总 Ying+ 所有 AI 功能（每日复盘、仓位建议、晨报等）的通用架构、数据流、Prompt 设计、后端/前端实现模式及 DIY 修改入口。各功能特有内容请参见对应的功能文档：

- `docs/daily-review.md` — AI 每日复盘
- `docs/ai-position-suggestion.md` — AI 仓位建议
- `docs/ai-morning-report.md` — AI 晨报

## 1. 功能概述

所有 AI 功能都遵循同一套底座：

- **Context Builder**：把用户数据、行情数据、新闻事件等整理成结构化上下文。
- **三层 Prompt**：System Prompt + Context JSON + Task Prompt。
- **DeepSeek API**：通过 `app/services/ai_service.py` 统一调用。
- **分层权限**：免费 / 积分按需 / 会员自动。
- **后台管理**：管理员可查看记录、数据源、重新生成、编辑内容。

设计目标：让 AI 输出围绕用户自己的股票和持仓，生成真正个性化、具有可读性和可执行价值的报告。

## 2. 产品定位与分层

为兼顾体验与 AI 成本，AI 内容分为三级：

| 层级 | 名称 | 计费/权限 | 获取方式 | 内容 | 典型长度 |
|------|------|----------|---------|------|---------|
| 一级 | 免费内容 | 免费 | 每日自动，全市场通用 | 极简市场概况/一句话总结 | 1~2 句 |
| 二级 | 积分内容 | 积分 | 用户手动点击生成 | 市场/板块/个股分析、风险提示 | 500~1200 字 |
| 三级 | 会员内容 | 会员权益 | 每日自动为每个会员生成 | 在积分内容基础上增加更详细的个股点评、仓位建议、多情景推演等 | 1000~2500 字 |

具体每个功能对应哪一级，由各功能文档说明。

## 3. 整体架构

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  用户数据    │   │  行情数据    │   │  新闻事件    │
│ (自选/持仓)  │   │ (大盘/板块)  │   │ (公告/政策)  │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                 ┌───────────────┐
                 │ Context Builder │
                 │  生成统一上下文  │
                 └───────┬───────┘
                         ▼
                 ┌───────────────┐
                 │ 三层 Prompt   │
                 │ System + Task │
                 └───────┬───────┘
                         ▼
                 ┌───────────────┐
                 │   LLM 输出    │
                 └───────┬───────┘
                         ▼
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ 免费通用内容   │ │ 积分按需内容   │ │ 会员自动内容   │
└───────────────┘ └───────────────┘ └───────────────┘
```

设计原则：

- **Context Builder 是核心**：所有原始数据先整理成统一上下文，再交给 AI。
- **AI 不做复杂计算**：MA、MACD、趋势、情绪等指标由后端计算好，以结论形式写入 Context。
- **AI 不读原始序列**：不给 AI 分时、逐笔等原始序列，只给压缩后的结构化描述。
- **一份 Context，多处复用**：同一套上下文未来可服务于盘前策略、持仓分析、周报月报等功能。

## 4. Context Builder

### 4.1 设计目标

Context Builder 负责把 Tushare、交易所、新闻、用户自选等多个数据源整理成一份结构化上下文，作为大模型输入。

目标：

- 降低 Token 消耗
- 保持数据一致性
- 避免模型重复计算
- 提高输出稳定性
- 支持不同 AI 模型复用

### 4.2 通用 Context 结构

各功能推荐的统一顶层结构：

```json
{
  "date": "2026-07-12",
  "market": {},
  "emotion": {},
  "sector": {},
  "watchlist": [],
  "holding": [],
  "news": [],
  "strategy": {}
}
```

各字段含义：

| 字段 | 说明 |
|------|------|
| `market` | 大盘指数、成交额、涨跌分布、北向资金等 |
| `emotion` | 市场情绪评分、趋势、赚钱效应等 |
| `sector` | 领涨/领跌板块及资金流向 |
| `watchlist` | 用户自选股列表（价格、涨跌幅、PE/PB、技术结论等） |
| `holding` | 用户持仓（成本、数量、盈亏、融资标识等） |
| `news` | 相关新闻事件摘要 |
| `strategy` | 程序提前生成的策略标签 |

具体字段由各功能根据数据源填充。

### 4.3 当前实现

所有 AI 功能的市场数据都从本地数据库读取，不在 AI 生成时调用外部 API（避免阻塞）：

| 数据 | 来源 | 说明 |
|------|------|------|
| A 股指数/个股 | 本地 `index_daily` / `stock_daily` 表 | 16:05~16:45 盘后同步 |
| 全球指数 | 本地 `index_global` 表 | Tushare `index_global` 16:50 同步 |
| 商品期货 | Tushare `fut_daily` + `fut_mapping` | 沪金/沪银/原油/沪铜主力合约 |
| 外汇 | Tushare `fx_daily` | 美元人民币/欧元/日元 |
| 北向资金 | 本地 `moneyflow_hsgt` 表 | 16:55 同步 |
| 板块资金流 | 本地 `sector_moneyflow_*` 表 | 16:35 同步 |
| 涨跌停/连板 | 本地 `limit_list_d` / `limit_step` 表 | 17:05~17:15 同步 |
| 个股资金流向 | 本地 `stock_moneyflow` 表 | 16:25 同步 |
| 分时 K 线 | 本地 `stock_intraday` 表 | 16:30 同步 |

**批量生成时的数据复用模式**：通用市场数据（`build_market_context()`）只构建一次，所有用户共享传入。个股数据每个用户单独查询。

**数据就绪校验**：AI 生成前会自动检查当天各核心数据源是否已同步完成，未就绪则拒绝生成并记录失败原因。

## 5. Prompt 三层架构

所有 AI 功能统一采用：

```
System Prompt
    ↓
Context JSON / 文本
    ↓
Task Prompt
    ↓
LLM
    ↓
Response
```

### 5.1 System Prompt（固定）

负责定义 AI 角色和通用约束，长期保持稳定。当前位于 `app/services/ai_service.py` 的 `SYSTEM_PROMPTS` 中。

示例：

```markdown
你是一位拥有15年以上经验的A股职业交易员和投资顾问，名叫"盈多多AI"。
你的分析必须满足以下要求：
1. 所有观点必须依据提供的数据。
2. 禁止编造任何事实。
3. 禁止预测确定性结果。
4. 允许表达概率和风险。
5. 优先分析用户关注的股票。
6. 如果数据不足，请明确说明。
7. 语言专业、客观、简洁。
8. 不要重复输入数据。
9. 所有分析必须具有可执行价值。
```

### 5.2 Context

即 Context Builder 的输出，只描述事实，不告诉 AI 怎么写。

### 5.3 Task Prompt（按功能定制）

负责告诉 AI 今天要完成什么任务、输出什么格式。各功能文档会给出对应 Task Prompt。

### 5.4 输出格式约束

推荐统一 Markdown 结构，典型五段式：

```markdown
# 市场概况
...

# 板块/资金流向
...

# 个股/持仓分析
...

# 风险提示
...

# 明日关注
...
```

禁止：

- 今天一定上涨。
- 明天肯定涨停。
- 建议全仓买入。
- 百分百机会。

允许：

- 若成交量继续放大，则趋势有望延续。
- 若跌破5日均线，需关注短线转弱风险。

### 5.5 Few-shot 示例

在 Task Prompt 中提供 1~2 个优秀示例，可显著提升不同模型之间输出一致性。

### 5.6 Prompt 版本管理

建议记录每次生成使用的 Prompt 版本号，便于问题追溯和 A/B Test。实现方式：

- 在记录表中增加 `prompt_version` 字段（如 `daily_reviews.prompt_version`）。
- 在 `ai_service.py` 中为每个 role 维护版本号常量。
- 生成时将版本号写入记录，便于后续按版本过滤和对比效果。

当前状态：每日复盘表已包含 `prompt_version` 字段，仓位建议和晨报表尚未添加，后续可统一补齐。

## 6. 后端通用实现

### 6.1 AI 调用封装与接口命名

统一入口：`app/services/ai_service.py`

```python
return await ai_service.analyze(
    prompt=task_prompt,
    role="market_analyst",  # 或各功能自定义 role
    context=context
)
```

各功能可在 `SYSTEM_PROMPTS` 中新增自己的 role key。

**接口命名规范**：AI 功能的路由前缀统一使用复数名词，保持 REST 风格一致。

| 功能 | 用户端前缀 | 管理端前缀 |
|------|-----------|-----------|
| 每日复盘 | `/api/v1/daily-reviews` | `/api/v1/admin/daily-reviews` |
| 仓位建议 | `/api/v1/ai-position-advices` | `/api/v1/admin/ai-position-advices` |
| 晨报 | `/api/v1/ai-morning-reports` | `/api/v1/admin/ai-morning-reports` |

### 6.2 定时任务

定时任务注册在 `app/services/scheduler_service.py` 的 `JOB_REGISTRY` / `JOB_DESCRIPTIONS` 中。默认配置在 `app/services/scheduler_seed.py`。

通用模式：

```python
def job_generate_xxx(days: int = 1):
    from app.services.xxx_service import generate_xxx
    from datetime import date

    report_date = date.today()
    generate_xxx(report_date=report_date)
```

仅交易日执行的判断：

```python
# 获取本地最新交易日
get_latest_trade_date(db)

# 判断某天是否为交易日
is_trading_day(db, target_date)
```

### 6.3 后台菜单与权限

后台菜单在 `app/services/admin_seed.py` 的 `_SEED_MENUS` 中定义。AI 功能统一放在「AI 内容管理」目录下。

功能权限在 `_SEED_FEATURE_PERMISSIONS` 中定义。权限评估在 `app/services/membership_service.py` 的 `check_and_consume` 中：

1. admin / 未配置功能 → 通过
2. 生效会员且 tier features 包含该功能 → 通过（不扣积分）
3. `required_role` 匹配 → 通过
4. 每日免费额度内 → 通过
5. 积分充足 → 扣积分通过
6. 否则拒绝

因此，要实现「会员自动 + 积分按需」，只需：

- 把功能加入对应会员档位的 `features` 列表。
- 功能权限中不设置 `required_tier`，设置 `required_points` 和 `consume_mode`。

要实现「完全免费」，设置 `required_points: 0` 且不要设置 `required_tier`，并移出会员档位 features。

### 6.4 数据表模式

每个 AI 功能通常有一张记录表，字段模式类似：

| 字段 | 说明 |
|------|------|
| `id` | SERIAL PK |
| `user_id` / `report_date` | 用户标识 + 日期（个人功能）；仅 `report_date`（全局功能） |
| `content` | AI 生成的 Markdown 内容 |
| `status` | `pending / running / success / failed` |
| `error_message` | 失败原因 |
| `created_at` / `updated_at` | 时间戳 |

### 6.5 状态流转与幂等

记录状态机：

```
pending → running → success
              ↘ failed
```

- `pending`：记录已创建，尚未开始生成。
- `running`：正在调用 AI 或组装上下文。
- `success`：AI 返回内容并保存成功。
- `failed`：生成过程中出现异常，`error_message` 记录原因。

幂等性设计：

- 个人功能（每日复盘、仓位建议）通过数据库唯一约束 `(user_id, report_date)` 防止同一天重复创建记录。
- 全局功能（晨报）通过唯一约束 `(report_date)` 保证每天只有一条。
- 重新生成时，服务层应更新已有记录的状态和内容，而不是插入新记录。
- 手动触发接口需考虑并发：同一用户/同一天的多并发请求应由唯一约束或行锁兜底，避免重复扣积分或重复调用 AI。

### 6.6 并发与失败隔离

当前批量生成采用串行逐用户执行，实现简单但会员数较多时较慢。设计要点：

- **失败隔离**：单个用户生成失败只更新该用户记录为 `failed`，不影响其他用户。
- **异常捕获**：每个用户的生成逻辑外层包裹 `try/except`，记录 `error_message`。
- **后续优化方向**：可改为线程池/进程池并发，或接入消息队列（Celery/RQ）实现异步削峰。
- **AI 调用超时**：`ai_service.analyze` 应设置合理超时，避免阻塞整个批量任务。

### 6.7 成本监控与告警

建议关注的指标：

| 指标 | 采集方式 | 告警阈值建议 |
|------|---------|------------|
| 单次 AI 调用 Token 数 | DeepSeek API 返回的 usage | 超过平均值 3 倍 |
| 单日 AI 调用总费用 | 汇总 usage × 单价 | 超过预算 80% |
| 生成失败率 | `failed` 记录数 / 总记录数 | 连续 3 次调度失败率 > 10% |
| 平均生成耗时 | 记录 `running` → `success` 的时间差 | 超过 30 秒 |
| 积分扣减异常 | 积分流水与功能调用对账 | 出现负流水或重复扣减 |

### 6.8 测试策略

- **Prompt 输出格式测试**：准备固定 Context，调用 `ai_service.analyze`，校验返回 Markdown 是否包含必填章节、是否出现禁用表述。
- **服务层单元测试**：mock `ai_service.analyze`，验证成功/失败状态更新、幂等性、积分扣减逻辑。
- **接口集成测试**：调用用户端和管理端接口，验证权限、分页、重新生成等路径。
- **本地手动触发**：参见第 9.1 节。

## 7. 前端通用实现

前端项目位于 `trade_admin/`。

### 7.1 关键文件

| 文件 | 作用 |
|------|------|
| `trade_admin/src/api/<feature>.ts` | 对接后端接口 |
| `trade_admin/src/views/ai-content/<feature>/index.vue` | 后台管理页面（每日复盘例外，实际位于 `trade_admin/src/views/daily-review/index.vue`） |

### 7.2 页面功能

- 列表：日期、状态、用户筛选；关键词搜索；分页。
- 操作：生成（全部/今日/为选中用户）、重试失败、重新生成。
- 详情弹窗：显示状态、数据源表格、AI 生成的 Markdown 内容；支持编辑并保存。

## 8. DIY 修改指南

### 8.1 修改 AI 提示词

当前所有 System Prompt 集中在 `app/services/ai_service.py` 的 `SYSTEM_PROMPTS` 中。编辑对应条目即可生效。

**后续规划**：将 Prompt 从代码中抽离为独立文件（如 `app/prompts/daily_review.md`），便于热更新、A/B Test 和多模型切换。抽离后 `ai_service.py` 只保留默认版本号与文件加载逻辑。

### 8.2 修改数据源

编辑各功能 Service 中的 Context Builder 函数（如 `build_watchlist_context`、`build_portfolio_context`、`build_market_context`）。

可用数据源来自 `app/services/stock_service.py`、`app/services/limit_up_service.py`、`app/models/analysis.py` 等。

### 8.3 修改定时时间

1. 改默认配置：`app/services/scheduler_seed.py`。
2. 运行时调整：后台「调度管理」页面直接修改 cron。

### 8.4 修改会员权限与计费

编辑 `app/services/admin_seed.py`：

- `_SEED_MEMBERSHIP_TIERS`：控制哪些会员档位自动包含该功能。
- `_SEED_FEATURE_PERMISSIONS`：控制积分/免费策略。

### 8.5 前端页面调整

编辑对应 `trade_admin/src/views/ai-content/<feature>/index.vue`：

- 表格列
- 搜索条件
- 详情弹窗中的数据表格
- MdEditor/MdPreview 配置

## 9. 调试技巧

### 9.1 本地手动触发

```bash
cd /Users/huangxin/Desktop/trade/trade_backend
source .venv/bin/activate

# 示例：手动触发某功能后台生成接口
curl -X POST http://127.0.0.1:8000/api/v1/admin/<feature>/generate \
  -H "Authorization: Bearer <admin_token>"
```

### 9.2 查看生成日志

启动服务后观察日志输出，关键词为对应服务的日志前缀（如 `[DailyReview]`、`[AiPositionAdvice]`、`[AiMorningReport]`、`[Scheduler]`）。

### 9.3 直接调用服务函数

```python
from app.db.base import SessionLocal
from datetime import date

# 示例：替换为对应功能的 service 函数
db = SessionLocal()
try:
    result = generate_xxx_sync(db, report_date=date.today())
    print(result.status)
    print(result.content)
finally:
    db.close()
```

### 9.4 查看上下文

```python
from app.db.base import SessionLocal
from datetime import date
import asyncio

# 示例：替换为对应功能的 build_context 函数
db = SessionLocal()
try:
    context = asyncio.run(build_xxx_context(db, ...))
    print(context)
finally:
    db.close()
```

## 10. 通用注意事项

- AI 调用是异步的，APScheduler 任务运行在线程中，通过 `asyncio.run()` 包装执行。
- 每个用户/记录生成失败会单独捕获，不影响其他用户。
- 行情数据来自本地 `stock_daily` / `stock_daily_basic` 等表，需确保盘后数据同步已完成。
- 各功能特有注意事项请参见对应功能文档。
