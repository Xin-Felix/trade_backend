"""用户端每日复盘接口。

根据用户身份返回不同层级内容：
- 会员：每日自动生成的深度复盘
- 积分用户：可手动点击生成标准复盘
- 免费用户：查看全市场通用的一句话复盘
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, require_feature
from app.db.base import get_db
from app.models.daily_review import DailyReview
from app.models.market_daily_review import MarketDailyReview
from app.models.user import User as UserModel
from app.schemas.daily_review import (
    DailyReviewDetailResponse,
    DailyReviewListResponse,
    DailyReviewTodayResponse,
    OperationResponse,
)
from app.schemas.user import User
from app.services import daily_review_service, market_daily_review_service, membership_service

router = APIRouter()


_DAILY_REVIEW_DEEP_FEATURE = "ai_daily_review_deep"
_DAILY_REVIEW_STANDARD_FEATURE = "ai_daily_review_standard"


def _get_db_user(db: Session, public_id: str) -> UserModel:
    user = (
        db.query(UserModel)
        .filter(UserModel.public_id == public_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def _report_to_dict(report) -> dict:
    return {
        "id": report.id,
        "user_id": report.user_id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "level": getattr(report, "level", "standard"),
        "status": report.status,
        "summary": report.summary,
        "content": report.content,
        "error_message": report.error_message,
        "prompt_version": getattr(report, "prompt_version", None),
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


def _market_report_to_dict(report: MarketDailyReview) -> dict:
    return {
        "id": report.id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "level": report.level,
        "status": report.status,
        "content": report.content,
        "error_message": report.error_message,
        "prompt_version": report.prompt_version,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


async def _check_feature_access(
    db: Session, db_user: UserModel, feature_code: str
) -> bool:
    """非消费式检查用户是否有某功能权限。"""
    result = await run_in_threadpool(
        membership_service.check_and_consume,
        db,
        db_user,
        feature_code,
        consume=False,
    )
    return result["allowed"]


async def _require_personal_review_access(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """校验用户是否有权限查看个人复盘历史（会员或积分用户）。

    会员拥有 deep 权限，积分用户拥有 standard 权限，两者均可查看个人复盘。
    """
    db_user = _get_db_user(db, user.id)
    has_deep = await _check_feature_access(db, db_user, _DAILY_REVIEW_DEEP_FEATURE)
    has_standard = await _check_feature_access(db, db_user, _DAILY_REVIEW_STANDARD_FEATURE)
    if not (has_deep or has_standard):
        raise HTTPException(
            status_code=402,
            detail={
                "feature_code": _DAILY_REVIEW_STANDARD_FEATURE,
                "reason": "需要积分或会员权限才能查看个人复盘",
                "required_points": 100,
            },
        )
    return user


@router.get("/today", response_model=DailyReviewTodayResponse)
async def get_today_review(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户今日的复盘报告。

    返回逻辑：
    - 会员：返回自动生成的深度复盘
    - 积分用户：返回已生成的标准复盘；未生成则提示可手动生成
    - 免费用户：返回全市场通用的一句话复盘
    """
    db_user = _get_db_user(db, user.id)
    today = date.today()

    # 1. 会员：返回深度复盘
    if await _check_feature_access(db, db_user, _DAILY_REVIEW_DEEP_FEATURE):
        report = (
            db.query(DailyReview)
            .filter(
                DailyReview.user_id == db_user.id,
                DailyReview.report_date == today,
                DailyReview.level == "deep",
                DailyReview.is_deleted == 0,
            )
            .first()
        )
        if report is None or report.status != "success":
            raise HTTPException(status_code=404, detail="今日深度复盘尚未生成，请稍后再试")
        return DailyReviewTodayResponse(level="deep", data=_report_to_dict(report))

    # 2. 积分用户：返回标准复盘
    if await _check_feature_access(db, db_user, _DAILY_REVIEW_STANDARD_FEATURE):
        report = (
            db.query(DailyReview)
            .filter(
                DailyReview.user_id == db_user.id,
                DailyReview.report_date == today,
                DailyReview.level == "standard",
                DailyReview.is_deleted == 0,
            )
            .first()
        )
        if report is not None and report.status == "success":
            return DailyReviewTodayResponse(level="standard", data=_report_to_dict(report))
        raise HTTPException(
            status_code=404,
            detail="今日标准复盘尚未生成，可点击生成",
        )

    # 3. 免费用户：返回全市场一句话复盘
    report = market_daily_review_service.get_market_brief(db, today)
    if report is None or report.status != "success":
        raise HTTPException(status_code=404, detail="今日市场复盘尚未生成，请稍后再试")
    return DailyReviewTodayResponse(level="brief", data=_market_report_to_dict(report))


@router.post("/generate", response_model=OperationResponse)
async def generate_standard_review(
    user: User = Depends(require_feature(_DAILY_REVIEW_STANDARD_FEATURE, consume=True)),
    db: Session = Depends(get_db),
):
    """积分用户手动生成今日标准复盘。"""
    db_user = _get_db_user(db, user.id)
    today = date.today()

    existing = (
        db.query(DailyReview)
        .filter(
            DailyReview.user_id == db_user.id,
            DailyReview.report_date == today,
            DailyReview.level == "standard",
            DailyReview.is_deleted == 0,
        )
        .first()
    )
    if existing is not None and existing.status == "success":
        return OperationResponse(message="今日标准复盘已生成，请勿重复生成")
    if existing is not None and existing.status == "running":
        return OperationResponse(message="今日标准复盘正在生成中，请勿重复点击")

    report = await daily_review_service.generate_standard_review_for_user(
        db, db_user.id, today
    )
    if report.status == "success":
        return OperationResponse(message="标准复盘生成成功")
    if report.status == "running":
        return OperationResponse(message="标准复盘正在生成中")
    return OperationResponse(message=f"标准复盘生成失败：{report.error_message}")


@router.get("", response_model=DailyReviewListResponse)
async def list_my_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(_require_personal_review_access),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的历史复盘列表（按日期倒序）。

    会员和积分用户均可查看自己的个人复盘历史。
    """
    db_user = _get_db_user(db, user.id)
    items, total = daily_review_service.get_user_reviews(
        db, db_user.id, page=page, page_size=page_size
    )
    return DailyReviewListResponse(
        data={
            "list": [_report_to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{review_id}", response_model=DailyReviewDetailResponse)
async def get_review_detail(
    review_id: int,
    user: User = Depends(_require_personal_review_access),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的复盘详情。"""
    db_user = _get_db_user(db, user.id)
    report = daily_review_service.get_review_detail(db, review_id, user_id=db_user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    return DailyReviewDetailResponse(data=_report_to_dict(report))
