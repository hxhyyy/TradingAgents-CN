#!/usr/bin/env python3
"""Test Strategy official API integration."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.providers.us.btc_treasury import get_btc_treasury_report


def main() -> int:
    for symbol in ("MSTR", "STRC", "MARA"):
        print("=" * 60)
        print(f"Testing {symbol}")
        report = get_btc_treasury_report(symbol, "2026-06-29")
        if not report:
            print("FAIL: no report")
            continue
        checks = {
            "holdings": "BTC 持仓量" in report or "持仓" in report,
            "mnav": "mNAV" in report,
            "official": "api.strategy.com" in report or "CoinGecko" in report,
            "purchases": "购币" in report or "售币" in report,
            "sec": "SEC" in report,
            "btc_trend": "BTC 价格趋势" in report,
            "kpi": "管理层 KPI" in report,
        }
        if symbol == "MSTR":
            checks["strc"] = "STRC" in report
            checks["options"] = "期权" in report or "OI" in report
        print("checks:", checks)
        print("length:", len(report))
        print(report[:2000])
        print("...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
