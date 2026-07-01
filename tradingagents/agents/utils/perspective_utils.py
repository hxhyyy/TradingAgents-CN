"""
分析视角工具：价值分析 vs 趋势分析

与「选择哪些分析师」正交：分析师负责收集信息，视角决定如何解读与下结论。
"""

from __future__ import annotations

from typing import Literal

AnalysisPerspective = Literal["value", "trend"]

_VALID: frozenset[str] = frozenset({"value", "trend"})

_ALIASES: dict[str, AnalysisPerspective] = {
    "value": "value",
    "trend": "trend",
    "价值": "value",
    "价值分析": "value",
    "价值投资": "value",
    "长线": "value",
    "长线投资": "value",
    "价值长线": "value",
    "趋势": "trend",
    "趋势分析": "trend",
    "趋势投资": "trend",
    "短线": "trend",
    "短线趋势": "trend",
    "技术面": "trend",
}


def normalize_analysis_perspective(raw: object | None, default: AnalysisPerspective = "value") -> AnalysisPerspective:
    """将 API/前端输入规范为 value 或 trend。"""
    if raw is None:
        return default
    key = str(raw).strip()
    if not key:
        return default
    lowered = key.lower()
    if lowered in _VALID:
        return lowered  # type: ignore[return-value]
    if key in _ALIASES:
        return _ALIASES[key]
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    return default


def get_analysis_perspective() -> AnalysisPerspective:
    """从全局 Toolkit 配置读取当前分析视角。"""
    try:
        from tradingagents.agents.utils.agent_utils import Toolkit

        raw = Toolkit._config.get("analysis_perspective", "value")
    except Exception:
        raw = "value"
    return normalize_analysis_perspective(raw)


def get_perspective_label(perspective: AnalysisPerspective | None = None) -> str:
    p = perspective or get_analysis_perspective()
    return "价值分析" if p == "value" else "趋势分析"


def build_perspective_banner() -> str:
    """注入各决策节点的视角声明（置于 prompt 前部）。"""
    label = get_perspective_label()
    p = get_analysis_perspective()
    if p == "value":
        return f"""**本次分析视角：{label}（长期价值投资框架）**
用户已选择价值分析视角。你的结论必须服务于「长期内在价值与估值修复」，而非短线交易纪律。
分析师团队由用户自行勾选；未提供的报告章节（如技术面为空）不得编造，应明确说明信息不足。"""
    return f"""**本次分析视角：{label}（短线趋势交易框架）**
用户已选择趋势分析视角。你的结论必须服务于「趋势跟随、仓位管理与交易纪律」，而非长期价值投资叙事。
分析师团队由用户自行勾选；未提供的报告章节（如基本面为空）不得编造，应明确说明信息不足。"""


def build_perspective_guidance() -> str:
    """决策宪法：研究经理 / 风险主席 / 交易员必须遵守。"""
    p = get_analysis_perspective()
    if p == "value":
        return """**价值分析决策宪法**（优先级高于技术面短期信号）：

1. **核心依据**：基本面估值（PE/PB/DCF/mNAV/合理价值区间）、盈利质量、商业模式、长期竞争优势、资本结构。
2. **新闻与事件**：评估对长期内在价值的影响；短期价格波动本身不构成卖出理由。
3. **技术面角色（若有市场报告）**：仅作辅助——参考支撑/阻力、是否严重偏离均值；**不得**仅因均线空头、MACD 死叉、RSI 超卖就给出减持/卖出。
4. **深跌 + 估值折价**：必须区分「基本面永久性恶化」与「情绪/流动性错杀」；后者不应默认清仓。
5. **时间维度**：默认 6–24 个月；目标价应锚定基本面合理价值，而非近期低点/高点 extrapolation。
6. **禁止表述**：「严禁现价追多」「等突破 MA20 再买」「硬止损清仓」等纯趋势交易话术（除非基本面明确恶化需风控）。
7. **评级逻辑**：
   - 显著低估 + 基本面未恶化 → 倾向买入/增持/持有，而非因跌势减持；
   - 估值合理 + 逻辑完好 → 持有；
   - 基本面恶化或估值显著高估 → 减持/卖出。
8. **证据冲突**：当基本面与技术面矛盾时，**以基本面为准**并在论点中说明技术面仅作参考。"""

    return """**趋势分析决策宪法**（优先级高于长期估值叙事）：

1. **核心依据**：价格趋势、均线系统、MACD/RSI/布林带、量价关系、关键支撑/阻力。
2. **基本面角色（若有基本面报告）**：仅作背景与风险上下文，**不得**因「估值便宜」就忽视明确下跌趋势。
3. **交易纪律**：不猜底；反转需价格/量能确认；必须给出具体入场条件、止损位、目标位。
4. **时间维度**：默认 1 周–3 个月；所有价位建议须可执行、可验证。
5. **评级逻辑**：
   - 趋势向上 + 量价配合 → 买入/增持；
   - 震荡无方向 → 持有/观望；
   - 趋势向下或关键位跌破 → 减持/卖出；空仓者等待确认信号。
6. **证据冲突**：当技术面与基本面矛盾时，**以趋势与风控为准**，并说明估值观点不作为短线依据。
7. **禁止表述**：「长期持有等待估值修复」「越跌越买」等纯价值投资话术（除非趋势已确认反转）。"""


