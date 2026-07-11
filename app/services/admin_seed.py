"""后台管理初始数据种子。

开发环境启动时自动插入，已存在则跳过。
"""

from sqlalchemy.orm import Session

from app.models.admin import AdminMenu, AdminRole
from app.models.h5_page import H5Page


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
        "path": "/data/scheduler/index",
        "name": "DataScheduler",
        "component": "data/scheduler/index",
        "redirect": None,
        "title": "定时任务",
        "icon": "ep:timer",
        "menu_type": 1,
        "rank": 1,
    },
    {
        "id": 12,
        "parent_id": 10,
        "path": "/data/sync/index",
        "name": "DataSync",
        "component": "data/sync/index",
        "redirect": None,
        "title": "数据同步",
        "icon": "ep:refresh",
        "menu_type": 1,
        "rank": 2,
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
        "rank": 3,
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
        "rank": 4,
    },
    {
        "id": 16,
        "parent_id": 10,
        "path": "/data/logs/index",
        "name": "DataLogs",
        "component": "data/logs/index",
        "redirect": None,
        "title": "执行日志",
        "icon": "ep:document-checked",
        "menu_type": 1,
        "rank": 5,
    },
    {
        "id": 17,
        "parent_id": 10,
        "path": "/data/limit-up-ladder/index",
        "name": "LimitUpLadder",
        "component": "data/limit-up-ladder/index",
        "redirect": None,
        "title": "涨停板天梯",
        "icon": "ep:trend-charts",
        "menu_type": 1,
        "rank": 6,
    },
    {
        "id": 18,
        "parent_id": 10,
        "path": "/data/aggregation/index",
        "name": "DataAggregation",
        "component": "data/aggregation/index",
        "redirect": None,
        "title": "聚合数据",
        "icon": "ep:odometer",
        "menu_type": 1,
        "rank": 7,
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
]


def seed_admin_menus(db: Session) -> None:
    """插入初始数据（按 ID 逐条检查，已存在跳过，新增插入）。"""
    # 种子角色
    if db.query(AdminRole).count() == 0:
        for role_data in _SEED_ROLES:
            db.add(AdminRole(**role_data))
        db.commit()

    # 种子菜单（逐条检查，支持增量）
    for menu_data in _SEED_MENUS:
        existing = db.query(AdminMenu).filter(AdminMenu.id == menu_data["id"]).first()
        if existing:
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
