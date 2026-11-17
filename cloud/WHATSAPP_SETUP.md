# RAGY WhatsApp Bot — إعداد آمن

## الحقيقة أولًا (من Meta الرسمي)
- **WhatsApp Business Cloud API**: أول **1,000 رسالة service مجانية/شهر/رقم** — بعدها مدفوع.
- رسائل العميل لك مجانية دائمًا. رسائل `/run` اللي بتتنفّذ كأوامر = service.
- **ممنوع** أتمتة واتساب الشخصي — مخالف وممكن يحظر الرقم.
- محتاج **Meta Business verification** + رقم عمل + 4 أسرار.

## اللي اتبنى ✅
- `cloud/src/whatsapp.js` — webhook verify + HMAC signature + parsing + send.
- `/whatsapp` route على الـ Worker (قبل الـ Bearer auth).
- الرسالة العادية → `ask_copilot` (ردّ بالعربي من مستندات RAGY).
- رسالة تبدأ بـ `/run` أو "نفّذ" → `post_command` → Hermes المحلي ينفّذها.
- كل ردّ/فشل مسجّل في `audit_log`.

## الأسرار المطلوبة (تُرفع عبر wrangler secret put، مش الشات)
| Secret | الغرض |
|---|---|
| `WHATSAPP_VERIFY_TOKEN` | تحقق webhook من Meta |
| `WHATSAPP_APP_SECRET` | توقيع HMAC `X-Hub-Signature-256` |
| `WHATSAPP_TOKEN` | access token للإرسال |
| `WHATSAPP_PHONE_ID` | معرّف رقم العمل |

## خطوات التفعيل (بعد موافقتك — إجراء خارجي)
1. Meta Business Suite → WhatsApp API → احصل على الـ 4 قيم.
2. ارفعهم كأسرار: `wrangler secret put WHATSAPP_VERIFY_TOKEN` (إلخ).
3. سجّل Webhook URL في Meta: `https://ragy-cloud-engine.aragy76.workers.dev/whatsapp`
   + Verify token = نفس القيمة اللي رفعتها.
4. اشترك في حقل `messages`.
5. اختبر: ابعت رسالة للرقم → هيرد Copilot → قول `/run read README.md` → هيتنفّذ على جهازك.

## الحماية
- Webhook GET: verify token بس (مفيش bearer — Meta مش بtera بعت توكننا).
- Webhook POST: **HMAC إلزامي** — أي توقيع غلط = 403.
- fail-closed: أي secret ناقص = 503.
- Rate limit عام على الـ Worker.

**الحالة الحالية:** الكود جاهز ومُختبر (67/67) — بس **مش مُفعّل** لحد ما ترفع الأسرار وتسجّل الـ webhook (ده إجراء خارجي محتاج موافقتك).

## التفعيل من الموبايل (الطريق الجديد — أسرع)
1. افتح `/app` على تليفونك → قسم 🔐 محفظة الأسرار.
2. احفظ الأربع أسرار (كل واحد في سطر): الاسم + القيمة. القيم مش هتظهر تاني.
3. قسم 💬 اضغط "فحص الحالة" → لازم تلاقي الأربع `true`.
4. في Meta Business Suite: سجّل الـ webhook `https://ragy-cloud-engine.aragy76.workers.dev/whatsapp` والـ verify token اللي حفظته.
5. ابعت رسالة للرقم → Copilot يرد · `/run read README.md` → Hermes ينفّذ.

**الأسرار تُحفظ مشفّرة AES-GCM في D1 — ما تكتبهاش في الشات.**