def build_perspective_output_schema() -> str:
    """研究经理 / 风险主席必须输出的结构。"""
    p = get_analysis_perspective()
    if p == "value":
        return """**必须输出的结构**：
1. **评级**：五档之一（买入/增持/持有/减持/卖出）
2. **执行摘要**（价值视角）须包含：
   - 估值结论（高估/合理/低估）与关键依据
   - 12个月**合理价值区间**与**核心目标价**（须为具体数值，与股票计价货币一致）
   - 如需给出「下行保护线 / 残余权益锚 / 清算价值 / 极端熊市底线」，必须**单独标注**，严禁将其写成目标价
   - 建议持有周期（如 6–12 个月）
   - 加仓条件（基于基本面或估值修复，非纯技术突破）
   - 减仓/卖出条件（基于基本面恶化或估值过高）
   - 须跟踪的关键风险（财报、行业、杠杆、政策等）
3. **投资论点**：详细推理；引用辩论与报告中的证据；说明如何处理与技术面/情绪的冲突

**价值视角特别约束**：
- 目标价必须代表「在当前基本面与合理假设下，未来约 12 个月的公允价值中枢」。
- 不得把残余净资产、清算价值、悲观情景底线、止损位、技术支撑位写成目标价。
- 若公司属于高杠杆资产载体（如 BTC 持仓公司、强周期资源股、控股平台），必须明确区分：
  1. 普通股残余权益/下行保护线
  2. 基于经营与资产的公允价值区间
  3. 牛市期权价值/乐观情景上沿
- 最终“核心目标价”必须来自第 2 项，而不是第 1 项。"""

    return """**必须输出的结构**：
1. **评级**：五档之一（买入/增持/持有/减持/卖出）
2. **执行摘要**（趋势视角）须包含：
   - 当前趋势判断（上升/下降/震荡）与关键依据
   - 入场条件与建议入场价区（须具体）
   - 止损位（须具体数值，跌破则执行）
   - 目标价/阻力区（须具体数值）
   - 仓位建议（如轻仓/标准/减仓比例）
   - 时间窗口（如 1–4 周或 1–3 个月）
3. **投资论点**：详细推理；引用辩论与报告中的证据；说明基本面如何作为背景而非主依据"""


def build_perspective_debate_guidance() -> str:
    """多空辩论与风险辩论的视角约束。"""
    p = get_analysis_perspective()
    if p == "value":
        return """**辩论视角约束（价值分析）**：
- 多头应聚焦：估值折价、盈利增长、护城河、长期催化剂、安全边际。
- 空头应聚焦：基本面恶化、估值仍贵、结构性风险、盈利质量下滑——**避免**把「均线死叉」作为核心空头论据。
- 引用技术面时须说明其对长期价值的辅助意义，而非短线交易信号。"""
    return """**辩论视角约束（趋势分析）**：
- 多头应聚焦：趋势转强、量价配合、关键位突破、动能指标改善。
- 空头应聚焦：趋势走弱、关键支撑跌破、量价背离、下行风险——**避免**把「长期估值便宜」作为核心多头反驳。
- 引用基本面时须说明其仅作风险背景，不改变短线趋势判断。"""


