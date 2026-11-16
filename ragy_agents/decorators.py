# ragy_agents/decorators.py
from functools import wraps
import json
from datetime import datetime

def audit_action(event_type):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # تسجيل قبل التنفيذ
            print(f"[AUDIT] Starting {event_type}...")
            result = func(*args, **kwargs)
            # تسجيل بعد التنفيذ
            with open("C:/AI-Agents-Lab/runtime/audit.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": datetime.now().isoformat(), "event": event_type, "status": "success"}) + "\n")
            return result
        return wrapper
    return decorator
