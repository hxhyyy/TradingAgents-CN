"""A-share news fetch: Eastmoney direct -> Tavily -> AKShare (last)."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from tradingagents.utils.logging_init import get_logger

logger = get_logger("agents")

MIN_USEFUL_CHARS = 200
FAILURE_MARKERS = ("获取失败", "未获取", "不可用", "❌", "No news found")


def _clean_symbol(symbol: str) -> str:
    return (
        str(symbol or "")
        .strip()
        .replace(".SH", "")
        .replace(".SZ", "")
        .replace(".SS", "")
        .replace(".XSHE", "")
        .replace(".XSHG", "")
        .zfill(6)
    )


def _useful_length(sections: List[str]) -> int:
    total = 0
    for section in sections:
        text = (section or "").strip()
        if not text or any(marker in text for marker in FAILURE_MARKERS):
            continue
        if "未返回搜索结果" in text:
            continue
        total += len(text)
    return total


def format_news_dataframe(df: pd.DataFrame, source_label: str = "东方财富") -> str:
    lines = [f"## {source_label}新闻", ""]
    for _, row in df.iterrows():
        title = row.get("新闻标题", "") or row.get("标题", "")
        news_time = row.get("发布时间", "") or row.get("时间", "")
        news_url = row.get("新闻链接", "") or row.get("链接", "")
        content = row.get("新闻内容", "") or row.get("内容", "")
        if not str(title).strip():
            continue
        lines.append(f"- **{title}** [{news_time}]({news_url})")
        if content and str(content).strip():
            preview = str(content).strip()
            if len(preview) > 200:
                preview = preview[:200] + "..."
            lines.append(f"  {preview}")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def fetch_a_share_news_sections(
    symbol: str,
    *,
    limit: int = 10,
    include_google: bool = False,
    curr_date: Optional[str] = None,
) -> List[str]:
    """
    Live A-share news chain:
    1. Eastmoney direct API
    2. Tavily web search (if still thin)
    3. AKShare stock_news_em (last resort)
    4. Google scrape (optional)
    """
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
    from tradingagents.dataflows.news.tavily_search import search_stock_news
    from tradingagents.utils.stock_utils import StockUtils

    clean = _clean_symbol(symbol)
    sections: List[str] = []
    provider = AKShareProvider()

    # 1) 东方财富直连
    try:
        df = provider.get_stock_news_direct_sync(clean, limit=limit)
        if df is not None and not df.empty:
            block = format_news_dataframe(df, "东方财富直连")
            if block:
                sections.append(block)
                logger.info(f"✅ [A股新闻] 东方财富直连: {clean}, {len(df)} 条")
    except Exception as exc:
        logger.warning(f"⚠️ [A股新闻] 东方财富直连失败 {clean}: {exc}")

    # 2) Tavily
    if _useful_length(sections) < MIN_USEFUL_CHARS:
        try:
            market_info = StockUtils.get_analysis_market_info(clean, "A股")
            tavily_block = search_stock_news(clean, market_info, max_results=5)
            if tavily_block and "未返回搜索结果" not in tavily_block:
                sections.append(tavily_block)
                logger.info(f"✅ [A股新闻] Tavily 补充: {clean}")
        except Exception as exc:
            logger.warning(f"⚠️ [A股新闻] Tavily 失败 {clean}: {exc}")

    # 3) AKShare 最后尝试
    if _useful_length(sections) < MIN_USEFUL_CHARS:
        try:
            df = provider.get_stock_news_akshare_sync(clean, limit=limit)
            if df is not None and not df.empty:
                block = format_news_dataframe(df, "AKShare/东方财富")
                if block:
                    sections.append(block)
                    logger.info(f"✅ [A股新闻] AKShare 兜底: {clean}, {len(df)} 条")
        except Exception as exc:
            logger.warning(f"⚠️ [A股新闻] AKShare 兜底失败 {clean}: {exc}")

    # 4) Google（可选）
    if include_google and _useful_length(sections) < MIN_USEFUL_CHARS and curr_date:
        try:
            from tradingagents.dataflows.interface import get_google_news

            query = f"{clean} 股票 新闻 财报 业绩"
            google_news = get_google_news(query, curr_date)
            if google_news and len(google_news.strip()) > 50:
                sections.append(f"## Google新闻\n{google_news}")
                logger.info(f"✅ [A股新闻] Google 兜底: {clean}")
        except Exception as exc:
            logger.warning(f"⚠️ [A股新闻] Google 失败 {clean}: {exc}")

    return sections


def fetch_a_share_news_markdown(
    symbol: str,
    *,
    limit: int = 10,
    include_google: bool = True,
    curr_date: Optional[str] = None,
) -> str:
    sections = fetch_a_share_news_sections(
        symbol,
        limit=limit,
        include_google=include_google,
        curr_date=curr_date,
    )
    if not sections:
        return ""
    return "\n\n---\n\n".join(sections)
