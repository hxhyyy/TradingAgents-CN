"""Yahoo Finance news provider (aligned with upstream TradingAgents)."""

from __future__ import annotations

import contextlib
from datetime import datetime

import yfinance as yf
from dateutil.relativedelta import relativedelta

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def _extract_article_data(article: dict) -> dict:
    if "content" in article:
        content = article["content"]
        title = content.get("title", "No title")
        summary = content.get("summary", "")
        provider = content.get("provider", {})
        publisher = provider.get("displayName", "Unknown")
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_obj.get("url", "")
        pub_date_str = content.get("pubDate", "")
        pub_date = None
        if pub_date_str:
            with contextlib.suppress(ValueError, AttributeError):
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
        return {
            "title": title,
            "summary": summary,
            "publisher": publisher,
            "link": link,
            "pub_date": pub_date,
        }

    pub_date = None
    ts = article.get("providerPublishTime")
    if ts:
        with contextlib.suppress(ValueError, OSError, TypeError):
            pub_date = datetime.fromtimestamp(ts)
    return {
        "title": article.get("title", "No title"),
        "summary": article.get("summary", ""),
        "publisher": article.get("publisher", "Unknown"),
        "link": article.get("link", ""),
        "pub_date": pub_date,
    }


def _in_news_window(pub_date, start_dt, end_dt) -> bool:
    if pub_date is not None:
        naive = pub_date.replace(tzinfo=None) if hasattr(pub_date, "replace") else pub_date
        return start_dt <= naive <= end_dt + relativedelta(days=1)
    return end_dt >= datetime.now() - relativedelta(days=1)


def get_stock_news(
    ticker: str,
    start_date: str,
    end_date: str,
    limit: int = 15,
) -> str:
    """Fetch ticker news via yfinance (no API key required)."""
    canonical = ticker.upper().split(".")[0]
    try:
        stock = yf.Ticker(canonical)
        news = stock.get_news(count=limit)
        if not news:
            return ""

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        lines = []
        for article in news:
            data = _extract_article_data(article)
            if not _in_news_window(data["pub_date"], start_dt, end_dt):
                continue
            block = f"### {data['title']} (source: {data['publisher']})\n"
            if data["summary"]:
                block += f"{data['summary']}\n"
            if data["link"]:
                block += f"Link: {data['link']}\n"
            lines.append(block)

        if not lines:
            return ""

        header = f"## {ticker} Yahoo Finance News, from {start_date} to {end_date}:\n\n"
        logger.info(f"[Yahoo新闻] {ticker} 获取 {len(lines)} 条")
        return header + "\n".join(lines)

    except Exception as e:
        logger.warning(f"[Yahoo新闻] 获取失败 {ticker}: {e}")
        return ""
