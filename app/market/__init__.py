# -*- coding: utf-8 -*-
"""市场拥挤度 / 每日复盘模块

从 market_congestion 项目迁移而来。
核心计算逻辑在 core/ 子包中，通过 database.py 适配层读取 trade_backend 已有的数据表。

架构：
    app/market/
    ├── __init__.py          本文件
    ├── database.py          数据适配层（读 trade 的 stock_daily 等表，适配成 core 需要的格式）
    ├── service.py           业务服务层（缓存 + 调用 core 计算）
    ├── router.py            FastAPI 路由（29 个接口）
    └── core/                核心计算逻辑（从 market_congestion/core/ 搬运）
        ├── config.py
        ├── datasource.py
        ├── metrics.py
        ├── market.py
        ├── breadth.py
        ├── congestion.py
        ├── industry.py
        ├── trend.py
        ├── review.py
        ├── screener.py
        ├── option.py
        ├── history.py
        └── utils.py
"""
