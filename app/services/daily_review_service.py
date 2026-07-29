"""每日复盘服务层。

为会员自动生成基于自选股的 AI 复盘报告，并提供查询/重试能力。
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.daily_review import DailyReview
from app.models.membership import UserMembership
from app.models.user import User as UserModel
from app.models.watchlist import Watchlist
from app.services import ai_service, stock_service
from app.services.limit_up_service import get_limit_up_ladder

logger = logging.getLogger(__name__)

# 批量生成时最大并发数，避免同时发起过多 AI 调用
MAX_CONCURRENT_REVIEWS = 3

# 中国时区 UTC+8
CN_TZ = timezone(timedelta(hours=8))


def _cn_today() -> date:
    """获取中国时间的今天日期。"""
    return datetime.now(CN_TZ).date()


def _cn_now() -> datetime:
    """获取中国时间的当前时刻。"""
    return datetime.now(CN_TZ)


# ---------------------------------------------------------------------------
# 交易日辅助
# ---------------------------------------------------------------------------


def get_latest_trade_date(db: Session) -> date | None:
    """获取本地数据库中最新的交易日（基于 stock_daily 表）。"""
    from app.models.stock import StockDaily

    latest = db.query(func.max(StockDaily.trade_date)).scalar()
    return latest


def is_trading_day(db: Session, target_date: date) -> bool:
    """判断指定日期是否为交易日。

    优先看本地 stock_daily 表是否有该日数据（最准确）；
    若当天数据尚未同步（如盘后但同步未完成），则回退到检查 trade_cal 交易日历表；
    若都没有，则用"周一至周五"作为兜底判断。
    """
    from app.models.stock import StockDaily

    # 1. 本地已有当天行情数据 → 确认是交易日
    has_data = (
        db.query(StockDaily)
        .filter(StockDaily.trade_date == target_date)
        .first()
        is not None
    )
    if has_data:
        return True

    # 2. 尝试查交易日历表（Tushare trade_cal 同步到本地）
    try:
        from app.models.stock import TradeCal
        cal = (
            db.query(TradeCal)
            .filter(TradeCal.cal_date == target_date, TradeCal.exchange == "SSE")
            .first()
        )
        if cal is not None:
            return cal.is_open == 1
    except Exception:
        pass  # 表不存在或其他问题，走兜底逻辑

    # 3. 兜底：周一到周五视为交易日（不含节假日，但节假日是少数）
    return target_date.weekday() < 5  # 0=周一, 4=周五


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _get_or_create_review(
    db: Session, user_id: int, report_date: date, level: str = "standard"
) -> DailyReview:
    """获取或创建某用户某日某层级的复盘记录。"""
    review = (
        db.query(DailyReview)
        .filter(
            DailyReview.user_id == user_id,
            DailyReview.report_date == report_date,
            DailyReview.level == level,
            DailyReview.is_deleted == 0,
        )
        .first()
    )
    if review is None:
        review = DailyReview(
            user_id=user_id, report_date=report_date, level=level, status="pending"
        )
        db.add(review)
        db.commit()
        db.refresh(review)
    return review


def get_user_watchlist_data(db: Session, user_id: int) -> dict:
    """获取用户持仓+自选股及其行情数据（结构化，供后台查看）。

    Returns:
        {"portfolio": [...], "watchlist": [...]}
    """
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return {"portfolio": [], "watchlist": []}

    # 持仓数据
    from app.models.portfolio import Portfolio
    portfolio_rows = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.public_id, Portfolio.is_deleted == 0)
        .all()
    )
    portfolio_codes = set()
    portfolio_result = []
    for item in portfolio_rows:
        portfolio_codes.add(item.ts_code)
        entry = {
            "code": item.code,
            "name": item.name,
            "ts_code": item.ts_code,
            "cost_price": float(item.cost_price) if item.cost_price is not None else None,
            "quantity": float(item.quantity) if item.quantity is not None else None,
            "is_margin": bool(item.is_margin) if item.is_margin is not None else False,
            "note": item.note,
            "type": "portfolio",
        }
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            basic = basic_list[0] if basic_list else None
            entry["price"] = quote.price if quote else None
            entry["change_percent"] = quote.change_percent if quote else None
            entry["pe"] = basic.get("pe") if basic else None
            entry["pb"] = basic.get("pb") if basic else None
            entry["turnover_rate"] = basic.get("turnover_rate") if basic else None
            # 计算盈亏
            if entry["cost_price"] and entry["quantity"] and entry["price"]:
                entry["profit"] = round((entry["price"] - entry["cost_price"]) * entry["quantity"], 2)
                entry["profit_pct"] = round((entry["price"] - entry["cost_price"]) / entry["cost_price"] * 100, 2)
                entry["market_value"] = round(entry["price"] * entry["quantity"], 2)
            else:
                entry["profit"] = None
                entry["profit_pct"] = None
                entry["market_value"] = None
        except Exception as exc:
            entry["error"] = str(exc)
        portfolio_result.append(entry)

    # 自选股数据（排除已在持仓中的）
    watchlist_rows = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.public_id, Watchlist.is_deleted == 0)
        .all()
    )
    watchlist_result = []
    for item in watchlist_rows:
        if item.ts_code in portfolio_codes:
            continue  # 已在持仓中，不重复显示
        entry = {
            "code": item.code,
            "name": item.name,
            "ts_code": item.ts_code,
            "type": "watchlist",
        }
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            basic = basic_list[0] if basic_list else None
            entry["price"] = quote.price if quote else None
            entry["change_percent"] = quote.change_percent if quote else None
            entry["pe"] = basic.get("pe") if basic else None
            entry["pb"] = basic.get("pb") if basic else None
            entry["turnover_rate"] = basic.get("turnover_rate") if basic else None
        except Exception as exc:
            entry["error"] = str(exc)
        watchlist_result.append(entry)

    return {"portfolio": portfolio_result, "watchlist": watchlist_result}


async def build_watchlist_context(db: Session, user_id: int, market_context: str | None = None) -> str:
    """基于用户持仓+自选股组装 AI 上下文文本。

    - 持仓股：深度分析（5天K线、4周周K、概念、资金流向、成本/盈亏）
    - 自选股（非持仓）：简要行情

    Args:
        market_context: 预构建的通用市场数据文本。若为 None 则当场构建。
                        批量生成时应预先调用 build_market_context() 并传入复用。
    """
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        return "用户不存在。"

    # 获取持仓
    from app.models.portfolio import Portfolio
    portfolio_rows = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.public_id, Portfolio.is_deleted == 0)
        .all()
    )

    # 获取自选股
    watchlist_rows = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.public_id, Watchlist.is_deleted == 0)
        .all()
    )

    # 持仓股票代码集合（用于区分自选里哪些是持仓）
    portfolio_codes = {p.ts_code for p in portfolio_rows}

    parts = [f"用户：{user.name or user.email}"]

    # 通用市场数据（复用或当场构建）
    if market_context is None:
        market_context = build_market_context()
    parts.append(market_context)

    # 持仓股深度分析
    if portfolio_rows:
        parts.append(_build_portfolio_detail_section(portfolio_rows))
    else:
        parts.append("【用户持仓】该用户当前没有持仓股票。")

    # 自选股简要行情（排除已在持仓中的）
    watchlist_only = [w for w in watchlist_rows if w.ts_code not in portfolio_codes]
    if watchlist_only:
        parts.append(_build_watchlist_brief_section(watchlist_only))

    # 如果既没有持仓也没有自选
    if not portfolio_rows and not watchlist_only:
        parts.append("该用户当前没有持仓和自选股，请生成一份面向整体市场的通用收盘复盘。")

    return "\n\n".join(parts)


async def _build_watchlist_context(db: Session, user: UserModel, market_context: str | None = None) -> str:
    """基于用户自选股组装 AI 上下文（内部兼容旧调用）。"""
    return await build_watchlist_context(db, user.id, market_context=market_context)


# ---------------------------------------------------------------------------
# 通用市场数据（所有用户共享，批量生成时只构建一次）
# ---------------------------------------------------------------------------


def _check_data_readiness(db: Session, today: date, latest_trade: date | None) -> dict:
    """检查当天交易日的各核心数据是否已同步完成。

    Returns:
        {
            "is_trading_day": bool,
            "has_today_data": bool,
            "errors": list[str],  # 未就绪的数据项
            "summary": str,       # 一句话概括
        }
    """
    from app.models.stock import IndexDaily, StockDaily, StockMoneyflow, MoneyflowHsgt, IndexGlobal

    errors = []
    is_td = is_trading_day(db, today)

    # 如果不是交易日，数据用最新即可，不需要校验当天
    if not is_td:
        return {
            "is_trading_day": False,
            "has_today_data": False,
            "errors": [],
            "summary": f"非交易日，使用最新交易日 {latest_trade} 数据",
        }

    has_today = latest_trade == today if latest_trade else False

    # 校验各数据源最新日期是否为今天
    checks = [
        ("A股日K", StockDaily, StockDaily.trade_date),
        ("指数日线", IndexDaily, IndexDaily.trade_date),
        ("北向资金", MoneyflowHsgt, MoneyflowHsgt.trade_date),
    ]

    for name, model, date_col in checks:
        latest = db.query(func.max(date_col)).scalar()
        if latest != today:
            errors.append(f"{name}最新={latest}(需要{today})")

    # 全球指数允许滞后1天（国际市场有时差）
    global_latest = db.query(func.max(IndexGlobal.trade_date)).scalar()
    if global_latest and (today - global_latest).days > 2:
        errors.append(f"全球指数最新={global_latest}(滞后超2天)")

    if errors:
        summary = f"交易日{today}，{len(errors)}项数据未就绪"
    else:
        summary = f"交易日{today}，所有数据已就绪"

    return {
        "is_trading_day": True,
        "has_today_data": has_today,
        "errors": errors,
        "summary": summary,
    }


def build_market_context() -> str:
    """构建通用市场数据上下文（大盘、国际、北向、涨跌停、板块）。

    此函数的输出不依赖用户，所有用户复盘共享同一份。
    批量生成时应只调用一次，然后传入每个用户的 build_watchlist_context。

    Raises:
        RuntimeError: 当天交易日数据尚未同步完成时抛出。
    """
    today = _cn_today()

    # 数据就绪检查：校验当天各核心数据源是否已同步
    db = SessionLocal()
    try:
        latest_trade = get_latest_trade_date(db)
        readiness = _check_data_readiness(db, today, latest_trade)
    finally:
        db.close()

    if readiness["errors"]:
        error_detail = "; ".join(readiness["errors"])
        logger.warning(f"[DailyReview] 数据就绪检查未通过: {error_detail}")
        # 非交易日允许用最新数据，交易日数据不全则报错
        if readiness["is_trading_day"] and not readiness["has_today_data"]:
            raise RuntimeError(
                f"当天({today})数据尚未同步完成，无法生成复盘。"
                f"详情: {error_detail}。请确认盘后数据同步任务已执行。"
            )

    data_date = latest_trade if latest_trade else today
    date_header = (
        f"【复盘日期】{today.isoformat()}（数据交易日：{data_date.isoformat()}）\n"
        f"数据就绪状态：{readiness['summary']}"
    )

    sections = [
        date_header,
        _build_market_index_section(),
        _build_global_market_section(),
        _build_hsgt_section(),
        _build_limit_ladder_section(),
        _build_hot_sector_section(),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Context 辅助函数：市场全貌
# ---------------------------------------------------------------------------


def _fmt_date(d: date) -> str:
    """日期格式化为 YYYYMMDD。"""
    return d.strftime("%Y%m%d")


def _build_market_index_section() -> str:
    """构建大盘指数近 5 天行情片段。"""
    lines = ["【大盘指数近 5 天走势】"]
    index_codes = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
    }
    for ts_code, name in index_codes.items():
        try:
            klines = stock_service.get_index_daily(ts_code, limit=5)
            if klines:
                lines.append(f"{name}（{ts_code}）：")
                for k in klines:
                    lines.append(
                        f"  {k.get('trade_date')}: 收盘={k.get('close')} 涨跌幅={k.get('pct_chg')}% "
                        f"成交额={k.get('amount')}亿"
                    )
            else:
                lines.append(f"{name}：暂无数据")
        except Exception as exc:
            lines.append(f"{name}：获取失败（{exc}）")
    return "\n".join(lines)


def _build_global_market_section() -> str:
    """构建欧美及国际市场行情片段（从本地 index_global 表读取）。"""
    lines = ["【国际市场（全球指数/商品/汇率）】"]

    # 全球指数 — 从本地 index_global 表读取最新一天数据
    try:
        from app.models.stock import IndexGlobal
        db = SessionLocal()
        try:
            # 取最新交易日
            latest_date = db.query(func.max(IndexGlobal.trade_date)).scalar()
            if latest_date:
                rows = (
                    db.query(IndexGlobal)
                    .filter(IndexGlobal.trade_date == latest_date)
                    .all()
                )
                # ts_code -> 中文名映射
                name_map = {
                    "HSI": "恒生指数", "HKTECH": "恒生科技", "XIN9": "国企指数",
                    "N225": "日经225", "KS11": "韩国综合", "TWII": "台湾加权",
                    "AS51": "澳洲标普200", "SENSEX": "印度孟买", "CKLSE": "马来综合",
                    "DJI": "道琼斯", "SPX": "标普500", "IXIC": "纳斯达克",
                    "FTSE": "英国富时100", "GDAXI": "德国DAX",
                }
                if rows:
                    lines.append(f"全球指数（{latest_date.isoformat()}）：")
                    for r in rows:
                        name = name_map.get(r.ts_code, r.ts_code)
                        pct = float(r.pct_chg) if r.pct_chg else 0
                        close = float(r.close) if r.close else 0
                        lines.append(f"- {name}（{r.ts_code}）: {close:.2f} ({pct:+.2f}%)")
                else:
                    lines.append("全球指数：暂无数据")
            else:
                lines.append("全球指数：本地无数据（请检查 sync_index_global 是否正常）")
        finally:
            db.close()
    except Exception as exc:
        lines.append(f"全球指数读取失败：{exc}")

    # 商品/汇率 — Tushare fx_daily 速度快，保留实时拉取；akshare 商品如果拉不到就跳过
    try:
        from app.services import global_market_service
        commodities = global_market_service.get_commodities_and_forex()
        if commodities:
            lines.append("商品/汇率：")
            for item in commodities:
                pct = item.get("change_percent", 0)
                lines.append(
                    f"- {item.get('name')}: {item.get('price')} ({pct:+.2f}%)"
                )
    except Exception as exc:
        lines.append(f"商品/汇率获取失败：{exc}")

    return "\n".join(lines)


def _build_hsgt_section() -> str:
    """构建北向资金近 5 天片段。"""
    lines = ["【北向资金（近 5 个交易日，单位：百万元）】"]
    try:
        rows = stock_service.get_moneyflow_hsgt(limit=5)
        if rows:
            for r in rows:
                lines.append(
                    f"- {r.get('trade_date')}: 北向净流入={r.get('north_money')} "
                    f"沪股通={r.get('hgt')} 深股通={r.get('sgt')}"
                )
        else:
            lines.append("暂无北向资金数据")
    except Exception as exc:
        lines.append(f"北向资金获取失败：{exc}")
    return "\n".join(lines)


def _build_limit_ladder_section() -> str:
    """构建涨跌停天梯片段。"""
    lines = ["【涨跌停天梯】"]
    try:
        data = get_limit_up_ladder(top_n_concepts=10)
        if not data.get("ladder"):
            lines.append("暂无涨停数据")
            return "\n".join(lines)

        lines.append(f"交易日：{data.get('trade_date')}")

        # 热门概念
        concepts = data.get("concept_tags", [])[:8]
        if concepts:
            lines.append("热门涨停概念：" + ", ".join(
                f"{c.get('name')}({c.get('count')}只)" for c in concepts
            ))

        # 天梯（连板）
        for group in data["ladder"][:6]:
            stocks_str = ", ".join(
                f"{s.get('name')}({s.get('pct_chg'):+.1f}%)" for s in group.get("stocks", [])[:5]
            )
            lines.append(f"- {group.get('label')}：{stocks_str}")

        # 炸板
        opened = data.get("opened_limit", [])
        if opened:
            opened_str = ", ".join(s.get("name") for s in opened[:5])
            lines.append(f"- 炸板（{len(opened)}只）：{opened_str}")
    except Exception as exc:
        lines.append(f"涨跌停数据获取失败：{exc}")
    return "\n".join(lines)


def _build_hot_sector_section() -> str:
    """构建热门板块（行业+概念）资金流向片段。"""
    lines = ["【热门板块资金流向】"]

    # 行业板块 Top 5 净流入
    try:
        industry = stock_service.get_sector_moneyflow_rank(
            sector_type="industry", sort_by="net_amount", limit=5
        )
        if industry.get("sectors"):
            lines.append("行业板块净流入 Top 5：")
            for s in industry["sectors"][:5]:
                lines.append(
                    f"  - {s.get('name')}: 净流入={s.get('net_amount')}亿 "
                    f"涨跌幅={s.get('pct_change')}% 领涨={s.get('lead_stock')}"
                )
    except Exception as exc:
        lines.append(f"行业板块获取失败：{exc}")

    # 行业板块 Top 5 净流出
    try:
        industry_out = stock_service.get_sector_moneyflow_rank(
            sector_type="industry", sort_by="net_amount_asc", limit=5
        )
        if industry_out.get("sectors"):
            lines.append("行业板块净流出 Top 5：")
            for s in industry_out["sectors"][:5]:
                lines.append(
                    f"  - {s.get('name')}: 净流出={abs(s.get('net_amount', 0))}亿 "
                    f"涨跌幅={s.get('pct_change')}%"
                )
    except Exception:
        pass

    # 概念板块 Top 5
    try:
        concept = stock_service.get_sector_moneyflow_rank(
            sector_type="concept", sort_by="net_amount", limit=5
        )
        if concept.get("sectors"):
            lines.append("概念板块净流入 Top 5：")
            for s in concept["sectors"][:5]:
                lines.append(
                    f"  - {s.get('name')}: 净流入={s.get('net_amount')}亿 "
                    f"涨跌幅={s.get('pct_change')}% 领涨={s.get('lead_stock')}"
                )
    except Exception as exc:
        lines.append(f"概念板块获取失败：{exc}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Context 辅助函数：个股深度数据
# ---------------------------------------------------------------------------


def _build_portfolio_detail_section(portfolio_rows) -> str:
    """构建持仓股深度分析数据（含成本/盈亏、5天K线、4周周K、概念、资金流向）。"""
    lines = ["【用户持仓深度分析】"]
    for item in portfolio_rows:
        stock_lines = _build_single_portfolio_context(item)
        lines.append(stock_lines)
    return "\n".join(lines)


def _build_watchlist_brief_section(watchlist_rows) -> str:
    """构建自选股（非持仓）简要行情。"""
    lines = ["【用户自选股（非持仓，简要行情）】"]
    for item in watchlist_rows:
        try:
            quote = stock_service.get_stock_quote(item.code)
            basic_list = stock_service.get_daily_basic(item.code, limit=1)
            extra = ""
            if basic_list:
                b = basic_list[0]
                extra = f" PE={b.get('pe')} PB={b.get('pb')} 换手={b.get('turnover_rate')}%"
            lines.append(
                f"- {item.name}（{item.code}）: 现价={quote.price} 涨跌幅={quote.change_percent}%{extra}"
            )
        except Exception:
            lines.append(f"- {item.name}（{item.code}）: 行情获取失败")
    return "\n".join(lines)


def _build_single_portfolio_context(item) -> str:
    """为单只持仓股构建完整深度上下文（含持仓盈亏信息）。"""
    code = item.code
    name = item.name
    lines = [f"\n▶ {name}（{code}）【持仓】"]

    # 0. 持仓信息（成本、数量、盈亏百分比，不暴露具体金额）
    cost_price = float(item.cost_price) if item.cost_price is not None else None
    quantity = float(item.quantity) if item.quantity is not None else None
    is_margin = "是" if item.is_margin else "否"
    note = item.note or ""

    holding_parts = [f"  持仓信息: 成本价={cost_price} 融资={is_margin}"]
    if note:
        holding_parts[0] += f" 备注={note}"

    # 计算浮动盈亏百分比
    try:
        quote = stock_service.get_stock_quote(code)
        current_price = quote.price
        change_pct = quote.change_percent
        lines.append(f"  当日: 现价={current_price} 涨跌幅={change_pct}%")

        if cost_price and current_price:
            profit_pct = (current_price - cost_price) / cost_price * 100
            holding_parts.append(f"  盈亏: 收益率={profit_pct:.2f}%")
    except Exception:
        lines.append(f"  当日行情获取失败")

    lines.extend(holding_parts)

    # 1. 基本面
    try:
        basic_list = stock_service.get_daily_basic(code, limit=1)
        if basic_list:
            b = basic_list[0]
            lines.append(
                f"  基本面: PE={b.get('pe')} PE_TTM={b.get('pe_ttm')} PB={b.get('pb')} "
                f"换手率={b.get('turnover_rate')}% 量比={b.get('volume_ratio')} "
                f"总市值={b.get('total_mv')}万 流通市值={b.get('circ_mv')}万"
            )
    except Exception:
        pass

    # 2. 近 5 天日线 K 线
    try:
        daily_klines = stock_service.get_klines(code, period="D", limit=5)
        if daily_klines:
            lines.append("  近5天日K：")
            for k in daily_klines:
                vol_str = f" 成交量={k.volume}" if k.volume else ""
                amt_str = f" 成交额={k.amount}" if k.amount else ""
                lines.append(
                    f"    {k.trade_date}: 开={k.open} 高={k.high} 低={k.low} "
                    f"收={k.close}{vol_str}{amt_str}"
                )
    except Exception:
        pass

    # 3. 近 4 周周线 K 线
    try:
        weekly_klines = stock_service.get_klines(code, period="W", limit=4)
        if weekly_klines:
            lines.append("  近4周周K：")
            for k in weekly_klines:
                lines.append(
                    f"    {k.trade_date}: 开={k.open} 高={k.high} 低={k.low} 收={k.close}"
                )
    except Exception:
        pass

    # 4. 所属概念板块
    try:
        concepts = stock_service.get_stock_concepts(code)
        if concepts:
            concept_names = [c.get("concept_name") for c in concepts[:10]]
            lines.append(f"  所属概念: {', '.join(concept_names)}")
    except Exception:
        pass

    # 5. 资金流向（近 5 天大小单数据）
    try:
        moneyflow = stock_service.get_stock_moneyflow(code, limit=5)
        if moneyflow:
            lines.append("  近5天资金流向（万元）：")
            for mf in moneyflow:
                net_sm = _net(mf.get("buy_sm_amount"), mf.get("sell_sm_amount"))
                net_md = _net(mf.get("buy_md_amount"), mf.get("sell_md_amount"))
                net_lg = _net(mf.get("buy_lg_amount"), mf.get("sell_lg_amount"))
                net_elg = _net(mf.get("buy_elg_amount"), mf.get("sell_elg_amount"))
                net_total = mf.get("net_mf_amount")
                lines.append(
                    f"    {mf.get('trade_date')}: "
                    f"小单净={net_sm} 中单净={net_md} 大单净={net_lg} "
                    f"特大单净={net_elg} 总净流入={net_total}"
                )
    except Exception:
        pass

    # 6. 当天 15 分钟分时 K 线（走势结构：冲高回落/震荡/尾盘拉升等）
    try:
        intraday = stock_service.get_intraday_klines(code, period="15", limit=16)
        if intraday:
            lines.append("  当日15分钟K线走势：")
            for k in intraday:
                time_str = k.datetime[-8:-3] if hasattr(k, 'datetime') else ""  # HH:MM
                lines.append(
                    f"    {time_str}: 开={k.open:.2f} 高={k.high:.2f} "
                    f"低={k.low:.2f} 收={k.close:.2f}"
                )
    except Exception:
        pass

    return "\n".join(lines)


def _net(buy, sell) -> str:
    """计算净额并格式化。"""
    if buy is None or sell is None:
        return "N/A"
    return f"{buy - sell:.1f}"


async def _generate_review_content(user: UserModel, context: str, level: str = "standard") -> dict:
    """调用 AI 生成复盘内容，返回 {"summary": ..., "content": ...}。"""
    today = _cn_today()
    cn_now = _cn_now()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekday_names[today.weekday()]
    prompt = (
        f"请为以下用户生成收盘复盘报告。\n"
        f"当前时间：{cn_now.strftime('%Y-%m-%d %H:%M')} {weekday_str}（北京时间）\n"
        f"用户：{user.name or user.email}\n"
        f"复盘层级：{level}\n"
        f"注意：报告标题和正文中使用数据对应的最新交易日日期（参考数据中已标注），而不是今天的日期。\n"
        f"我已经提供了完整的数据：\n"
        f"- 通用市场数据：大盘走势、国际市场、北向资金、涨跌停天梯、热门板块\n"
        f"- 用户持仓股（重点）：每只持仓的成本价、数量、浮动盈亏、5天日K、4周周K、所属概念、大小单资金流向\n"
        f"- 用户自选股（非持仓）：简要行情\n"
        f"请以持仓股为核心做深度分析，自选股简要提及即可。\n"
        f"特别注意：\n"
        f"- 如果某持仓股亏损较多或当日跌幅大，在分析中自然带一句安慰，不要刻意单独写情绪关怀标题；\n"
        f"- 如果盈利不错或涨幅好，顺带提醒下风险就行。\n"
        f"整体语调自然亲切，像老朋友聊天。"
    )
    return await ai_service.analyze_json(
        prompt=prompt, role="daily_review", context=context, schema=ai_service.AiReportOutput
    )


def _run_async(coro):
    """在同步上下文中运行异步协程，兼容 APScheduler 线程环境。"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # 当前线程可能已有 event loop（如测试/某些运行时），新建一个运行
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------


