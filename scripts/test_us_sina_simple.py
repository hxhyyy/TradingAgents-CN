#!/usr/bin/env python3
"""简单测试：新浪财经美股数据是否正常"""

from tradingagents.dataflows.providers.us.sina_akshare import (
    get_us_quote,
    get_us_kline,
    get_fundamentals,
)
from tradingagents.dataflows.interface import get_fundamentals_openai


def main():
    code = "MSTR"
    passed = 0
    total = 3

    print("=" * 60)
    print(f"测试股票: {code}")
    print("=" * 60)

    # 1. 行情
    print("\n[1/3] 新浪行情")
    try:
        q = get_us_quote(code)
        assert q.get("price") and q["price"] > 0
        print(f"  价格: ${q['price']}")
        print(f"  日期: {q['trade_date']}")
        print(f"  涨跌: {q['change_percent']}%")
        print("  结果: OK")
        passed += 1
    except Exception as e:
        print(f"  结果: FAIL - {e}")

    # 2. K线
    print("\n[2/3] 新浪K线(最近3根)")
    try:
        bars = get_us_kline(code, "day", 3)
        assert len(bars) == 3
        for bar in bars:
            print(f"  {bar['date']} close={bar['close']} vol={bar['volume']}")
        print("  结果: OK")
        passed += 1
    except Exception as e:
        print(f"  结果: FAIL - {e}")

    # 3. 基本面
    print("\n[3/3] 基本面分析接口")
    try:
        report = get_fundamentals_openai(code, "2026-06-29")
        assert "失败" not in report and len(report) > 200
        print(f"  标题: {report.splitlines()[0]}")
        print(f"  长度: {len(report)} 字符")
        print("  结果: OK")
        passed += 1
    except Exception as e:
        print(f"  结果: FAIL - {e}")

    print("\n" + "=" * 60)
    print(f"总计: {passed}/{total} 通过")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
