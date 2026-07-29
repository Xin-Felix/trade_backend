# AI 每日复盘功能文档

本文档描述 AI 每日复盘功能的特有实现。通用架构、Context Builder、Prompt 设计、DIY 修改等请参见 `docs/ai-feature-base.md`。

## 1. 功能概述

- **每日 19:00** 自动为所有生效会员生成一份基于其持仓的 AI 复盘报告。
- 积分用户目前仅可在后台/管理端触发为其生成；App 端手动生成是后续规划功能。
- 会员可在 App/用户端查看自己的复盘列表和今日复盘。
- 后台管理可查看所有会员/积分用户的复盘记录、持仓数据源、重新生成、编辑内容。

## 2. 权限与计费模型

| 人群 | 计费 | 生成方式 | 说明 |
|------|------|----------|------|
| 会员 | 会员权益 | 每日 19:00 自动生成 | VIP/SVIP 档位 features 包含 `ai_daily_review` |
| 非会员积分用户 | 100 积分/天 | 管理端手动触发 | `ai_daily_review` 设置 `required_points: 100`、`consume_mode: per_day` |

## 3. 数据组装架构（两层分离）

### 3.1 通用市场数据（`build_market_context()`，所有用户共享，只构建一次）

| 模块 | 数据内容 | 数据来源 |
|------|----------|----------|
| 复盘日期 | 当前日期 + 最新交易日标注 | `get_latest_trade_date()` |
| 大盘指数近 5 天 | 上证/深证/创业板 收盘、涨跌幅、成交额 | 本地 `index_daily` 表 |
| 国际市场 | 全球指数（恒生/日经/韩国等） | 本地 `index_global` 表 |
| 商品/汇率 | 沪金/沪银/原油/沪铜 + 美元人民币/欧元/日元 | Tushare `fut_daily` + `fx_daily` |
| 北向资金 | 近 5 天北向/沪股通/深股通净流入 | 本地 `moneyflow_hsgt` 表 |
| 涨跌停天梯 | 连板梯队 + 热门涨停概念 + 炸板 | 本地 `limit_list_d` / `limit_step` 表 |
| 热门板块 | 行业/概念 Top5 净流入 + Top5 净流出 | 本地 `sector_moneyflow_*` 表 |

### 3.2 用户个性化数据（每个用户单独查询）

**持仓股（深度分析）：**

| 数据项 | 说明 |
|--------|------|
| 当日行情 | 现价、涨跌幅 |
| 持仓信息 | 成本价、收益率百分比、融资标记 |
| 基本面 | PE/PE_TTM/PB/换手率/量比/总市值/流通市值 |
| 近 5 天日K | 开高低收 + 成交量/成交额 |
| 近 4 周周K | 开高低收 |
| 当日 15 分钟K线 | 走势结构（16 根 K 线） |
| 所属概念 | 最多 10 个概念板块名称 |
| 近 5 天资金流向 | 小单/中单/大单/特大单净流入 |

**自选股（非持仓，简要）：**
- 名称、代码、现价、涨跌幅、PE、PB、换手率

### 3.3 数据就绪校验

生成前 `_check_data_readiness()` 自动校验：
- A 股日K（`stock_daily`）最新日期是否为当天
- 指数日线（`index_daily`）
- 北向资金（`moneyflow_hsgt`）
- 全球指数（`index_global`，允许滞后 2 天）

交易日数据未就绪 → 抛 `RuntimeError`，复盘标记为 `failed`，不会生成空洞内容。

## 4. AI Prompt 核心要求

角色：盈多多AI，专业 A 股收盘复盘助手，既有分析经验也理解散户心理。

报告结构：
1. 今日市场全貌（大盘 + 欧美盘影响）
2. 持仓账户概览（总收益率、涨跌分布）
3. 重点持仓深度点评（技术面 + 资金面 + 概念/板块 + 自然融入情绪关怀）
4. 自选股简评（非持仓，简要提及）
5. 涨停天梯与市场热点
6. 明日展望与策略建议
7. 免责声明

约束：
- 总字数 ≤ 1500 字
- 只给收益率百分比，不暴露用户具体金额
- 情绪关怀自然融入分析末尾，不单独列标题
- 语调像经验丰富的老朋友帮你复盘
- 使用中国时间（UTC+8）

## 5. 定时任务

| 配置 | 值 |
|------|-----|
| job_id | `generate_daily_reviews` |
| 触发时间 | 周一至周五 19:00 |
| 执行逻辑 | `generate_deep_reviews_for_all_members(skip_non_trading_day=True)` |
| 并发控制 | 最多 3 路并发 AI 调用 |

时间线保证：
```
16:05~17:25  盘后数据同步完成
19:00        AI 复盘生成（数据就绪校验通过才执行）
```

## 6. 后台管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/daily-reviews` | 复盘列表（支持日期/状态/用户筛选） |
| GET | `/api/v1/admin/daily-reviews/{id}` | 复盘详情 |
| PUT | `/api/v1/admin/daily-reviews/{id}` | 编辑复盘内容 |
| GET | `/api/v1/admin/daily-reviews/{id}/watchlist` | 查看持仓+自选数据源 |
| POST | `/api/v1/admin/daily-reviews/generate` | 手动生成（后台线程执行） |
| POST | `/api/v1/admin/daily-reviews/{id}/regenerate` | 重新生成（后台线程执行） |
| POST | `/api/v1/admin/daily-reviews/retry-failed` | 重试失败记录（后台线程执行） |

所有生成类接口立即返回，不阻塞服务。

### 后台详情数据源返回结构

```json
{
  "portfolio": [
    {"code": "000001", "name": "平安银行", "price": 12.5, "change_percent": 1.2,
     "cost_price": 11.0, "quantity": 1000, "profit": 1500, "profit_pct": 13.6,
     "is_margin": false, "pe": 5.2, "pb": 0.6}
  ],
  "watchlist": [
    {"code": "600519", "name": "贵州茅台", "price": 1800, "change_percent": -0.5,
     "pe": 28, "pb": 8.5}
  ],
  "portfolio_count": 3,
  "watchlist_count": 2
}
```

## 7. 用户端接口

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/v1/daily-reviews/today` | 会员/积分用户 |
| GET | `/api/v1/daily-reviews` | 会员/积分用户 |
| GET | `/api/v1/daily-reviews/{id}` | 会员/积分用户 |

## 8. 关键实现保障

| 机制 | 说明 |
|------|------|
| 幂等 | `(user_id, report_date, level)` 唯一约束 |
| 失败隔离 | 每个用户独立 try/except |
| 并发控制 | Semaphore 限制 3 路并发 |
| 市场数据复用 | `build_market_context()` 一次构建，N 用户共享 |
| 数据就绪 | 交易日数据未同步完则拒绝生成 |
| 日期准确 | 使用中国时区 UTC+8 |
| 输出完整 | max_tokens=4096, timeout=120s |
| 不阻塞服务 | 生成接口全部后台线程执行 |

## 9. 文件清单

### 后端
- `app/models/daily_review.py`
- `app/models/stock.py`（含 `IndexGlobal`）
- `app/services/daily_review_service.py`
- `app/services/ai_service.py`
- `app/services/global_market_service.py`
- `app/services/scheduler_service.py`
- `app/services/scheduler_seed.py`
- `app/api/v1/endpoints/daily_review.py`
- `app/api/v1/endpoints/daily_review_admin.py`
- `app/schemas/daily_review.py`
- `alembic/versions/a1b2c3d4e5f6_add_index_global.py`

### 前端
- `trade_admin/src/api/daily-review.ts`
- `trade_admin/src/views/daily-review/index.vue`
