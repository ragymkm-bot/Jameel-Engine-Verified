# روابط المنظومة الحية + تشخيص MCP

## الروابط (كلها HTTP 200)
- المستودع: https://github.com/ragymkm-bot/Jameel-Engine-Verified
- لوحة GitHub Pages: https://ragymkm-bot.github.io/Jameel-Engine-Verified/
- لوحة Cloudflare Pages: https://jameel-ragy-command-center.pages.dev/

## ليه الـ MCP "مش كونكتت"؟
السيرفر نفسه **شغال ومُختبَر** (initialize + list_files + read_file + رفض outside safe zone).
السبب الحقيقي: **الجلسة الحالية اتولدت قبل ما أصلّح config.yaml**، فالـ runtime بتاع الجلسة ما حمّلش الـ MCP tools الجديدة.
الحل: إعادة تشغيل Hermes (أو فتح جلسة جديدة) عشان يقرأ الإعدادات المصححة.

## اللي اتعمله دلوقتي
1. `.mcp.json` و `~/.claude.json` اتثبّتوا على المسار الصريح لـ Python (بدل `python` العام اللي ممكن يشير لنسخة غلط).
2. `ragy-mcp` في config يشير لـ `mcp_stdio_server.py` (السيرفر الحقيقي).
3. 4 سيرفرات MCP ظهرين في `hermes tools list`: ragy-mcp, gitlab, hugging_face, cloudflare.

## عشان تشوف الـ MCP في Claude Code
افتح المشروع في Claude Code → اكتب `/mcp` → المفروض تشوف `ragy-stdio` متصل.
لو ما ظهرش: أعد تشغيل Claude Code (نفس سبب الجلسة القديمة).

## ملاحظة
الـ cloud bridge (HTTP) متاح كمان: `PORT=8902 python mcp_cloud_bridge.py` → `/health` و `/tools`.
