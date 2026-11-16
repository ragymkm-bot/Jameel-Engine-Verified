from task_router import route_task

# تشغيل الدالة
result = route_task("احتاج كود برمجي سريع", priority="high")
print(f"Result: {result}")

# قراءة آخر سطر في السجل للتأكد
with open("C:/AI-Agents-Lab/runtime/audit.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    print(f"Audit log entry: {lines[-1].strip()}")
