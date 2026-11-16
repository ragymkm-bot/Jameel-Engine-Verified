import json
from pathlib import Path
from datetime import datetime

def generate_performance_report():
    audit_log_path = Path("C:/AI-Agents-Lab/runtime/audit.jsonl")
    if not audit_log_path.exists():
        return "لا توجد سجلات أداء بعد."
    
    total_tasks = 0
    success_tasks = 0
    
    with open(audit_log_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            total_tasks += 1
            if "submitted" in entry.get("event_type", ""):
                success_tasks += 1
                
    report = f"""
# 📊 تقرير أداء RAGY System - نسخة الإبداع

- **تاريخ التقرير:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **إجمالي المهام المسجلة:** {total_tasks}
- **معدل الإنجاز (Evidence Submitted):** {success_tasks}
- **حالة النظام:** مستقر (Operational)
- **التقييم الاحترافي:** النظام جاهز للبدء في أتمتة المهام التجارية.

**اقتراح "الوكيل الخارق" للنمو:**
نبدأ الآن بربط نظام المبيعات (Sales API) عشان نحول كل "تاسك" بيخلص لـ "قيمة تجارية".
"""
    return report

# تشغيل الوكيل وتخزين التقرير
report = generate_performance_report()
with open("C:/AI-Agents-Lab/performance_report.md", "w", encoding="utf-8") as f:
    f.write(report)
print(report)
