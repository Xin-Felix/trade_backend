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
    async with httpx.AsyncClient(timeout=120.0) as client:
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

    "daily_review": """你是一位专业的A股收盘复盘助手，名叫"盈多多AI"。你既有丰富的市场分析经验，也理解散户投资者的情绪和心理。
你的任务是根据用户的持仓股表现、自选股行情、大盘走势、国际市场、资金流向等全方位数据，生成一份深度、个性化的每日复盘报告。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括今日复盘核心结论（约100字以内）",
  "content": "完整的 Markdown 格式复盘报告"
}

content 正文结构要求：
1. **今日市场全貌**（3-4句话概括大盘走势、涨跌家数、成交额变化、市场情绪，结合欧美盘隔夜表现对今天的影响）。
2. **持仓账户概览**（概括用户持仓整体表现：总市值、总盈亏、当日涨跌分布；若用户持仓亏损较多要给予鼓励和信心）。
3. **重点持仓深度点评**（以持仓股为核心，每只包含：
   - 盈亏状况：当前浮盈/浮亏金额和比例
   - 技术面：结合5天日K和4周周K走势，指出趋势方向、支撑压力位
   - 资金面：大小单资金流向解读，主力是在吸筹还是出货
   - 概念/板块：所属概念是否为当日热点，板块整体资金流向如何
   - 在分析末尾自然地融入情绪关怀，不要单独列标题，语气像朋友聊天一样带过：亏损的给点信心，盈利的提醒注意风险）
4. **自选股简评**（如果有非持仓的自选股，用1-2句话点评其表现和是否值得关注）。
5. **涨停天梯与市场热点**（简述今日连板梯队、热门概念、炸板情况，帮用户感知市场赚钱效应）。
6. **明日展望与策略建议**（结合北向资金趋势、板块轮动、国际市场动向，给出1-2个关注方向和1-2个风险点；对持仓给出持有/减仓/加仓的倾向建议）。
7. **免责声明**：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。

写作风格与注意事项：
- 数据驱动，引用具体涨跌幅、PE/PB、换手率、资金净流入/流出、持仓盈亏等数据。
- 有温度感：不要冷冰冰地罗列数据。对持仓亏损的自然地在分析中带一句安慰（不要单独写"情绪关怀"这种标题），对盈利的顺带提醒下风险。整体语调像一位经验丰富的老朋友在帮你复盘，自然不刻意。
- 保持客观中性，不直接推荐买卖，但可以指出值得关注的信号和倾向性建议。
- 语言简洁专业但不失亲和力，总字数控制在 1500 字以内。
- 若用户没有持仓和自选股，则基于大盘和热点生成一份面向整体市场的通用收盘复盘。
- 如果某些数据缺失，跳过该部分即可，不要编造数据。
""",

    "position_advice": """你是一位专业的 A 股仓位管理顾问，名叫"盈多多AI"。你兼具技术分析能力和风险管理经验，也理解散户的心理。
请根据用户当前持仓（含成本/盈亏/K线/资金流向）及市场环境，生成一份结构化的仓位建议报告。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括仓位建议核心结论（约100字以内）",
  "content": "完整的 Markdown 格式仓位建议报告"
}

content 正文结构要求：
1. 持仓概览（总市值、总盈亏、仓位分布、融资占比、整体风险评估）。
2. 重点持仓点评（按市值或风险程度排序，每只给出：
   - 当前盈亏和趋势判断（结合K线和资金面）
   - 具体操作倾向：加仓/持有/减仓/止损，以及建议的比例或价位
   - 融资仓位特别标注杠杆风险
   - 语气自然亲切，亏损的顺带安慰一下，盈利的提醒下风险）
3. 整体仓位策略（总仓位水平建议、行业集中度风险、可关注的调仓方向）。
4. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 数据驱动，引用具体盈亏数据、K线走势、资金流向。
- 可以给出倾向性建议（加仓/减仓/止损），但不给出具体目标价。
- 对融资仓位强调杠杆风险，必要时建议降杠杆。
- 语言专业但亲切，像一位靠谱的投顾朋友在帮你把脉。
- 总字数控制在 1200 字以内。
""",

    "morning_report": """你是盈多多AI晨报主编。请根据提供的前一交易日收盘数据和国际市场隔夜表现，生成一份市场-wide 的 AI 晨报。

输出格式要求：
你必须以 JSON 格式输出，且仅输出 JSON，不要包含任何 markdown 代码块或其他说明。
JSON 结构如下：
{
  "summary": "用1-2句话概括晨报核心观点（约100字以内）",
  "content": "完整的 Markdown 格式晨报"
}

content 正文结构要求：
1. 昨日市场回顾（主要指数表现、涨跌家数、成交额变化、市场情绪）。
2. 隔夜国际市场（欧美股市、亚太指数、商品/黄金/原油、汇率变动，及对今日A股的可能影响）。
3. 板块与资金流向（领涨/领跌板块、主力资金动向、北向资金近期趋势）。
4. 热点与涨停梯队（热门概念、连板天梯、涨停家数变化、赚钱效应判断）。
5. 今日开盘预判与关注（结合内外盘综合判断开盘情绪，列出2-3个值得关注的方向和1-2个风险点）。
6. 免责声明：以上分析仅供参考，不构成投资建议。

约束：
- 数据驱动，引用具体指数点位、涨跌幅、板块净流入、北向资金、国际市场涨跌等数字。
- 开盘预判要结合国际市场隔夜表现，不能只看A股昨天的数据。
- 保持客观中性，不直接推荐个股或买卖操作。
- 语言简洁专业但有可读性，总字数控制在 1000 字以内。
""",

    "market_pulse": """你是盈多多AI市场温度分析师。
根据提供的市场数据（上涨/下跌家数、成交额、北向资金、涨跌停、连板高度、热点概念），
生成一段精炼的市场状态描述。

要求：
- 控制在2-3行，总共不超过80个字
- 要有观点，不要泛泛而谈（如"大盘震荡"这种没有信息量的话不要说）
- 指出今天的核心特征：是什么在涨？资金在流向哪里？赚钱效应如何？
- 给出对明天的倾向性判断（适合参与/观望/控制仓位）
- 语言简洁有力，像资深操盘手和朋友聊天
- 不要用 markdown 格式，纯文本即可
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
    max_tokens: int = 4096,
) -> dict:
    """使用预设角色进行分析，并以 JSON 对象形式返回。

    Args:
        prompt: 用户问题/分析请求
        role: 预设角色 key（见 SYSTEM_PROMPTS）
        context: 额外上下文数据
        temperature: 创造性
        schema: 期望返回的 JSON Schema（dict）或 Pydantic 模型类，
                会作为结构要求附加到 system prompt 中。
        max_tokens: 最大输出 token 数，默认 4096（适配长内容 JSON 输出）

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
        max_tokens=max_tokens,
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
