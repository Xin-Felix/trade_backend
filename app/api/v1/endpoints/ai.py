"""AI 中心接口。

提供 AI 市场分析、个股分析、新闻解读、晨报生成等功能。
底层使用 DeepSeek 模型，通过统一 AI 服务层调用。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_current_user, require_feature
from app.schemas.user import User
from app.services import ai_service

router = APIRouter()


class ChatRequest(BaseModel):
    """AI 对话请求"""
    prompt: str
    role: str = "market_analyst"  # market_analyst / morning_brief / stock_analyst / news_interpreter / global_impact
    context: Optional[str] = ""
    stream: bool = False


class AnalyzeStockRequest(BaseModel):
    """个股分析请求"""
    code: str
    question: Optional[str] = ""


# ============================================================
# 通用 AI 对话
# ============================================================


@router.post("/chat", response_model=None)
async def ai_chat(
    body: ChatRequest,
    user: User = Depends(require_feature("ai_chat", consume=True)),
):
    """AI 对话（支持流式和非流式）。

    角色预设：
    - market_analyst: 市场分析师（默认）
    - morning_brief: AI 晨报编辑
    - stock_analyst: 个股分析师
    - news_interpreter: 新闻解读
    - global_impact: 国际市场影响分析
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    if body.stream:
        generator = await ai_service.analyze_stream(
            prompt=body.prompt,
            role=body.role,
            context=body.context or "",
        )
        return StreamingResponse(
            _wrap_sse(generator),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        try:
            result = await ai_service.analyze(
                prompt=body.prompt,
                role=body.role,
                context=body.context or "",
            )
            return {"success": True, "data": {"content": result}}
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 调用失败: {e}")


# ============================================================
# 专项分析
# ============================================================


@router.post("/analyze/stock")
async def analyze_stock(
    body: AnalyzeStockRequest,
    user: User = Depends(require_feature("ai_stock_analyze", consume=True)),
) -> dict:
    """AI 个股分析。自动拉取该股票的行情和基本面数据作为上下文。"""
    from app.services.stock_service import get_stock_quote, get_daily_basic

    # 获取股票数据作为 context
    context_parts = []
    try:
        quote = get_stock_quote(body.code)
        if quote:
            context_parts.append(f"实时行情: {quote}")
    except Exception:
        pass

    try:
        basic = get_daily_basic(body.code)
        if basic:
            context_parts.append(f"基本面指标: {basic}")
    except Exception:
        pass

    context = "\n".join(context_parts) if context_parts else ""
    question = body.question or f"请分析 {body.code} 的当前走势和投资价值"

    try:
        result = await ai_service.analyze(
            prompt=question,
            role="stock_analyst",
            context=context,
        )
        return {"success": True, "data": {"code": body.code, "content": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.post("/analyze/global-impact")
async def analyze_global_impact(
    user: User = Depends(require_feature("ai_global_impact", consume=True)),
) -> dict:
    """分析当前国际市场对A股的影响。自动获取全球市场数据作为上下文。"""
    from app.services.global_market_service import get_global_market_overview

    # 获取国际市场数据
    try:
        global_data = get_global_market_overview()
        context = _format_global_context(global_data)
    except Exception:
        context = ""

    prompt = "根据当前国际市场数据，分析对今日A股市场的影响，给出开盘预判和关注建议。"

    try:
        result = await ai_service.analyze(
            prompt=prompt,
            role="global_impact",
            context=context,
        )
        return {"success": True, "data": {"content": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.get("/roles")
async def list_ai_roles(
    user: User = Depends(get_current_user),
) -> dict:
    """获取可用的 AI 角色列表。"""
    roles = [
        {"key": "market_analyst", "name": "市场分析师", "description": "分析大盘走势和市场动态"},
        {"key": "morning_brief", "name": "AI 晨报", "description": "生成每日市场晨报摘要"},
        {"key": "stock_analyst", "name": "个股分析师", "description": "深度分析个股技术面和基本面"},
        {"key": "news_interpreter", "name": "新闻解读", "description": "解读财经新闻对市场的影响"},
        {"key": "global_impact", "name": "国际市场分析", "description": "分析全球市场变动对A股的影响"},
    ]
    return {"success": True, "data": roles}


# ============================================================
# 辅助
# ============================================================


async def _wrap_sse(generator):
    """将 async generator 包装为 SSE 格式。"""
    async for chunk in generator:
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"


def _format_global_context(data: dict) -> str:
    """将国际市场数据格式化为 AI 可读的文本。"""
    parts = []

    if data.get("indices"):
        parts.append("全球主要指数：")
        for item in data["indices"]:
            sign = "+" if item["change_percent"] >= 0 else ""
            parts.append(f"  {item['name']}: {item['price']} ({sign}{item['change_percent']}%)")

    if data.get("commodities"):
        parts.append("\n商品期货：")
        for item in data["commodities"]:
            sign = "+" if item["change_percent"] >= 0 else ""
            parts.append(f"  {item['name']}: {item['price']} {item.get('unit', '')} ({sign}{item['change_percent']}%)")

    if data.get("forex"):
        parts.append("\n汇率：")
        for item in data["forex"]:
            parts.append(f"  {item['name']}: {item['price']}")

    return "\n".join(parts)
