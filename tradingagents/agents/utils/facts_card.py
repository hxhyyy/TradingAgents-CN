"""
统一 Facts 底稿（用于治本：跨节点数字一致性）

目标：
- 从已有报告（优先 fundamentals_report）中抽取关键数值，形成“唯一事实卡片”
- 注入研究经理 / 交易员 / 风险主席 prompt，避免不同节点各自编数字
- 缺失时明确标注未知，不阻断主流程
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # remove common separators/symbols
    s = s.replace(",", "").replace("，", "").replace("$", "").replace("¥", "").replace("￥", "")
    # handle suffix like M/B
    m = re.match(r"^(-?\d+(?:\.\d+)?)([MmBb])?$", s)
    if not m:
        return None
    v = float(m.group(1))
    suf = m.group(2)
    if suf in ("M", "m"):
        return v * 1_000_000
    if suf in ("B", "b"):
        return v * 1_000_000_000
    return v


def _to_int(raw: str | None) -> int | None:
    v = _to_float(raw)
    if v is None:
        return None
    try:
        return int(round(v))
    except Exception:
        return None


def _first_group(text: str, patterns: list[str], flags: int = 0) -> str | None:
    for p in patterns:
        m = re.search(p, text, flags)
        if m and m.group(1):
            return m.group(1)
    return None


@dataclass(frozen=True)
class FactsCard:
    # Generic
    symbol: str | None = None
    currency: str | None = None
    currency_symbol: str | None = None

    # Price & equity
    last_price: float | None = None
    market_cap: float | None = None
    ev: float | None = None
    shares_basic: int | None = None

    # BTC proxy specifics (optional)
    btc_holdings: int | None = None
    btc_price: float | None = None
    btc_nav: float | None = None
    debt: float | None = None
    preferred: float | None = None
    mnav_basic: float | None = None
    mnav_ev: float | None = None

    # Derived
    residual_equity_value: float | None = None  # market_cap - debt - preferred
    residual_nav_per_share: float | None = None

    # Warnings
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_facts_from_fundamentals_report(
    fundamentals_report: str,
    *,
    symbol: str | None = None,
    currency: str | None = None,
    currency_symbol: str | None = None,
) -> FactsCard:
    """
    从 fundamentals_report 文本中抽取关键事实。

    约束：
    - 只做“提取/推导”，不编造；提取不到就 None
    - 尽量兼容中英混排与表格
    """
    text = fundamentals_report or ""

    # Shares
    shares_raw = _first_group(
        text,
        [
            r"基本股本.*?\|\s*([0-9][0-9,]+)\s*股",
            r"基本股本.*?([0-9][0-9,]+)\s*股",
            r"shares?\s*\(basic\).*?([0-9][0-9,]+)",
        ],
        flags=re.IGNORECASE,
    )
    shares_basic = _to_int(shares_raw)

    # Price / Market cap / EV
    last_price_raw = _first_group(
        text,
        [
            r"最新收盘价.*?\|\s*\*{0,2}\$?([0-9]+(?:\.[0-9]+)?)",
            r"最新收盘价.*?\$([0-9]+(?:\.[0-9]+)?)",
            r"当前价格.*?\$([0-9]+(?:\.[0-9]+)?)",
        ],
        flags=re.IGNORECASE,
    )
    last_price = _to_float(last_price_raw)

    market_cap_raw = _first_group(
        text,
        [
            r"\|\s*市值\s*\|\s*\$?([0-9][0-9,]*)(?:\s*M)?\s*\|",
            r"\|\s*市值\s*\|\s*\$?([0-9]+(?:\.[0-9]+)?)\s*M",
            r"市值.*?\$?([0-9]+(?:\.[0-9]+)?)\s*M",
        ],
        flags=re.IGNORECASE,
    )
    market_cap = None
    if market_cap_raw:
        # many reports use $xx,xxxM
        if re.search(r"[Mm]\b", market_cap_raw):
            market_cap = _to_float(market_cap_raw)
        else:
            # assume "M" if it came from "M" line
            market_cap = _to_float(market_cap_raw)
            if market_cap is not None and market_cap < 10_000_000:  # e.g. 32304 meaning 32,304M
                market_cap *= 1_000_000

    ev_raw = _first_group(
        text,
        [
            r"\|\s*企业价值\s*\(EV\)\s*\|\s*\$?([0-9]+(?:\.[0-9]+)?)\s*M",
            r"企业价值\s*\(EV\).*?\$?([0-9]+(?:\.[0-9]+)?)\s*M",
        ],
        flags=re.IGNORECASE,
    )
    ev = None
    if ev_raw:
        ev = _to_float(ev_raw)
        if ev is not None and ev < 10_000_000:
            ev *= 1_000_000

    # BTC holdings / BTC price / BTC NAV
    btc_holdings_raw = _first_group(
        text,
        [
            r"\|\s*BTC\s*持仓量\s*\|\s*([0-9][0-9,]+)\s*BTC",
            r"持有\s*([0-9][0-9,]+)\s*(?:枚|个)?\s*BTC",
        ],
        flags=re.IGNORECASE,
    )
    btc_holdings = _to_int(btc_holdings_raw)

    btc_price_raw = _first_group(
        text,
        [
            r"\|\s*BTC\s*现价.*?\|\s*\$?([0-9]+(?:\.[0-9]+)?)",
            r"BTC\s*现价.*?\$?([0-9]+(?:\.[0-9]+)?)",
        ],
        flags=re.IGNORECASE,
    )
    btc_price = _to_float(btc_price_raw)

    btc_nav_raw = _first_group(
        text,
        [
            r"\|\s*比特币\s*NAV.*?\|\s*\*{0,2}\$?([0-9]+(?:\.[0-9]+)?)\s*M",
            r"比特币\s*NAV.*?\$?([0-9]+(?:\.[0-9]+)?)\s*M",
        ],
        flags=re.IGNORECASE,
    )
    btc_nav = None
    if btc_nav_raw:
        btc_nav = _to_float(btc_nav_raw)
        if btc_nav is not None and btc_nav < 10_000_000:
            btc_nav *= 1_000_000

    # Debt / Preferred
    debt_raw = _first_group(
        text,
        [
            r"\|\s*债务\s*\|\s*\$?([0-9]+(?:\.[0-9]+)?)\s*M",
            r"债务.*?\$?([0-9]+(?:\.[0-9]+)?)\s*M",
        ],
        flags=re.IGNORECASE,
    )
    debt = None
    if debt_raw:
        debt = _to_float(debt_raw)
        if debt is not None and debt < 10_000_000:
            debt *= 1_000_000

    preferred_raw = _first_group(
        text,
        [
            r"\|\s*优先股.*?\|\s*\$?([0-9]+(?:\.[0-9]+)?)\s*M",
            r"优先股.*?\$?([0-9]+(?:\.[0-9]+)?)\s*M",
        ],
        flags=re.IGNORECASE,
    )
    preferred = None
    if preferred_raw:
        preferred = _to_float(preferred_raw)
        if preferred is not None and preferred < 10_000_000:
            preferred *= 1_000_000

    # mNAVs
    mnav_basic_raw = _first_group(
        text,
        [
            r"mNAV\s*\(Basic\).*?\|\s*\*{0,2}([0-9]+(?:\.[0-9]+)?)",
            r"mNAV\s*\(Basic\).*?=\s*.*?([0-9]+(?:\.[0-9]+)?)\s*×",
        ],
        flags=re.IGNORECASE,
    )
    mnav_basic = _to_float(mnav_basic_raw)

    mnav_ev_raw = _first_group(
        text,
        [
            r"mNAV\s*\(EV\).*?\|\s*\*{0,2}([0-9]+(?:\.[0-9]+)?)",
            r"mNAV\s*\(EV\).*?=\s*.*?([0-9]+(?:\.[0-9]+)?)\s*×",
        ],
        flags=re.IGNORECASE,
    )
    mnav_ev = _to_float(mnav_ev_raw)

    warnings: list[str] = []

    # Derived residual equity (simple)
    residual_equity_value = None
    residual_nav_per_share = None
    if market_cap is not None and debt is not None and preferred is not None:
        residual_equity_value = market_cap - debt - preferred
        if shares_basic:
            residual_nav_per_share = residual_equity_value / shares_basic

    # Minimal sanity checks / warnings
    if btc_holdings is not None and btc_holdings < 10_000:
        warnings.append(f"BTC 持仓数值疑似过小：{btc_holdings}（请核对数据源）")
    if shares_basic is not None and shares_basic < 1_000_000:
        warnings.append(f"基本股本疑似异常：{shares_basic}（请核对数据源）")
    if market_cap is not None and market_cap < 100_000_000:
        warnings.append(f"市值疑似异常：{market_cap}（请核对单位是否为 M）")

    return FactsCard(
        symbol=symbol,
        currency=currency,
        currency_symbol=currency_symbol,
        last_price=last_price,
        market_cap=market_cap,
        ev=ev,
        shares_basic=shares_basic,
        btc_holdings=btc_holdings,
        btc_price=btc_price,
        btc_nav=btc_nav,
        debt=debt,
        preferred=preferred,
        mnav_basic=mnav_basic,
        mnav_ev=mnav_ev,
        residual_equity_value=residual_equity_value,
        residual_nav_per_share=residual_nav_per_share,
        warnings=tuple(warnings),
    )


def build_facts_card_text(card: FactsCard) -> str:
    """
    将 FactsCard 渲染为 prompt 可直接粘贴的“唯一事实底稿”。
    """
    def fmt_money(v: float | None) -> str:
        if v is None:
            return "未知"
        # show in billions if large
        if abs(v) >= 1_000_000_000:
            return f"{v/1_000_000_000:.3f}B"
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.3f}M"
        return f"{v:.2f}"

    def fmt_num(v: float | int | None) -> str:
        if v is None:
            return "未知"
        if isinstance(v, int):
            return f"{v:,}"
        return f"{v:.4g}"

    lines: list[str] = []
    lines.append("## ✅ 统一事实底稿（所有节点必须以此为准，不得自行编造/替换口径）")
    if card.symbol:
        lines.append(f"- **标的**：{card.symbol}")
    if card.currency and card.currency_symbol:
        lines.append(f"- **计价货币**：{card.currency}（{card.currency_symbol}）")
    lines.append("")
    lines.append("### 价格与市值")
    lines.append(f"- **最新价**：{fmt_num(card.last_price)}")
    lines.append(f"- **市值**：{fmt_money(card.market_cap)}")
    lines.append(f"- **企业价值 EV**：{fmt_money(card.ev)}")
    lines.append(f"- **基本股本**：{fmt_num(card.shares_basic)} 股")
    lines.append("")
    lines.append("### BTC 资产与资本结构（如适用）")
    lines.append(f"- **BTC 持仓**：{fmt_num(card.btc_holdings)} BTC")
    lines.append(f"- **BTC 现价**：{fmt_num(card.btc_price)}")
    lines.append(f"- **BTC NAV**：{fmt_money(card.btc_nav)}")
    lines.append(f"- **债务**：{fmt_money(card.debt)}")
    lines.append(f"- **优先股**：{fmt_money(card.preferred)}")
    lines.append(f"- **mNAV (Basic)**：{fmt_num(card.mnav_basic)}")
    lines.append(f"- **mNAV (EV)**：{fmt_num(card.mnav_ev)}")
    lines.append("")
    lines.append("### 残余权益（普通股）粗算（仅供价值分析参考）")
    lines.append(f"- **残余权益总额**：{fmt_money(card.residual_equity_value)}")
    lines.append(f"- **残余权益/股（Residual NAV/Share）**：{fmt_num(card.residual_nav_per_share)}")

    if card.warnings:
        lines.append("")
        lines.append("### ⚠️ 数据一致性告警（不阻断流程）")
        for w in card.warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("**约束**：后续任何推理、估值、目标价、风险测算必须引用以上底稿数字；若发现报告其他部分出现不同口径，请判定为冲突并以本底稿为准，同时在结论中说明“不一致导致不确定性上升”。")
    return "\n".join(lines)


def build_facts_card_from_state(state: dict[str, Any], *, market_info: dict[str, Any] | None = None) -> FactsCard:
    """
    从 graph state 构建 FactsCard。
    目前以 fundamentals_report 为主；未来可扩展为直接从工具返回的结构化数据生成。
    """
    fundamentals_report = state.get("fundamentals_report", "") or ""
    symbol = state.get("company_of_interest") or None
    currency = None
    currency_symbol = None
    if market_info:
        currency = market_info.get("currency_name")
        currency_symbol = market_info.get("currency_symbol")
    return extract_facts_from_fundamentals_report(
        fundamentals_report,
        symbol=symbol,
        currency=currency,
        currency_symbol=currency_symbol,
    )

