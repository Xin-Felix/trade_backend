"""涨停板天梯后台管理接口。

供后台管理页面单独管理涨停板天梯功能：
- 查看数据依赖和同步状态
- 手动触发相关数据源同步
- 查询/修改定时任务配置（复用 scheduler_service）
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.schemas.user import User
from app.services import limit_up_admin_service
from app.services.scheduler_service import save_job_config

router = APIRouter()


class SyncRequest(BaseModel):
    """手动同步请求"""

    trade_date: Optional[str] = None  # YYYYMMDD
    days: int = 1


class JobConfigRequest(BaseModel):
    """调度任务配置请求"""

    trigger_type: str = "interval"  # cron / interval
    cron_hour: int = 18
    cron_minute: int = 0
    cron_day_of_week: str = "mon-fri"
    interval_hours: int = 0
    interval_minutes: int = 1
    days: int = 1
    enabled: bool = True


@router.get("/overview")
async def get_limit_up_ladder_overview(
    user: User = Depends(get_current_user),
) -> dict:
    """获取涨停板天梯功能概览（数据依赖 + 调度任务状态）。"""
    return {"success": True, "data": limit_up_admin_service.get_limit_up_ladder_overview()}


@router.post("/sync")
async def sync_limit_up_ladder_data(
    body: SyncRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """手动触发涨停板天梯相关数据源同步。

    - trade_date: 指定日期 YYYYMMDD，不传则同步最近 days 天
    - days: 同步天数
    """
    target_date = None
    if body.trade_date:
        try:
            target_date = datetime.strptime(body.trade_date, "%Y%m%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="trade_date 格式错误，应为 YYYYMMDD") from exc

    try:
        result = limit_up_admin_service.sync_limit_up_ladder_dependencies(
            trade_date=target_date, days=body.days
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {e}") from e


@router.get("/job")
async def get_limit_up_ladder_job(
    user: User = Depends(get_current_user),
) -> dict:
    """获取涨停板天梯关联的调度任务配置。"""
    overview = limit_up_admin_service.get_limit_up_ladder_overview()
    return {"success": True, "data": overview.get("scheduler_job")}


@router.put("/job")
async def update_limit_up_ladder_job(
    body: JobConfigRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """更新涨停板天梯关联的调度任务配置（即 sync_limit_data）。

    建议配置：
    - 盘中实时：interval，interval_minutes=1
    - 盘后低频：cron，cron_hour=15，cron_minute=30
    """
    try:
        result = save_job_config(
            job_id="sync_limit_data",
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}") from e


@router.get("/data")
async def get_limit_up_ladder_data(
    trade_date: str | None = Query(None, min_length=8, max_length=8, description="交易日期 YYYYMMDD"),
    top_n_concepts: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> dict:
    """获取涨停板天梯数据（管理端，不消费积分）。"""
    from datetime import datetime as dt

    from app.services import limit_up_service

    target_date = None
    if trade_date:
        target_date = dt.strptime(trade_date, "%Y%m%d").date()
    result = limit_up_service.get_limit_up_ladder(
        trade_date=target_date, top_n_concepts=top_n_concepts
    )
    return {"success": True, "data": result}
