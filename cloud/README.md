# RAGY Cloud Engine

Cloudflare Worker — مركز التحكم السحابي لـ RAGY.

## اللي شغال
- `GET /health` — فحص عام (بدون أي معلومات حساسة)
- `POST /mcp` — JSON-RPC: `initialize`, `tools/list`, `tools/call`, `ping`
- `GET /tasks` — قائمة المهام من D1
- `GET /audit` — التحقق من سلسلة SHA-256

## الأدوات
- `list_tasks` · `get_task` · `verify_audit`

## الحماية
- Bearer token من Workers Secret `RAGY_BRIDGE_TOKEN` (fail-closed)
- Origin allowlist · Rate limit 200/دقيقة · Idempotency بحد 512
- كل عملية في `audit_log` على D1 بنفس منطق `ragy_agents/audit.py`

## النشر
```bash
cd cloud
wrangler secret put RAGY_BRIDGE_TOKEN   # التوكن من مصدر آمن، مش من الشات
wrangler deploy
```

## الاختبار محليًا
```bash
python -c 'import secrets,pathlib; pathlib.Path("cloud/.dev-token").write_text(secrets.token_hex(24))'
printf 'RAGY_BRIDGE_TOKEN=%s\n' "$(cat cloud/.dev-token)" > cloud/.dev.vars
wrangler d1 execute ragy-tasks --local --file=cloud/schema.sql
python -m unittest tests.test_ragy_cloud_worker -v
```

`.dev-token` و `.dev.vars` مستبعدان من git — لا ترفعهما ولا تشاركهما.

## الرابط المؤقت
`https://ragy-cloud-engine.aragy76.workers.dev`
