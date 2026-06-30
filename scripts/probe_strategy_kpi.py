#!/usr/bin/env python3
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
BASES = [
    "https://www.strategy.com",
    "https://api.strategy.com",
]
PATHS = [
    "/btc/mstrKpiData",
    "/mstrKpiData",
    "/bitcoinKpis",
    "/btc/bitcoinKpis",
    "/btc/mstrOptionsData",
    "/btc/strfKpiData",
    "/btc/strcKpiData",
    "/btc/strdKpiData",
    "/btc/strkKpiData",
]

def main():
    for base in BASES:
        for path in PATHS:
            url = base + path
            try:
                r = httpx.get(url, timeout=15, headers=HEADERS)
                ct = r.headers.get("content-type", "")
                preview = r.text[:200].replace("\n", " ")
                print(f"{url}\n  {r.status_code} {ct}\n  {preview}\n")
            except Exception as e:
                print(f"{url}\n  ERR {e}\n")

if __name__ == "__main__":
    main()
