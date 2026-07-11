# API 接口文档

所有业务接口前缀为 `/api/v1`。

## 基础接口

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| GET | `/` | 服务状态 | 否 |
| GET | `/health` | 健康检查 | 否 |

### GET /

返回服务运行状态。

**响应示例：**

```json
{
  "message": "Ying+ API is running"
}
```

### GET /health

健康检查。

**响应示例：**

```json
{
  "status": "ok"
}
```

## 认证接口

### POST /auth/email/code

发送邮箱验证码。

**请求体：**

```json
{
  "email": "user@example.com",
  "purpose": "login"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `email` | string | 是 | 邮箱地址 |
| `purpose` | string | 否 | 用途：`login` / `register` / `reset_password`，默认 `login` |

**响应：**

- 成功：`204 No Content`
- 失败：`429 Too Many Requests`（同一邮箱同一用途 5 分钟内最多 3 条未使用验证码）

### POST /auth/email/verify

校验邮箱验证码，新用户自动注册并登录。

**请求体：**

```json
{
  "email": "user@example.com",
  "code": "123456",
  "purpose": "login"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `email` | string | 是 | 邮箱地址 |
| `code` | string | 是 | 6 位纯数字验证码 |
| `purpose` | string | 否 | 默认 `login` |

**响应示例：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "name": "user",
    "avatar": null
  }
}
```

### POST /auth/login/email

邮箱密码登录，主要用于测试账号快速登录。

**请求体：**

```json
{
  "email": "1538933906@qq.com",
  "password": "123456"
}
```

**响应示例：** 同 `/auth/email/verify`

**测试账号：**

- 邮箱：`1538933906@qq.com`
- 密码：`123456`

开发环境启动时会自动创建该账号；若已存在则重置密码为 `123456`，确保 iOS 端测试登录始终可用。

### POST /auth/login/apple

Apple 登录（当前为占位实现）。

**请求参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `identity_token` | string | 是 | Apple 返回的 identity token |
| `user_id` | string | 是 | Apple user identifier |

**响应示例：** 同 `/auth/email/verify`

**注意：** 后端目前未验证 Apple identity token 真实性，生产环境上线前需补充验证逻辑。

## 天气接口

### GET /weather/beijing

获取北京当前天气（后端代理 Open-Meteo）。

**认证：** 不需要登录。

**响应示例：**

```json
{
  "city": "北京",
  "temperature": 25.5,
  "description": "晴天",
  "updated_at": "2026-07-08T10:30:00"
}
```

## 股票接口

股票接口均需登录，请求头中必须携带：

```
Authorization: Bearer {access_token}
```

### GET /stocks/quote/{code}

获取单只股票最新行情。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码，支持 `000001`、`000001.SZ`、`600519.SH`、`00700.HK` 等格式 |

**响应示例：**

```json
{
  "code": "000001",
  "name": "平安银行",
  "price": 12.35,
  "change_percent": 1.25,
  "pre_close": 12.20,
  "updated_at": "2026-07-08T10:30:00"
}
```

### GET /stocks/klines/{code}

获取股票 K 线数据。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `period` | string | 否 | 周期：`D`（日）、`W`（周）、`M`（月）、`Y`（年），默认 `D` |
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "ts_code": "000001.SZ",
    "trade_date": "20240708",
    "period": "D",
    "open": 12.10,
    "high": 12.50,
    "low": 12.05,
    "close": 12.35,
    "volume": 123456.78,
    "amount": 1523456.78
  }
]
```

### GET /stocks/intraday/{code}

获取股票实时分时 K 线数据（分钟级）。

**数据源：**

- 1 分钟线优先从数据库 `stock_intraday` 表读取（已收盘数据完整 241 条）
- 盘中或数据库缺失时，降级到 akshare 实时拉取
- 结果写入 Redis 缓存：盘中 30 秒，已收盘/历史数据 7 天

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码，支持 `600519`、`600519.SH`、`sh600519` 等格式 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `period` | string | 否 | 分钟周期：`1`、`5`、`15`、`30`、`60`，默认 `1` |
| `limit` | int | 否 | 返回条数，默认 240，最大 1000 |

