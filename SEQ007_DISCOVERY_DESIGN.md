# HERMES → CHATGPT | SEQ 007 — RAGY AUTONOMOUS EXECUTION SYSTEM
**Task ID:** ragy-external-mcp-bridge-001
**Phase:** Discovery & Design ONLY — NO IMPLEMENTATION
**Timestamp:** 2026-11-18
**Classification key:** VERIFIED / REPORTED / PROPOSED / UNKNOWN / NOT IMPLEMENTED

---

## 1) ما الذي يعمل حالياً بالفعل؟

| # | Claim | Status | Evidence | Exit |
|---|---|---|---|---|
| 1 | ragy-mcp متصل | **VERIFIED** | `hermes mcp test ragy-mcp` → `✓ Connected (2023ms)`, `✓ Tools discovered: 2` | 0 |
| 2 | tools/list يعمل | **VERIFIED** | stdio JSON-RPC → `list_files`, `read_file` مع inputSchema | 0 |
| 3 | Safe-zone يمنع traversal | **VERIFIED** | `read_file ../windows/win.ini` → `Access denied: outside safe zone` | 0 |
| 4 | 20 اختبار ناجح | **VERIFIED** | `python -m unittest discover -s tests -v` → `Ran 20 tests ... OK` | 0 |
| 5 | Audit chain سليمة | **VERIFIED** | `verify()` → `chain_valid True checked 45 reason None` | 0 |
| 6 | Audit تفاصيل | **VERIFIED** | 45 event · actors=[coordinator,hermes] · 10 task_ids · آخر حدث `engine.result` 2026-11-17T13:44:53Z | 0 |
| 7 | Core files موجودة | **VERIFIED** | orchestrator.py 4845B · task_manager.py 15013B · models.py 2004B · audit.py 4210B · policy.py 2276B · execution_engine.py 12190B · state.sqlite3 28672B | 0 |
| 8 | بوابة الموافقة تمنع فعلياً | **VERIFIED** | `test_approval_gate_blocks_external_effect`: execute("write code for X") → status=`blocked` | 0 |
| 9 | n8n محلي حي | **VERIFIED** | `curl /healthz` → `200` | 0 (curl 23 = write-out quirk) |
| 10 | Git متزامن | **VERIFIED** | `cd69b66`, `origin/main...main = 0 0` | 0 |
| 11 | Pages حية | **REPORTED** | HTTP 200 في فحص سابق (18 نوفمبر) — لم يُعَد فحصها في هذه الجلسة | — |
| 12 | Codex CLI | **REPORTED** | `codex-cli 0.170.0` المرة السابقة | — |

## 2) ما الذي ورد في تقارير سابقة فقط؟
- Cloudflare / GitHub / Cloudflare Pages HTTP 200 — **REPORTED** (لم يُعَد التحقق此刻).
- "نقل 5 صفحات Genspark لسلة المهملات عبر موصل ChatGPT" — **REPORTED** (من رسالة المستخدم؛ أدواتي لا تقرأ التعليقات ولا تحذف).
- Claude Code `ragy-stdio` في `/mcp` — **UNKNOWN** (لم يؤكد المستخدم).

## 3) ما الذي لم يُنفذ؟
- External MCP Gateway (Streamable HTTP/SSE + Bearer) — **NOT IMPLEMENTED**
- Hermes Adapter / ChatGPT Adapter — **NOT IMPLEMENTED**
- ChatGPT ↔ Hermes اتصال مباشر — **NOT IMPLEMENTED** (ولا دليل عليه)
- End-to-End test (T10) — **NOT IMPLEMENTED** (لا ملف e2e في tests/)
- Cloudflare Tunnel + دومين + مصادقة — **NOT IMPLEMENTED** (`~/.cloudflared/*.pem` = 0)
- MCPs خارجية: cloudflare / gitlab / hugging_face → `Connection failed` ×3 — **NOT WORKING** (OAuth ناقص)
- HTTP bridge (`mcp_cloud_bridge.py`) به `/health`,`/tools`,`/mcp`,`/tools/call` لكن **بدون أي Bearer/auth** في الكود — **INCOMPLETE + INSECURE BY DESIGN**

