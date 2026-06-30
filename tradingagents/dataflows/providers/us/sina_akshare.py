#!/usr/bin/env python3
"""
新浪财经美股数据（通过 AKShare）

数据来源：
- stock_us_daily: 新浪财经美股历史日线
- stock_us_spot: 新浪财经美股实时行情（可选，需拉取全量列表）
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

SINA_SOURCE_NAME = "sina"


def is_available() -> bool:
    try:
        import akshare  # noqa: F401
        return True
    except ImportError:
        return False


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper().replace(".", "")


def fetch_daily_df(symbol: str, adjust: str = "") -> pd.DataFrame:
    """获取新浪财经美股日线数据"""
    import akshare as ak

    code = normalize_symbol(symbol)
    df = ak.stock_us_daily(symbol=code, adjust=adjust)
    if df is None or df.empty:
        raise ValueError(f"新浪财经未返回 {code} 的日线数据")

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df


def _latest_bar(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1]


def _previous_bar(df: pd.DataFrame) -> Optional[pd.Series]:
    if len(df) < 2:
        return None
    return df.iloc[-2]


def get_us_quote(symbol: str) -> Dict[str, Any]:
    """从新浪日线的最新一根K线构造行情"""
    df = fetch_daily_df(symbol)
    latest = _latest_bar(df)
    prev = _previous_bar(df)

    close = float(latest["close"])
    prev_close = float(prev["close"]) if prev is not None else close
    change = close - prev_close
    change_percent = (change / prev_close * 100) if prev_close else 0.0

    trade_date = latest["date"]
    if hasattr(trade_date, "strftime"):
        trade_date_str = trade_date.strftime("%Y-%m-%d")
    else:
        trade_date_str = str(trade_date)[:10]

    return {
        "name": f"美股{normalize_symbol(symbol)}",
        "price": close,
        "open": float(latest["open"]),
        "high": float(latest["high"]),
        "low": float(latest["low"]),
        "volume": int(float(latest["volume"])),
        "change_percent": round(change_percent, 2),
        "trade_date": trade_date_str,
        "currency": "USD",
    }


def get_us_kline(symbol: str, period: str = "day", limit: int = 120) -> List[Dict[str, Any]]:
    """获取新浪美股K线（目前支持日K）"""
    if period not in ("day", "daily", "1d", "d"):
        raise ValueError(f"新浪财经暂不支持周期: {period}")

    df = fetch_daily_df(symbol)
    df = df.tail(limit)

    kline_data: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        kline_data.append(
            {
                "date": date_str,
                "trade_date": date_str,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(float(row["volume"])),
            }
        )
    return kline_data


def get_us_info(symbol: str) -> Dict[str, Any]:
    """从新浪日线数据提取基础信息"""
    df = fetch_daily_df(symbol)
    latest = _latest_bar(df)
    code = normalize_symbol(symbol)

    lookback = df.tail(min(len(df), 252))
    high_52w = float(lookback["high"].max())
    low_52w = float(lookback["low"].min())
    avg_volume = float(lookback["volume"].mean())

    return {
        "name": f"美股{code}",
        "industry": None,
        "sector": None,
        "market_cap": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "dividend_yield": None,
        "currency": "USD",
        "latest_price": float(latest["close"]),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "avg_volume_252d": avg_volume,
    }


def _pct_change(current: float, past: float) -> Optional[float]:
    if past is None or past == 0:
        return None
    return round((current - past) / past * 100, 2)


def get_fundamentals(symbol: str, curr_date: str) -> str:
    """生成基于新浪日线数据的基本面/行情分析报告"""
    code = normalize_symbol(symbol)
    df = fetch_daily_df(code)
    latest = _latest_bar(df)
    prev = _previous_bar(df)

    close = float(latest["close"])
    prev_close = float(prev["close"]) if prev is not None else close
    daily_change = close - prev_close
    daily_change_pct = _pct_change(close, prev_close) or 0.0

    def price_at(offset: int) -> Optional[float]:
        if len(df) <= offset:
            return None
        return float(df.iloc[-(offset + 1)]["close"])

    periods = {
        "5日": 5,
        "20日": 20,
        "60日": 60,
        "120日": 120,
        "252日": 252,
    }
    returns = {}
    for label, offset in periods.items():
        past = price_at(offset)
        if past is not None:
            returns[label] = _pct_change(close, past)

    lookback = df.tail(min(len(df), 252))
    high_52w = float(lookback["high"].max())
    low_52w = float(lookback["low"].min())
    avg_volume = float(lookback["volume"].mean())
    ma5 = float(df["close"].tail(5).mean()) if len(df) >= 5 else close
    ma20 = float(df["close"].tail(20).mean()) if len(df) >= 20 else close
    ma60 = float(df["close"].tail(60).mean()) if len(df) >= 60 else close

    trade_date = latest["date"]
    if hasattr(trade_date, "strftime"):
        trade_date_str = trade_date.strftime("%Y-%m-%d")
    else:
        trade_date_str = str(trade_date)[:10]

    report = f"""# {code} 美股基本面数据 (来源: 新浪财经)

