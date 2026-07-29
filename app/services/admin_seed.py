"""后台管理初始数据种子。

开发环境启动时自动插入，已存在则跳过。
"""

from app.models.membership import MembershipTier
from app.models.points import FeaturePermission
from sqlalchemy.orm import Session

from app.models.admin import AdminMenu, AdminRole, RoleMenu
from app.models.h5_page import H5Page
from app.models.sector_default_config import SectorDefaultConfig
from sqlalchemy import text


# 牛市热门概念预设（同花顺概念代码）
_HOT_CONCEPT_IDS = [
    "885728.TI",  # 人工智能
    "885756.TI",  # 芯片概念
    "886069.TI",  # 人形机器人
    "885517.TI",  # 机器人概念
    "886100.TI",  # DeepSeek概念
    "885431.TI",  # 新能源汽车
    "885921.TI",  # 储能
    "886067.TI",  # 低空经济
    "885806.TI",  # 华为概念
    "885800.TI",  # 消费电子概念
    "885700.TI",  # 军工
    "885531.TI",  # 光伏概念
    "885710.TI",  # 锂电池概念
    "885887.TI",  # 数据中心
    "886108.TI",  # AI应用
    "885957.TI",  # 东数西算(算力)
    "886099.TI",  # AI智能体
    "885736.TI",  # 无人驾驶
    "885946.TI",  # 传感器
    "886042.TI",  # 存储芯片
]

# 牛市热门行业预设
_HOT_INDUSTRY_NAMES = [
    "半导体", "元器件", "软件服务", "专用机械", "汽车配件",
    "通信设备", "IT设备", "互联网", "电气设备", "电器仪表",
    "机械基件", "化工原料", "化学制药", "生物制药", "中成药",
    "医疗保健", "航空", "证券", "银行", "小金属"
]


# 初始角色数据
_SEED_ROLES = [
    {"code": "admin", "name": "管理员", "description": "系统管理员，拥有所有权限"},
    {"code": "user", "name": "普通用户", "description": "普通用户，仅可访问授权菜单"},
]

