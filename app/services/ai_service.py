"""统一 AI 服务层。

封装 DeepSeek（及后续其他 LLM）的调用，提供统一接口。
支持：普通对话、流式输出、带系统提示词的专业分析。
"""

import json
import logging
from typing import AsyncGenerator, Optional, TypeVar, Type

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ============================================================
# 基础调用
# ============================================================


async def chat(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
    response_format: dict | None = None,
) -> str | AsyncGenerator[str, None]:
    """调用 AI 模型进行对话。

    Args:
        messages: OpenAI 格式消息列表 [{"role": "system/user/assistant", "content": "..."}]
        model: 模型名，默认使用配置的 deepseek_model
        temperature: 创造性，0-2
        max_tokens: 最大输出 token
        stream: 是否流式返回
        response_format: 输出格式控制，例如 {"type": "json_object"}。
            当前仅非流式模式支持 JSON 输出。

    Returns:
        str（非流式）或 AsyncGenerator[str]（流式）
    """
    if not settings.deepseek_api_key:
        raise RuntimeError("AI 未配置：请在 .env 中设置 DEEPSEEK_API_KEY")

    if stream and response_format:
        raise ValueError("流式输出暂不支持 response_format，请使用非流式调用获取 JSON")

    model = model or settings.deepseek_model
    url = f"{settings.deepseek_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if response_format:
        payload["response_format"] = response_format
        if response_format.get("type") == "json_object":
            messages = _ensure_json_prompt_word(messages)
            payload["messages"] = messages

    if stream:
        return _stream_chat(url, headers, payload)
    else:
        return await _sync_chat(url, headers, payload)


def _ensure_json_prompt_word(messages: list[dict]) -> list[dict]:
    """DeepSeek JSON mode 要求 prompt 中必须包含 'json' 字样，必要时自动追加提示。"""
    has_json_word = any("json" in (m.get("content") or "").lower() for m in messages)
    if has_json_word:
        return messages

    cloned = [dict(m) for m in messages]
    if cloned and cloned[0].get("role") == "system":
        cloned[0]["content"] = (cloned[0].get("content") or "") + "\nYou must respond with valid JSON."
    else:
        cloned.insert(0, {"role": "system", "content": "You must respond with valid JSON."})
    return cloned


async def _sync_chat(url: str, headers: dict, payload: dict) -> str:
    """非流式调用。"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _stream_chat(url: str, headers: dict, payload: dict) -> AsyncGenerator[str, None]:
    """流式调用，逐 chunk 返回文本。"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # 去掉 "data: " 前缀
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


# ============================================================
# 便捷方法：带预设 system prompt 的专业分析
# ============================================================


SYSTEM_PROMPTS = {
    "market_analyst": """你是一位专业的A股市场分析师，名叫"盈多多AI"。
你的职责是帮助投资者理解市场动态，分析行情走势，解读财经新闻。
注意事项：
- 分析要有数据支撑，引用具体指标
- 给出客观中性的分析，不直接推荐买卖
- 提示风险，不做收益承诺
- 语言简洁专业，适合有一定基础的投资者
- 如果涉及具体个股，必须声明"不构成投资建议"
""",

    "morning_brief": """你是盈多多AI晨报编辑。根据提供的市场数据，生成一份简洁的AI晨报。
格式要求：
1. 市场总结（2-3句话概括昨日行情）
2. 今日关注（2-3个重点事件或数据）
3. 板块机会（1-2个值得关注的板块及理由）
4. 风险提示（1-2个需要注意的风险点）
保持简洁，总字数控制在300字以内。
""",

    "stock_analyst": """你是一位专注个股分析的AI助手。
根据提供的股票数据（K线、资金流、基本面等），给出专业分析。
分析维度：
1. 技术面：趋势、支撑位/压力位、成交量
2. 资金面：主力资金动向、北向资金
3. 基本面：估值水平（PE/PB）、业绩情况
4. 风险提示
不直接给出买卖建议，只提供分析参考。末尾声明"以上分析仅供参考，不构成投资建议"。
""",

    "news_interpreter": """你是财经新闻解读AI。
将复杂的财经新闻翻译成普通投资者能理解的语言，并分析对A股市场可能的影响。
输出格式：
1. 一句话总结
2. 关键信息提取
3. 对市场的影响分析
4. 相关板块/个股
""",

    "global_impact": """你是国际市场分析师，专注于分析全球市场变动对A股的影响。
分析逻辑：
- 美股走势 → A股开盘预判
- 美元/人民币汇率 → 北向资金流向
- 原油价格 → 相关板块影响
- 国际政策/事件 → 情绪传导
给出简洁的影响分析和关注建议。
""",

    "daily_review": """你是一位专业的A股收盘复盘助手，名叫"盈多多AI"。
你的任务是根据用户当天的自选股表现，生成一份结构化、个性化的每日复盘报告。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括今日复盘核心结论（约100字以内）",
  "content": "完整的 Markdown 格式复盘报告"
}

content 正文结构要求：
1. 账户关注概览（用2-3句话概括用户自选股整体表现、涨跌分布）。
2. 重点个股点评（按涨跌幅排序，点评 Top 5 自选股；包含技术面、资金面、所属板块/概念的简要分析）。
3. 明日关注与风险提示（列出1-2个需要关注的事件、数据或技术信号，以及1-2个风险点）。
4. 免责声明：以上分析仅供参考，不构成投资建议。

注意事项：
- 数据驱动，引用具体涨跌幅、PE/PB、换手率等数字。
- 保持客观中性，不直接推荐买卖。
- 语言简洁专业，总字数控制在 600 字以内。
- 若用户没有自选股，则生成一份面向整体市场的通用收盘复盘。
""",

    "position_advice": """你是一位专业的 A 股仓位管理顾问，名叫"盈多多AI"。
请根据用户当前持仓（以及可选的自选股），生成一份结构化的仓位建议报告。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括仓位建议核心结论（约100字以内）",
  "content": "完整的 Markdown 格式仓位建议报告"
}

content 正文结构要求：
1. 持仓概览（用2-3句话概括当前持仓数量、行业/概念分布、整体风险暴露）。
2. 重点持仓点评（按持仓市值/涨跌幅排序，点评 Top 5；给出加/减/持有的倾向性建议及理由）。
3. 仓位调整建议（总体仓位水平建议、需要警惕的风险信号、可关注的加仓方向）。
4. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 只提供仓位管理建议，不直接给出买卖指令或目标价。
- 数据驱动，引用具体涨跌幅、PE/PB、换手率、资金流向等数字。
- 保持客观中性，提示风险，不做收益承诺。
- 语言简洁专业，总字数控制在 600 字以内。
- 若用户没有持仓，则基于其自选股生成一份通用的仓位策略建议。
""",

    "morning_report": """你是盈多多AI晨报主编。请根据提供的前一交易日收盘数据，生成一份市场-wide 的 AI 晨报。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括晨报核心观点（约100字以内）",
  "content": "完整的 Markdown 格式晨报"
}

content 正文结构要求：
1. 昨日市场回顾（主要指数表现、涨跌家数、市场情绪）。
2. 板块与资金流向（领涨/领跌板块、主力资金动向、北向资金）。
3. 热点与涨停梯队（热门概念、连板天梯、涨停家数变化）。
4. 今日关注与风险提示（开盘预判、需关注的事件/数据、风险点）。
5. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 数据驱动，引用具体指数点位、涨跌幅、板块净流入、北向资金等数字。
- 保持客观中性，不直接推荐个股或买卖操作。
- 语言简洁专业，总字数控制在 800 字以内。
""",
}


