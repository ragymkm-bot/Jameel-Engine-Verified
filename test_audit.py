from pathlib import Path
from ragy_agents.orchestrator import CoreOrchestrator
from ragy_agents.models import AgentRole
import json

# إعداد المسارات
project_root = Path("C:/AI-Agents-Lab")
data_dir = project_root / "runtime"

# تشغيل المنسق
orch = CoreOrchestrator(project_root, data_dir)

# 1. إنشاء مهمة
task, approval = orch.create_planned_task("اختبار التدقيق", "التحقق من سجل التدقيق أثناء التنفيذ")
print(f"Task ID: {task.task_id}")

# 2. الاعتماد
orch.grant_human_approval(approval.request_id, "Admin")

# 3. الإسناد للباحث
orch.assign_approved_task(task.task_id, AgentRole.RESEARCH)

# 4. التنفيذ
task = orch.dispatch_assigned_task(task.task_id)
print(f"Task State: {task.state}")

# 5. قراءة آخر سطر في سجل التدقيق
with open(data_dir / "audit.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    print("Last audit log entry:")
    print(lines[-1])
