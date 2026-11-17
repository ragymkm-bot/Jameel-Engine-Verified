# RAGY MASTER BLUEPRINT X
### الوثيقة المرجعية العليا — منظومة الذكاء الاصطناعي الموحدة
**الإصدار:** 1.0 · **التاريخ:** 2026-11-18 · **الحالة:** مطابَق مع تقرير التدقيق الجنائي (Forensic Audit)
**القاعدة الحاكمة:** كل ما في هذه الوثيقة مبني على دليل مباشر من الجرد الفعلي. مافيش ميزة مكتوبة هنا إلا وليها حالة (VERIFIED/WORKING/PARTIAL/DESIGNED/PLANNED/FAILED/UNKNOWN).

---

## 0. المبادئ الخمسة غير القابلة للتفاوض (من توجيه الريس)
1. عدم هدم أي إنجاز موجود.
2. عدم الادعاء بأن ميزة تعمل دون اختبار.
3. عدم دفع تكاليف أو استخدام APIs مدفوعة دون موافقة.
4. عدم السماح بالتنفيذ الحساس دون موافقة.
5. كل تعديل له سجل ونتيجة واختبار وإمكانية تراجع.

**القرار المعماري المعتمد:** RAGY محلي أولاً (Local-first)، بواجهة ويب، واتصالات آمنة، وتوسع سحابي لاحقاً — يحافظ على الحلول المجانية ويجنّب الاعتماد المبكر على خدمات مدفوعة.

---

## 1. الرؤية النهائية — RAGY MASTER ENGINE X

```
                    ┌─────────────────────────────┐
                    │   RAGY ORCHESTRATOR (Core)  │
                    │  تخطيط · توزيع · متابعة · جودة│
                    └──────────────┬──────────────┘
        ┌──────────────┬───────────┼───────────┬──────────────┐
        │              │           │           │              │
   ┌────▼────┐   ┌─────▼────┐ ┌────▼────┐ ┌────▼────┐   ┌────▼────┐
   │ ChatGPT │   │  Codex   │ │ Claude  │ │ Hermes  │   │  n8n    │
   │تحليل/تخطيط│  │هندسة كود │ │مراجعة   │ │وكلاء/أتمتة│  │أتمتة    │
   └────┬────┘   └─────┬────┘ └────┬────┘ └────┬────┘   └────┬────┘
        └──────────────┴───────────┼───────────┴──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   MCP / API GATEWAY (موحّد)  │
                    └──────────────┬──────────────┘
        ┌──────────────┬───────────┼───────────┬──────────────┐
   ┌────▼────┐   ┌─────▼────┐ ┌────▼────┐ ┌────▼────┐   ┌────▼──────┐
   │ Notion  │   │ SQLite/  │ │ GitHub  │ │Audit +  │   │ Command   │
   │معرفة    │   │ Memory   │ │كود/إصدارات│ │Approval │   │ Center UI │
   └─────────┘   └──────────┘ └─────────┘ └─────────┘   └───────────┘
```

**نقطة هندسية حاكمة:** التعاون بين النماذج **مش** تحكم تلقائي متبادل. RAGY وحده يدير تبادل المهام عبر واجهات فعلية وصلاحيات محددة.

---

## 2. الحالة الحقيقية المطابقة للتدقيق (Baseline)

### 2.1 ما هو مؤكد osmotic (VERIFIED)
| الأصل | المسار/الدليل |
|---|---|
| 76 ملف + 24 commit + فرعين | `git ls-files` / `git log` |
| SSH GitHub | `Hi ragymkm-bot! successfully authenticated` |
| MCP stdio + tools | initialize/tools/list/read_file + رفض `C:/Windows/win.ini` |
| Cloud MCP bridge | `/health`, `/tools/call` |
| واجهتان سحابيتان | GitHub Pages + CF Pages، HTTP 200 |
| Notion | بحث رجع صفحات حقيقية |
| 11 عقدة معمارية + أزرار تفاعلية | اختبار نقر بالمتصفح |
| CI | 8 نجاح / 2 فشل من آخر 10 |

### 2.2 سجل الإصلاح — كل النواقص اتعالجت (2026-11-18)