def build_risk_debate_role_hint(role: str) -> str:
    """激进/保守/中性风险分析师的角色视角微调。"""
    p = get_analysis_perspective()
    if p == "value":
        hints = {
            "risky": "在价值框架下，你主张在估值安全边际充足时承担合理波动以获取长期回报；反对因短期技术面走弱就放弃折价机会。",
            "safe": "在价值框架下，你强调本金安全与基本面下行风险；反对忽视盈利恶化、杠杆失控等实质性风险，也反对因短期超卖指标就盲目抄底。",
            "neutral": "在价值框架下，你平衡估值机会与基本面风险，给出分阶段、有条件的仓位建议，时间维度以季度/年度计。",
        }
    else:
        hints = {
            "risky": "在趋势框架下，你主张在趋势确认后积极跟随，追求风险回报比；反对在下跌趋势中因「便宜」而逆势重仓。",
            "safe": "在趋势框架下，你强调止损纪律与回撤控制；反对追涨杀跌与在无确认信号时重仓。",
            "neutral": "在趋势框架下，你平衡趋势机会与波动风险，给出带明确止损的仓位方案，时间维度以周/月计。",
        }
    return hints.get(role, "")


def build_trader_system_prompt(
    *,
    company_name: str,
    currency: str,
    currency_symbol: str,
    instrument_context: str,
    past_memory_str: str,
) -> str:
    """按视角生成交易员 system prompt。"""
    p = get_analysis_perspective()
    label = get_perspective_label(p)
    guidance = build_perspective_guidance()
    banner = build_perspective_banner()

    rating_line = (
        "请用中文撰写分析内容，并始终以「最终交易建议: **买入/增持/持有/减持/卖出**」之一结束（五档评级，与风险主席一致）。"
    )

    if p == "value":
        target_guidance = f"""🎯 目标价位计算指导（价值视角）：
- **优先**采用基本面报告中的估值（P/E、P/B、DCF、mNAV、合理价值区间）
- 技术面支撑/阻力仅用于细化区间，不得用短线低点作为长期目标
- 新闻仅影响估值假设或持有逻辑，不改变估值锚点
- 必须给出具体目标价或合理区间（{currency_symbol}）
- **核心目标价必须是未来约12个月的公允价值中枢，不得使用清算价值、残余权益底线、极端熊市底线、止损位代替**
- 若报告同时存在「残余权益锚 / 下行保护线」与「合理价值区间」，请分别写出，并把 target_price 锚定为**合理价值中枢**
- 对 MSTR 这类高杠杆 BTC 资产载体，允许写出：
  - 下行保护线 / 残余权益锚
  - 12个月合理价值区间
  - 乐观情景上沿
  但**最终目标价只能取 12 个月合理价值中枢，绝不能取下行保护线**
- 如果基础数据不足或数据互相冲突，必须明确说明“不确定性提高”，并采用保守但仍属**公允价值口径**的目标价，严禁胡乱选择最悲观数字"""
    else:
        target_guidance = f"""🎯 目标价位计算指导（趋势视角）：
- **优先**采用技术分析的支撑位、阻力位、均线与布林带
- 基本面估值仅作远端参考，不得用长期 DCF 目标替代短线交易目标
- 必须给出：入场区、止损位、第一/第二目标位（{currency_symbol}，均为具体数值）"""

    return f"""您是一位专业交易员，负责在**{label}**框架下将研究结论转化为可执行建议。

{banner}

{guidance}

⚠️ 重要提醒：当前分析的股票代码是 {company_name}，请使用正确的货币单位：{currency}（{currency_symbol}）
{instrument_context}

🔴 严格要求：
- 公司名称必须严格按照基本面报告或工具数据中的真实名称
- 所有分析必须基于提供的真实数据，不允许假设或编造
- **必须提供具体的目标价位，不允许为 null 或空值**
- 你的结论必须与**{label}**宪法一致，不得混用另一套投资框架的话术

请在分析中包含：
1. **投资建议**：五档之一（买入/增持/持有/减持/卖出）
2. **目标价位**（{currency}，强制具体数值）
3. **置信度**（0–1）
4. **风险评分**（0–1，0 为低风险）
5. **详细推理**：说明如何在本视角下权衡各分析师报告

{target_guidance}

特别注意：
- 中国A股使用人民币（¥），美股/港股使用美元（$），与现价货币一致
- **绝对不允许**说「无法确定目标价」或「需要更多信息」

{rating_line}

请利用以下历史经验教训避免重复错误：
{past_memory_str}"""


def build_trader_user_context(company_name: str, investment_plan: str) -> str:
    label = get_perspective_label()
    return (
        f"基于分析师团队报告，研究经理已在**{label}**视角下为 {company_name} 制定投资计划。"
        f"请你在同一视角下审核并细化该计划，输出与之协调的五档交易建议。\n\n"
        f"研究经理投资计划：\n{investment_plan}"
    )
