#!/usr/bin/env python3
"""Run a quick MSTR analysis and poll until completion."""

import json
import sys
import time

import httpx

BASE = "http://localhost:8000"
POLL_INTERVAL_SEC = 10
MAX_POLLS = 90


def main() -> int:
    login = httpx.post(
        f"{BASE}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=30,
    )
    login.raise_for_status()
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    health = httpx.get(f"{BASE}/api/health", headers=headers, timeout=10)
    print(f"health: {health.status_code}")

    payload = {
        "symbol": "MSTR",
        "stock_code": "MSTR",
        "parameters": {
            "market_type": "美股",
            "analysis_date": "2026-06-29",
            "research_depth": "快速",
            "selected_analysts": ["market", "fundamentals"],
            "include_sentiment": True,
            "include_risk": True,
            "language": "zh-CN",
            "quick_analysis_model": "meta/llama-3.1-8b-instruct",
            "deep_analysis_model": "meta/llama-3.1-8b-instruct",
        },
    }
    start = httpx.post(
        f"{BASE}/api/analysis/single",
        headers=headers,
        json=payload,
        timeout=120,
    )
    print(f"start: {start.status_code}")
    print(start.text[:800])
    start.raise_for_status()

    body = start.json()
    task_id = (body.get("data") or {}).get("task_id") or body.get("task_id")
    if not task_id:
        print("No task_id in response", body)
        return 1
    print(f"task_id: {task_id}")

    for i in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL_SEC)
        status_resp = httpx.get(
            f"{BASE}/api/analysis/tasks/{task_id}/status",
            headers=headers,
            timeout=60,
        )
        if status_resp.status_code != 200:
            print(f"poll {i}: HTTP {status_resp.status_code} {status_resp.text[:200]}")
            continue

        data = status_resp.json().get("data", status_resp.json())
        status = data.get("status")
        progress = data.get("progress", data.get("progress_percentage"))
        message = data.get("message") or data.get("current_step") or ""
        print(f"poll {i}: status={status} progress={progress} {str(message)[:100]}")

        if status in ("completed", "success", "failed", "error", "cancelled"):
            print("--- final ---")
            print(json.dumps(data, ensure_ascii=False, default=str)[:3000])
            if status in ("completed", "success"):
                result = httpx.get(
                    f"{BASE}/api/analysis/tasks/{task_id}/result",
                    headers=headers,
                    timeout=60,
                )
                if result.status_code == 200:
                    rdata = result.json().get("data", result.json())
                    summary = rdata.get("summary") or rdata.get("recommendation") or str(rdata)[:500]
                    print("--- result excerpt ---")
                    print(str(summary)[:800])
            return 0 if status in ("completed", "success") else 2

    print("Timed out waiting for task")
    return 3


if __name__ == "__main__":
    sys.exit(main())
