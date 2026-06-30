#!/usr/bin/env python3
"""Supplemental Strategy data: purchases, BTC trend, SEC filings."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

MSTR_CIK = "0001050446"
SEC_HEADERS = {
    "User-Agent": "TradingAgents-CN/1.0 (research@local)",
    "Accept": "application/json",
}
WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingAgents-CN/1.0"}


def fetch_purchase_records(limit: int = 10) -> List[Dict[str, Any]]:
    """Purchase/sale history from strategy.com/purchases (same as official site)."""
    try:
        response = httpx.get(
            "https://www.strategy.com/purchases",
            timeout=30,
            headers=WEB_HEADERS,
        )
        response.raise_for_status()
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            response.text,
        )
        if not match:
            return []
        data = json.loads(match.group(1))
        records = data.get("props", {}).get("pageProps", {}).get("bitcoinData", [])
        if not isinstance(records, list):
            return []
        return records[-limit:]
    except Exception as exc:
        logger.warning(f"⚠️ [Strategy Supplemental] 购币历史获取失败: {exc}")
        return []


def fetch_btc_price_series() -> List[Dict[str, Any]]:
    try:
        response = httpx.get(
            "https://api.strategy.com/btc/bitcoinHistory",
            timeout=30,
            headers={**WEB_HEADERS, "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("results") or []
    except Exception as exc:
        logger.warning(f"⚠️ [Strategy Supplemental] BTC 历史价格获取失败: {exc}")
        return []


def fetch_recent_8k_filings(limit: int = 6) -> List[Dict[str, str]]:
    try:
        response = httpx.get(
            f"https://data.sec.gov/submissions/CIK{MSTR_CIK}.json",
            timeout=25,
            headers=SEC_HEADERS,
        )
        response.raise_for_status()
        recent = response.json().get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary = recent.get("primaryDocument", [])

        filings: List[Dict[str, str]] = []
        for i, form in enumerate(forms):
            if form != "8-K":
                continue
            acc = accessions[i].replace("-", "")
            doc = primary[i] if i < len(primary) else ""
            url = (
                f"https://www.sec.gov/Archives/edgar/data/1050446/"
                f"{acc}/{doc}"
            )
            filings.append(
                {
                    "date": dates[i],
                    "accession": accessions[i],
                    "url": url,
                }
            )
            if len(filings) >= limit:
                break
        return filings
    except Exception as exc:
        logger.warning(f"⚠️ [Strategy Supplemental] SEC 8-K 列表获取失败: {exc}")
        return []


def _price_at_offset(
    series: List[Dict[str, Any]], days: int
) -> Optional[float]:
    if not series:
        return None
    target = datetime.now(timezone.utc) - timedelta(days=days)
    best: Optional[float] = None
    best_delta = None
    for row in series:
        try:
            dt = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        delta = abs((dt - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = float(row.get("price", 0))
    return best


def format_btc_trend_section(series: List[Dict[str, Any]]) -> List[str]:
    if not series:
        return ["## BTC 价格趋势", "数据暂不可用", ""]

    latest = float(series[-1].get("price", 0))
    lines = [
        "## BTC 价格趋势 (Strategy 官方历史)",
        "| 周期 | 涨跌幅 |",
        "|------|--------|",
    ]
    for label, days in (("30 天", 30), ("90 天", 90), ("1 年", 365)):
        past = _price_at_offset(series, days)
        if past and past > 0:
            chg = (latest - past) / past * 100
            lines.append(f"| {label} | {chg:+.2f}% |")
        else:
            lines.append(f"| {label} | N/A |")
    lines.append(f"| 当前价格 | ${latest:,.0f} |")
    lines.append("")
    return lines


def format_purchase_section(records: List[Dict[str, Any]]) -> List[str]:
    if not records:
        return ["## 近期购币/售币记录 (strategy.com)", "数据暂不可用", ""]

    lines = [
        "## 近期购币/售币记录 (strategy.com / 8-K)",
        "| 日期 | 类型 | BTC数量 | 成交价 | 总金额 | 持仓后总量 | BTC Yield YTD |",
        "|------|------|---------|--------|--------|------------|---------------|",
    ]
    for row in reversed(records):
        date = row.get("date_of_purchase", "N/A")
        count = row.get("count", 0)
        is_sale = row.get("sale") is True
        kind = "出售/调整" if is_sale else "收购"
        price = row.get("purchase_price", "N/A")
        price_str = f"${float(price):,.0f}" if isinstance(price, (int, float)) else str(price)
        total = row.get("total_purchase_price")
        if isinstance(total, (int, float)):
            if abs(total) >= 1_000_000_000:
                total_str = f"${total / 1e9:.2f}B"
            elif abs(total) >= 1_000_000:
                total_str = f"${total / 1e6:.0f}M"
            else:
                total_str = f"${total:,.0f}"
        else:
            total_str = "N/A"
        holdings = row.get("btc_holdings", "N/A")
        ytd_yield = row.get("btc_yield_ytd", "N/A")
        count_str = f"{count:+,}" if isinstance(count, (int, float)) else str(count)
        lines.append(
            f"| {date} | {kind} | {count_str} | {price_str} | {total_str} | "
            f"{holdings:,} | {ytd_yield}% |"
            if isinstance(holdings, (int, float))
            else f"| {date} | {kind} | {count_str} | {price_str} | {total_str} | {holdings} | {ytd_yield}% |"
        )
    lines.append("")

    latest = records[-1]
    lines.extend([
        "## 管理层 KPI (最新 8-K 披露)",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| BTC 持仓 | {latest.get('btc_holdings', 'N/A'):,} BTC |"
        if isinstance(latest.get("btc_holdings"), (int, float))
        else "| BTC 持仓 | N/A |",
        f"| 平均持仓成本 | ${latest.get('average_price', 'N/A'):,}/BTC |"
        if latest.get("average_price")
        else "| 平均持仓成本 | N/A |",
        f"| 累计收购成本 | ${latest.get('total_acquisition_cost', 'N/A'):,}M |"
        if latest.get("total_acquisition_cost")
        else "| 累计收购成本 | N/A |",
        f"| BTC Yield (YTD) | {latest.get('btc_yield_ytd', 'N/A')}% |",
        f"| BTC Gain (YTD, BTC) | {latest.get('btc_gain_ytd_btc', 'N/A'):,} BTC |"
        if isinstance(latest.get("btc_gain_ytd_btc"), (int, float))
        else f"| BTC Gain (YTD, BTC) | {latest.get('btc_gain_ytd', 'N/A')} |",
        f"| 基本股本 | {latest.get('basic_shares_outstanding', 'N/A'):,} |"
        if isinstance(latest.get("basic_shares_outstanding"), (int, float))
        else "| 基本股本 | N/A |",
        f"| 稀释股本 | {latest.get('assumed_diluted_shares_outstanding', 'N/A'):,} |"
        if isinstance(latest.get("assumed_diluted_shares_outstanding"), (int, float))
        else "| 稀释股本 | N/A |",
        "",
    ])

    announcement = (latest.get("x_post_plain_text") or "").strip()
    if announcement:
        lines.extend([
            "## 最新官方声明摘要",
            f"> {announcement[:500]}",
            "",
        ])
    return lines


def format_sec_section(filings: List[Dict[str, str]]) -> List[str]:
    if not filings:
        return ["## SEC 近期 8-K 披露", "数据暂不可用", ""]

    lines = [
        "## SEC 近期 8-K 披露",
        "| 披露日期 | 文件链接 |",
        "|----------|----------|",
    ]
    for f in filings:
        lines.append(f"| {f['date']} | {f['url']} |")
    lines.append("")
    return lines


def get_supplemental_sections() -> str:
    """Fetch and format all supplemental Strategy sections."""
    purchases = fetch_purchase_records(limit=8)
    btc_series = fetch_btc_price_series()
    sec_filings = fetch_recent_8k_filings(limit=6)

    parts: List[str] = []
    parts.extend(format_btc_trend_section(btc_series))
    parts.extend(format_purchase_section(purchases))
    parts.extend(format_sec_section(sec_filings))
    return "\n".join(parts)