**响应示例：**

```json
[
  {
    "ts_code": "600519.SH",
    "datetime": "2026-07-08 15:00:00",
    "period": "1",
    "open": 1199.30,
    "high": 1199.30,
    "low": 1199.30,
    "close": 1199.30,
    "volume": 44500.00,
    "amount": 53368852.70
  }
]
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `ts_code` | 标准化后的股票代码，如 `600519.SH` |
| `datetime` | 分钟线时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `period` | 分钟周期 |
| `open` / `high` / `low` / `close` | 开盘价、最高价、最低价、收盘价 |
| `volume` | 成交量（股） |
| `amount` | 成交金额 |

**说明：**

- 首次请求会实时调用 akshare，后续 30 秒内重复请求直接走 Redis 缓存。
- 如果未配置 `REDIS_URL`，会自动降级为本地内存缓存（仍带 30 秒 TTL）。
- 该接口数据不落库，适合前端分时图实时刷新。

### GET /stocks/daily-basic/{code}

获取股票日线因子数据（PE、PB、换手率等）。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "ts_code": "000001.SZ",
    "trade_date": "20240708",
    "close": 12.35,
    "turnover_rate": 1.25,
    "turnover_rate_f": 1.10,
    "volume_ratio": 0.95,
    "pe": 6.78,
    "pe_ttm": 6.50,
    "pb": 0.85,
    "ps": 1.20,
    "ps_ttm": 1.15,
    "dv_ratio": 2.50,
    "dv_ttm": 2.60,
    "total_share": 1940602.00,
    "float_share": 1940602.00,
    "free_share": 1940602.00,
    "total_mv": 23966535.00,
    "circ_mv": 23966535.00
  }
]
```

### GET /stocks/watchlist

获取当前登录用户的自选股列表，按加入时间排序。

**响应示例：**

```json
{
  "items": [
    {
      "code": "000001",
      "name": "平安银行",
      "ts_code": "000001.SZ",
      "created_at": "2026-07-08T10:30:00"
    },
    {
      "code": "600519",
      "name": "贵州茅台",
      "ts_code": "600519.SH",
      "created_at": "2026-07-08T10:35:00"
    }
  ],
  "total": 2
}
```

### POST /stocks/watchlist

添加自选股。

**请求体：**

```json
{
  "code": "000001",
  "name": "平安银行"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code` | string | 是 | 股票代码 |
| `name` | string | 是 | 股票名称 |

**响应示例：**

```json
{
  "code": "000001",
  "name": "平安银行",
  "ts_code": "000001.SZ",
  "created_at": "2026-07-08T10:30:00"
}
```

### DELETE /stocks/watchlist/{code}

删除自选股。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码 |

**响应示例：**

```json
{
  "success": true
}
```

### GET /stocks/search

搜索股票，支持代码、名称或拼音缩写。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `q` | string | 是 | 搜索关键词 |
| `limit` | int | 否 | 返回条数，默认 10，最大 50 |

**响应示例：**

```json
[
  { "code": "000001", "name": "平安银行" },
  { "code": "600519", "name": "贵州茅台" }
]
```

### GET /stocks/basics

获取全部股票基础信息，供 iOS 端本地缓存和搜索。

**响应示例：**

```json
[
  {
    "code": "000001",
    "name": "平安银行",
    "cnspell": "PAYH"
  },
  {
    "code": "600519",
    "name": "贵州茅台",
    "cnspell": "GZMT"
  }
]
```

### GET /stocks/indices

获取主要大盘指数最新数据（上证、深证成指、创业板指）。

**响应示例：**

```json
[
  { "name": "上证指数", "value": 3050.23, "change": 0.68, "ts_code": "000001.SH" },
  { "name": "深证成指", "value": 9876.54, "change": 1.23, "ts_code": "399001.SZ" },
  { "name": "创业板指", "value": 1890.12, "change": -0.45, "ts_code": "399006.SZ" }
]
```

