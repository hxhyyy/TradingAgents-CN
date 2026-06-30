#!/usr/bin/env python3
"""Configure Alpha Vantage API key in MongoDB system_configs."""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync


def main() -> None:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set ALPHA_VANTAGE_API_KEY in .env first")

    db = get_mongo_db_sync()
    now = datetime.now(timezone.utc)

    cfg = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    if not cfg:
        raise SystemExit("ERROR: no active system_configs")

    configs = cfg.get("data_source_configs", [])
    updated = False
    for ds in configs:
        if ds.get("type") == "alpha_vantage":
            ds["api_key"] = api_key
            ds["enabled"] = True
            ds["updated_at"] = now
            updated = True
            break

    if not updated:
        configs.append(
            {
                "name": "alpha_vantage",
                "type": "alpha_vantage",
                "api_key": api_key,
                "enabled": True,
                "endpoint": "https://www.alphavantage.co/query",
                "timeout": 30,
                "rate_limit": 100,
                "priority": 3,
                "market_categories": ["us_stocks"],
                "display_name": "Alpha Vantage",
                "updated_at": now,
            }
        )

    result = db.system_configs.update_one(
        {"_id": cfg["_id"]},
        {"$set": {"data_source_configs": configs, "updated_at": now}},
    )
    print(f"MongoDB update modified: {result.modified_count}")

    from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key
    from tradingagents.dataflows.providers.us.alpha_vantage_news import get_news

    key = get_api_key()
    print(f"get_api_key OK, length={len(key)}")

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=7)).isoformat()
    news = get_news("MSTR", start, end)
    print(f"MSTR news test length: {len(news)}")
    print(news[:400])


if __name__ == "__main__":
    main()
