"""Binance 公开 API — 最小版比特币（BTCUSDT）行情数据。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from tradingagents.utils.logging_init import get_logger

logger = get_logger("agents")

BINANCE_API_BASE = "https://api.binance.com"
SUPPORTED_SYMBOLS = {"BTC", "BTCUSDT"}
DEFAULT_PAIR = "BTCUSDT"
REQUEST_TIMEOUT = 30.0


def normalize_crypto_symbol(symbol: str) -> str:
    """将 BTC / BTCUSDT 规范为 Binance 交易对 BTCUSDT。"""
    cleaned = str(symbol).strip().upper().replace("/", "").replace("-", "")
    if cleaned in SUPPORTED_SYMBOLS:
        return DEFAULT_PAIR
    raise ValueError(f"不支持的加密货币代码: {symbol}，当前仅支持 BTC / BTCUSDT")


def is_supported_crypto(symbol: str) -> bool:
    try:
        normalize_crypto_symbol(symbol)
        return True
    except ValueError:
        return False


def _date_to_ms(date_str: str, end_of_day: bool = False) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _fetch_klines(pair: str, start_date: str, end_date: str) -> List[list]:
    params = {
        "symbol": pair,
        "interval": "1d",
        "startTime": _date_to_ms(start_date),
        "endTime": _date_to_ms(end_date, end_of_day=True),
        "limit": 1000,
    }
    response = httpx.get(
        f"{BINANCE_API_BASE}/api/v3/klines",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _fetch_24hr_ticker(pair: str) -> dict:
    response = httpx.get(
        f"{BINANCE_API_BASE}/api/v3/ticker/24hr",
        params={"symbol": pair},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def get_market_analyst_lookback_days() -> int:
    """与 A股/美股/港股共用 MARKET_ANALYST_LOOKBACK_DAYS 配置。"""
    try:
        from app.core.config import get_settings
        return int(get_settings().MARKET_ANALYST_LOOKBACK_DAYS)
    except Exception:
        return 365


def resolve_crypto_date_range(end_date: str, lookback_days: int | None = None) -> tuple[str, str]:
    """按市场分析师配置，将日期范围扩展到指定回溯天数。"""
    from tradingagents.utils.dataflow_utils import get_trading_date_range

    if lookback_days is None:
        lookback_days = get_market_analyst_lookback_days()
    return get_trading_date_range(end_date, lookback_days=lookback_days)


def get_crypto_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    auto_expand: bool = True,
) -> str:
    """获取比特币日线行情与技术指标摘要（文本，供 LLM 使用）。"""
    pair = normalize_crypto_symbol(symbol)

    original_start_date = start_date
    original_end_date = end_date
    if auto_expand:
        lookback_days = get_market_analyst_lookback_days()
        start_date, end_date = resolve_crypto_date_range(end_date, lookback_days)
        logger.info(
            f"₿ [Binance] 日期扩展: {original_start_date}~{original_end_date} "
            f"-> {start_date}~{end_date} (回溯{lookback_days}天)"
        )
    else:
        logger.info(f"₿ [Binance] 获取行情: {pair}, {start_date} ~ {end_date}")

    klines = _fetch_klines(pair, start_date, end_date)
    if not klines:
        return f"❌ 未获取到 {pair} 在 {start_date} 至 {end_date} 期间的 K 线数据"

    ticker = _fetch_24hr_ticker(pair)

    closes: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    volumes: List[float] = []
    for row in klines:
        o, h, l, c, vol = map(float, row[1:6])
        closes.append(c)
        highs.append(h)
        lows.append(l)
        volumes.append(vol)

    latest_close = closes[-1] if closes else float(ticker.get("lastPrice", 0))
    first_close = closes[0] if closes else latest_close
    period_change = latest_close - first_close
    period_change_pct = (period_change / first_close * 100) if first_close else 0.0

    lines = [
        f"# {pair} 加密货币市场数据（Binance）",
        "",
        f"**交易对**: {pair}",
        f"**分析区间**: {start_date} 至 {end_date}",
        f"**日K数量**: {len(klines)} 根",
        f"**最新价 (USDT)**: {float(ticker.get('lastPrice', 0)):,.2f}",
        f"**区间涨跌**: {period_change:+,.2f} USDT ({period_change_pct:+.2f}%)",
        f"**24h 涨跌**: {float(ticker.get('priceChangePercent', 0)):+.2f}%",
        f"**24h 最高**: {float(ticker.get('highPrice', 0)):,.2f}",
        f"**24h 最低**: {float(ticker.get('lowPrice', 0)):,.2f}",
        f"**24h 成交量 (BTC)**: {float(ticker.get('volume', 0)):,.4f}",
        f"**24h 成交额 (USDT)**: {float(ticker.get('quoteVolume', 0)):,.2f}",
        "",
        "## 区间统计",
        f"- 区间最高: {max(highs):,.2f} USDT" if highs else "- 区间最高: N/A",
        f"- 区间最低: {min(lows):,.2f} USDT" if lows else "- 区间最低: N/A",
        f"- 平均成交量: {sum(volumes) / len(volumes):,.4f} BTC" if volumes else "- 平均成交量: N/A",
        "",
        "## 移动平均线（基于全部日K）",
    ]

    for window in (5, 10, 20, 60):
        if len(closes) >= window:
            ma = sum(closes[-window:]) / window
            lines.append(f"- MA{window}: {ma:,.2f} USDT")

    if len(closes) >= 14:
        gains, losses = [], []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            lines.extend(["", "## 技术指标", f"- RSI(14): {rsi:.2f}"])

    lines.extend(
        [
            "",
            "## 最近5日 K 线",
            "",
            "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量(BTC) |",
            "|------|------|------|------|------|-------------|",
        ]
    )

    for row in klines[-5:]:
        ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        o, h, l, c, vol = map(float, row[1:6])
        lines.append(f"| {ts} | {o:,.2f} | {h:,.2f} | {l:,.2f} | {c:,.2f} | {vol:,.4f} |")

    lines.append("")
    lines.append("*数据来源: Binance 公开 API*")
    return "\n".join(lines)


def get_crypto_fundamentals_summary(symbol: str) -> str:
    """比特币无传统财报，返回链上交易市场概况。"""
    pair = normalize_crypto_symbol(symbol)
    ticker = _fetch_24hr_ticker(pair)

    return f"""# {pair} 加密货币基本面概况

**说明**: 比特币无传统上市公司财报（无 P/E、营收、利润率），以下为交易市场与流动性指标。

| 指标 | 数值 |
|------|------|
| 最新价 (USDT) | {float(ticker.get('lastPrice', 0)):,.2f} |
| 24h 涨跌 | {float(ticker.get('priceChangePercent', 0)):+.2f}% |
| 24h 成交量 (BTC) | {float(ticker.get('volume', 0)):,.4f} |
| 24h 成交额 (USDT) | {float(ticker.get('quoteVolume', 0)):,.2f} |
| 24h 最高价 | {float(ticker.get('highPrice', 0)):,.2f} |
| 24h 最低价 | {float(ticker.get('lowPrice', 0)):,.2f} |
| 加权均价 | {float(ticker.get('weightedAvgPrice', 0)):,.2f} |

### 分析提示
- 关注宏观流动性、美元走势、ETF 资金流、减半周期与链上持仓分布
- 高波动资产，需结合止损与仓位管理

*数据来源: Binance 公开 API*
"""
