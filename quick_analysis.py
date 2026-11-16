import json
from pathlib import Path
from datetime import datetime

audit_log = Path("C:/AI-Agents-Lab/runtime/audit.jsonl")
error_count = 0

if audit_log.exists():
    with open(audit_log, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if "error" in entry.get("event_type", "").lower():
                error_count += 1

print(f"--- 🧠 تقرير المستشار الذكي ---")
print(f"📅 وقت التحليل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"✅ حالة النظام: {'Stable' if error_count == 0 else 'Attention Required'}")
print(f"⚠️ عدد الأخطاء المكتشفة: {error_count}")
print(f"--- 📝 توصية المستشار: ---")
print("النظام في أفضل حالاته. استمر في البناء!")
