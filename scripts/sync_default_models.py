"""将系统默认模型同步为已配置 API Key 的 NVIDIA 模型。"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

DEFAULT_NEMOTRON_MODEL = "nvidia/nemotron-3-super-120b-a12b"

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
db = client[os.getenv("MONGODB_DATABASE", "tradingagentscn")]

result = db.system_configs.update_one(
    {"is_active": True},
    {
        "$set": {
            "system_settings.quick_analysis_model": DEFAULT_NEMOTRON_MODEL,
            "system_settings.deep_analysis_model": DEFAULT_NEMOTRON_MODEL,
            "system_settings.default_provider": "custom_openai",
            "system_settings.default_model": DEFAULT_NEMOTRON_MODEL,
        }
    },
)
print(f"updated: {result.modified_count}, quick/deep -> {DEFAULT_NEMOTRON_MODEL}")
