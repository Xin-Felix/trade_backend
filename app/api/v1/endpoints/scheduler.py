"""调度管理接口，供后台管理面板配置定时同步任务。

任务配置持久化到数据库，每个任务可单独配置触发时间。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_current_user
from app.schemas.user import User
from app.services.scheduler_service import (
    get_all_job_configs,
    get_available_jobs,
    get_available_jobs_grouped,
    get_job_logs,
    run_job_now,
    save_job_config,
    toggle_job,
)

router = APIRouter()


class JobConfigRequest(BaseModel):
    """创建/更新任务配置"""
    job_id: str
    trigger_type: str = "cron"  # cron / interval
    cron_hour: int = 18
    cron_minute: int = 0
    cron_day_of_week: str = "mon-fri"
    interval_hours: int = 0
    interval_minutes: int = 30
    days: int = 1
    enabled: bool = True


class ToggleRequest(BaseModel):
    """启用/禁用任务"""
    enabled: bool


@router.get("/jobs")
async def list_jobs(
    user: User = Depends(get_current_user),
) -> dict:
    """获取所有已配置的定时任务（含运行状态）。"""
    jobs = get_all_job_configs()
    return {"success": True, "data": jobs}


@router.get("/available")
async def list_available_jobs(
    user: User = Depends(get_current_user),
) -> dict:
    """获取所有可配置的任务类型。"""
    return {"success": True, "data": get_available_jobs()}


@router.get("/available-grouped")
async def list_available_jobs_grouped(
    user: User = Depends(get_current_user),
) -> dict:
    """获取所有任务按分组归类（供数据中心页面展示）。"""
    return {"success": True, "data": get_available_jobs_grouped()}


@router.post("/jobs")
async def create_or_update_job(
    body: JobConfigRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """创建或更新任务配置（保存到数据库并立即生效）。

    - trigger_type: "cron" 或 "interval"
    - cron 模式: 配置 cron_hour / cron_minute / cron_day_of_week
    - interval 模式: 配置 interval_hours / interval_minutes
    - days: 每次同步多少天的数据
    - enabled: 是否启用
    """
    try:
        result = save_job_config(
            job_id=body.job_id,
            trigger_type=body.trigger_type,
            cron_hour=body.cron_hour,
            cron_minute=body.cron_minute,
            cron_day_of_week=body.cron_day_of_week,
            interval_hours=body.interval_hours,
            interval_minutes=body.interval_minutes,
            days=body.days,
            enabled=body.enabled,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/jobs/{job_id}/toggle")
async def toggle_job_endpoint(
    job_id: str,
    body: ToggleRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """启用/禁用任务。"""
    result = toggle_job(job_id, body.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail=f"任务配置不存在: {job_id}")
    return {"success": True, "data": result}


@router.post("/jobs/{job_id}/run")
async def trigger_job(
    job_id: str,
    days: int = Query(1, ge=1, le=30),
    user: User = Depends(get_current_user),
) -> dict:
    """立即执行任务（后台运行，不影响定时调度）。"""
    success = run_job_now(job_id, days=days)
    if not success:
        raise HTTPException(status_code=404, detail=f"未知任务: {job_id}")
    return {"success": True, "data": {"job_id": job_id, "days": days, "status": "started"}}


@router.get("/logs")
async def list_job_logs(
    job_id: str = Query("", description="按任务ID筛选"),
    status: str = Query("", description="按状态筛选: success/failed/running"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> dict:
    """获取任务执行日志（分页，按时间倒序）。"""
    data = get_job_logs(job_id=job_id or None, status=status or None, page=page, page_size=page_size)
    return {"success": True, "data": data}
