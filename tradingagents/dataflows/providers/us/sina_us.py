"""
新浪财经美股日线（在线 API，与看盘插件同源思路）。

- 实时报价: hq.sinajs.cn/list=usr_{symbol}
- 历史日线: stock2.finance.sina.com.cn/.../US_MinKService.getDailyK

每次请求均走 HTTP 在线拉取，不读本地 CSV。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

_SINA_DAILY_K_URL = (
    "https://stock2.finance.sina.com.cn/usstock/api/json.php/"
    "US_MinKService.getDailyK"
)
_SINA_QUOTE_URL = "https://hq.sinajs.cn/list=usr_{symbol}"
_EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().strip().split(".")[-1]


def _parse_yyyy_mm_dd(value: str) -> datetime:
    return datetime.strptime(value[:10], "%Y-%m-%d")


def fetch_us_daily_ohlcv_sina(
    symbol: str,
    start_date: str,
    end_date: str,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """从新浪财经在线拉取美股日线 OHLCV。"""
    symbol = _normalize_symbol(symbol)
    start_dt = _parse_yyyy_mm_dd(start_date)
    end_dt = _parse_yyyy_mm_dd(end_date)

    response = requests.get(
        _SINA_DAILY_K_URL,
        params={"symbol": symbol},
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    rows = json.loads(response.text)
    if not rows:
        raise RuntimeError(f"新浪无 {symbol} 日线数据")

    records = []
    for row in rows:
        day = row.get("d")
        if not day:
            continue
        bar_dt = _parse_yyyy_mm_dd(day)
        if bar_dt < start_dt or bar_dt > end_dt:
            continue
        records.append(
            {
                "Date": bar_dt,
                "Open": float(row["o"]),
                "High": float(row["h"]),
                "Low": float(row["l"]),
                "Close": float(row["c"]),
                "Volume": float(row.get("v") or 0),
            }
        )

    if not records:
        raise RuntimeError(
            f"新浪 {symbol} 在 {start_date}~{end_date} 区间内无日线数据"
        )

    df = pd.DataFrame(records).set_index("Date").sort_index()
    df.attrs["data_source"] = "sina"
    logger.info(f"✅ [新浪美股日线] {symbol}: {len(df)} 条 ({start_date}~{end_date})")
    return df


def fetch_us_daily_ohlcv_eastmoney(
    symbol: str,
    start_date: str,
    end_date: str,
    timeout: float = 20.0,
) -> pd.DataFrame:
    """东财 push2his 日线（在线备用，secid=105.{symbol}）。"""
    symbol = _normalize_symbol(symbol)
    beg = start_date.replace("-", "")
    end = end_date.replace("-", "")

    params = {
        "secid": f"105.{symbol}",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": beg,
        "end": end,
    }
    headers = {
        "User-Agent": _DEFAULT_HEADERS["User-Agent"],
        "Referer": "https://finance.eastmoney.com/",
    }
    response = requests.get(
        _EASTMONEY_KLINE_URL, params=params, headers=headers, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    klines = (payload.get("data") or {}).get("klines") or []
    if not klines:
        raise RuntimeError(f"东财无 {symbol} 日线数据")

    records = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        records.append(
            {
                "Date": _parse_yyyy_mm_dd(parts[0]),
                "Open": float(parts[1]),
                "Close": float(parts[2]),
                "High": float(parts[3]),
                "Low": float(parts[4]),
                "Volume": float(parts[5]),
            }
        )

    if not records:
        raise RuntimeError(f"东财 {symbol} 日线解析失败")

    df = pd.DataFrame(records).set_index("Date").sort_index()
    df.attrs["data_source"] = "eastmoney"
    logger.info(f"✅ [东财美股日线] {symbol}: {len(df)} 条 ({start_date}~{end_date})")
    return df


def fetch_us_daily_ohlcv(
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, str]:
    """
    在线获取美股日线：优先新浪，失败则东财。
    返回 (DataFrame, source_name)。
    """
    errors: list[str] = []
    for fetcher, name in (
        (fetch_us_daily_ohlcv_sina, "sina"),
        (fetch_us_daily_ohlcv_eastmoney, "eastmoney"),
    ):
        try:
            return fetcher(symbol, start_date, end_date), name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning(f"⚠️ [美股日线-{name}] {symbol} 失败: {exc}")

    raise RuntimeError(" | ".join(errors) or f"无法在线获取 {symbol} 美股日线")


def fetch_us_quote_sina(symbol: str, timeout: float = 10.0) -> Optional[dict]:
    """新浪财经美股实时报价（看盘插件同款 usr_ 前缀）。"""
    symbol = _normalize_symbol(symbol)
    code = f"usr_{symbol.lower()}"
    response = requests.get(
        _SINA_QUOTE_URL.format(symbol=symbol.lower()),
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.encoding = "gb18030"
    text = response.text
    if "FAILED" in text:
        return None

    import re

    match = re.search(r'="([^"]*)"', text)
    if not match:
        return None

    params = match.group(1).split(",")
    if len(params) < 11:
        return None

    price = float(params[1] or 0)
    if not price:
        return None

    return {
        "symbol": symbol,
        "name": params[0],
        "price": price,
        "open": float(params[5] or 0),
        "high": float(params[6] or 0),
        "low": float(params[7] or 0),
        "previous_close": float(params[26] if len(params) > 26 else params[10] or 0),
        "volume": float(params[10] or 0),
        "code": code,
    }