## 最新行情
| 指标 | 数值 |
|------|------|
| 最新收盘价 | ${close:.2f} |
| 交易日期 | {trade_date_str} |
| 开盘价 | ${float(latest['open']):.2f} |
| 最高价 | ${float(latest['high']):.2f} |
| 最低价 | ${float(latest['low']):.2f} |
| 成交量 | {int(float(latest['volume'])):,} |
| 日涨跌 | ${daily_change:+.2f} ({daily_change_pct:+.2f}%) |

## 区间表现（截至 {curr_date}）
| 周期 | 涨跌幅 |
|------|--------|
"""
    for label, value in returns.items():
        if value is not None:
            report += f"| {label} | {value:+.2f}% |\n"

    report += f"""
## 价格区间与均线
| 指标 | 数值 |
|------|------|
| 52周最高 | ${high_52w:.2f} |
| 52周最低 | ${low_52w:.2f} |
| 距52周高点 | {_pct_change(close, high_52w) or 0:+.2f}% |
| 距52周低点 | {_pct_change(close, low_52w) or 0:+.2f}% |
| MA5 | ${ma5:.2f} |
| MA20 | ${ma20:.2f} |
| MA60 | ${ma60:.2f} |
| 252日平均成交量 | {avg_volume:,.0f} |

## 最近5个交易日
| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |
|------|------|------|------|------|--------|
"""
    for _, row in df.tail(5).iterrows():
        d = row["date"].strftime("%Y-%m-%d")
        report += (
            f"| {d} | ${float(row['open']):.2f} | ${float(row['high']):.2f} | "
            f"${float(row['low']):.2f} | ${float(row['close']):.2f} | "
            f"{int(float(row['volume'])):,} |\n"
        )

    report += """
## 数据说明
- 本报告使用新浪财经美股日线数据（通过 AKShare `stock_us_daily`）
- 行情数据通常有 15 分钟延迟
- 财务指标（PE/PB/ROE 等）需结合财报数据源补充分析

"""
    return report


def get_historical_data_text(symbol: str, start_date: str, end_date: str) -> Optional[str]:
    """获取指定日期区间的新浪美股历史数据文本"""
    df = fetch_daily_df(symbol)
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    filtered = df[(df["date"] >= start) & (df["date"] <= end)]
    if filtered.empty:
        return None

    data = filtered.copy()
    data = data.set_index("date")
    data = data.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    from tradingagents.tools.analysis.indicators import add_all_indicators

    data = add_all_indicators(data, close_col="Close", high_col="High", low_col="Low")
    latest = data.iloc[-1]
    latest_price = float(latest["Close"])
    first_price = float(data["Close"].iloc[0])
    price_change = latest_price - first_price
    price_change_pct = (price_change / first_price * 100) if first_price else 0

    code = normalize_symbol(symbol)
    result = f"""# {code} 美股数据分析

## 基本信息
- 股票代码: {code}
- 数据期间: {start_date} 至 {end_date}
- 数据条数: {len(data)}条
- 最新价格: ${latest_price:.2f}
- 期间涨跌: ${price_change:+.2f} ({price_change_pct:+.2f}%)

## 价格统计
- 期间最高: ${data['High'].max():.2f}
- 期间最低: ${data['Low'].min():.2f}
- 平均成交量: {data['Volume'].mean():,.0f}

## 技术指标（最新值）
**移动平均线**:
- MA5: ${latest['ma5']:.2f}
- MA10: ${latest['ma10']:.2f}
- MA20: ${latest['ma20']:.2f}
- MA60: ${latest['ma60']:.2f}

**MACD指标**:
- DIF: {latest['macd_dif']:.2f}
- DEA: {latest['macd_dea']:.2f}
- MACD: {latest['macd']:.2f}

**RSI指标**:
- RSI(14): {latest['rsi']:.2f}

**布林带**:
- 上轨: ${latest['boll_upper']:.2f}
- 中轨: ${latest['boll_mid']:.2f}
- 下轨: ${latest['boll_lower']:.2f}

## 最近5日数据
{data[['Open', 'High', 'Low', 'Close', 'Volume']].tail().to_string()}

数据来源: 新浪财经 (AKShare)
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return result
