import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import redis

load_dotenv()
db = MongoClient(os.getenv("MONGODB_URL", "mongodb://localhost:27017"))[
    os.getenv("MONGODB_DATABASE", "tradingagentscn")
]
r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), protocol=2)

print("=== recent analysis_tasks (last 5) ===")
for t in db.analysis_tasks.find().sort("start_time", -1).limit(5):
  print(json.dumps({
    "task_id": t.get("task_id"),
    "stock": t.get("stock_code") or t.get("symbol"),
    "status": t.get("status"),
    "progress": t.get("progress"),
    "message": t.get("message"),
    "start_time": str(t.get("start_time")),
    "end_time": str(t.get("end_time")),
  }, ensure_ascii=False))

task_id = "0e28b516-4244-426a-9fa4-19043c3e7905"
print(f"\n=== task {task_id} ===")
t = db.analysis_tasks.find_one({"task_id": task_id})
if t:
  print(json.dumps({
    "status": t.get("status"),
    "progress": t.get("progress"),
    "message": t.get("message"),
    "current_step": t.get("current_step"),
    "start_time": str(t.get("start_time")),
    "end_time": str(t.get("end_time")),
    "stock": t.get("stock_code"),
  }, ensure_ascii=False, indent=2))
else:
  print("not in analysis_tasks")

print("\n=== redis progress keys ===")
keys = [k.decode() for k in r.keys("progress:*")]
print(f"count={len(keys)}")
for k in sorted(keys)[-5:]:
  print(k, r.get(k).decode()[:200] if r.get(k) else None)
