# RAGY — نموذج الأمان (Security Model)

**المبدأ:** صفر أسرار في الكود/Git/Notion/الشات · fail-closed · أقل صلاحية ممكنة · كل قرار مسجّل.

---

## ١) خريطة الثقة
```
مستخدم (متصفح/موبايل)
   │ Bearer token (في localStorage بتاعه بس)
   ▼
Cloudflare Worker (RAGY Cloud Engine)
   │ ├─ D1: audit (SHA-256 chain) + tasks + automations + commands + clients + vault
   │ ├─ Secrets env: RAGY_BRIDGE_TOKEN · OPENROUTER_API_KEY
   │ └─ Vault (AES-GCM مشفّر): أسرار واتساب/أي سر يرفعه المستخدم من الواجهة
   ▼
Hermes المحلي (poller) ── safe-zone C:/AI-Agents-Lab ── ExecutionEngine + Approval Gate
   ▼
OpenRouter / Meta WhatsApp API (خارجي، بمفاتيح من Secrets/Vault فقط)
```

## ٢) طبقات الحماية
| الطبقة | الآلية | التحقق |
|---|---|---|
| مصادقة | Bearer `compare_digest` | no-token → 401 |
| Origin | allowlist صريح | evil.example → 403 |
| Rate limit | 200/دقيقة لكل IP | 205 طلب → 429 |
| Idempotency | X-Request-Id، 512 entries | تكرار بنفس الـ payload → نفس النتيجة، تغيير → 409 |
| توقيع واتساب | HMAC SHA-256 `X-Hub-Signature-256` | توقيع غلط → 403 |
| Vault | AES-GCM، مفتاح من Secret | القيم ما تظهرش في أي endpoint |
| حذف | `confirm='DELETE'` إلزامي | بدونه → error |
| Audit | SHA-256 hash chain | أي تعديل يكسر السلسلة |

## ٣) الأسرار — أين وماذا
| السر | المكان | قابل للعرض؟ |
|---|---|---|
| `RAGY_BRIDGE_TOKEN` | Workers Secret + `cloud/.dev-token` (gitignored) | لا |
| `OPENROUTER_API_KEY` | Workers Secret | لا |
| `WHATSAPP_TOKEN` إلخ | Workers Secret **أو** Vault مشفّر | لا (أسماء فقط) |
| SSH key | `~/.ssh` | لا |

## ٤) التهديدات المعروفة
| التهديد | الحالة | التخفيف |
|---|---|---|
| سر في الشات | منع سياسات | توجيه لـ `wrangler secret put` / Vault |
| serialPort/Origin spoofing | محمي | allowlist صريح |
| vault key مشتق من bridge token | مقبول مؤقتًا | ترقية لـ secrets_store/HSM لما يتوفر |
| CDN cache يعرض نسخة قديمة | مش أمني بس مزعج | `?v=` + Cache-Control: no-store |
| ChatGPT مباشر | غير موجود | Notion bridge فقط |

## ٥) قاعدة التغيير
أي تغيير في الأمان لازم: اختبار جديد + توثيق في `DECISION_LOG.md` + تحديث الوثيقة دي.
