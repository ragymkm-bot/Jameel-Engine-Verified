# روابط المنظومة الحية + تشخيص MCP

## الروابط (كلها HTTP 200)
- المستودع: https://github.com/ragymkm-bot/Jameel-Engine-Verified
- لوحة GitHub Pages: https://ragymkm-bot.github.io/Jameel-Engine-Verified/
- لوحة Cloudflare Pages: https://jameel-ragy-command-center.pages.dev/

## ليه الـ MCP "مش كونكتت"؟ — التشخيص النهائي بالدليل

اختبرت كل سيرفر بـ `hermes mcp test` (من جوه Hermes مش من command line):

| السيرفر | النتيجة | السبب |
|---|---|---|
| **ragy-mcp** (بتاعنا) | ✅ `✓ Connected 2670ms` + أداتين | شغال تمام — `list_files`, `read_file` |
| hugging_face | ❌Connection failed | OAuth: no cached tokens |
| gitlab | ❌ Connection failed | OAuth: no cached tokens |
| cloudflare | ❌ Connection failed | OAuth: no cached tokens |

**الخلاصة:** الـ MCP بتاعنا (ragy-mcp) **متصل وشغال**. اللي بيظهر "مش كونكتت" هم الـ 3 سيرفرات الخارجية اللي محتاجين **OAuth login تفاعلي منك**.

## الحل للسيرفرات الخارجية (لازم تسويها أنت)
الـ OAuth بيفتح متصفح وبيحتاج دخول بحسابك — مش أقدر أقوم بيها من non-interactive:
```bash
hermes mcp login hugging_face
hermes mcp login gitlab
hermes mcp login cloudflare
```
بعدين `hermes mcp test <name>` يرجع `✓ Connected`.

## اللي اتصلح في الجلسة دي
- `ragy-mcp` في Hermes اتثبّت على مسار Python صريح (كان `python` عام) — النتيجة `✓ Connected`.
- نفس التثبيت في `.mcp.json` و `~/.claude.json` لـ Claude Code.
- `hermes config check` → `Config version 52 ✓`.

## اللي اتعمله دلوقتي
1. `.mcp.json` و `~/.claude.json` اتثبّتوا على المسار الصريح لـ Python (بدل `python` العام اللي ممكن يشير لنسخة غلط).
2. `ragy-mcp` في config يشير لـ `mcp_stdio_server.py` (السيرفر الحقيقي).
3. 4 سيرفرات MCP ظهرين في `hermes tools list`: ragy-mcp, gitlab, hugging_face, cloudflare.

## عشان تشوف الـ MCP في Claude Code
افتح المشروع في Claude Code → اكتب `/mcp` → المفروض تشوف `ragy-stdio` متصل.
لو ما ظهرش: أعد تشغيل Claude Code (نفس سبب الجلسة القديمة).

## ملاحظة
الـ cloud bridge (HTTP) متاح كمان: `PORT=8902 python mcp_cloud_bridge.py` → `/health` و `/tools`.
