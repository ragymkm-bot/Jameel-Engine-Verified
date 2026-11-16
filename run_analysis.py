from pathlib import Path
from ragy_agents.analyst_agent import AnalystAgent

audit_log = Path("C:/AI-Agents-Lab/runtime/audit.jsonl")
analyst = AnalystAgent(audit_log)
report = analyst.analyze_health()

print(f"--- 🧠 تقرير المستشار الذكي ---")
print(f"📅 وقت التحليل: 2026-11-15")
print(f"✅ حالة النظام: {report['status']}")
print(f"⚠️ عدد الأخطاء المكتشفة: {report['error_count']}")
print(f"--- 📝 توصية المستشار: ---")
if report['error_count'] == 0:
    print("النظام في أفضل حالاته. استمر في البناء!")
else:
    print("نحتاج لمراجعة سجلات الأخطاء. هل أبدأ في استخراج تفاصيل هذه الأخطاء؟")
