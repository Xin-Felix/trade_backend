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

获取示例自选股列表。

**响应示例：**

```json
[
  {
    "code": "000001.SZ",
    "name": "平安银行",
    "price": 12.35,
    "change_percent": 1.25,
    "updated_at": "2026-07-08T10:30:00"
  },
  {
    "code": "600519.SH",
    "name": "贵州茅台",
    "price": 1680.00,
    "change_percent": -0.50,
    "updated_at": "2026-07-08T10:30:00"
  }
]
```

**说明：** 当前后端返回固定的示例股票列表。后续会改为用户可自定义的自选股持久化。

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
