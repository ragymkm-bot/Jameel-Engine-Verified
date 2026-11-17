# RAGY Cloud — دليل التشغيل اليومي (Operations Runbook)

**الجمهور:** المهندس/الوكيل اللي هيكمل الشغل · **القاعدة:** كل إجراء ليه دليل، ومفيش ادعاء بالنجاح بدون تحقق.

---

## ١) فحص الصحة (كل يوم / قبل أي تغيير)
```bash
cd C:/AI-Agents-Lab
# Worker
curl -s https://ragy-cloud-engine.aragy76.workers.dev/health
# Audit chain
TOK=$(cat cloud/.dev-token)
curl -s https://ragy-cloud-engine.aragy76.workers.dev/audit -H "Authorization: Bearer $TOK"
# CLI tools
python -m unittest discover -s tests          # لازم 69/69 OK
cd C:/AI-Agents-Lab && git rev-list --left-right --count origin/main...main   # لازم 0 0
```

## ٢) الأوامر الأساسية
| الإجراء | الأمر |
|---|---|
| نشر Worker | `cd cloud && wrangler deploy` |
| رفع سر | `wrangler secret put NAME` (من جهازك، مش الشات) |
| فحص الأسرار (أسماء فقط) | `wrangler secret list` |
| تشغيل الـ poller | `python cloud/hermes_poller.py` |
| فحص MCP المحلي | `hermes mcp test ragy-mcp` |
| فحص ن8ن | `curl -s http://127.0.0.1:5690/healthz` |
| نسخة احتياطية D1 | `wrangler d1 export ragy-tasks --remote --output backup.sql` |

## ٣) الاستعادة (Recovery)
| الموقف | الإجراء |
|---|---|
| نشر فاشل | `wrangler deployments list` → الرجوع لآخر version صالح |
| OAuth منتهي | `wrangler login --browser false` أو refresh عبر client_id من `wrangler login --help` |
| audit chain مكسورة | لا تُصلح يدويًا — ارجع لآخر backup + أبلغ |
| أسرب سر | `wrangler secret put NAME` بقيمة جديدة (القديم يبطل) |
| الموقع بيعرض القديم | `?v=<timestamp>` أو `Ctrl+Shift+R` (CDN cache) |

## ٤) التصعيد (Escalation)
- أي 401/403 غير متوقع → أفحص الـ Origin والـ token الأول.
- أي فشل اختبار → أوقف النشر، سجّل في `DECISION_LOG.md`، وأبلغ الريس.
- أي طلب مدفوع → موافقة صريحة منفصلة.

## ٥) القواعد غير القابلة للتفاوض
1. مفيش سر في الشات / الكود / Git / Notion.
2. مفيش حذف نهائي بدون `confirm='DELETE'` + audit.
3. مفيش نشر قبل 69/69 OK.
4. كلfinding يُوثّق في `RAGY_MASTER_BLUEPRINT_X.md`.
5. التدقيق read-only — حتى مع صلاحيات كاملة.