### GET /stocks/sector-moneyflow

获取板块资金流排行（行业/概念）。

**认证：** 需要登录。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `sector_type` | string | 否 | 板块类型：`industry`（行业，默认）/ `concept`（概念） |
| `trade_date` | string | 否 | 交易日期 `YYYYMMDD`，默认取数据库最新日期 |
| `sort_by` | string | 否 | 排序字段：`net_amount`（净流入，默认降序）、`pct_change`（涨跌幅降序）、`net_amount_asc`（净流入升序） |
| `limit` | int | 否 | 返回条数，默认 20，最大 100 |

**响应示例：**

```json
{
  "sectors": [
    {
      "ts_code": "881121.TI",
      "trade_date": "20260708",
      "name": "半导体",
      "lead_stock": "芯朋微",
      "close_price": 98.09,
      "pct_change": -0.66,
      "company_num": 180,
      "pct_change_stock": 16.80,
      "net_buy_amount": 2108.00,
      "net_sell_amount": 2041.00,
      "net_amount": 66.00
    }
  ],
  "trade_date": "20260708",
  "sector_type": "industry"
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `ts_code` | 板块代码，如 `881121.TI` |
| `trade_date` | 交易日期 |
| `name` | 板块名称 |
| `lead_stock` | 龙头股 |
| `close_price` | 领涨股/板块指数收盘价 |
| `pct_change` | 板块涨跌幅% |
| `company_num` | 成分股数量 |
| `pct_change_stock` | 领涨股涨跌幅% |
| `net_buy_amount` | 净流入-买入金额（亿元） |
| `net_sell_amount` | 净流入-卖出金额（亿元） |
| `net_amount` | 净流入金额（亿元） |

**iOS 调用示例：**

```swift
let rank = try await StockService.fetchSectorMoneyflow(sectorType: .industry, limit: 20)
```

### GET /stocks/sector-moneyflow/trend

获取板块资金流时间段趋势（动态折线图）。

**认证：** 需要登录。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `sector_type` | string | 否 | 板块类型：`industry`（行业，默认）/ `concept`（概念） |
| `start_date` | string | 是 | 开始日期 `YYYYMMDD` |
| `end_date` | string | 是 | 结束日期 `YYYYMMDD` |
| `top_n` | int | 否 | 返回累计净流入前 N 的板块，默认 30 |

**响应示例：**

```json
{
  "sector_type": "industry",
  "start_date": "20260601",
  "end_date": "20260708",
  "dates": ["20260601", "20260602", "..."],
  "series": [
    {
      "ts_code": "881121.TI",
      "name": "半导体",
      "values": [
        { "trade_date": "20260601", "net_amount": 120.5, "pct_change": 1.23 },
        { "trade_date": "20260602", "net_amount": -45.0, "pct_change": -0.50 }
      ]
    }
  ]
}
```

### GET /stocks/moneyflow/{code}

获取个股资金流向（小单/中单/大单/特大单）。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 股票代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "ts_code": "000001.SZ",
    "trade_date": "20260708",
    "buy_sm_amount": 1234.56,
    "sell_sm_amount": 1000.00,
    "buy_md_amount": 2345.67,
    "sell_md_amount": 2100.00,
    "buy_lg_amount": 3456.78,
    "sell_lg_amount": 3200.00,
    "buy_elg_amount": 4567.89,
    "sell_elg_amount": 4300.00,
    "net_mf_amount": 1500.00
  }
]
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `buy_sm_amount` / `sell_sm_amount` | 小单买入/卖出金额 |
| `buy_md_amount` / `sell_md_amount` | 中单买入/卖出金额 |
| `buy_lg_amount` / `sell_lg_amount` | 大单买入/卖出金额 |
| `buy_elg_amount` / `sell_elg_amount` | 特大单买入/卖出金额 |
| `net_mf_amount` | 净流入金额 |

### GET /stocks/moneyflow-hsgt

获取沪深港通资金流向（北向/南向资金）。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `start_date` | string | 否 | 开始日期 `YYYYMMDD` |
| `end_date` | string | 否 | 结束日期 `YYYYMMDD` |
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "trade_date": "20260708",
    "ggt_ss": 1234.56,
    "ggt_sz": 2345.67,
    "hgt": 3456.78,
    "sgt": 4567.89,
    "north_money": 7890.12,
    "south_money": 6789.01
  }
]
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `ggt_ss` | 港股通（沪） |
| `ggt_sz` | 港股通（深） |
| `hgt` | 沪股通 |
| `sgt` | 深股通 |
| `north_money` | 北向资金 |
| `south_money` | 南向资金 |

### GET /stocks/index-daily/{code}

获取指数日线行情（如 `000001.SH`）。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 指数代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "ts_code": "000001.SH",
    "trade_date": "20260708",
    "open": 3050.00,
    "high": 3060.00,
    "low": 3040.00,
    "close": 3055.00,
    "pre_close": 3048.00,
    "change": 7.00,
    "pct_chg": 0.23,
    "vol": 1234567.00,
    "amount": 2345678901.00
  }
]
```