# 初始菜单数据定义
_SEED_MENUS = [
    {
        "id": 1,
        "parent_id": 0,
        "path": "/system",
        "name": None,
        "component": None,
        "redirect": "/system/user",
        "title": "系统管理",
        "icon": "ep:setting",
        "menu_type": 0,
        "rank": 10,
    },
    {
        "id": 2,
        "parent_id": 1,
        "path": "/system/user/index",
        "name": "SystemUser",
        "component": "system/user/index",
        "redirect": None,
        "title": "用户管理",
        "icon": "ep:user",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 3,
        "parent_id": 1,
        "path": "/system/role/index",
        "name": "SystemRole",
        "component": "system/role/index",
        "redirect": None,
        "title": "角色管理",
        "icon": "ep:avatar",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 4,
        "parent_id": 1,
        "path": "/system/menu/index",
        "name": "SystemMenu",
        "component": "system/menu/index",
        "redirect": None,
        "title": "菜单管理",
        "icon": "ep:menu",
        "menu_type": 1,
        "rank": 3,
    },
    # ====== 数据管理 ======
    {
        "id": 10,
        "parent_id": 0,
        "path": "/data",
        "name": None,
        "component": None,
        "redirect": "/data/browser/index",
        "title": "数据管理",
        "icon": "ep:coin",
        "menu_type": 0,
        "rank": 5,
    },
    {
        "id": 11,
        "parent_id": 10,
        "path": "/data/center/index",
        "name": "DataCenter",
        "component": "data/center/index",
        "redirect": None,
        "title": "数据中心",
        "icon": "ep:timer",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 13,
        "parent_id": 10,
        "path": "/data/browser/index",
        "name": "DataBrowser",
        "component": "data/browser/index",
        "redirect": None,
        "title": "数据浏览",
        "icon": "ep:document",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 15,
        "parent_id": 10,
        "path": "/data/source/index",
        "name": "DataSource",
        "component": "data/source/index",
        "redirect": None,
        "title": "数据源管理",
        "icon": "ep:connection",
        "menu_type": 1,
        "rank": 3,
    },
    # ====== 聚合数据（数据清理/汇总） ======
    {
        "id": 18,
        "parent_id": 10,
        "path": "/data/aggregation",
        "name": None,
        "component": None,
        "redirect": "/data/aggregation/index",
        "title": "聚合数据",
        "icon": "ep:odometer",
        "menu_type": 0,
        "rank": 4,
    },
    {
        "id": 19,
        "parent_id": 18,
        "path": "/data/aggregation/index",
        "name": "DataAggregation",
        "component": "data/aggregation/index",
        "redirect": None,
        "title": "聚合概览",
        "icon": "ep:data-board",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 17,
        "parent_id": 18,
        "path": "/data/limit-up-ladder/index",
        "name": "LimitUpLadder",
        "component": "data/limit-up-ladder/index",
        "redirect": None,
        "title": "涨停天梯",
        "icon": "ep:trend-charts",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 24,
        "parent_id": 10,
        "path": "/data/sector-default/index",
        "name": "SectorDefault",
        "component": "data/sector-default/index",
        "redirect": None,
        "title": "分时资金流向默认配置",
        "icon": "ep:files",
        "menu_type": 1,
        "rank": 5,
    },
    # ====== 会员管理 ======
    {
        "id": 40,
        "parent_id": 0,
        "path": "/membership",
        "name": None,
        "component": None,
        "redirect": "/membership/tiers/index",
        "title": "会员管理",
        "icon": "ep:vIP",
        "menu_type": 0,
        "rank": 6,
    },
    {
        "id": 41,
        "parent_id": 40,
        "path": "/membership/tiers/index",
        "name": "MembershipTiers",
        "component": "membership/tiers/index",
        "redirect": None,
        "title": "会员套餐",
        "icon": "ep:ticket",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 42,
        "parent_id": 40,
        "path": "/membership/orders/index",
        "name": "MembershipOrders",
        "component": "membership/orders/index",
        "redirect": None,
        "title": "订阅订单",
        "icon": "ep:shopping-cart",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 43,
        "parent_id": 40,
        "path": "/membership/users/index",
        "name": "MembershipUsers",
        "component": "membership/users/index",
        "redirect": None,
        "title": "用户会员",
        "icon": "ep:user-filled",
        "menu_type": 1,
        "rank": 3,
    },
    # ====== 积分管理 ======
    {
        "id": 30,
        "parent_id": 0,
        "path": "/points",
        "name": None,
        "component": None,
        "redirect": "/points/rules/index",
        "title": "积分管理",
        "icon": "ep:medal",
        "menu_type": 0,
        "rank": 7,
    },
    {
        "id": 31,
        "parent_id": 30,
        "path": "/points/rules/index",
        "name": "PointRules",
        "component": "points/rules/index",
        "redirect": None,
        "title": "积分规则",
        "icon": "ep:present",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 32,
        "parent_id": 30,
        "path": "/points/records/index",
        "name": "PointRecords",
        "component": "points/records/index",
        "redirect": None,
        "title": "积分明细",
        "icon": "ep:list",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 33,
        "parent_id": 30,
        "path": "/points/features/index",
        "name": "PointFeatures",
        "component": "points/features/index",
        "redirect": None,
        "title": "功能权限",
        "icon": "ep:key",
        "menu_type": 1,
        "rank": 3,
    },
    # ====== 内容管理 ======
    {
        "id": 20,
        "parent_id": 0,
        "path": "/content",
        "name": None,
        "component": None,
        "redirect": "/content/h5/index",
        "title": "内容管理",
        "icon": "ep:document",
        "menu_type": 0,
        "rank": 8,
    },
    {
        "id": 21,
        "parent_id": 20,
        "path": "/content/h5/index",
        "name": "ContentH5",
        "component": "content/h5/index",
        "redirect": None,
        "title": "H5页面管理",
        "icon": "ep:iphone",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 22,
        "parent_id": 20,
        "path": "/content/daily-quote/index",
        "name": "ContentDailyQuote",
        "component": "content/daily-quote/index",
        "redirect": None,
        "title": "每日一言",
        "icon": "ep:chat-dot-round",
        "menu_type": 1,
        "rank": 2,
    },
    # ====== AI 内容管理 ======
    {
        "id": 52,
        "parent_id": 0,
        "path": "/ai-content",
        "name": None,
        "component": None,
        "redirect": "/ai-content/daily-review/index",
        "title": "AI 内容管理",
        "icon": "ep:data-analysis",
        "menu_type": 0,
        "rank": 9,
    },
    {
        "id": 51,
        "parent_id": 52,
        "path": "/ai-content/daily-review/index",
        "name": "DailyReview",
        "component": "daily-review/index",
        "redirect": None,
        "title": "每日自动复盘",
        "icon": "ep:memo",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 53,
        "parent_id": 52,
        "path": "/ai-content/position-advice/index",
        "name": "AiPositionAdvice",
        "component": "ai-content/position-advice/index",
        "redirect": None,
        "title": "AI 仓位建议",
        "icon": "ep:pie-chart",
        "menu_type": 1,
        "rank": 2,
    },
    {
        "id": 54,
        "parent_id": 52,
        "path": "/ai-content/morning-report/index",
        "name": "AiMorningReport",
        "component": "ai-content/morning-report/index",
        "redirect": None,
        "title": "AI 晨报",
        "icon": "ep:sunrise",
        "menu_type": 1,
        "rank": 3,
    },
    {
        "id": 55,
        "parent_id": 52,
        "path": "/ai-content/market-pulse/index",
        "name": "MarketPulse",
        "component": "ai-content/market-pulse/index",
        "redirect": None,
        "title": "AI 市场温度",
        "icon": "ep:odometer",
        "menu_type": 1,
        "rank": 4,
    },
]