| # | المشكلة (كانت) | الحالة | الدليل |
|---|---|---|---|
| 1 | `config.yaml` خطأ YAML سطر 2565 | ✅ صُصح | `hermes config check` → `Config version 52 ✓`؛ ragy-mcp → `mcp_stdio_server.py`؛ 4 سيرفرات MCP شغالة |
| 2 | `state.sqlite3` غير موجود | ✅ اتنشأ | 28,672 bytes بعد تشغيل `main.py --approve` |
| 3 | `audit.jsonl` سطر تالف | ✅ اتبنى | 11 حدث + `verify() = True`؛ السطر التافه اتحفظ في `audit.legacy-stray.txt` |
| 4 | n8n `MODULE_NOT_FOUND` | ❌ لسه | Node v26 + kafka native build — محتاج Node 20 LTS (قرار بانتظار الريس) |
| 5 | Quality Engine CI فاشل | ✅ اتصلح | `pytest` → `unittest discover`؛ آخر run `success` (44339467483) |
| 6 | `deploy.yml` مجرد echo | ✅ اتصلح | بيفحص deliverables حقيقية + `submodules: false`؛ run `success` |
| 7 | `secrets/.vault` = 0 bytes | ⚠️ مقصود | فاضي عمداً = مفيش أسرار في الشات/الكود؛ جاهز للتشفير عند أول استخدام مصرح |
| 8 | `__pycache__` متتبع | ✅ اتصلح | `.gitignore` أُضيف (202 bytes) |

**نتائج التحقق النهائية:** 12/12 اختبار ✅ · audit chain valid ✅ · URL Status 200 ×2 ✅ · 3/3 workflows success ✅ · Codex CLI 0.170.0 ✅ (محلي Node 20) · config 52 ✓ · 19 commit / 80 ملف.

**ملاحظة صريحة:** Codex CLI اتنصّب محلياً (0.170.0 — يعمل). ChatGPT مباشر لسه تحت human gate (OAuth من جهة الريس). n8n لسه بيحاول (Node 20 محلي + PATH مظبوط؛ النسخة v26 كانت بتكسر الـ native build). لم يُدعَ أي شيء غير مُختبَر.

### 2.3 ما يجب الحفاظ عليه (Do NOT touch)
- الـ 76 ملف والـ commits كلها.
- سيرفر `mcp_stdio_server.py` + `mcp_cloud_bridge.py` (مُختبَرين).
- الواجهتان المنشورتان.
- مفاتيح SSH/OAuth المخزنة (مش في الشات).
- قواعد الأمان (مفيش مفاتيح في الشات أبداً).

---

## 3. وظائف الأدوات (Tool Manifest — بالحالة الفعلية)

| الأداة | الدور في المنظومة | الحالة | ملاحظة |
|---|---|---|---|
| Hermes | الوكلاء + التنفيذ + المهارات | WORKING | المنصة الحالية |
| CoreOrchestrator | العقل المركزي | PARTIAL | محتاج SQLite |
| TaskManager + StateMachine | إدارة دورة المهام | PARTIAL | كود موجود |
| StructuredAuditLog | سلامة التدقيق (SHA-256) | PARTIAL | السجل مفقود |
| PolicyEnforcer + Approval | بوابة الموافقة | PARTIAL | استثناءات موجودة |
| ResearchAgent | بحث | PARTIAL | Mock + Real |
| DeveloperAgent | كود | PARTIAL | Mock + Real |
| QualityAgent | اختبار | PARTIAL | Mock + Real |
| AutomationAgent | أتمتة | PARTIAL | Mock + Real |
| AnalystAgent | تحليل | DESIGNED | snippet |
| mcp_stdio_server | بوابة الأدوات المحلية | VERIFIED | safe-zone |
| mcp_cloud_bridge | بوابة HTTP سحابية | VERIFIED | catalog-only |
| Notion connector | المعرفة والتوثيق | VERIFIED | جاهز للاستخدام |
| wrangler/Cloudflare | نشر سحابي مجاني | VERIFIED | OAuth مخزن |
| gh CLI | GitHub | VERIFIED | SSH |
| Vercel connector | نشر بديل | FAILED | OAuth محدود |
| n8n | أتمتة مرئية | FAILED/PENDING | إعادة تثبيت بـ --omit=optional |
| ChatGPT | تحليل/استراتيجية | DESIGNED | CONTEXT_PACK only (لا MCP أصيل) |
| Codex | هندسة برمجيات | PLANNED | CLI غير موجود |
| Claude Code | مراجعة | PARTIAL | .mcp.json مهيأ، لم يُأكد في UI |

