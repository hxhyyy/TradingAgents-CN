#!/usr/bin/env python3
"""Ping NVIDIA integrate API chat models (availability + latency only)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE_URL = "https://integrate.api.nvidia.com/v1"
PING_TIMEOUT = 120

CANDIDATES = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-4-340b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "qwen/qwen3.5-397b-a17b",
    "qwen/qwen3.5-122b-a10b",
    "qwen/qwen3-next-80b-a3b-instruct",
    "stockmark/stockmark-2-100b-instruct",
    "moonshotai/kimi-k2.6",
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v4-flash",
    "z-ai/glm-5.1",
    "meta/llama-3.3-70b-instruct",
    "openai/gpt-oss-120b",
    "writer/palmyra-fin-70b-32k",
]


def load_api_key() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CUSTOM_OPENAI_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if value and not value.startswith("your-"):
                return value
    raise RuntimeError("CUSTOM_OPENAI_API_KEY not found in .env")


def ping_model(client: httpx.Client, model: str) -> dict:
    t0 = time.perf_counter()
    try:
        r = client.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 16,
                "temperature": 0.0,
            },
            timeout=PING_TIMEOUT,
        )
        elapsed = round(time.perf_counter() - t0, 2)
        if r.status_code == 200:
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage") or {}
            return {
                "ok": True,
                "status": r.status_code,
                "elapsed_s": elapsed,
                "reply": (content or "").strip()[:120],
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
        err = r.text
        try:
            err = r.json().get("error", {}).get("message", r.text)
        except Exception:
            pass
        return {
            "ok": False,
            "status": r.status_code,
            "elapsed_s": elapsed,
            "error": str(err)[:400],
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_s": round(time.perf_counter() - t0, 2),
            "error": str(exc)[:400],
        }


def main() -> None:
    api_key = load_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    results: dict[str, dict] = {}

    with httpx.Client(headers=headers) as client:
        listed: set[str] = set()
        try:
            r = client.get(f"{BASE_URL}/models", timeout=60)
            r.raise_for_status()
            listed = {m["id"] for m in r.json().get("data", []) if m.get("id")}
        except Exception as exc:
            print(f"WARN: list models failed: {exc}")

        print(f"Ping {len(CANDIDATES)} models (timeout={PING_TIMEOUT}s each)\n")
        for model in CANDIDATES:
            entry = {"listed": model in listed if listed else None}
            probe = ping_model(client, model)
            entry["ping"] = probe
            results[model] = entry
            if probe.get("ok"):
                print(f"OK   {probe['elapsed_s']:>6}s  {model}  -> {probe.get('reply', '')[:40]}")
            else:
                print(f"FAIL {probe.get('elapsed_s', 0):>6}s  {model}  -> {probe.get('error', '')[:80]}")

    out_path = Path(__file__).resolve().parent / "nvidia_model_ping_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")

    ok_models = [m for m in CANDIDATES if results[m]["ping"].get("ok")]
    fail_models = [m for m in CANDIDATES if not results[m]["ping"].get("ok")]
    print(f"\nPassed: {len(ok_models)}/{len(CANDIDATES)}")
    for m in ok_models:
        print(f"  + {m} ({results[m]['ping']['elapsed_s']}s)")


if __name__ == "__main__":
    main()
