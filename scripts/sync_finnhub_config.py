"""同步 Finnhub API Key 到数据库，并提高美股数据源优先级。"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
key = os.getenv("FINNHUB_API_KEY", "").strip()
if not key:
    raise SystemExit("FINNHUB_API_KEY missing in .env")

client = MongoClient(os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
db = client[os.getenv("MONGODB_DATABASE", "tradingagentscn")]

# 写入 system_configs 中的 Finnhub 配置
cfg_result = db.system_configs.update_one(
    {"is_active": True},
    {"$set": {"data_source_configs.$[finn].api_key": key}},
    array_filters=[{"finn.type": "finnhub"}],
)
print(f"system_configs finnhub key updated: {cfg_result.modified_count}")

# Finnhub 优先于 Yahoo（国内 Yahoo 常不可用）
for query in (
    {"market_category_id": "us_stocks", "data_source_name": {"$regex": "finnhub", "$options": "i"}},
    {"market_category_id": "us_stocks", "data_source_name": "finnhub"},
):
    r = db.datasource_groupings.update_many(query, {"$set": {"priority": 10, "enabled": True}})
    if r.modified_count:
        print(f"datasource_groupings finnhub priority -> 10: {r.modified_count}")

r = db.datasource_groupings.update_many(
    {"market_category_id": "us_stocks", "data_source_name": {"$regex": "yahoo", "$options": "i"}},
    {"$set": {"priority": 2, "enabled": True}},
)
print(f"yahoo priority kept at 2: {r.modified_count}")
