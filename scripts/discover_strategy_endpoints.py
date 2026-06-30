#!/usr/bin/env python3
"""Discover all Strategy api.strategy.com endpoints from frontend JS."""
import re
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
BASE_WEB = "https://www.strategy.com"
BASE_API = "https://api.strategy.com"

def main():
    r = httpx.get(BASE_WEB + "/", timeout=30, headers=HEADERS)
    scripts = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', r.text)
    paths = set()
    for path in scripts:
        try:
            js = httpx.get(BASE_WEB + path, timeout=20, headers=HEADERS).text
            for m in re.findall(r'["\'](/btc/[a-zA-Z0-9]+)["\']', js):
                paths.add(m)
            for m in re.findall(r'["\'](btc/[a-zA-Z0-9]+)["\']', js):
                paths.add("/" + m)
        except Exception:
            pass
    print("Found paths:", sorted(paths))
    for p in sorted(paths):
        url = BASE_API + p
        try:
            resp = httpx.get(url, timeout=15, headers=HEADERS)
            preview = resp.text[:180].replace("\n", " ")
            print(f"{p} -> {resp.status_code} {preview}")
        except Exception as e:
            print(f"{p} -> ERR {e}")

if __name__ == "__main__":
    main()