### GET /stocks/stock-limit

获取涨跌停股票列表。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trade_date` | string | 否 | 交易日期 `YYYYMMDD`，默认最新 |
| `limit` | int | 否 | 返回条数，默认 100，最大 500 |

**响应示例：**

```json
[
  {
    "trade_date": "20260708",
    "ts_code": "000001.SZ",
    "up_limit": 13.58,
    "down_limit": 11.12
  }
]
```

### GET /stocks/top-list

获取龙虎榜每日明细（分页）。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trade_date` | string | 否 | 交易日期 `YYYYMMDD`，默认最新 |
| `limit` | int | 否 | 每页条数，默认 20，最大 500 |
| `offset` | int | 否 | 偏移量，默认 0 |

**响应示例：**

```json
{
  "items": [
    {
      "trade_date": "20260708",
      "ts_code": "000001.SZ",
      "name": "平安银行",
      "close": 12.35,
      "pct_change": 10.02,
      "turnover_rate": 5.60,
      "amount": 123456789.00,
      "net_amount": 12345678.00,
      "net_rate": 10.00,
      "reason": "日涨幅偏离值达7%的证券"
    }
  ],
  "total": 98,
  "limit": 20,
  "offset": 0
}
```

### GET /stocks/top-inst

获取龙虎榜机构明细。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trade_date` | string | 否 | 交易日期 `YYYYMMDD` |
| `code` | string | 否 | 股票代码 |
| `limit` | int | 否 | 返回条数，默认 100，最大 500 |

**响应示例：**

```json
[
  {
    "trade_date": "20260708",
    "ts_code": "000001.SZ",
    "exalter": "机构专用",
    "buy": 12345678.00,
    "buy_rate": 10.00,
    "sell": 2345678.00,
    "sell_rate": 2.00,
    "net_buy": 10000000.00,
    "side": "buy",
    "reason": "日涨幅偏离值达7%的证券"
  }
]
```

### GET /stocks/limit-up-ladder

获取涨停板天梯聚合数据（概念标签 + 连板天梯 + 炸板）。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trade_date` | string | 否 | 交易日期 `YYYYMMDD`，默认最新 |
| `top_n_concepts` | int | 否 | 顶部概念标签数量，默认 30 |

**响应示例：**

