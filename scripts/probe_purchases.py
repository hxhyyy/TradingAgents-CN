#!/usr/bin/env python3
import json
import re
import httpx

H = {"User-Agent": "Mozilla/5.0"}
API = "https://api.strategy.com"

paths = [
    "/btc/bitcoinHistory",
    "/btc/strcKpiData",
    "/btc/strdKpiData",
    "/btc/strkKpiData",
    "/btc/btcPurchases",
    "/btc/purchaseHistory",
    "/btc/holdingsHistory",
    "/btc/mstrPurchases",
    "/btc/debt",
    "/btc/digitalCreditKpis",
    "/btc/btcYield",
    "/btc/kpiDashboard",
]

for p in paths:
    r = httpx.get(API + p, timeout=15, headers={**H, "Accept": "application/json"})
    print(p, r.status_code, len(r.text))
    if r.status_code == 200:
        print(r.text[:300])
    print()

r = httpx.get("https://www.strategy.com/purchases", timeout=30, headers=H)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text)
if m:
    d = json.loads(m.group(1))
    pp = d.get("props", {}).get("pageProps", {})
    print("pageProps keys:", list(pp.keys()))
    for k, v in pp.items():
        if k.lower() in ("purchases", "data", "purchasehistory", "btcdata", "initialdata"):
            print(k, type(v), str(v)[:500])
