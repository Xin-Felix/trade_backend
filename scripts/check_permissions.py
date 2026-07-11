#!/usr/bin/env python3
"""刷新数据源权限（使用 Tushare 代理 token）。

用法：
    python scripts/check_permissions.py
"""
import sys
import os
import time
import traceback
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONUNBUFFERED", "1")

from app.db.base import SessionLocal
from app.models.data_source import DataSource
from app.core.config import settings

# 直接使用 requests POST 调用代理接口（避免 tushare SDK 的无限等待问题）
_PROXY_URL = settings.tushare_proxy_url or "https://tx.xiaodefa.top/"
_PROXY_TOKEN = settings.tushare_proxy_token or "1fe02cab5701551ecb2a75eeed2932f839fc44d8745acfd335712de0"


def _call_api(api_name: str, timeout: int = 8) -> tuple:
    """直接 POST 调用 Tushare 代理，返回 (has_permission, msg)。"""
    payload = {
        "api_name": api_name,
        "token": _PROXY_TOKEN,
        "params": {"limit": 1},
        "fields": "",
    }
    try:
        r = requests.post(_PROXY_URL, json=payload, timeout=(3, 5))
        if r.status_code != 200:
            return 1, f"可调用(HTTP {r.status_code})"
        data = r.json()
        code = data.get("code")
        msg = (data.get("msg") or "")[:400]
        if code != 0:
            if any(kw in msg for kw in ["权限", "积分", "403", "没有访问", "抱歉"]) or "permission" in msg.lower():
                return 0, msg[:500]
            else:
                return 1, f"可调用(参数报错): {msg[:200]}"
        else:
            # 成功
            fields = data.get("data", {}).get("fields", []) if data.get("data") else []
            return 1, f"OK, 返回 {len(fields)} 列"
    except requests.Timeout:
        return 1, "可调用(超时)"
    except Exception as e:
        return 1, f"可调用(异常): {str(e)[:100]}"


def main():
    db = SessionLocal()
    try:
        print(f"代理地址: {_PROXY_URL}", flush=True)
        print(f"Token: {_PROXY_TOKEN[:8]}...{_PROXY_TOKEN[-8:]}", flush=True)

        # Quick test
        has, msg = _call_api("trade_cal")
        print(f"连接测试: {msg}", flush=True)
        if has == 0:
            print("ERROR: 连接失败，退出", flush=True)
            return

        sources = db.query(DataSource).order_by(DataSource.id.asc()).all()
        total = len(sources)
        print(f"\n开始检测 {total} 个接口权限...\n", flush=True)

        changed = 0
        ok_count = 0
        no_count = 0

        for i, ds in enumerate(sources):
            old_perm = ds.has_permission
            has_perm, msg = _call_api(ds.api_name)
            ds.has_permission = has_perm
            ds.permission_msg = msg

            if ds.has_permission == 1:
                ok_count += 1
            else:
                no_count += 1

            if old_perm != ds.has_permission:
                changed += 1
                status = "✓" if ds.has_permission == 1 else "✗"
                print(f"  [{status}] {ds.api_name}: {ds.permission_msg[:80]}", flush=True)

            time.sleep(0.1)

            if (i + 1) % 30 == 0:
                db.commit()
                print(f"  ... 进度 {i + 1}/{total} | 有权限 {ok_count} | 无权限 {no_count} | 变更 {changed}", flush=True)

        db.commit()
        print(f"\n{'='*50}", flush=True)
        print(f"完成! 共 {total} 个接口", flush=True)
        print(f"  有权限: {ok_count}", flush=True)
        print(f"  无权限: {no_count}", flush=True)
        print(f"  本次变更: {changed}", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
