# نشر RAGY MCP على السحابة — دليل كامل

الهدف: خلي المستشار الذكي (Claude / ChatGPT / أي متصفح) يوصل لمشروعك **24/7** حتى والكمبيوتر مقفول.

## الخيار الأسهل (مجاني — Render)

1. افتح https://render.com واعمل حساب (أو سجل دخول بحساب GitHub).
2. اضغط **New + → Blueprint**.
3. اختر الريبو: `ragymkm-bot/Jameel-Engine-Verified`.
4. Render هيقرأ ملف `render.yaml` تلقائياً وينشئ الخدمة.
5. بعد دقائق هتلاقي رابط زي: `https://ragy-mcp-cloud.onrender.com`.
6. اختبره: افتح `https://ragy-mcp-cloud.onrender.com/health` → المفروض تشوف `{"status":"ok"}`.

## بديل (Hugging Face Spaces — مجاني)

1. افتح https://huggingface.co/new-space واختر **Docker**.
2. ارفع ملفات: `Dockerfile.cloud` (سمّيه `Dockerfile`) + `mcp_stdio_server.py` + `mcp_cloud_bridge.py` + `mcp_server.py` + `README.md` + `CONTEXT_PACK.md` + `requirements.txt`.
3. الرابط هيكون: `https://<username>-<space>.hf.space`.

## النقاط المتاحة بعد النشر

| Endpoint | الوظيفة |
|---|---|
| `/health` | فحص الحالة |
| `/tools` | قائمة الأدوات (`list_files`, `read_file`) |
| `/mcp` | بروتوكول MCP JSON-RPC |
| `/tools/call` | تنفيذ أداة (قراءة ملف من الكتالوج فقط) |

## الأمان (مهم)
- السحابة تقرأ **كتالوج ثابت فقط** (`README.md`, `CONTEXT_PACK.md`) — مش عندها وصول لملفات جهازك.
- مفيش أسرار أو مفاتيح في الكود أو الصورة.
- الملفات الحساسة بتاعتك (secrets/.vault) تفضل محلياً على جهازك.

## الربط من المتصفح
بعد ما تاخد الرابط، افتح Claude/ChatGPT وقول:
> "Read the MCP catalog from https://<your-cloud-url>/tools then /tools/call to read CONTEXT_PACK.md"

أو الصق محتوى `CONTEXT_PACK.md` مباشرة في الشات (دي أسهل طريقة وأضمنها).