```json
{
  "trade_date": "20260709",
  "concept_tags": [
    {
      "name": "商业航天",
      "count": 29,
      "cons_count": 4,
      "pct_change": 2.07,
      "rank": 1
    }
  ],
  "ladder": [
    {
      "step": 8,
      "label": "8板",
      "stocks": [
        {
          "ts_code": "603137.SH",
          "name": "恒尚节能",
          "close": 25.20,
          "pct_chg": 10.00,
          "first_time": "09:30",
          "last_time": "09:30",
          "open_times": 0,
          "concept_tags": []
        }
      ]
    },
    {
      "step": 1,
      "label": "首板",
      "stocks": [...]
    }
  ],
  "opened_limit": [
    {
      "ts_code": "000001.SZ",
      "name": "平安银行",
      "close": 12.35,
      "pct_chg": 8.50,
      "first_time": "10:15",
      "last_time": null,
      "open_times": 3,
      "concept_tags": ["银行"]
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `concept_tags` | 当日涨停最多的概念板块，按涨停家数排序 |
| `concept_tags.count` | 该概念涨停家数 |
| `concept_tags.cons_count` | 该概念连板家数 |
| `ladder` | 连板天梯，按 step 降序排列 |
| `ladder.step` | 连板天数，1 表示首板 |
| `ladder.label` | 展示文案：`首板` / `2板` / `8板` 等 |
| `ladder.stocks` | 该连板层级的个股列表 |
| `first_time` | 首次涨停时间，格式 `HH:MM` |
| `open_times` | 涨停打开次数 |
| `concept_tags`（个股内） | 该股所属的热门概念，最多返回 2 个 |
| `opened_limit` | 炸板股票列表（盘中触及涨停但未封住） |

## 涨停板天梯后台管理

后台管理页面路径：`/data/limit-up-ladder/index`

### GET /admin/limit-up-ladder/overview

获取涨停板天梯功能的数据依赖概览和调度任务状态。

**响应示例：**

```json
{
  "success": true,
  "data": {
    "feature_name": "涨停板天梯",
    "api_endpoint": "/api/v1/stocks/limit-up-ladder",
    "latest_trade_date": "20260710",
    "scheduler_job": {
      "job_id": "sync_limit_data",
      "description": "[盘后] 打板数据（涨跌停+连板天梯+THS榜单）",
      "trigger_type": "interval",
      "interval_hours": 0,
      "interval_minutes": 1,
      "enabled": true,
      "running": true,
      "next_run_time": "2026-07-11T15:45:00+08:00"
    },
    "dependencies": [
      {
        "key": "limit_cpt_list",
        "name": "涨停最强板块统计",
        "table": "limit_cpt_list",
        "description": "同花顺概念板块涨停家数统计，用于顶部概念标签",
        "latest_trade_date": "2026-07-10",
        "total_records": 80
      },
      {
        "key": "limit_step",
        "name": "涨停连板天梯",
        "table": "limit_step",
        "description": "个股连板天数，用于 8板/3板/2板/首板 分组",
        "latest_trade_date": "2026-07-10",
        "total_records": 32
      },
      {
        "key": "limit_list_d",
        "name": "涨跌停明细",
        "table": "limit_list_d",
        "description": "涨停个股首次涨停时间、打开次数、封单强度等明细",
        "latest_trade_date": "2026-07-10",
        "total_records": 479
      },
      {
        "key": "stock_concept",
        "name": "股票概念映射",
        "table": "stock_concept",
        "description": "个股所属概念，用于个股卡片下的概念标签",
        "latest_trade_date": "长期有效",
        "total_records": 71868
      }
    ]
  }
}
```

### POST /admin/limit-up-ladder/sync

手动触发涨停板天梯相关数据源同步。

**请求体：**

```json
{
  "trade_date": "20260710",
  "days": 1
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trade_date` | string | 否 | 指定日期 `YYYYMMDD`，不传则同步最近 `days` 天 |
| `days` | int | 否 | 同步天数，默认 1 |

**响应示例：**

```json
{
  "success": true,
  "data": {
    "synced_tables": ["limit_list_d", "limit_step", "limit_cpt_list"],
    "start_date": "20260710",
    "end_date": "20260710"
  }
}
```

### GET /admin/limit-up-ladder/job

获取涨停板天梯关联的调度任务（`sync_limit_data`）配置。

### PUT /admin/limit-up-ladder/job

更新涨停板天梯关联的调度任务配置。

**请求体（每分钟更新）：**

```json
{
  "trigger_type": "interval",
  "interval_hours": 0,
  "interval_minutes": 1,
  "days": 1,
  "enabled": true
}
```

**请求体（盘后低频）：**

```json
{
  "trigger_type": "cron",
  "cron_hour": 15,
  "cron_minute": 30,
  "cron_day_of_week": "mon-fri",
  "days": 1,
  "enabled": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `trigger_type` | string | 是 | `cron` 或 `interval` |
| `cron_hour` | int | 否 | cron 小时 |
| `cron_minute` | int | 否 | cron 分钟 |
| `cron_day_of_week` | string | 否 | cron 星期 |
| `interval_hours` | int | 否 | 间隔小时 |
| `interval_minutes` | int | 否 | 间隔分钟 |
| `days` | int | 否 | 每次同步天数 |
| `enabled` | bool | 否 | 是否启用 |

### GET /stocks/ths-index

获取同花顺指数列表（行业/概念）。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 1000，最大 5000 |

**响应示例：**

```json
[
  {
    "ts_code": "885560.TI",
    "name": "半导体",
    "count": 180,
    "type": "概念"
  }
]
```

### GET /stocks/ths-daily/{code}

获取同花顺指数日线行情。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 同花顺指数代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 30，最大 500 |

**响应示例：**

```json
[
  {
    "ts_code": "885560.TI",
    "trade_date": "20260708",
    "open": 1200.00,
    "high": 1210.00,
    "low": 1195.00,
    "close": 1205.00,
    "pre_close": 1198.00,
    "pct_change": 0.58,
    "vol": 1234567.00,
    "turnover_rate": 1.20
  }
]
```

### GET /stocks/ths-member/{code}

获取同花顺指数成分股。

**路径参数：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 同花顺指数代码 |

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | int | 否 | 返回条数，默认 1000，最大 5000 |

**响应示例：**

```json
[
  {
    "ts_code": "885560.TI",
    "con_code": "688001.SH",
    "con_name": "华兴源创"
  }
]
```

## AI 接口

AI 接口均需登录。

### POST /ai/chat

通用 AI 对话，支持流式返回。

**请求体：**

```json
{
  "prompt": "今天大盘怎么看？",
  "role": "market_analyst",
  "context": "",
  "stream": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | 是 | 用户问题 |
| `role` | string | 否 | 角色：`market_analyst` / `morning_brief` / `stock_analyst` / `news_interpreter` / `global_impact`，默认 `market_analyst` |
| `context` | string | 否 | 附加上下文 |
| `stream` | bool | 否 | 是否流式返回，默认 `false` |

**响应示例（非流式）：**

```json
{
  "success": true,
  "data": {
    "content": "今天市场..."
  }
}
```

### POST /ai/analyze/stock

个股 AI 分析，后端自动拉取行情和基本面作为上下文。

**请求体：**

```json
{
  "code": "000001",
  "question": "分析一下平安银行"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code` | string | 是 | 股票代码 |
| `question` | string | 否 | 问题，不传则使用默认问题 |

### POST /ai/analyze/global-impact

分析当前国际市场对 A 股的影响。

**响应示例：**

```json
{
  "success": true,
  "data": {
    "content": "当前国际市场..."
  }
}
```

### GET /ai/roles

获取可用的 AI 角色列表。

## 股票代码格式

接口支持以下格式，后端会自动标准化为 Tushare 格式：

- `000001` → `000001.SZ`
- `600519` → `600519.SH`
- `00700` → `00700.HK`
- `000001.SZ`（直接传入）

## 错误码

| 状态码 | 含义 | 常见场景 |
|---|---|---|
| 200 | 成功 | 正常返回 |
| 204 | 成功，无返回体 | 发送验证码 |
| 400 | 请求参数错误 | 验证码错误/过期、格式错误 |
| 401 | 未认证 | 缺少 token、token 失效、用户不存在 |
| 429 | 请求过于频繁 | 验证码发送过多 |
| 500 | 服务器内部错误 | 数据库异常、外部 API 失败 |