def seed_admin_menus(db: Session) -> None:
    """插入初始数据：只补充缺失的菜单和角色，不覆盖已有记录。"""
    # 种子角色：按 code 补充缺失的角色
    for role_data in _SEED_ROLES:
        existing = db.query(AdminRole).filter(AdminRole.code == role_data["code"]).first()
        if not existing:
            db.add(AdminRole(**role_data))
    db.commit()

    # 清理已合并/废弃的菜单（如原来的 "AI 复盘管理" 父目录、旧的数据同步/执行日志）
    obsolete_menu_ids = {50, 12, 16}
    seed_menu_ids = {m["id"] for m in _SEED_MENUS}
    obsolete_menu_ids -= seed_menu_ids
    for obsolete_id in obsolete_menu_ids:
        obsolete = db.query(AdminMenu).filter(AdminMenu.id == obsolete_id).first()
        if obsolete:
            db.delete(obsolete)
    if obsolete_menu_ids:
        db.commit()

    # 种子菜单：只插入不存在的菜单，保留后台手动修改（图标、标题等）
    # 对已存在的菜单，同步可能影响菜单结构的字段（parent_id、path、rank 等）
    structural_fields = ("parent_id", "path", "name", "component", "redirect", "title", "menu_type", "rank")
    for menu_data in _SEED_MENUS:
        existing = db.query(AdminMenu).filter(AdminMenu.id == menu_data["id"]).first()
        if existing:
            for field in structural_fields:
                seed_value = menu_data.get(field)
                if seed_value is None:
                    continue
                current_value = getattr(existing, field)
                if current_value != seed_value:
                    setattr(existing, field, seed_value)
            continue
        menu = AdminMenu(
            id=menu_data["id"],
            parent_id=menu_data["parent_id"],
            path=menu_data["path"],
            name=menu_data.get("name"),
            component=menu_data.get("component"),
            redirect=menu_data.get("redirect"),
            title=menu_data["title"],
            icon=menu_data.get("icon"),
            menu_type=menu_data.get("menu_type", 1),
            rank=menu_data.get("rank", 0),
        )
        db.add(menu)
    db.commit()

    # 为 admin 角色自动关联所有菜单（只补充缺失的）
    admin_role_code = "admin"
    existing_menu_ids = {
        rm.menu_id
        for rm in db.query(RoleMenu).filter(RoleMenu.role == admin_role_code).all()
    }
    all_menu_ids = {m["id"] for m in _SEED_MENUS}
    missing_menu_ids = all_menu_ids - existing_menu_ids
    for menu_id in missing_menu_ids:
        db.add(RoleMenu(role=admin_role_code, menu_id=menu_id))
    if missing_menu_ids:
        db.commit()


def seed_h5_pages(db: Session) -> None:
    """预置一条帮助与反馈示例页面（已存在则跳过）。"""
    sample_slug = "help-feedback"
    existing = db.query(H5Page).filter(H5Page.slug == sample_slug).first()
    if existing:
        return

    content = """# 帮助与反馈

欢迎使用 Ying+！

## 常见问题

1. **如何查看自选股？**
   进入 App 首页，点击底部“自选”即可管理。

2. **数据多久更新一次？**
   日K线、资金等核心数据在每个交易日盘后自动同步。

3. **如何联系客服？**
   请发送邮件至 **support@yingplus.com**，我们会尽快回复。

## 意见反馈

如果你有任何建议或遇到问题，欢迎通过以下方式告诉我们：

- 邮箱：support@yingplus.com
- 微信：YingPlusOfficial

我们会认真阅读每一条反馈，持续优化产品体验。
"""

    page = H5Page(
        slug=sample_slug,
        title="帮助与反馈",
        content_type="markdown",
        content=content,
        is_published=1,
    )
    db.add(page)
    db.commit()


# 默认会员档位
_SEED_MEMBERSHIP_TIERS = [
    {
        "code": "vip",
        "name": "VIP 会员",
        "description": "月度 VIP，可访问 AI 对话、概念资金流、涨停天梯等高级功能",
        "price": 2990,
        "duration_days": 30,
        "monthly_points_grant": 500,
        "features": [
            "ai_chat",
            "ai_stock_analyze",
            "ai_daily_review_deep",
            "ai_position_advice",
            "analytics_concept_flow",
            "limit_up_ladder",
            "sector_moneyflow",
            "stock_moneyflow",
            "top_list",
            "ths_member",
        ],
        "enabled": 1,
    },
    {
        "code": "svip",
        "name": "SVIP 会员",
        "description": "月度 SVIP，畅享全部功能及 Tushare 代理",
        "price": 9990,
        "duration_days": 30,
        "monthly_points_grant": 2000,
        "features": ["*"],
        "enabled": 1,
    },
]

