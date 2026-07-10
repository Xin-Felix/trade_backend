"""后台管理初始数据种子。

开发环境启动时自动插入，已存在则跳过。
"""

from sqlalchemy.orm import Session

from app.models.admin import AdminMenu, AdminRole


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
        "id": 14,
        "parent_id": 10,
        "path": "/data/sources/index",
        "name": "DataSources",
        "component": "data/sources/index",
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
