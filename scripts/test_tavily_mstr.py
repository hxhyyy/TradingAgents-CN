#!/usr/bin/env python3
"""Smoke test for Tavily news search module."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.dataflows.news.tavily_search import (
    build_search_query,
    is_tavily_configured,
    search_stock_news,
)
from tradingagents.utils.stock_utils import StockUtils


def main() -> int:
    if not is_tavily_configured():
        print("Set TAVILY_API_KEY in .env first")
        return 1

    for ticker, market_hint in [
        ("MSTR", "美股"),
        ("BTCUSDT", "加密货币"),
    ]:
        market_info = StockUtils.get_analysis_market_info(ticker, market_hint)
        query = build_search_query(ticker, market_info)
        print("=" * 60)
        print(f"{ticker} ({market_hint}) query: {query}")
        result = search_stock_news(ticker, market_info, max_results=4)
        if result:
            print(result[:1200])
        else:
            print("No result")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