async def generate_daily_review_for_user(
    db: Session, user_id: int, report_date: date, level: str = "standard",
    force: bool = False, market_context: str | None = None,
) -> DailyReview:
    """为单个用户生成指定日期、指定层级的复盘（异步）。

    Args:
        force: 为 True 时强制重新生成，即使状态为 running 也会覆盖。
        market_context: 预构建的通用市场数据，批量生成时传入以复用。
    """
    review = _get_or_create_review(db, user_id, report_date, level=level)
    if not force and review.status == "running":
        logger.info(f"[DailyReview] 用户 {user_id} {report_date} {level} 复盘正在生成中，跳过")
        return review

    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_deleted == 0)
        .first()
    )
    if user is None:
        review.status = "failed"
        review.error_message = "用户不存在"
        db.commit()
        return review

    review.status = "running"
    db.commit()

    try:
        context = await _build_watchlist_context(db, user, market_context=market_context)
        result = await _generate_review_content(user, context, level=level)
        review.summary = result.get("summary")
        review.content = result.get("content")
        review.status = "success"
        review.error_message = None
    except Exception as exc:
        review.status = "failed"
        review.error_message = str(exc)[:2000]
        logger.exception(f"[DailyReview] 为用户 {user_id} 生成 {level} 复盘失败")
    finally:
        db.commit()
        db.refresh(review)

    return review


