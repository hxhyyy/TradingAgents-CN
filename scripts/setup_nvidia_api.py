#!/usr/bin/env python3
"""Sync all NVIDIA NIM models into TradingAgents-CN."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pymongo import MongoClient

API_KEY = os.getenv("NVIDIA_API_KEY") or os.getenv("CUSTOM_OPENAI_API_KEY")
BASE_URL = os.getenv("CUSTOM_OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"
DB_NAME = "tradingagentscn"
PROVIDER = "custom_openai"

NON_CHAT_KEYWORDS = (
    "embed",
    "bge-",
    "rerank",
    "reward",
    "safety",
    "guard",
    "topic-control",
    "detector",
    "gliner",
    "parse",
    "nvclip",
    "deplot",
    "diffusion",
    "arctic-embed",
    "nemoretriever",
    "nv-embed",
    "translate",
    "riva-translate",
    "ising-calibration",
    "kosmos-2",
    "nemotron-parse",
)


def _load_api_key_from_env_file() -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CUSTOM_OPENAI_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if value and not value.startswith("your-"):
                return value
    return None


def fetch_model_ids(api_key: str) -> list[str]:
    response = httpx.get(
        f"{BASE_URL.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return sorted(item["id"] for item in payload.get("data", []) if item.get("id"))


def _display_name(model_id: str) -> str:
    return model_id.split("/")[-1].replace("-", " ")


def _is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if any(keyword in lowered for keyword in NON_CHAT_KEYWORDS):
        return False
    if lowered.endswith("-embed") or "/embed-" in lowered:
        return False
    return True


def _capability_level(model_id: str) -> int:
    lowered = model_id.lower()
    if any(token in lowered for token in ("550b", "397b", "340b", "253b", "122b", "120b", "100b")):
        return 5
    if any(token in lowered for token in ("70b", "72b", "80b", "90b", "675b", "49b", "51b")):
        return 4
    if any(token in lowered for token in ("30b", "34b", "36b", "32b", "22b", "27b", "24b")):
        return 3
    if any(token in lowered for token in ("12b", "14b", "17b", "13b", "11b", "10b", "9b", "8b", "7b")):
        return 2
    return 2


def _recommended_depths(level: int) -> list[str]:
    if level <= 2:
        return ["快速", "基础", "标准"]
    if level == 3:
        return ["标准", "深度"]
    return ["深度", "全面"]


def _model_category(model_id: str, chat: bool) -> str:
    if chat:
        return "chat"
    lowered = model_id.lower()
    if "embed" in lowered or "bge-" in lowered:
        return "embedding"
    if any(token in lowered for token in ("vision", "vl", "vila", "neva", "fuyu", "phi-3-vision")):
        return "vision"
    return "utility"


def _catalog_entry(model_id: str) -> dict:
    chat = _is_chat_model(model_id)
    return {
        "name": model_id,
        "display_name": _display_name(model_id),
        "description": "NVIDIA NIM",
        "context_length": 128000,
        "max_tokens": None,
        "input_price_per_1k": 0,
        "output_price_per_1k": 0,
        "currency": "USD",
        "is_deprecated": False,
        "release_date": None,
        "capabilities": ["tool_calling"] if chat else [],
        "model_category": _model_category(model_id, chat),
    }


def _llm_config_entry(model_id: str, base_url: str) -> dict:
    chat = _is_chat_model(model_id)
    level = _capability_level(model_id)
    return {
        "provider": PROVIDER,
        "model_name": model_id,
        "model_display_name": _display_name(model_id),
        "api_key": "",
        "api_base": base_url,
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": 180 if level >= 4 else 120,
        "retry_times": 3,
        "enabled": chat,
        "description": "NVIDIA NIM",
        "model_category": _model_category(model_id, chat),
        "custom_endpoint": None,
        "enable_memory": False,
        "enable_debug": False,
        "priority": 0,
        "input_price_per_1k": 0,
        "output_price_per_1k": 0,
        "currency": "USD",
        "capability_level": level,
        "suitable_roles": ["both"],
        "features": ["tool_calling"] if chat else [],
        "recommended_depths": _recommended_depths(level),
        "performance_metrics": {
            "speed": 4 if level <= 2 else 2,
            "cost": 5,
            "quality": level,
        },
    }


def _ensure_system_llm_configs(db, base_url: str, model_ids: list[str]) -> tuple[int, int]:
    cfg = db.system_configs.find_one({"is_active": True}) or db.system_configs.find_one(
        {"config_name": "默认配置"}, sort=[("version", -1)]
    )
    if not cfg:
        return 0, 0

    kept = [
        item
        for item in cfg.get("llm_configs", [])
        if item.get("provider") != PROVIDER
    ]
    nvidia_configs = [_llm_config_entry(model_id, base_url) for model_id in model_ids]
    chat_count = sum(1 for item in nvidia_configs if item["enabled"])

    db.system_configs.update_one(
        {"_id": cfg["_id"]},
        {
            "$set": {
                "llm_configs": kept + nvidia_configs,
                "quick_analysis_model": DEFAULT_MODEL,
                "deep_analysis_model": DEFAULT_MODEL,
                "default_provider": PROVIDER,
                "default_model": DEFAULT_MODEL,
            }
        },
    )
    return len(nvidia_configs), chat_count


def main() -> None:
    api_key = API_KEY or _load_api_key_from_env_file()
    if not api_key or api_key.startswith("your-"):
        raise SystemExit("Set NVIDIA_API_KEY or CUSTOM_OPENAI_API_KEY before running.")

    model_ids = fetch_model_ids(api_key)
    if not model_ids:
        raise SystemExit("No models returned from NVIDIA API.")

    now = datetime.now(timezone.utc).isoformat()
    db = MongoClient("mongodb://localhost:27017/")[DB_NAME]
    catalog_models = [_catalog_entry(model_id) for model_id in model_ids]

    db.llm_providers.update_one(
        {"name": PROVIDER},
        {
            "$set": {
                "name": PROVIDER,
                "display_name": "NVIDIA NIM",
                "description": "NVIDIA integrate.api.nvidia.com OpenAI-compatible API",
                "website": "https://build.nvidia.com",
                "api_doc_url": "https://docs.api.nvidia.com/nim/reference/llm-apis",
                "default_base_url": BASE_URL,
                "is_active": True,
                "api_key": api_key,
                "supported_features": [
                    "chat",
                    "completion",
                    "streaming",
                    "function_calling",
                ],
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    db.model_catalog.update_one(
        {"provider": PROVIDER},
        {
            "$set": {
                "provider": PROVIDER,
                "provider_name": "NVIDIA NIM",
                "models": catalog_models,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    db.platform_configs.update_one(
        {"config_type": "llm", "provider": PROVIDER},
        {
            "$set": {
                "config_type": "llm",
                "provider": PROVIDER,
                "api_key": api_key,
                "is_active": True,
                "config_data": {
                    "model": DEFAULT_MODEL,
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "base_url": BASE_URL,
                },
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    db.system_configs.update_many(
        {},
        {"$set": {"default_provider": PROVIDER, "default_model": DEFAULT_MODEL}},
    )
    total, chat_count = _ensure_system_llm_configs(db, BASE_URL, model_ids)

    cache_path = Path(__file__).resolve().parent.parent / "tmp" / "nvidia_models.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(model_ids, indent=2, ensure_ascii=False), encoding="utf-8")

    print("NVIDIA NIM sync completed")
    print(f"  total models: {total}")
    print(f"  chat-enabled: {chat_count}")
    print(f"  non-chat catalog only: {total - chat_count}")
    print(f"  default model: {DEFAULT_MODEL}")
    print(f"  cache: {cache_path}")


if __name__ == "__main__":
    main()
