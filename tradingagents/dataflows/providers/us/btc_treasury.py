#!/usr/bin/env python3
"""
Bitcoin treasury company metrics (holdings, mNAV, BTC per share).

Primary holdings source: CoinGecko public treasury API (free, no API key).
mNAV is derived from market cap / enterprise value vs Bitcoin NAV.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

COINGECKO_TREASURY_URL = (
    "https://api.coingecko.com/api/v3/companies/public_treasury/bitcoin"
)
COINGECKO_BTC_PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
)

# Tickers known to hold BTC on balance sheet (Strategy + common miners/treasuries)
BTC_TREASURY_SYMBOLS = frozenset(
    {
        "MSTR",
        "STRK",
        "STRF",
        "STRD",
        "STRC",
        "MARA",
        "RIOT",
        "CLSK",
        "HUT",
        "BITF",
        "CIFR",
        "CORZ",
    }
)


def is_btc_treasury_symbol(symbol: str) -> bool:
    return (symbol or "").strip().upper().replace(".US", "") in BTC_TREASURY_SYMBOLS


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper().replace(".US", "")


def _fetch_json(url: str, timeout: float = 20.0) -> Dict[str, Any]:
    response = httpx.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "TradingAgents-CN/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _find_treasury_company(symbol: str) -> Optional[Dict[str, Any]]:
    code = _normalize_symbol(symbol)
    payload = _fetch_json(COINGECKO_TREASURY_URL)
    for company in payload.get("companies", []):
        raw = (company.get("symbol") or "").upper()
        company_code = raw.replace(".US", "").split(".")[0]
        if company_code == code:
            return company
    return None


def _get_btc_price_usd() -> float:
    payload = _fetch_json(COINGECKO_BTC_PRICE_URL)
    return float(payload["bitcoin"]["usd"])


def _get_market_metrics(symbol: str) -> Dict[str, Optional[float]]:
    """Market cap / EV / shares from yfinance (best-effort)."""
    try:
        import yfinance as yf

        info = yf.Ticker(_normalize_symbol(symbol)).info or {}
        return {
            "market_cap": _as_float(info.get("marketCap")),
            "enterprise_value": _as_float(info.get("enterpriseValue")),
            "shares_outstanding": _as_float(info.get("sharesOutstanding")),
            "stock_price": _as_float(
                info.get("currentPrice") or info.get("regularMarketPrice")
            ),
        }
    except Exception as exc:
        logger.warning(f"⚠️ [BTC Treasury] yfinance 市场数据获取失败 {symbol}: {exc}")
        return {
            "market_cap": None,
            "enterprise_value": None,
            "shares_outstanding": None,
            "stock_price": None,
        }


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_usd(value: Optional[float], precision: int = 2) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.{precision}f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.{precision}f}M"
    return f"${value:,.{precision}f}"


def get_btc_treasury_report(symbol: str, curr_date: Optional[str] = None) -> Optional[str]:
    """
    Build a markdown report with BTC holdings and mNAV metrics.

    Strategy (MSTR/STRC/...) uses api.strategy.com; other miners use CoinGecko.
    """
    code = _normalize_symbol(symbol)
    if not is_btc_treasury_symbol(code):
        return None

    # Strategy Inc. — official dashboard API (holdings, mNAV, Digital Credit)
    try:
        from .strategy_official import get_strategy_official_report, is_strategy_symbol

        if is_strategy_symbol(code):
            report = get_strategy_official_report(code, curr_date)
            if report:
                logger.info(f"✅ [BTC Treasury] Strategy 官方 API 数据: {code}")
                return report
            logger.warning(f"⚠️ [BTC Treasury] Strategy 官方 API 失败，降级 CoinGecko: {code}")
    except Exception as exc:
        logger.warning(f"⚠️ [BTC Treasury] Strategy 官方 API 异常: {exc}")

    company = _find_treasury_company(code)
    if not company:
        logger.info(f"ℹ️ [BTC Treasury] CoinGecko 未找到 {code} 的 BTC 持仓记录")
        return None

    btc_price = _get_btc_price_usd()
    holdings = float(company.get("total_holdings") or 0)
    if holdings <= 0:
        return None

    entry_value = _as_float(company.get("total_entry_value_usd"))
    current_value = _as_float(company.get("total_current_value_usd"))
    btc_nav = holdings * btc_price

    market = _get_market_metrics(code)
    market_cap = market["market_cap"]
    enterprise_value = market["enterprise_value"]
    shares = market["shares_outstanding"]
    stock_price = market["stock_price"]

    mnav_basic = (market_cap / btc_nav) if market_cap and btc_nav else None
    mnav_ev = (enterprise_value / btc_nav) if enterprise_value and btc_nav else None
    btc_per_share = (holdings / shares) if shares else None
    nav_per_share = (btc_nav / shares) if shares and btc_nav else None
    premium_basic = ((mnav_basic - 1) * 100) if mnav_basic is not None else None

    unrealized_pnl = None
    if entry_value is not None and current_value is not None:
        unrealized_pnl = current_value - entry_value
    elif entry_value is not None:
        unrealized_pnl = btc_nav - entry_value

    as_of = curr_date or datetime.now().strftime("%Y-%m-%d")
    company_name = company.get("name") or code

    lines = [
        f"# {code} 比特币国库指标 (BTC Treasury)",
        "",
        f"**公司**: {company_name}",
        f"**数据日期**: {as_of}",
        f"**数据来源**: CoinGecko Public Treasury + yfinance（mNAV 为系统计算值）",
        "",
        "## 持币情况",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| BTC 持仓量 | {holdings:,.0f} BTC |",
        f"| 占总流通量 | {company.get('percentage_of_total_supply', 'N/A')}% |",
        f"| BTC 现价 | ${btc_price:,.0f} |",
        f"| 比特币 NAV (持仓×BTC价) | {_fmt_usd(btc_nav)} |",
        f"| 持仓成本 (入账) | {_fmt_usd(entry_value)} |",
        f"| 未实现盈亏 (估算) | {_fmt_usd(unrealized_pnl)} |",
        "",
        "## mNAV 与每股指标",
        "| 指标 | 数值 | 说明 |",
        "|------|------|------|",
        f"| mNAV (Basic) | {mnav_basic:.3f}× | 市值 ÷ 比特币 NAV |" if mnav_basic else "| mNAV (Basic) | N/A | 市值 ÷ 比特币 NAV |",
        f"| mNAV (EV) | {mnav_ev:.3f}× | 企业价值 ÷ 比特币 NAV |" if mnav_ev else "| mNAV (EV) | N/A | 企业价值 ÷ 比特币 NAV |",
        f"| 相对 NAV 溢价/折价 | {premium_basic:+.1f}% | (mNAV Basic - 1) × 100 |" if premium_basic is not None else "| 相对 NAV 溢价/折价 | N/A | (mNAV Basic - 1) × 100 |",
        f"| BTC / 股 (BPS) | {btc_per_share:.6f} BTC | 持仓 ÷ 总股本 |" if btc_per_share else "| BTC / 股 (BPS) | N/A | 持仓 ÷ 总股本 |",
        f"| 每股比特币 NAV | ${nav_per_share:,.2f} | 比特币 NAV ÷ 总股本 |" if nav_per_share else "| 每股比特币 NAV | N/A | 比特币 NAV ÷ 总股本 |",
        f"| 股价 | ${stock_price:.2f} | yfinance 实时/延时 |" if stock_price else "| 股价 | N/A | yfinance |",
        "",
        "## 分析提示",
        "- mNAV < 1：股价低于比特币资产净值，可能存在折价",
        "- mNAV > 1：市场为比特币敞口和融资能力支付溢价",
        "- Strategy (MSTR) 官方还会在 8-K / 投资者关系披露最新持仓，CoinGecko 通常有数小时至数天延迟",
        "- 本指标为分析辅助，投资决策请以公司 SEC 披露为准",
        "",
    ]
    return "\n".join(lines)
