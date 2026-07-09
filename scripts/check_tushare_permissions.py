"""检测所有 Tushare 接口的调用权限。

遍历 data_sources 表中所有 api_name，逐个调用（limit=1），
根据返回结果标记 has_permission: 1=有权限, 0=无权限。

Usage:
    docker exec yingplus_backend python scripts/check_tushare_permissions.py
"""

import sys
import time

sys.path.insert(0, "/app")

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.data_source import DataSource


def check_permissions():
    if not settings.tushare_token:
        print("ERROR: TUSHARE_TOKEN 未配置")
        return

    import tushare as ts
    ts.set_token(settings.tushare_token)
    pro = ts.pro_api()

    db = SessionLocal()
    try:
        sources = db.query(DataSource).order_by(DataSource.id.asc()).all()
        total = len(sources)
        print(f"开始检测 {total} 个接口的权限...")

        has_count = 0
        no_count = 0

        for i, src in enumerate(sources, 1):
            api_name = src.api_name
            try:
                # 调用接口（limit=1，尽量减少数据传输）
                df = pro.query(api_name, limit=1)
                # 能返回 DataFrame（即使为空）就说明有权限
                src.has_permission = 1
                src.permission_msg = None
                has_count += 1
                status = "✓"
            except Exception as e:
                err_msg = str(e)
                # 判断是否为权限错误
                if "权限" in err_msg or "permission" in err_msg.lower() or "抱歉" in err_msg or "没有访问" in err_msg:
                    src.has_permission = 0
                    src.permission_msg = err_msg[:500]
                    no_count += 1
                    status = "✗"
                elif "输入参数" in err_msg or "必须" in err_msg:
                    # 参数错误说明接口可达，有权限
                    src.has_permission = 1
                    src.permission_msg = f"需要参数: {err_msg[:200]}"
                    has_count += 1
                    status = "✓(需参数)"
                else:
                    # 其他错误归为无权限
                    src.has_permission = 0
                    src.permission_msg = err_msg[:500]
                    no_count += 1
                    status = "?"

            print(f"  [{i}/{total}] {status} {api_name} - {src.title}")

            # 每 3 个请求间隔 0.3 秒，避免频率限制
            if i % 3 == 0:
                time.sleep(0.3)

        db.commit()
        print(f"\n检测完成: 有权限 {has_count}, 无权限 {no_count}, 总计 {total}")

    finally:
        db.close()


if __name__ == "__main__":
    check_permissions()
