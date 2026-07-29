"""AI 市场温度接口。

提供首页"AI 市场温度"卡片所需数据。
所有登录用户可访问（免费功能）。
"""

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_db
from app.schemas.user import User
from app.services import market_pulse_service
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/today")
async def get_market_pulse_today(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取最新一条市场温度数据（当天或最近交易日）。

    返回：温度分数、等级、AI总结、关键指标、热点关键词。
    """
    record = market_pulse_service.get_market_pulse_today(db)
    if record is None:
        return {
            "success": True,
            "data": None,
            "message": "暂无市场温度数据",
        }

    return {
        "success": True,
        "data": _format_pulse(record),
    }


@router.get("/history")
async def get_market_pulse_history(
    limit: int = Query(30, ge=1, le=100, description="返回条数"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取历史市场温度列表（用于趋势展示和后台管理）。"""
    records = market_pulse_service.get_market_pulse_history(db, limit=limit)
    return {
        "success": True,
        "data": [_format_pulse_flat(r) for r in records],
    }


@router.post("/generate")
async def manual_generate_market_pulse(
    user: User = Depends(get_current_user),
) -> dict:
    """手动触发生成市场温度（管理员调试用，后台线程执行）。"""
    import threading

    def _run():
        market_pulse_service.generate_market_pulse()

    threading.Thread(target=_run, daemon=True).start()
    return {"success": True, "message": "市场温度生成任务已启动"}


def _format_pulse(record) -> dict:
    """格式化 MarketPulse 记录为 API 响应（嵌套 indicators，给 iOS 用）。"""
    return {
        "trade_date": record.trade_date.isoformat() if record.trade_date else None,
        "score": record.score,
        "level": record.level,
        "summary": record.summary,
        "keywords": record.keywords.split(",") if record.keywords else [],
        "indicators": {
            "up_count": record.up_count,
            "down_count": record.down_count,
            "amount": float(record.amount) if record.amount else None,
            "amount_change_pct": float(record.amount_change_pct) if record.amount_change_pct else None,
            "north_money": float(record.north_money) if record.north_money else None,
            "limit_up_count": record.limit_up_count,
            "limit_down_count": record.limit_down_count,
            "open_limit_count": record.open_limit_count,
            "max_continuous_board": record.max_continuous_board,
        },
        "status": record.status,
    }


def _format_pulse_flat(record) -> dict:
    """格式化 MarketPulse 记录为平铺结构（给后台管理用）。"""
    return {
        "trade_date": record.trade_date.isoformat() if record.trade_date else None,
        "score": record.score,
        "level": record.level,
        "summary": record.summary,
        "keywords": record.keywords if record.keywords else None,
        "up_count": record.up_count,
        "down_count": record.down_count,
        "amount": float(record.amount) if record.amount else None,
        "amount_change_pct": float(record.amount_change_pct) if record.amount_change_pct else None,
        "north_money": float(record.north_money) if record.north_money else None,
        "limit_up_count": record.limit_up_count,
        "limit_down_count": record.limit_down_count,
        "open_limit_count": record.open_limit_count,
        "max_continuous_board": record.max_continuous_board,
        "status": record.status,
        "error_message": record.error_message,
    }