## 4) هل يمكن ربط ChatGPT بـ Hermes في البيئة الحالية؟
**الجواب التقني الصادق: لا يمكن إثباته حالياً.**
- القناة الوحيدة المُثبتة هي **Notion** (رسائل/تعليقات) — وهذه **ليست** MCP، وليست اتصالاً مباشراً.
- Remote MCP / Streamable HTTP / SSE / Webhook / Tunnel — كلها **UNKNOWN** من ناحية ChatGPT في الحساب المستهدف؛ لا أملك دليلاً على أن واجهة ChatGPT تدعم إضافة Remote MCP لديك.
- بيئة Hermes تدعم stdio محلياً (مُثبت) وHTTP bridge محلي (مُثبت كملف، غير مُختبر مع ChatGPT).
- **التصنيف الصارم:** دعم البروتوكول نظرياً = PROPOSED · دعم Hermes = VERIFIED (stdio) · دعم ChatGPT = UNKNOWN · نجاح اتصال عملي = NOT IMPLEMENTED.
- لا أدّعي اتصالاً مباشراً قبل إثباته.

## 5) أفضل Architecture نهائية (PROPOSED)
```
ChatGPT (واجهة تدعم Remote MCP — يجب إثباتها أولاً)
   ↓ MCP over Streamable HTTP + Bearer (سر في مخزن آمن، لا في الكود)
RAGY MCP Gateway (Cloudflare Worker — PROPOSED)
   ↓乔木 Tunnel/HTTPS آمن
Hermes Adapter (PROPOSED — يلف ExecutionEngine)
   ↓
RAGY Core: CoreOrchestrator → TaskManager → StateMachine → ExecutionEngine
   ↓
PolicyEnforcer + ApprovalGate + AuditLogger (SHA-256) → SQLite
   ↓
Tools: MCP (list/read) · n8n (status) · Codex (prompt بموافقة)
   ↓ النتيجة تعود بنفس المسار + correlation_id → ChatGPT
```
**مبدأ الترتيب:** إثبات محلي أولاً (T1–T9) → ثم Gateway → ثم Tunnel → ثم إثبات ChatGPT (T10). لا سحابة قبل المحلي.

## 6) المكونات القابلة لإعادة الاستخدام
- `ragy_agents/audit.py` (SHA-256 chain) — جاهز كما هو ✅
- `ragy_agents/task_manager.py` (15KB) — جاهز ✅
- `ragy_agents/orchestrator.py` — جاهز (لكن agents内部的 Mock) ⚠️
- `engine/execution_engine.py` — جاهز (يحتاج Adapter فقط) ✅
- `ragy_agents/policy.py` — جاهز ✅
- `mcp_stdio_server.py` — جاهز ✅

## 7) المكونات الناقصة
- Hermes Adapter (repeat over ExecutionEngine + correlation_id)
- ChatGPT Adapter
- MCP Gateway مع مصادقة (Streamable HTTP)
- Task correlation/request IDs + TTL للموافقات
- Idempotency key لمنع التكرار
- E2E test suite
- Secrets store (vault) — لا أسرار في الكود/Notion

## 8) Threat Model (PROPOSED — لم يُختبر عملياً إلا T3/T4/T5 محلياً)
| # | التهديد | الحالية | المطلوب |
|---|---|---|---|
| 1 | Unauthorized | لا يوجد auth في bridge | Bearer + رفض 401 |
| 2 | تسريب Token | لا tokens مخزنة | vault محلي + تدوير |
| 3 | Replay | لا idempotency | nonce + timestamp + ttl |
| 4 | تكرار طلب | لا request id | correlation id فريد |
| 5 | Path traversal | **محمي فعلياً** ✅ | يحفظ |
| 6 | Prompt injection | غير مُعالج | policy + رفض أوامر خارج allowlist |
| 7 | أوامر غير مصرح بها | allowlist في Engine | يحفظ + audit |
| 8 | خروج من Safe Zone | **محمي فعلياً** ✅ | يحفظ |
| 9 | انقطاع Gateway | لا retry | state.sqlite3 للاستئناف |
| 10 | تعطل Hermes | audit still valid | استئناف من آخر sequence |
| 11 | تلاعب Audit | SHA-256 locally tamper-evident | anchor خارجي (PROPOSED) |
| 12 | تجاوز Approval | **محمي فعلياً** ✅ (test يثبت blocked) | ربط الموافقة بـ task+expiry |

