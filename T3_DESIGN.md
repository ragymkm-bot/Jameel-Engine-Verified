# T3 — Secure Streamable HTTP MCP Bridge: Design & Method

**Task:** SEQ 007 → T3 | **Scope:** local-only | **No cloud / no Worker / no Tunnel / no new packages**
**Principle:** fail-closed · reuse existing components · zero secrets in code/git/Notion

## 1. الأهداف (Acceptance Criteria)
| # | الهدف | معيار القبول |
|---|---|---|
| G1 | Bearer auth | أي طلب بدون `Authorization: Bearer` يُرفض 401؛ التوكن يُقارَن بـ `compare_digest` (constant-time) |
| G2 | Fail-closed | لو ما فيهاش توكن مُهيّأ → السيرفر **يرفض البدء** (ما يشتغلش مفتوح) |
| G3 | Streamable HTTP | `POST /mcp` JSON-RPC + `Mcp-Session-Id` + `GET /mcp` SSE + `DELETE /mcp` |
| G4 | Idempotency (T6) | `X-Request-Id` مكرر بنفس الـ payload → نفس النتيجة بدون إعادة تنفيذ |
| G5 | Origin check | Origin غير مسموح → 403 (DNS-rebinding protection) |
| G6 | Safe zone | `read_file` خارج `C:/AI-Agents-Lab` → "Access denied" (موروث من stdio) |
| G7 | Audit | كل قرار (سماح/رفض/idempotency) في نفس SHA-256 chain |
| G8 | Zero leak | التوكن ما يظهرش في الاستجابات أو اللوجات أو الجيت |
| G9 | Reuse | منطق JSON-RPC من `mcp_stdio_server.handle` — بدون نسخ |

## 2. القرارات الهندسية
- **التوكن:** يُقرأ من `RAGY_BRIDGE_TOKEN` (env) أو `runtime/vault.json` (مفتاح `bridge_token`) — **ملف غير متتبَّع في git**. ما فيش توكن في الكود.
- **المقارنة:** `hmac.compare_digest` — لا timing attacks.
- **Origin allowlist:** `http://localhost:*`, `http://127.0.0.1:*` — أي Origin تاني يُرفض.
- **Idempotency cache:** dict في الذاكرة بحد أقصى 512 مدخل (LRU بسيط) + hash للـ payload.
- **Sessions:** `uuid4` على `initialize`; يُرجع في `Mcp-Session-Id`; يُطلَب في الطلبات التالية.
- **Audit:** `StructuredAuditLog` نفسه (project root) — حدث لكل حالة.
- **Health:** `GET /health` بدون auth (للمراقبة فقط — ما يرجّعش أي معلومة حساسة).

## 3. التهديدات اللي التصميم بيعالجها (من SEQ 007 Threat Model)
T1 Unauthorized → 401 · T2 Token leak → compare_digest + لا لوج · T3 Replay → idempotency + X-Request-Id · T4 Duplicate → cache · T5 Traversal → safe zone · T6 Prompt injection → allowlist أدوات بس · T7 Gateway outage → fail-closed.

## 4. المنهجية (خطوات التنفيذ)
1. كتابة التصميم (هذا الملف).
2. تنفيذ `engine/secure_mcp_bridge.py` (طبقة جديدة، بدون تعديل القديم).
3. اختبارات حقيقية: T3 unauthorized / wrong token / valid token / idempotency / origin / safe-zone / fail-closed.
4. تشغيل الاختبارات + إصلاح أي فشل.
5. تجهيز توكن محلي مخفي (بدون عرضه) + smoke test عبر curl.
6. commit + push + تحقق إن ما فيش secret في git.

## 5. حدود صريحة
- الـ bridge **محلي** (127.0.0.1) — ما فيش ربط بأي خدمة خارجية.
- Idempotency في الذاكرة (process واحد) — التخزين المشترك بند T2 القادم.
- SSE بسيط (server→client notifications) — لا يفتح اتصال دائم طويل.
- لا يوجد رابط ChatGPT لسه (Q1 UNKNOWN) — T7 مستنى القرار.