def generate_daily_review_for_user_sync(
    db: Session, user_id: int, report_date: date, level: str = "standard", force: bool = False
) -> DailyReview:
    """为单个用户生成指定日期、指定层级的复盘（同步包装，供定时任务使用）。"""
    return _run_async(generate_daily_review_for_user(db, user_id, report_date, level=level, force=force))


async def _generate_one_user(
    user_id: int, report_date: date, level: str, semaphore: asyncio.Semaphore,
    market_context: str | None = None,
) -> tuple[int, bool]:
    """为一个用户生成复盘（带并发控制），使用独立 session。"""
    async with semaphore:
        db = SessionLocal()
        try:
            review = await generate_daily_review_for_user(
                db, user_id, report_date, level=level, market_context=market_context
            )
            return (user_id, review.status == "success")
        except Exception:
            logger.exception(f"[DailyReview] 批量生成时用户 {user_id} 失败")
            return (user_id, False)
        finally:
            db.close()


def generate_daily_reviews_for_all_members(
    report_date: date | None = None,
    level: str = "standard",
    skip_non_trading_day: bool = False,
    max_concurrent: int = MAX_CONCURRENT_REVIEWS,
) -> dict:
    """为所有生效会员生成指定日期、指定层级的复盘。

    Args:
        report_date: 复盘日期，默认今天
        level: 复盘层级，standard / deep
        skip_non_trading_day: 为 True 时，若 report_date 不是交易日则跳过不生成
        max_concurrent: 批量生成时的最大并发数
    """
    if report_date is None:
        report_date = _cn_today()

    db = SessionLocal()
    try:
        if skip_non_trading_day and not is_trading_day(db, report_date):
            latest = get_latest_trade_date(db)
            logger.info(
                f"[DailyReview] {report_date} 不是交易日（最新数据 {latest}），跳过批量生成"
            )
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": True,
                "reason": f"非交易日，最新数据 {latest}",
            }

        now = datetime.now(timezone.utc)
        memberships = (
            db.query(UserMembership)
            .filter(
                UserMembership.status == "active",
                UserMembership.expires_at > now,
                UserMembership.is_deleted == 0,
            )
            .all()
        )
        user_ids = list({m.user_id for m in memberships})

        # 过滤已删除用户
        active_user_ids = {
            u.id
            for u in db.query(UserModel.id).filter(
                UserModel.id.in_(user_ids),
                UserModel.is_deleted == 0,
            )
        }
        user_ids = [uid for uid in user_ids if uid in active_user_ids]

        # 跳过已成功或正在生成中的用户，避免重复调用 AI
        skip_statuses = ("success", "running")
        skip_user_ids = {
            r.user_id
            for r in db.query(DailyReview.user_id)
            .filter(
                DailyReview.report_date == report_date,
                DailyReview.level == level,
                DailyReview.status.in_(skip_statuses),
                DailyReview.is_deleted == 0,
            )
            .all()
        }
        eligible_user_ids = [uid for uid in user_ids if uid not in skip_user_ids]
        skipped_count = len(user_ids) - len(eligible_user_ids)
    finally:
        db.close()

    # 通用市场数据只构建一次，所有用户共享
    logger.info("[DailyReview] 构建通用市场上下文...")
    market_context = build_market_context()
    logger.info(f"[DailyReview] 通用市场上下文构建完成（{len(market_context)} 字符）")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_all():
        return await asyncio.gather(
            *[
                _generate_one_user(uid, report_date, level, semaphore, market_context=market_context)
                for uid in eligible_user_ids
            ]
        )

    results = _run_async(_run_all())
    success = sum(1 for _, ok in results if ok)
    failed = len(results) - success

    logger.info(
        f"[DailyReview] {report_date} {level} 批量生成完成："
        f"生效会员 {len(user_ids)}，已存在成功记录跳过 {skipped_count}，"
        f"实际生成 {len(eligible_user_ids)}，成功 {success}，失败 {failed}"
    )
    return {
        "total": len(user_ids),
        "skipped": skipped_count,
        "generated": len(eligible_user_ids),
        "success": success,
        "failed": failed,
    }


