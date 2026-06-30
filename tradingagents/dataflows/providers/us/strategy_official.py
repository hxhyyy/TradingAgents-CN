#!/usr/bin/env python3
"""
Strategy Inc. (MSTR) official treasury metrics via api.strategy.com.

Same data source as https://www.strategy.com/ dashboard — no API key required.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

STRATEGY_API_BASE = "https://api.strategy.com"
STRATEGY_SYMBOLS = frozenset({"MSTR", "STRC", "STRF", "STRD", "STRK"})
PREFERRED_TICKERS = ("STRC", "STRF", "STRD", "STRK")

_HTTP_HEADERS = {
    "User-Agent": "TradingAgents-CN/1.0",
    "Accept": "application/json",
}


def is_strategy_symbol(symbol: str) -> bool:
    return (symbol or "").strip().upper().replace(".US", "") in STRATEGY_SYMBOLS


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper().replace(".US", "")


def _fetch_json(path: str, timeout: float = 25.0) -> Any:
    url = f"{STRATEGY_API_BASE}{path}"
    response = httpx.get(url, timeout=timeout, headers=_HTTP_HEADERS)
    response.raise_for_status()
    return response.json()


def _parse_millions(value: Any) -> Optional[float]:
    """Parse Strategy API dollar fields (millions USD), e.g. '34,441' or 8776.5."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def _fmt_millions(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.0f}M"


def _fmt_pct(value: Any, signed: bool = True) -> str:
    if value is None:
        return "N/A"
    try:
        num = float(value)
        if signed:
            return f"{num:+.2f}%"
        return f"{num:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _first_kpi_row(payload: Any) -> Optional[Dict[str, Any]]:
    if isinstance(payload, list) and payload:
        return payload[0]
    if isinstance(payload, dict):
        return payload
    return None


def fetch_bitcoin_kpis() -> Dict[str, Any]:
    data = _fetch_json("/btc/bitcoinKpis")
    return data.get("results") or {}


def fetch_mstr_kpi() -> Optional[Dict[str, Any]]:
    return _first_kpi_row(_fetch_json("/btc/mstrKpiData"))


def fetch_pref_kpi(ticker: str) -> Optional[Dict[str, Any]]:
    code = _normalize_symbol(ticker)
    if code not in PREFERRED_TICKERS:
        return None
    return _first_kpi_row(_fetch_json(f"/btc/{code.lower()}KpiData"))


def fetch_mstr_options() -> Dict[str, Any]:
    data = _fetch_json("/btc/mstrOptionsData")
    return data if isinstance(data, dict) else {}


def _format_pref_row(row: Dict[str, Any]) -> List[str]:
    code = row.get("company", "?")
    price = row.get("price", "N/A")
    mcap = row.get("marketCap")
    eff_yield = row.get("effYield")
    div = row.get("currentDividend")
    notional = row.get("notional")
    mstr_cor = row.get("mstrCor")
    btc_cor = row.get("btcCor")
    vol = row.get("annualizedVolatility")
    oi = row.get("totalOi", "N/A")

    notional_str = _fmt_millions(notional / 1_000_000) if notional else "N/A"
    mcap_str = _fmt_millions(mcap) if isinstance(mcap, (int, float)) else str(mcap)
    next_record = row.get("nextRecordDate", "N/A")
    next_payout = row.get("nextPayoutDate", "N/A")
    vwap = row.get("vwap1mo")

    return [
        f"### {code}",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 价格 | ${price} |",
        f"| 市值 | {mcap_str} |",
        f"| 有效收益率 | {_fmt_pct(eff_yield, signed=False) if eff_yield else 'N/A'} |",
        f"| 当前股息率 | {_fmt_pct(div, signed=False) if div else 'N/A'} |",
        f"| 名义规模 (Notional) | {notional_str} |",
        f"| 1个月 VWAP | ${vwap:.2f} |" if vwap else "| 1个月 VWAP | N/A |",
        f"| 下一除息日 | {next_record} |",
        f"| 下一派息日 | {next_payout} |",
        f"| 与 MSTR 相关性 | {mstr_cor}% |" if mstr_cor is not None else "| 与 MSTR 相关性 | N/A |",
        f"| 与 BTC 相关性 | {btc_cor}% |" if btc_cor is not None else "| 与 BTC 相关性 | N/A |",
        f"| 年化波动率 | {vol}% |" if vol is not None else "| 年化波动率 | N/A |",
        f"| 期权未平仓 | {oi} |",
        "",
    ]