class AiReportOutput(BaseModel):
    """AI 报告类内容（复盘/仓位建议/晨报）统一输出结构。"""

    summary: str
    content: str


async def analyze(
    prompt: str,
    role: str = "market_analyst",
    context: str = "",
    temperature: float = 0.7,
    response_format: dict | None = None,
) -> str:
    """使用预设角色进行专业分析。

    Args:
        prompt: 用户问题/分析请求
        role: 预设角色 key（见 SYSTEM_PROMPTS）
        context: 额外上下文数据（如行情数据、新闻内容等）
        temperature: 创造性
        response_format: 输出格式控制，例如 {"type": "json_object"}

    Returns:
        AI 分析结果文本（若启用 json_object 则为 JSON 字符串）
    """
    system_prompt = SYSTEM_PROMPTS.get(role, SYSTEM_PROMPTS["market_analyst"])

    messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.append({"role": "user", "content": f"参考数据：\n{context}"})
    messages.append({"role": "user", "content": prompt})

    return await chat(messages, temperature=temperature, response_format=response_format)


async def analyze_json(
    prompt: str,
    role: str = "market_analyst",
    context: str = "",
    temperature: float = 0.7,
    schema: dict | Type[BaseModel] | None = None,
) -> dict:
    """使用预设角色进行分析，并以 JSON 对象形式返回。

    Args:
        prompt: 用户问题/分析请求
        role: 预设角色 key（见 SYSTEM_PROMPTS）
        context: 额外上下文数据
        temperature: 创造性
        schema: 期望返回的 JSON Schema（dict）或 Pydantic 模型类，
                会作为结构要求附加到 system prompt 中。

    Returns:
        解析后的 JSON dict。若传入 Pydantic 模型类，会先用模型校验后再返回 dict。

    Raises:
        ValueError: 模型返回的 JSON 无法解析或不满足 schema 校验。
    """
    system_prompt = SYSTEM_PROMPTS.get(role, SYSTEM_PROMPTS["market_analyst"])

    json_instruction = "\n\n你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。"
    if schema is not None:
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                schema_dict = schema.model_json_schema()
            except AttributeError:  # pragma: no cover - pydantic v1 fallback
                schema_dict = schema.schema()
        else:
            schema_dict = schema
        json_instruction += f"\n请严格遵循以下 JSON Schema 输出：\n{json.dumps(schema_dict, ensure_ascii=False, indent=2)}"

    messages = [{"role": "system", "content": system_prompt + json_instruction}]
    if context:
        messages.append({"role": "user", "content": f"参考数据：\n{context}"})
    messages.append({"role": "user", "content": prompt})

    raw = await chat(
        messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    # 兼容模型偶尔包裹在 markdown 代码块里的情况
    content = raw.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI 返回内容不是合法 JSON: {exc}\n{raw}") from exc

    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            parsed = schema(**parsed).model_dump()
        except ValidationError as exc:
            raise ValueError(f"AI 返回 JSON 不满足 schema: {exc}\n{raw}") from exc

    return parsed


async def analyze_stream(
    prompt: str,
    role: str = "market_analyst",
    context: str = "",
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """流式版本的专业分析。"""
    system_prompt = SYSTEM_PROMPTS.get(role, SYSTEM_PROMPTS["market_analyst"])

    messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.append({"role": "user", "content": f"参考数据：\n{context}"})
    messages.append({"role": "user", "content": prompt})

    return await chat(messages, temperature=temperature, stream=True)