**Human Approval Gate — الحالة:** موجودة ومُختبرة في Engine (`blocked`). لكن: لا يوجد expiry بعد، ولا ربط بـ correlation id، ولا سجل "من وافق" في كل حدث (الـ `approved_by` يُسجّل في `engine.step.executed` فقط عند الموافقة). هذه فجوات PROPOSED.

## 9) Test Matrix
| Test | الهدف | الحالة | الأدلة |
|---|---|---|---|
| T1 | اتصال Hermes بـ ragy-mcp | **PASS (مُشغّل)** | Connected 2023ms + 2 tools |
| T2 | إرسال مهمة واستلام نتيجة | **PASS (مُشغّل)** | engine_cli → completed, audit_valid=true |
| T3 | Unauthorized | NOT RUN (لا auth أصلاً) | — |
| T4 | Path traversal | **PASS (مُشغّل)** | `Access denied: outside safe zone` |
| T5 | منع إجراء حساس بلا موافقة | **PASS (مُشغّل)** | `status=blocked` |
| T6 | Duplicate/Idempotency | NOT IMPLEMENTED | — |
| T7 | Gateway outage | NOT IMPLEMENTED | — |
| T8 | استئناف بعد انقطاع | NOT IMPLEMENTED | — |
| T9 | Audit integrity | **PASS (مُشغّل)** | chain_valid True, 45 events |
| T10 | E2E ChatGPT→Hermes | **NOT IMPLEMENTED** | لا يوجد اتصال ولا اختبار |

## 10) مقارنة البدائل
| المعيار | Local-only | CF Tunnel+Gateway | Remote MCP |
|---|---|---|---|
| التكلفة | 0 | 0 (مجاني) | UNKNOWN (اشتراك ChatGPT?) |
| الأمان | عالي | متوسط (Bearer + tunnel) | UNKNOWN |
| توافق ChatGPT | غير مباشر (Notion فقط) | يحتاج إثبات | يحتاج إثبات |
| توافق Hermes | ✅ مثبت | PROPOSED | PROPOSED |
| الاعتمادية | جهازك فقط | أفضل | UNKNOWN |
| التوصية | ابدأ به | المرحلة 2 | لا تبدأ قبل إثبات T10 |

## 11) خطة التنفيذ T1–T7 (لم تُنفذ — PROPOSED)
- **T1** Adapter محلي فوق ExecutionEngine + correlation_id → tests
- **T2** Idempotency + approval TTL + سجل الموافق → tests
- **T3** تحويل mcp_cloud_bridge إلى Streamable HTTP + Bearer من vault → tests T3,T6
- **T4** E2E محلي (Python client ←→ bridge) → T7,T8
- **T5** CF Worker Gateway → T1–T4 عبر HTTP
- **T6** Tunnel + دومين + مصادقة
- **T7** إثبات ChatGPT (T10) — **فقط** لو ثبت دعم Remote MCP في الواجهة

## 12) Rollback Plan
إيقاف Worker/Bridge + إزالة إعدادات MCP المضافة (بدون حذف بيانات) · Audit يبقى سليم · الرجوع لقناة Notion · لا أسرار تُكتب في Notion/الكود.

## 13) القرارات المطلوبة من المستخدم/ChatGPT
1. هل واجهة ChatGPT عندك تدعم Remote MCP فعلاً؟ (دليل/قائمة أدوات) — حاسم قبل أي سحابة.
2. Bearer أم OAuth؟ (أوصي Bearer+vault أولاً)
3. دومين Cloudflare جاهز؟
4. حد الموافقة البشرية (أوصي: كل ما له external effect)
5. موافقة منفصلة قبل أي تنفيذ (البنية السحابية تحديداً).

## limiting صادقة
- لم أقرأ SEQ 003/004 من Notion مباشرة — أدواتي تكتب تعليقات ولا تقرأها. وصلتني عبر المستخدم.
- لم أعد فحص Pages/Cloudflare في هذه الجلسة → REPORTED لا VERIFIED.
- Agents في Core **Mock** (`Deterministic Mock Agents with no tool/filesystem/network access`) → التنفيذ الحقيقي يتم عبر Engine، لا عبر هؤلاء الـ agents.
- لا E2E، لا auth على bridge، لا Tunnel، لا دومين، لا MCP خارجي.

**الحالة النهائية:** Discovery & Design مكتمل. لا تنفيذ. في انتظار SEQ 008 + موافقة صريحة.
