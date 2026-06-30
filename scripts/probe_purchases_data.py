#!/usr/bin/env python3
import json
import re
import httpx

r = httpx.get("https://www.strategy.com/purchases", timeout=30, headers={"User-Agent": "Mozilla/5.0"})
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text)
d = json.loads(m.group(1))
pp = d["props"]["pageProps"]
bd = pp.get("bitcoinData", [])
print("bitcoinData len", len(bd))
if bd:
    print("first:", json.dumps(bd[0], indent=2)[:800])
    print("last:", json.dumps(bd[-1], indent=2)[:800])
    print("last 5:")
    for row in bd[-5:]:
        print(row)
