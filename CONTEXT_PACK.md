# RAGY SYSTEM — CONTEXT PACK v1.0
# الصق هذا الملف في ChatGPT / أي نموذج في المتصفح ليساعدك فوراً.

## 1. هوية المشروع
- الاسم: Jameel-System (RAGY)
- النوع: منظومة أتمتة متعددة الوكلاء (Multi-Agent Orchestration)
- المطور: ragymkm-bot | etaj.me@gmail.com
- الريبو: https://github.com/ragymkm-bot/Jameel-Engine-Verified

## 2. المعمارية
User → MCP Server (list_files, read_file, safe zone) → Core Orchestrator
→ State Machine → Task Manager → Agents (Research, Developer, QA, Security, Automation)
→ Audit Log (SHA-256 hash chain) + SQLite + Webhook/Vault

## 3. قواعد الأمان (غير قابلة للكسر)
- الـ MCP يقرأ فقط من C:/AI-Agents-Lab — أي طلب لخارجه يُرفض.
- المفاتيح لا تُكتب أبداً في الشات؛ تُخزن محلياً في secrets/.vault.
- كل وكيل بصلاحية مهمته فقط (Least Privilege).
- كل حدث في audit.jsonl له بصمة مشفرة مرتبطة بالسابق.

## 4. الملفات الأساسية
- mcp_stdio_server.py  → خادم MCP الحقيقي (JSON-RPC / stdio)
- mcp_server.py        → shim توافق مع الإعدادات القديمة
- ragy_agents/orchestrator.py → المنسق
- ragy_agents/audit.py        → سجل التدقيق المشفر
- ragy_agents/decorators.py   → @audit_action لتسجيل الدوال تلقائياً
- ragy_agents/webhook_server.py → مستقبل الأوامر + /save_key للخزنة
- task_router.py       → توجيه المهام للوكيل المناسب
- .mcp.json            → إعداد ربط Claude Code
- .github/workflows/   → ci.yml (اختبار) + deploy.yml + pages.yml (واجهة أونلاين)

## 5. الحالة الحالية
- Claude: متصل بالـ MCP ويقرأ الملفات فعلياً (تم اختباره).
- GitHub: متصل ومُحدَّث.
- Audit Log: شغال.
- GitHub Pages: واجهة Dashboard أونلاين.
- Cloudflare Tunnel: متوقف (محتاج دومين/شهادة).
- ChatGPT: يُستخدم عبر هذا الملف كـ Context Pack.

## 6. تعليمات الاستخدام
اسأل أي سؤال عن الكود أو اطلب تعديلاً، وسيكون الرد مبنياً على هذه الحقيقة، لا على تخمين.
