"""Tavily web search — optional real-time news supplement for stock analysis."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from tradingagents.utils.logging_init import get_logger

logger = get_logger("agents")

MIN_USEFUL_CONTENT_CHARS = 800
FAILURE_MARKERS = ("获取失败", "未获取", "不可用", "❌", "No news found")
DEFAULT_MAX_RESULTS = 5


def is_tavily_configured() -> bool:
    return bool((os.getenv("TAVILY_API_KEY") or "").strip())


def is_tavily_enabled() -> bool:
    flag = (os.getenv("TAVILY_ENABLED") or "true").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _useful_content_length(sections: List[str]) -> int:
    total = 0
    for section in sections:
        text = (section or "").strip()
        if not text:
            continue
        if any(marker in text for marker in FAILURE_MARKERS):
            continue
        total += len(text)
    return total


def should_use_tavily(sections: List[str], market_info: Dict) -> bool:
    """Decide whether to call Tavily for this analysis."""
    if not is_tavily_configured() or not is_tavily_enabled():
        return False

    if any("Tavily" in (section or "") for section in sections):
        return False

    useful_len = _useful_content_length(sections)
    if market_info.get("is_us") or market_info.get("is_crypto"):
        return True

    if market_info.get("is_china"):
        return useful_len < MIN_USEFUL_CONTENT_CHARS

    return useful_len < MIN_USEFUL_CONTENT_CHARS


def build_search_query(ticker: str, market_info: Dict) -> str:
    """Build a Tavily query from ticker and market context."""
    code = (ticker or "").strip().upper()
    if market_info.get("is_crypto"):
        if code in {"BTC", "BTCUSDT"}:
            return "Bitcoin BTC price news market analysis"
        return f"{code} cryptocurrency news"

    if market_info.get("is_china"):
        clean = code.replace(".SH", "").replace(".SZ", "").replace(".SS", "")
        return f"{clean} A股 股票 财报 新闻"

    if market_info.get("is_hk"):
        clean = code.replace(".HK", "")
        return f"{clean} 港股 香港 股票 新闻"

    if market_info.get("is_us"):
        return f"{code} stock news earnings analyst rating"

    return f"{code} stock market news"


def format_tavily_response(response: Dict, query: str) -> str:
    lines = [f"## Tavily 网络搜索", "", f"**搜索词**: {query}", ""]

    answer = (response.get("answer") or "").strip()
    if answer:
        lines.extend(["### AI 摘要", answer, ""])

    results = response.get("results") or []
    if not results:
        lines.append("*未返回搜索结果*")
        return "\n".join(lines)

    lines.append("### 相关新闻")
    for index, item in enumerate(results, 1):
        title = item.get("title") or "无标题"
        url = item.get("url") or ""
        score = item.get("score")
        content = (item.get("content") or "").strip()
        if len(content) > 320:
            content = content[:320] + "..."
        score_text = f" (相关度 {score:.2f})" if isinstance(score, (int, float)) else ""
        lines.append(f"{index}. **{title}**{score_text}")
        if url:
            lines.append(f"   - 链接: {url}")
        if content:
            lines.append(f"   - {content}")
        lines.append("")

    lines.append("*数据来源: Tavily API*")
    return "\n".join(lines)


def search_stock_news(
    ticker: str,
    market_info: Dict,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> Optional[str]:
    """Run one Tavily search and return formatted markdown."""
    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return None

    query = build_search_query(ticker, market_info)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
        formatted = format_tavily_response(response, query)
        logger.info(f"✅ [Tavily] 搜索成功: {ticker}, 结果长度 {len(formatted)}")
        return formatted
    except Exception as exc:
        logger.warning(f"⚠️ [Tavily] 搜索失败 {ticker}: {exc}")
        return None


def maybe_append_tavily_section(
    sections: List[str],
    ticker: str,
    market_info: Dict,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> List[str]:
    """Append Tavily results when configured and useful."""
    if not should_use_tavily(sections, market_info):
        return sections

    tavily_block = search_stock_news(ticker, market_info, max_results=max_results)
    if not tavily_block:
        return sections

    updated = list(sections)
    updated.append(tavily_block)
    return updated
