# T4 — Local End-to-End Client: Design & Method

**Task:** SEQ 007 → T4 | **Scope:** local-only | **No cloud / no ChatGPT / no secrets in code**
**Goal:** إثبات أن مهمة تبدأ من client → bridge → RAGY → ترجع بنتيجة قابلة للتحقق، وأن الانقطاع لا يكسر الحالة.

## 1. الأهداف (Acceptance Criteria)
| # | الهدف | المعيار |
|---|---|---|
| G1 | E2E حقيقي | client يرسل initialize → tools/list → tools/call ويستقبل نتائج صحيحة |
| G2 | T7 Outage | إيقاف الـ bridge أثناء التشغيل → الـ client يكتشف الانقطاع ويرجع خطأ صريح (مش نتيجة مزيفة) |
| G3 | T8 Resume | إعادة تشغيل الـ bridge → الـ client يعيد الاتصال ويكمل من آخر `audit_sequence` |
| G4 | Correlation | كل مهمة ليها `request_id` + `correlation_id` في الـ audit |
| G5 | Idempotency عبر إعادة الاتصال | نفس `X-Request-Id` بعد إعادة الاتصال → نتيجة متطابقة (أو 404 Session صريح، مش تنفيذ مزدوج صامت) |
| G6 | Audit سليم | الـ chain يفضل `valid=True` بعد كل عمليات الانقطاع والاستئناف |
| G7 | Zero secrets | التوكن من env/test فقط — لا يظهر في الكود أو اللوجات |

## 2. القرارات الهندسية
- **Client:** `engine/e2e_client.py` — `RAGYLocalClient` يستخدم `urllib` (stdlib، بدون حزم جديدة).
- **Session:** يتخزّن `Mcp-Session-Id` بعد `initialize` ويُعاد إرساله في كل طلب.
- **Resume:** الـ client يحتفظ بآخر `audit_sequence` ناجح؛ بعد إعادة الاتصال يتحقق أن السيرفر أكمل من نفس النقطة (الـ audit في ملف مشترك).
- **Idempotency:** نفس `X-Request-Id` يُعاد إرساله بعد إعادة الاتصال. لو الجلسة انتهت (404) → الـ client يعمل `initialize` جديد ويحصل على session جديد؛ النتيجة تظل متطابقة لأن الـ tool للقراءة فقط.
- **Fail-closed:** أي انقطاع → استثناء صريح `BridgeOffline`، مفيش retry أعمى يخفي الفشل.

## 3. المنهجية
1. التصميم (هذا الملف).
2. تنفيذ `engine/e2e_client.py`.
3. اختبارات: E2E كامل + T7 outage + T8 resume + correlation + audit.
4. تشغيل + إصلاح.
5. Smoke حقيقي (خادم منفصل + client).
6. تدقيق + commit.

## 4. حدود صريحة
- **T10 (ChatGPT → Hermes) لسه NOT IMPLEMENTED** — T4 هو E2E محلي فقط.
- الـ idempotency cache في الذاكرة: بعد إعادة تشغيل السيرفر يُمسح — الـ client يتعامل مع ده عبر إعادة التهيئة (مش عبر تخزين مشترك).
- الـ SSE stream في الـ bridge بسيط (endpoint event فقط).