def get_strategy_official_report(
    symbol: str, curr_date: Optional[str] = None
) -> Optional[str]:
    """
    Build a comprehensive Strategy treasury report from api.strategy.com.
    """
    code = _normalize_symbol(symbol)
    if code not in STRATEGY_SYMBOLS:
        return None

    try:
        btc = fetch_bitcoin_kpis()
        mstr = fetch_mstr_kpi()
        options = fetch_mstr_options()
    except Exception as exc:
        logger.warning(f"⚠️ [Strategy Official] API 请求失败: {exc}")
        return None

    if not btc or not mstr:
        return None

    as_of = curr_date or datetime.now().strftime("%Y-%m-%d")
    ts = btc.get("timestamp") or mstr.get("timeStampUtc", "")

    holdings = _parse_int(btc.get("btcHoldings"))
    btc_price = _as_float(btc.get("ufPrice")) or _as_float(btc.get("latestPrice"))
    btc_nav_m = _parse_millions(btc.get("btcNav"))
    sats_per_share = btc.get("satsPerShare")

    mcap_m = _parse_millions(mstr.get("marketCap"))
    ev_m = _parse_millions(mstr.get("entVal"))
    debt_m = _parse_millions(mstr.get("debt"))
    pref_m = _parse_millions(mstr.get("pref"))

    mnav_basic = (mcap_m / btc_nav_m) if mcap_m and btc_nav_m else None
    mnav_ev = (ev_m / btc_nav_m) if ev_m and btc_nav_m else None
    premium = ((mnav_basic - 1) * 100) if mnav_basic is not None else None
    btc_per_share = (sats_per_share / 100_000_000) if sats_per_share else None

    lines = [
        f"# Strategy (MSTR) 官方国库数据",
        "",
        f"**分析标的**: {code}",
        f"**数据日期**: {as_of}",
        f"**API 更新时间**: {ts}",
        f"**数据来源**: [strategy.com](https://www.strategy.com/) 官方 API (`api.strategy.com`)",
        "",
        "## 比特币持仓 (Bitcoin KPIs)",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| BTC 持仓量 | {holdings:,} BTC |" if holdings else "| BTC 持仓量 | N/A |",
        f"| 占 BTC 总供应量 | {btc.get('pctOfBtcTotalSupply', 'N/A')}% |",
        f"| BTC 现价 | ${btc_price:,.0f} |" if btc_price else "| BTC 现价 | N/A |",
        f"| 比特币 NAV | {_fmt_millions(btc_nav_m)} |",
        f"| Satoshis / 股 | {sats_per_share:,.1f} |" if sats_per_share else "| Satoshis / 股 | N/A |",
        f"| BTC / 股 (BPS) | {btc_per_share:.6f} BTC |" if btc_per_share else "| BTC / 股 | N/A |",
        f"| BTC Gain (QTD) | {_fmt_millions(_parse_millions(btc.get('btcGainQtd')))} |",
        f"| BTC Gain (YTD) | {_fmt_millions(_parse_millions(btc.get('btcGainYTD')))} |",
        f"| 债务 / BTC NAV | {btc.get('debtByBN', 'N/A')}% |",
        f"| 优先股 / BTC NAV | {btc.get('prefByBN', 'N/A')}% |",
        f"| 股息保障 (BTC年数) | {btc.get('btcYearsOfDividends', 'N/A'):.1f} 年 |"
        if btc.get("btcYearsOfDividends") is not None
        else "| 股息保障 (BTC年数) | N/A |",
        f"| USD 储备可覆盖股息月数 | {btc.get('usdMonthsOfDividends', 'N/A'):.1f} 月 |"
        if btc.get("usdMonthsOfDividends") is not None
        else "| USD 储备可覆盖股息月数 | N/A |",
        f"| 年化股息支出 | ${btc.get('totalAnnualDividends', 0) / 1e9:.2f}B |"
        if btc.get("totalAnnualDividends")
        else "| 年化股息支出 | N/A |",
        "",
        "## MSTR 估值与 mNAV",
        "| 指标 | 数值 | 说明 |",
        "|------|------|------|",
        f"| MSTR 股价 | ${mstr.get('price', 'N/A')} |",
        f"| 日涨跌 | {_fmt_pct(mstr.get('priceVarPerc'))} |",
        f"| 市值 | {_fmt_millions(mcap_m)} |",
        f"| 企业价值 (EV) | {_fmt_millions(ev_m)} |",
        f"| 债务 | {_fmt_millions(debt_m)} |",
        f"| 优先股 (账面) | {_fmt_millions(pref_m)} |",
        f"| 债务+优先股/市值 | {mstr.get('debtPrefByMC', 'N/A')}% |",
        f"| **mNAV (Basic)** | **{mnav_basic:.3f}×** | 市值 ÷ 比特币 NAV |" if mnav_basic else "| mNAV (Basic) | N/A |",
        f"| **mNAV (EV)** | **{mnav_ev:.3f}×** | 企业价值 ÷ 比特币 NAV |" if mnav_ev else "| mNAV (EV) | N/A |",
        f"| 相对 NAV 溢价/折价 | {premium:+.1f}% | (mNAV Basic - 1) × 100 |" if premium is not None else "| 相对 NAV 溢价/折价 | N/A |",
        f"| 3 个月回报 | {_fmt_pct(mstr.get('threeMonth'))} |",
        f"| 1 年回报 | {_fmt_pct(mstr.get('oneYear'))} |",
        f"| 历史波动率 (30D) | {mstr.get('historicVolatility', 'N/A')}% |",
        f"| 年化波动率 | {mstr.get('annualizedVolatility', 'N/A')}% |",
        "",
        "## MSTR 期权市场",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总未平仓 (OI) | {options.get('totalOi', 'N/A')} |",
        f"| Call OI | {options.get('callOi', 'N/A')} |",
        f"| Put OI | {options.get('putOi', 'N/A')} |",
        f"| Put/Call 比 | {options.get('putCallRatio', 'N/A')} |",
        f"| 隐含波动率 (IV) | {options.get('impliedVolatility', 'N/A')}% |",
        f"| 历史波动率 (HV) | {options.get('historicVolatility', 'N/A')}% |",
        "",
        "## Digital Credit — 优先股系列",
        "Strategy 通过 STRC/STRF/STRK/STRD 筹集资金购买 BTC，分析 MSTR 必须结合这套资本结构：",
        "",
    ]

    for pref_ticker in PREFERRED_TICKERS:
        try:
            row = fetch_pref_kpi(pref_ticker)
            if row:
                lines.extend(_format_pref_row(row))
        except Exception as exc:
            logger.warning(f"⚠️ [Strategy Official] {pref_ticker} KPI 获取失败: {exc}")
            lines.append(f"### {pref_ticker}\n数据暂不可用: {exc}\n")

    if code in PREFERRED_TICKERS:
        try:
            focus = fetch_pref_kpi(code)
            if focus:
                lines.extend([
                    f"## 当前分析标的 {code} 要点",
                    f"- 价格: ${focus.get('price', 'N/A')}",
                    f"- 有效收益率: {focus.get('effYield', 'N/A')}%",
                    f"- 与 MSTR 相关性: {focus.get('mstrCor', 'N/A')}%",
                    f"- 下一除息日: {focus.get('nextRecordDate', 'N/A')}",
                    f"- 下一派息日: {focus.get('nextPayoutDate', 'N/A')}",
                    "",
                ])
        except Exception:
            pass

    # Purchases, BTC trend, SEC 8-K, management KPIs
    try:
        from .strategy_supplemental import get_supplemental_sections

        supplemental = get_supplemental_sections()
        if supplemental:
            lines.append(supplemental)
    except Exception as exc:
        logger.warning(f"⚠️ [Strategy Official] 补充数据获取失败: {exc}")

    lines.extend([
        "## 分析框架提示",
        "- **mNAV < 1**：股价低于比特币资产净值（折价），增发普通股可能稀释",
        "- **mNAV > 1**：市场愿意为比特币敞口和融资能力付溢价",
        "- **STRC**：变量利率优先股，是近期主要 ATM 融资工具，影响 BTC 增持节奏",
        "- **Enterprise mNAV** 含债务和优先股，比 Basic mNAV 更能反映债权人视角",
        "- 持仓与 mNAV 以官网/SEC 8-K 为准；本数据来自 Strategy 官方 API",
        "",
    ])
    return "\n".join(lines)