def generate_deep_reviews_for_all_members(
    report_date: date | None = None,
    skip_non_trading_day: bool = True,
    max_concurrent: int = MAX_CONCURRENT_REVIEWS,
) -> dict:
    """为所有生效会员生成深度复盘。"""
    return generate_daily_reviews_for_all_members(
        report_date=report_date,
        level="deep",
        skip_non_trading_day=skip_non_trading_day,
        max_concurrent=max_concurrent,
    )


async def generate_standard_review_for_user(
    db: Session, user_id: int, report_date: date
) -> DailyReview:
    """为积分用户手动生成标准复盘。

    调用前需由接口层完成积分扣减。
    """
    return await generate_daily_review_for_user(db, user_id, report_date, level="standard")


# ---------------------------------------------------------------------------
# 查询与重试
# ---------------------------------------------------------------------------


def get_user_reviews(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[DailyReview], int]:
    """查询指定用户的复盘列表（按日期倒序）。"""
    query = db.query(DailyReview).filter(
        DailyReview.user_id == user_id,
        DailyReview.is_deleted == 0,
    )
    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_review_detail(
    db: Session, review_id: int, user_id: int | None = None, level: str | None = None
) -> DailyReview | None:
    """获取复盘详情，普通用户需校验归属。"""
    query = db.query(DailyReview).filter(
        DailyReview.id == review_id,
        DailyReview.is_deleted == 0,
    )
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    if level is not None:
        query = query.filter(DailyReview.level == level)
    return query.first()


