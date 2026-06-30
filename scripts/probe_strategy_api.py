#!/usr/bin/env python3
import re
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingAgents/1.0"}
BASE = "https://www.strategy.com"


def scan_js_chunks():
    r = httpx.get(f"{BASE}/", timeout=30, headers=HEADERS, follow_redirects=True)
    scripts = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', r.text)
    keywords = ["bitcoin", "mnav", "holdings", "metrics", "massive", "api."]
    found_urls = set()
    found_paths = set()
    for path in scripts:
        url = BASE + path
        try:
            js = httpx.get(url, timeout=20, headers=HEADERS).text
            if not any(k in js.lower() for k in keywords):
                continue
            print("HIT", path, "len", len(js))
            for m in re.findall(r"https://[a-zA-Z0-9._/-]{10,120}", js):
                if any(k in m.lower() for k in ["api", "btc", "bitcoin", "metric", "massive", "strategy"]):
                    found_urls.add(m)
            for m in re.findall(r'"(/[a-zA-Z0-9/_-]{5,80})"', js):
                if any(k in m.lower() for k in ["api", "btc", "bitcoin", "metric", "data"]):
                    found_paths.add(m)
        except Exception as exc:
            print("fail", path, exc)
    print("\nURLs:")
    for u in sorted(found_urls):
        print(" ", u)
    print("\nPaths:")
    for p in sorted(found_paths):
        print(" ", p)


def probe_paths():
    paths = [
        "/data",
        "/btc",
        "/learn",
        "/purchases",
        "/notes",
    ]
    for p in paths:
        try:
            rr = httpx.get(BASE + p, timeout=20, headers=HEADERS)
            print(p, rr.status_code, "len", len(rr.text))
            if "__NEXT_DATA__" in rr.text:
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', rr.text)
                if m:
                    print("  has __NEXT_DATA__", len(m.group(1)))
        except Exception as exc:
            print(p, "ERR", exc)


def main():
    scan_js_chunks()
    print("\n--- pages ---")
    probe_paths()


if __name__ == "__main__":
    main()
