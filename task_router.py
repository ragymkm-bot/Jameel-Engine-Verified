import json
from datetime import datetime

from ragy_agents.decorators import audit_action

def log_event(event_type, description, priority):
    with open("C:/AI-Agents-Lab/runtime/audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": datetime.now().isoformat(), "event": event_type, "desc": description, "priority": priority}) + "\n")

@audit_action("RouteTask")
def route_task(task_description, priority="normal"):
    """نظام توجيه المهام الذكي المطور."""
    # سجل الدخول للعملية
    log_event("Routing", task_description, priority)
    
    mapping = {
        "كود": "Developer",
        "بحث": "Researcher",
        "اختبار": "QA",
        "أمن": "Security"
    }
    
    for key, role in mapping.items():
        if key in task_description:
            return f"Agent assigned: {role} | Priority: {priority}"
            
    return "Agent assigned: General Agent"