def get_admin_reviews(
    db: Session,
    user_id: int | None = None,
    report_date: date | None = None,
    status: str | None = None,
    level: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DailyReview], int]:
    """管理端复盘记录列表。"""
    query = db.query(DailyReview).filter(DailyReview.is_deleted == 0)
    if user_id is not None:
        query = query.filter(DailyReview.user_id == user_id)
    if report_date is not None:
        query = query.filter(DailyReview.report_date == report_date)
    if status is not None:
        query = query.filter(DailyReview.status == status)
    if level is not None:
        query = query.filter(DailyReview.level == level)

    total = query.count()
    items = (
        query.order_by(DailyReview.report_date.desc(), DailyReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_review_content(
    db: Session, review_id: int, content: str, summary: str | None = None
) -> DailyReview | None:
    """管理员手工编辑复盘内容。"""
    review = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.is_deleted == 0)
        .first()
    )
    if review is None:
        return None
    review.content = content
    if summary is not None:
        review.summary = summary
    review.status = "success"
    review.error_message = None
    db.commit()
    db.refresh(review)
    return review


async def retry_failed_reviews(
    db: Session, report_date: date | None = None, level: str | None = None
) -> dict:
    """重试指定日期、指定层级的失败复盘。"""
    if report_date is None:
        report_date = _cn_today()

    query = db.query(DailyReview).filter(
        DailyReview.report_date == report_date,
        DailyReview.status == "failed",
        DailyReview.is_deleted == 0,
    )
    if level is not None:
        query = query.filter(DailyReview.level == level)

    failed_reviews = query.all()

    # 通用市场数据只构建一次
    market_context = build_market_context()

    success = 0
    still_failed = 0
    for review in failed_reviews:
        try:
            result = await generate_daily_review_for_user(
                db, review.user_id, report_date, level=review.level,
                force=True, market_context=market_context,
            )
            if result.status == "success":
                success += 1
            else:
                still_failed += 1
        except Exception:
            still_failed += 1
            logger.exception(f"[DailyReview] 重试复盘 {review.id} 失败")

    return {"total": len(failed_reviews), "success": success, "still_failed": still_failed}
