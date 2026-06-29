"""将系统默认模型同步为金融向最强组合（NVIDIA NIM 免费可用）。"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

QUICK_MODEL = "writer/palmyra-fin-70b-32k"
DEEP_MODEL = "stockmark/stockmark-2-100b-instruct"

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
db = client[os.getenv("MONGODB_DATABASE", "tradingagentscn")]

result = db.system_configs.update_one(
    {"is_active": True},
    {
        "$set": {
            "system_settings.quick_analysis_model": QUICK_MODEL,
            "system_settings.deep_analysis_model": DEEP_MODEL,
            "system_settings.default_provider": "custom_openai",
            "system_settings.default_model": DEEP_MODEL,
        }
    },
)
print(f"updated: {result.modified_count}")
print(f"  quick -> {QUICK_MODEL}")
print(f"  deep  -> {DEEP_MODEL}")