# 默认功能权限（只创建不存在的）
_SEED_FEATURE_PERMISSIONS = [
    {"code": "ai_chat", "name": "AI 对话", "required_points": 50, "free_daily_limit": 3, "consume_mode": "per_call"},
    {"code": "ai_stock_analyze", "name": "AI 个股分析", "required_points": 80, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "ai_global_impact", "name": "AI 国际市场影响", "required_points": 100, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "ai_daily_review_brief", "name": "AI 每日复盘（一句话）", "required_points": 0, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "ai_daily_review_standard", "name": "AI 每日复盘（标准）", "required_points": 100, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "ai_daily_review_deep", "name": "AI 每日复盘（深度）", "required_points": 0, "free_daily_limit": 0, "consume_mode": "per_call", "required_tier": "vip"},
    {"code": "ai_position_advice", "name": "AI 仓位建议", "required_points": 100, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "ai_morning_report", "name": "AI 晨报", "required_points": 0, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "analytics_concept_flow", "name": "板块/个股资金流", "required_points": 30, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "limit_up_ladder", "name": "涨停板天梯", "required_points": 50, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "sector_moneyflow", "name": "板块资金流排行", "required_points": 30, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "stock_moneyflow", "name": "个股资金流向", "required_points": 20, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "top_list", "name": "龙虎榜", "required_points": 30, "free_daily_limit": 0, "consume_mode": "per_day"},
    {"code": "ths_member", "name": "同花顺成分股", "required_points": 20, "free_daily_limit": 0, "consume_mode": "per_call"},
    {"code": "tushare_proxy", "name": "Tushare 代理", "required_points": 10, "free_daily_limit": 0, "consume_mode": "per_call"},
]


def seed_membership_data(db: Session) -> None:
    """初始化会员档位和功能权限（已存在则跳过）。"""
    # 会员档位
    for tier_data in _SEED_MEMBERSHIP_TIERS:
        existing = db.query(MembershipTier).filter(MembershipTier.code == tier_data["code"]).first()
        if existing:
            # 已存在时，把种子中新增的功能补充进去（不删除人工修改）
            existing_features = set(existing.features or [])
            seed_features = set(tier_data.get("features") or [])
            if "*" in seed_features:
                existing.features = ["*"]
            else:
                merged = list(existing_features | seed_features)
                if merged != existing.features:
                    existing.features = merged
            continue
        db.add(MembershipTier(**tier_data))
    db.commit()

    # 功能权限
    for fp_data in _SEED_FEATURE_PERMISSIONS:
        existing = db.query(FeaturePermission).filter(FeaturePermission.code == fp_data["code"]).first()
        if existing:
            # 同步关键字段，确保新功能权限约束生效
            if "required_tier" in fp_data and existing.required_tier != fp_data["required_tier"]:
                existing.required_tier = fp_data["required_tier"]
            if "required_points" in fp_data and existing.required_points != fp_data["required_points"]:
                existing.required_points = fp_data["required_points"]
            continue
        db.add(FeaturePermission(**fp_data, enabled=1, consume_points=1))
    db.commit()


def seed_sector_default_configs(db: Session) -> None:
    """初始化分时资金流向默认配置（已存在则跳过）。"""
    # 概念：过滤掉数据库中不存在的，保留前 20 个有效
    existing_concept_rows = db.execute(
        text("SELECT concept_id FROM stock_concept WHERE concept_id = ANY(:ids)"),
        {"ids": _HOT_CONCEPT_IDS}
    ).fetchall()
    existing_concept_ids = {row[0] for row in existing_concept_rows}
    concept_ids = [cid for cid in _HOT_CONCEPT_IDS if cid in existing_concept_ids][:20]

    # 行业：按热门顺序取实际存在的 20 个
    existing_industry_rows = db.execute(
        text("SELECT DISTINCT industry FROM stock_basic WHERE industry IS NOT NULL AND industry != ''")
    ).fetchall()
    existing_industry_names = {row[0] for row in existing_industry_rows}
    industry_ids = [name for name in _HOT_INDUSTRY_NAMES if name in existing_industry_names][:20]

    defaults = [
        {"sector_type": "concept", "sector_ids": concept_ids},
        {"sector_type": "industry", "sector_ids": industry_ids},
    ]

    for item in defaults:
        existing = db.query(SectorDefaultConfig).filter(
            SectorDefaultConfig.sector_type == item["sector_type"]
        ).first()
        if existing:
            continue
        db.add(SectorDefaultConfig(
            sector_type=item["sector_type"],
            sector_ids=item["sector_ids"],
            is_enabled=1,
        ))
    db.commit()
