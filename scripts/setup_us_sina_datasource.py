#!/usr/bin/env python3
"""Configure US stock market data to use Sina (AKShare) as primary source."""

import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync


def main() -> None:
    db = get_mongo_db_sync()
    now = datetime.now(timezone.utc)

    # Enable Sina as the only active US market data source for technical analysis
    for name in ("sina", "akshare"):
        db.datasource_groupings.update_one(
            {"market_category_id": "us_stocks", "data_source_name": name},
            {
                "$set": {
                    "market_category_id": "us_stocks",
                    "data_source_name": name,
                    "priority": 100,
                    "enabled": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    # Disable sources that cannot provide full historical K-line data for TA
    disable_names = [
        "Finnhub",
        "finnhub",
        "Yahoo Finance",
        "yahoo_finance",
        "yfinance",
        "Alpha Vantage",
        "alpha_vantage",
    ]
    result = db.datasource_groupings.update_many(
        {"market_category_id": "us_stocks", "data_source_name": {"$in": disable_names}},
        {"$set": {"enabled": False, "updated_at": now}},
    )

    print(f"Disabled {result.modified_count} legacy US data source groupings")
    print("Enabled: sina, akshare (priority 100)")
    print("\nCurrent us_stocks groupings:")
    for g in db.datasource_groupings.find({"market_category_id": "us_stocks"}).sort(
        "priority", -1
    ):
        status = "ON" if g.get("enabled") else "OFF"
        print(
            f"  [{status}] {g.get('data_source_name')} "
            f"(priority={g.get('priority')})"
        )


if __name__ == "__main__":
    main()
