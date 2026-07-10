"""数据源权限检测服务。

逐个调用 Tushare 接口，检测当前 token 是否有权限调用。
结果写入 data_sources.has_permission 字段。
"""

import logging
import time

from app.db.base import SessionLocal
from app.models.data_source import DataSource

logger = logging.getLogger(__name__)


def check_permissions_async():
    """批量检测所有数据源的权限（耗时操作，应在后台线程运行）。"""
    from app.services.data_sync_service import get_pro

    db = SessionLocal()
    try:
        pro = get_pro()
        sources = db.query(DataSource).order_by(DataSource.id.asc()).all()
        logger.info(f"[PermCheck] 开始检测 {len(sources)} 个接口权限...")

        for i, ds in enumerate(sources):
            try:
                # 尝试调用接口，只取1条数据
                func = getattr(pro, ds.api_name, None)
                if func is None:
                    ds.has_permission = 0
                    ds.permission_msg = "接口不存在"
                    continue

                df = func(limit=1)
                if df is not None:
                    ds.has_permission = 1
                    ds.permission_msg = f"OK, 返回 {len(df.columns)} 列"
                else:
                    ds.has_permission = 1
                    ds.permission_msg = "OK, 返回 None(可能无数据)"

            except Exception as e:
                err_msg = str(e)[:400]
                if "权限" in err_msg or "积分" in err_msg or "403" in err_msg or "permission" in err_msg.lower():
                    ds.has_permission = 0
                    ds.permission_msg = err_msg[:500]
                elif "没有访问该接口的权限" in err_msg or "抱歉" in err_msg:
                    ds.has_permission = 0
                    ds.permission_msg = err_msg[:500]
                else:
                    # 其他错误（如必填参数缺失、参数校验失败）说明有权限但参数不对
                    ds.has_permission = 1
                    ds.permission_msg = f"可调用(参数报错): {err_msg[:200]}"

            # Tushare 限流
            time.sleep(0.25)

            if (i + 1) % 20 == 0:
                db.commit()
                logger.info(f"[PermCheck] 已检测 {i + 1}/{len(sources)}")

        db.commit()
        logger.info(f"[PermCheck] 权限检测完成，共 {len(sources)} 个接口")
    except Exception as e:
        logger.error(f"[PermCheck] 检测异常: {e}")
        db.rollback()
    finally:
        db.close()


def check_single_api(api_name: str) -> dict:
    """检测单个接口权限。"""
    from app.services.data_sync_service import get_pro

    db = SessionLocal()
    try:
        pro = get_pro()
        ds = db.query(DataSource).filter(DataSource.api_name == api_name).first()
        if ds is None:
            return {"api_name": api_name, "has_permission": -1, "message": "接口不在注册表中"}

        try:
            func = getattr(pro, api_name, None)
            if func is None:
                ds.has_permission = 0
                ds.permission_msg = "接口不存在"
            else:
                df = func(limit=1)
                ds.has_permission = 1
                ds.permission_msg = f"OK, 返回 {len(df.columns) if df is not None else 0} 列"
        except Exception as e:
            err_msg = str(e)[:400]
            if "权限" in err_msg or "积分" in err_msg or "403" in err_msg or "没有访问" in err_msg:
                ds.has_permission = 0
                ds.permission_msg = err_msg[:500]
            else:
                ds.has_permission = 1
                ds.permission_msg = f"可调用: {err_msg[:200]}"

        db.commit()
        return {
            "api_name": api_name,
            "has_permission": ds.has_permission == 1,
            "message": ds.permission_msg,
        }
    finally:
        db.close()