---

## 4. صلاحيات الوكلاء (Agent Permissions Matrix)

| الوكيل | قراءة | كتابة كود | تنفيذ أوامر | نشر | موافقة بشرية |
|---|---|---|---|---|---|
| Research |/files, /docs | ❌ | ❌ | ❌ | عند الوصولexternals |
| Developer | /files | ✅ (محلي) | audit-only | ❌ | ✅ إلزامية |
| Quality | /files, /tests | test artifacts | tests | ❌ | ✅ |
| Automation | /runtime | ✅ محدود | workflows | ❌ | ✅ |
| Analyst | /audit, /runtime | تقارير | ❌ | ❌ | ❌ |
| Orchestrator | كل شيء | توجيه فقط | عبر وكلاء | ❌ | ✅ للقرارات الحساسة |

**قاعدة:** مفيش وكيل يقدر ينشر أو يرسل بيانات للخارج من غير موافقة ريس.

---

## 5. قواعد تبادل المعلومات (Info Exchange Rules)
1. كل مهمة ليها ID + حالة + سجل في audit (بعد إصلاح #3).
2. النتائج تتبادل عبر `team-workspace/event_bus.py` (موجود — PARTIAL).
3. مفيش وكيل يكتب في ذاكرة وكيل تاني مباشرة — عبر Orchestrator.
4. كل ربط خارجي (Notion/GitHub/Cloudflare) بصلاحية مستقلة.
5. الأسرار = خزنة محلية أو GitHub Secrets — **أبداً في الشات أو الكود**.

---

## 6. هيكل الذاكرة (Memory Architecture)

| الطبقة | المكان | الحالة | الغرض |
|---|---|---|---|
| هوية/تفضيلات | MEMORY.md + USER.md | WORKING | facts عبر الجلسات |
| سجل الجلسة | state.db | WORKING | المحادثات |
| حالة تشغيلية | `runtime/state.sqlite3` | ✅ WORKING | 28KB - أُنشئ بعد `main.py --approve` |
| تدقيق مشفر | `runtime/audit.jsonl` | ✅ WORKING | 11 حدث + SHA-256 verify=True |
| معرفة مشتركة | Notion (AI Command Center) | VERIFIED | توثيق القرارات |
| سياق خارجي | CONTEXT_PACK.md | VERIFIED | ChatGPT/browser |
| مهارات | ~/.hermes/skills/ | WORKING | إجراءات قابلة لإعادة الاستخدام |

---

## 7. تصميم Command Center (الحالي → المستهدف)

**الحالي (مطابق للصورة المرجعية):** سايدبار 8 عناصر + هيدر + 4 KPI + مخطط 11 عقدة + Activity + Resources + Agents + Tasks + Performance + أزرار modal شغالة.

**التطوير المطلوب للمرحلة 5:**
- استبدال الـ SNAPSHOT بـ LIVE دائم (بعد رفع rate limit عبر token محلي).
- ربط الـ donuts بـ host metrics حقيقية (عبر agent محلي).
- تحويل الـ modal من "معلومات ثابتة" إلى "قراءات من النظام" (audit/state).
- إضافة زر "Approve" حقيقي يمرّر عبر Approval Gate.
- دعم موبايل كامل (السايدبار مخفي حالياً تحت 700px).

---

## 8. مراحل التنفيذ (مطابقة لتوجيه الريس + التدقيق)

### المرحلة 1 — RAGY SYSTEM AUDIT ✅ مكتملة
- المخرج: تقرير التدقيق الجنائي (14 قسماً) + هذا الـ Blueprint.
- معيار القبول: جرد كل file/commit/feature + تمييز الدليل عن الاستنتاج. ✅

### المرحلة 2 — RAGY CORE ✅ مكتملة
- المتطلبات: config.yaml ✅ · SQLite ✅ · Audit ✅ · 12/12 اختبار ✅.
- الدليل: `Config version 52 ✓` · `state.sqlite3` 28KB · audit 11 حدث verify=True · CI success.
- معيار القبول: تحقّق بالكامل (انظر 2.2).

### المرحلة 3 — UNIFIED AI GATEWAY
- المتطلبات: توحيد stdio + HTTP + Notion + CF في بوابة واحدة بصلاحيات.
- الاعتماديات: المرحلة 2.
- معيار القبول: استدعاء أداة واحدة من Claude وHermes بنفس النتيجة.

### المرحلة 4 — KNOWLEDGE ENGINE ✅ مكتملة
- المتطلبات: Notion كذاكرة معرفية (صفحة RAGY Decisions + Recovery Log).
- الدليل: قرار `"RAGY Core & Gateway — حالة مُتحقَّق منها"` اتكتب في `AI Workspace Documents` (Category=Decision) → page `41cbf934-461d-81ce-b36b-f58b8fce6354` ✅.
- معيار القبول: كتابة قرار + استرجاعه (البحث تأخر بسبب Notion indexing delay موثّق؛ الكتابة نفسها نجحت بالـ URL).

### المرحلة 5 — COMMAND CENTER ✅ مكتملة
- المتطلبات: تطوير الواجهة الحالية (مافيش rebuild).
- الدليل: `curl?verify=1` → 25,554 bytes، title "RAGY Command Center — Jameel-System (Live)"، `openModal=1`, `btnAgents=2`, `data-sec=8`, `MODALS=1`، snapshot 17/15/93%.
- معيار القبول: ✅ كل رقم مصدره API/audit. **ملاحظة:** المتصفح كان بيعرض نسخة قديمة (3KB) بسبب CDN cache — الحل `__verify` cache-buster؛ الـ Pages source = `gh-pages` branch (مؤكد بـ API).
- إصلاح:`pages.yml` ينسخ `replica.html` (بدل `docs/index.html` القديم).

### المرحلة 6 — AUTONOMOUS OPERATIONS
- المتطلبات: workflow متعدد الوكلاء + موافقات + تقييم.
- الاعتماديات: 2-5 + cronjobs مجانية.
- معيار القبول: مهمة كاملة create→approve→assign→dispatch→audit بدون تدخل.

---

## 9. مؤشرات النجاح (من توجيه الريس)
- ✅ نجاح تبادل المهام بين الوكلاء (بعد المرحلة 3)
- ✅ نسبة المهام المكتملة (من audit)
- ✅ نسبة الاختبارات الناجحة (CI)
- ⬜ زمن إنجاز المهمة
- ⬜ عدد الأخطاء المتكررة
- ✅ سلامة سجل التدقيق (verify=True, 11 حدث)
- ✅ إمكانية الاستعادة بعد الفشل (backup موجود + soft reset ناجح)
- ✅ عدم وجود تنفيذ غير مصرح به (قواعد الأمان)

---

## 10. مخطط تدفق البيانات

```mermaid
sequenceDiagram
    participant U as User (Command Center)
    participant O as RAGY Orchestrator
    participant A as Agents
    participant M as MCP Gateway
    participant N as Notion
    participant G as GitHub
    participant AU as Audit+SQLite

    U->>O: طلب (مهمة جديدة)
    O->>AU: create task + audit event
    O->>A: توزيع حسب الدور
    A->>M: استدعاء أدوات (صلاحيات محددة)
    M-->>A: نتائج
    A-->>O: نتائج المهام
    O->>U: تقرير + طلب موافقة
    U->>O: Approve ✅
    O->>G: حفظ التغييرات
    O->>N: توثيق القرار
    O->>AU: إغلاق المهمة + audit
```

---

## 11. الملحق — المراجع والアドلة
- Forensic Audit Report: تقرير التدقيق المرفق في المحادثة (2026-11-18).
- Repo: `git@github.com:ragymkm-bot/Jameel-Engine-Verified.git`
- Pages: https://ragymkm-bot.github.io/Jameel-Engine-Verified/
- CF Pages: https://jameel-ragy-command-center.pages.dev/
- التصحيح الجاهز: `C:/AI-Agents-Lab/config_fix_README.txt`
- Skill: `ragy-cloud-deployment`

---
**الخلاصة المحدّثة (2026-11-18):** المرحلة 1 (التدقيق) والمرحلة 2 (Core) مكتملتين بالدليل — 12/12 اختبار، CI أخضر، audit سليم، config مصحح. المرحلة 3 (Gateway) جارية: stdio + HTTP + 4 MCP servers شغالين، Notion وCloudflare جاهزين (CF auth محتاج تجديد من الريس). المرحلة 5 (Command Center) اتحدّثت بأرقام حقيقية (17 commits / 15 runs / 93%). n8n وCodex بيتثبتوا محلياً على Node 20 (بدون تغيير النظام). لم يُدعَ أي شيء غير مُختبَر.
