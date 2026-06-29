#!/usr/bin/env python3
"""Update per-model timeout values in MongoDB system_configs."""

from __future__ import annotations

from pymongo import MongoClient

DB_NAME = "tradingagentscn"
MONGO_URI = "mongodb://localhost:27017/"


def timeout_for_level(level: int) -> int:
    if level >= 5:
        return 900
    if level >= 4:
        return 600
    if level >= 3:
        return 300
    return 180


def main() -> None:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    updated = 0
    samples: list[tuple[str, int | None, int]] = []

    for doc in db.system_configs.find():
        llm_configs = doc.get("llm_configs", [])
        changed = False
        for cfg in llm_configs:
            level = cfg.get("capability_level", 2)
            new_timeout = timeout_for_level(level)
            old_timeout = cfg.get("timeout")
            if old_timeout != new_timeout:
                cfg["timeout"] = new_timeout
                changed = True
                updated += 1
                if len(samples) < 8:
                    samples.append((cfg.get("model_name", "?"), old_timeout, new_timeout))
        if changed:
            db.system_configs.update_one(
                {"_id": doc["_id"]},
                {"$set": {"llm_configs": llm_configs}},
            )

    doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    ultra_timeout = None
    if doc:
        for cfg in doc.get("llm_configs", []):
            if "ultra-550b" in cfg.get("model_name", ""):
                ultra_timeout = (cfg["model_name"], cfg.get("timeout"))
                break

    print(f"Updated {updated} model timeout entries")
    for name, old, new in samples:
        print(f"  {name}: {old} -> {new}s")
    if ultra_timeout:
        print(f"Ultra 550B: {ultra_timeout[0]} timeout={ultra_timeout[1]}s")


if __name__ == "__main__":
    main()
