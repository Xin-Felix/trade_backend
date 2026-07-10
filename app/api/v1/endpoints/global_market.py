"""国际市场数据接口。

提供全球主要指数、商品期货、汇率的实时行情数据。
用于 iOS 首页"国际市场"模块和后续 AI 分析对国内市场影响。
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.schemas.user import User
from app.services import global_market_service

router = APIRouter()


@router.get("/overview")
async def global_market_overview(
    user: User = Depends(get_current_user),
) -> dict:
    """获取国际市场概览（指数 + 商品 + 汇率），一次拿全。

    返回数据结构：
    - indices: 全球主要股票指数（道琼斯、标普、纳斯达克、恒生、日经等）
    - commodities: 商品期货（黄金、白银、WTI原油、布伦特原油）
    - forex: 汇率（美元指数、美元/人民币、欧元/美元、美元/日元）
    """
    data = global_market_service.get_global_market_overview()
    return {"success": True, "data": data}


@router.get("/indices")
async def global_indices(
    user: User = Depends(get_current_user),
) -> dict:
    """获取全球主要股票指数实时行情。

    包括：道琼斯、标普500、纳斯达克、恒生指数、恒生科技、
    国企指数、日经225、韩国综合、富时100、德国DAX
    """
    data = global_market_service.get_global_indices()
    return {"success": True, "data": data}


@router.get("/commodities")
async def global_commodities(
    user: User = Depends(get_current_user),
) -> dict:
    """获取主要商品期货和汇率数据。

    商品：伦敦金、伦敦银、WTI原油、布伦特原油
    汇率：美元指数、美元/人民币、欧元/美元、美元/日元
    """
    data = global_market_service.get_commodities_and_forex()
    return {"success": True, "data": data}


@router.get("/available")
async def available_symbols(
    user: User = Depends(get_current_user),
) -> dict:
    """获取可用的国际市场标的列表（代码 + 名称 + 分类）。"""
    indices = [
        {"code": code, "name": info["name"], "market": info["market"], "type": "index"}
        for code, info in global_market_service.GLOBAL_INDICES.items()
    ]
    commodities = [
        {"code": code, "name": info["name"], "category": info["category"], "unit": info["unit"], "type": "commodity"}
        for code, info in global_market_service.GLOBAL_COMMODITIES.items()
    ]
    return {
        "success": True,
        "data": {
            "indices": indices,
            "commodities": commodities,
        },
    }
