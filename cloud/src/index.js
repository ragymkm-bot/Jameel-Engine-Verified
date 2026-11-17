// RAGY Cloud Engine — Cloudflare Worker.
// Bearer auth + Origin allowlist + bounded idempotency + SHA-256 audit.
// No secrets in source. Fail-closed when the token secret is missing.

import { appendEvent, verifyChain } from "./audit.js";
import UI_HTML from "./ui-embedded.js";

const MAX_IDEMPOTENCY = 512;
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 200;
const STATE = { idem: new Map(), rate: new Map() };

function rateOk(req) {
  const ip = req.headers.get("CF-Connecting-IP") || req.headers.get("X-Forwarded-For") || "local";
  const now = Date.now();
  let entry = STATE.rate.get(ip);
  if (!entry || now - entry.start > RATE_WINDOW_MS) {
    entry = { start: now, count: 0 };
    STATE.rate.set(ip, entry);
  }
  entry.count += 1;
  if (STATE.rate.size > 1000) STATE.rate.delete(STATE.rate.keys().next().value);
  return entry.count <= RATE_MAX;
}

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...headers,
    },
  });
}

function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function authorized(req, env) {
  const token = (env.RAGY_BRIDGE_TOKEN || "").trim();
  if (!token) return false; // fail-closed
  const header = req.headers.get("Authorization") || "";
  if (!header.startsWith("Bearer ")) return false;
  return constantTimeEqual(header.slice(7).trim(), token);
}

function originOk(req, env) {
  const origin = req.headers.get("Origin");
  if (!origin) return true; // non-browser MCP clients
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim()).filter(Boolean);
  return allowed.some(prefix => origin.startsWith(prefix));
}

function idemGet(key, method) {
  if (!key) return "MISS";
  const entry = STATE.idem.get(key);
  if (!entry) return "MISS";
  if (entry.method !== method) return "CONFLICT";
  return entry.response;
}

function idemPut(key, method, response) {
  if (!key) return;
  STATE.idem.set(key, { method, response });
  while (STATE.idem.size > MAX_IDEMPOTENCY) {
    const oldest = STATE.idem.keys().next().value;
    STATE.idem.delete(oldest);
  }
}

async function deny(env, requestId, reason, code, type) {
  try {
    await appendEvent(env.DB, type, "ragy-cloud-engine", requestId || null, { reason });
  } catch { /* audit failure must not leak the reason to the client */ }
  return json({ error: reason }, code, code === 401 ? { "WWW-Authenticate": "Bearer" } : {});
}

const TOOLS = [
  { name: "list_tasks", description: "List tasks from the cloud task store" },
  { name: "get_task", description: "Get one task by task_id" },
  { name: "create_task", description: "Create a task: {title, description?, assigned_role?}" },
  { name: "verify_audit", description: "Verify the SHA-256 audit chain" },
  { name: "create_automation", description: "Create an automation: {name, steps:[{tool,args}], description?}" },
  { name: "list_automations", description: "List automations" },
  { name: "run_automation", description: "Run an automation by automation_id" },
  { name: "list_runs", description: "List recent automation runs" },
  { name: "post_command", description: "Queue a command for the local Hermes agent: {task}" },
  { name: "list_commands", description: "List commands and their status" },
  { name: "delete_automation", description: "Delete an automation. Requires {automation_id, confirm:'DELETE'}" },
  { name: "delete_command", description: "Delete a queued command. Requires {command_id, confirm:'DELETE'}" },
];

function textResult(value) {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

async function callTool(name, args, env, ctx = {}) {
  if (name === "list_tasks") {
    const { results } = await env.DB.prepare("SELECT task_id, title, state, assigned_role, created_at FROM tasks ORDER BY created_at DESC LIMIT 50").all();
    return textResult(results || []);
  }
  if (name === "get_task") {
    const { results } = await env.DB.prepare("SELECT * FROM tasks WHERE task_id = ?").bind(args?.task_id || "").all();
    return textResult(results?.[0] || { error: "not found" });
  }
  if (name === "create_task") {
    const title = String(args?.title || "").trim();
    if (!title) return { ...textResult({ error: "title is required" }), isError: true };
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    await env.DB.prepare(
      `INSERT INTO tasks (task_id,title,description,state,assigned_role,attempt_count,max_attempts,created_at,updated_at)
       VALUES (?,?,?,'created',?,0,3,?,?)`
    ).bind(id, title.slice(0, 200), String(args?.description || "").slice(0, 2000),
           String(args?.assigned_role || "unassigned").slice(0, 80), now, now).run();
    await appendEvent(env.DB, "cloud.task.created", ctx.actor || "ragy-cloud-engine", id, { title: title.slice(0, 200) });
    return textResult({ task_id: id, title, state: "created" });
  }
  if (name === "verify_audit") {
    return textResult(await verifyChain(env.DB));
  }
  if (name === "create_automation") {
    const nameValue = String(args?.name || "").trim();
    const steps = Array.isArray(args?.steps) ? args.steps : [];
    if (!nameValue) return { ...textResult({ error: "name is required" }), isError: true };
    if (!steps.length || steps.length > 20) return { ...textResult({ error: "steps must contain 1-20 items" }), isError: true };
    const allowed = new Set(TOOLS.map(t => t.name));
    for (const s of steps) {
      if (!allowed.has(s?.tool)) return { ...textResult({ error: "unknown tool in steps: " + s?.tool }), isError: true };
      if (s.tool === "run_automation" || s.tool === "create_automation") {
        return { ...textResult({ error: "recursive automation tools are not allowed in steps" }), isError: true };
      }
    }
    const id = crypto.randomUUID();
    await env.DB.prepare(
      `INSERT INTO automations (automation_id,name,description,steps_json,enabled,created_by,created_at)
       VALUES (?,?,?,?,1,?,?)`
    ).bind(id, nameValue.slice(0, 200), String(args?.description || "").slice(0, 1000),
           JSON.stringify(steps), ctx.actor || "ragy-cloud-engine", new Date().toISOString()).run();
    await appendEvent(env.DB, "cloud.automation.created", ctx.actor || "ragy-cloud-engine", id, { name: nameValue, steps: steps.length });
    return textResult({ automation_id: id, name: nameValue, steps: steps.length });
  }
  if (name === "list_automations") {
    const { results } = await env.DB.prepare(
      "SELECT automation_id,name,description,enabled,created_at FROM automations ORDER BY created_at DESC LIMIT 50"
    ).all();
    return textResult(results || []);
  }
  if (name === "run_automation") {
    const id = String(args?.automation_id || "");
    const { results: found } = await env.DB.prepare("SELECT * FROM automations WHERE automation_id = ?").bind(id).all();
    const auto = found?.[0];
    if (!auto) return { ...textResult({ error: "automation not found" }), isError: true };
    if (!auto.enabled) return { ...textResult({ error: "automation is disabled" }), isError: true };
    const steps = JSON.parse(auto.steps_json || "[]");
    const runId = crypto.randomUUID();
    const started = new Date().toISOString();
    await env.DB.prepare(
      "INSERT INTO automation_runs (run_id,automation_id,status,results_json,started_at) VALUES (?,?,'running','[]',?)"
    ).bind(runId, id, started).run();
    await appendEvent(env.DB, "cloud.automation.started", ctx.actor || "ragy-cloud-engine", id, { run_id: runId, steps: steps.length });
    const results = [];
    let ok = true;
    for (const step of steps) {
      try {
        const out = await callTool(step.tool, step.args || {}, env, ctx);
        results.push({ tool: step.tool, ok: !out.isError, output: out.content?.[0]?.text?.slice(0, 2000) });
        if (out.isError) ok = false;
      } catch (error) {
        results.push({ tool: step.tool, ok: false, error: String(error).slice(0, 300) });
        ok = false;
      }
    }
    const finished = new Date().toISOString();
    await env.DB.prepare(
      "UPDATE automation_runs SET status=?,results_json=?,finished_at=? WHERE run_id=?"
    ).bind(ok ? "success" : "partial", JSON.stringify(results), finished, runId).run();
    await appendEvent(env.DB, "cloud.automation.finished", ctx.actor || "ragy-cloud-engine", id,
                      { run_id: runId, status: ok ? "success" : "partial", steps: results.length });
    return textResult({ run_id: runId, automation_id: id, status: ok ? "success" : "partial", results });
  }
  if (name === "list_runs") {
    const { results } = await env.DB.prepare(
      "SELECT run_id,automation_id,status,started_at,finished_at FROM automation_runs ORDER BY started_at DESC LIMIT 50"
    ).all();
    return textResult(results || []);
  }
  if (name === "post_command") {
    const task = String(args?.task || "").trim();
    if (!task) return { ...textResult({ error: "task is required" }), isError: true };
    const id = crypto.randomUUID();
    await env.DB.prepare(
      "INSERT INTO commands (command_id,task,requested_by,status,created_at) VALUES (?,?,?,'pending',?)"
    ).bind(id, task.slice(0, 4000), ctx.actor || "ragy-cloud-engine", new Date().toISOString()).run();
    await appendEvent(env.DB, "cloud.command.posted", ctx.actor || "ragy-cloud-engine", id, { task: task.slice(0, 300) });
    return textResult({ command_id: id, status: "pending" });
  }
  if (name === "list_commands") {
    const { results } = await env.DB.prepare(
      "SELECT command_id,task,status,result_json,created_at,completed_at FROM commands ORDER BY created_at DESC LIMIT 50"
    ).all();
    return textResult(results || []);
  }
  if (name === "delete_automation" || name === "delete_command") {
    const isAuto = name === "delete_automation";
    const id = String(isAuto ? args?.automation_id : args?.command_id || "").trim();
    if (args?.confirm !== "DELETE") {
      return { ...textResult({ error: "confirm must be exactly 'DELETE'" }), isError: true };
    }
    if (!id) return { ...textResult({ error: "id is required" }), isError: true };
    const table = isAuto ? "automations" : "commands";
    const col = isAuto ? "automation_id" : "command_id";
    // runs are historical audit evidence — keep them, only remove the definition/queue item
    const { success } = await env.DB.prepare(`DELETE FROM ${table} WHERE ${col} = ?`).bind(id).run();
    if (!success) return { ...textResult({ error: "delete failed or not found" }), isError: true };
    await appendEvent(env.DB, isAuto ? "cloud.automation.deleted" : "cloud.command.deleted",
                      ctx.actor || "ragy-cloud-engine", id, { deleted: true });
    return textResult({ deleted: true, id, table });
  }
  return { content: [{ type: "text", text: "unknown tool" }], isError: true };
}

const LANDING = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAGY Cloud — Gate</title>
<style>body{background:#0b0e14;color:#e8eef7;font-family:system-ui,'Segoe UI',Tahoma;margin:0;display:grid;place-items:center;min-height:100vh}
.card{background:#121826;border:1px solid #263049;border-radius:16px;padding:28px;width:min(420px,90vw)}
h1{margin:0 0 6px;font-size:22px}p{color:#9fb0c8;font-size:14px;line-height:1.7}
input{width:100%;box-sizing:border-box;background:#0b0e14;border:1px solid #2c3a56;color:#e8eef7;padding:12px;border-radius:8px;margin:10px 0}
button{width:100%;background:#4f8cff;border:0;color:#fff;padding:12px;border-radius:8px;font-weight:bold;cursor:pointer}
#out{margin-top:14px;font-size:13px;word-break:break-all}</style></head><body>
<div class="card"><h1>RAGY Cloud Engine</h1><p>المنصة محمية بـ Bearer token. التوكن لا يُحفظ على الخادم ولا يظهر في الرابط — يُخزَّن فقط في هذا المتصفح.</p>
<input id="tok" type="password" placeholder="RAGY_BRIDGE_TOKEN" autocomplete="off">
<button onclick="go()">دخول</button><div id="out"></div></div>
<script>
function go(){
  var t=document.getElementById('tok').value.trim();
  if(!t){document.getElementById('out').textContent='اكتب التوكن أولاً';return;}
  localStorage.setItem('ragy_token',t);
  fetch('/audit',{headers:{'Authorization':'Bearer '+t}}).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(x){if(x.ok&&x.j.valid){document.getElementById('out').textContent='تم ✅ — جاري فتح اللوحة...';location.href='/app';}else{document.getElementById('out').textContent='فشل: '+JSON.stringify(x.j);}})
  .catch(function(e){document.getElementById('out').textContent='خطأ اتصال: '+e.message;});
}
</script></body></html>`;

const CONSOLE = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAGY Cloud — Console</title>
<style>
:root{color-scheme:dark}body{background:#0b0e14;color:#e8eef7;font-family:system-ui,'Segoe UI',Tahoma;margin:0;padding:24px}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:22px}
h1{margin:0;font-size:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.card{background:#121826;border:1px solid #263049;border-radius:14px;padding:18px}
.card h2{margin:0 0 12px;font-size:15px;color:#9fb0c8}.v{font-size:26px;font-weight:bold}
.ok{color:#4ade80}.bad{color:#f87171}.muted{color:#9fb0c8;font-size:13px}
pre{background:#0b0e14;border:1px solid #263049;border-radius:8px;padding:10px;overflow:auto;max-height:260px;font-size:12px}
button{background:#4f8cff;border:0;color:#fff;padding:9px 14px;border-radius:8px;cursor:pointer}
a{color:#8ab4ff;text-decoration:none}
</style></head><body>
<header><h1>RAGY Cloud Console</h1><div><a href="https://github.com/ragymkm-bot/Jameel-Engine-Verified" target="_blank">GitHub ↗</a> · <button onclick="logout()">خروج</button></div></header>
<div class="grid">
<div class="card"><h2>الحالة</h2><div class="v" id="status">…</div><div class="muted" id="ver">—</div></div>
<div class="card"><h2>سلسلة التدقيق</h2><div class="v" id="audit">…</div><div class="muted" id="auditd">—</div></div>
<div class="card"><h2>المهام</h2><div class="v" id="tasks">…</div><div class="muted">من D1 السحابي</div></div>
<div class="card"><h2>الأدوات المتاحة</h2><pre id="tools">—</pre></div>
<div class="card" style="grid-column:1/-1"><h2>آخر الأحداث</h2><pre id="events">—</pre></div>
<div class="card" style="grid-column:1/-1">
<h2>🏭 Automation Studio — اصنع وشغّل أتمتة</h2>
<p class="muted">خطوات متاحة: create_task · list_tasks · verify_audit · list_automations · list_runs. ممنوع التكرار (/create_automation / run_automation) جوه الخطوات.</p>
<input id="aname" placeholder="اسم الأتمتة (مثلاً: فحص يومي)">
<textarea id="astep" rows="4" placeholder='[{"tool":"verify_audit","args":{}},{"tool":"create_task","args":{"title":"مهمة جديدة"}}]' style="width:100%;box-sizing:border-box;background:#0b0e14;border:1px solid #2c3a56;color:#e8eef7;padding:10px;border-radius:8px;margin-top:10px;font-family:monospace"></textarea>
<div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap"><button onclick="createAuto()">إنشاء أتمتة</button><input id="arun" placeholder="automation_id للتشغيل" style="flex:1;min-width:200px;margin:0"><button onclick="runAuto()">تشغيل ▶</button></div>
<pre id="amsg" style="margin-top:10px">—</pre>
<div class="muted" style="margin-top:14px">الأتمتات: <span id="alist">—</span></div>
<div class="muted" style="margin-top:6px">التشغيلات: <span id="aruns">—</span></div>
</div>
<div class="card" style="grid-column:1/-1">
<h2>📤 قائمة أوامر الجهاز (Hermes Bridge)</h2>
<p class="muted">الأوامر هنا بتتنفّذ على جهازك عن طريق Hermes. اكتب أمر وسيبه قيد الانتظار — الـ bridge هيقرأه وينفّذه ويرجّع النتيجة هنا.</p>
<input id="ctask" placeholder="مثلاً: اقرأ README.md أو اعمل بحث سريع">
<button onclick="postCmd()">إضافة أمر</button>
<pre id="cmsg" style="margin-top:10px">—</pre>
<div class="muted" style="margin-top:8px">الأوامر: <span id="clist">—</span></div>
</div>
</div>
<script>
var T=localStorage.getItem('ragy_token');
if(!T){location.href='/';}
function H(){return {'Authorization':'Bearer '+T,'Content-Type':'application/json'};}
function logout(){localStorage.removeItem('ragy_token');location.href='/';}
function fail(r){if(r.status===401){logout();return true;}return false;}
function load(){
  fetch('/health').then(function(r){return r.json();}).then(function(j){
    document.getElementById('status').textContent=j.status==='ok'?(j.ready?'متصل ✅':'غير جاهز'):'خطأ';
    document.getElementById('status').className='v '+(j.ready?'ok':'bad');
    document.getElementById('ver').textContent=j.service+' v'+j.version;
  });
  fetch('/audit',{headers:H()}).then(function(r){if(fail(r))return;return r.json();}).then(function(j){if(!j)return;
    document.getElementById('audit').textContent=j.valid?'سليمة ✅':'مكسورة ❌';
    document.getElementById('audit').className='v '+(j.valid?'ok':'bad');
    document.getElementById('auditd').textContent=j.checked+' حدث';
  });
  fetch('/tasks',{headers:H()}).then(function(r){if(fail(r))return;return r.json();}).then(function(j){if(!j)return;
    document.getElementById('tasks').textContent=(j.tasks||[]).length;
  });
  fetch('/mcp',{method:'POST',headers:H(),body:JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/list'})}).then(function(r){if(fail(r))return;return r.json();}).then(function(j){if(!j)return;
    document.getElementById('tools').textContent=(j.result.tools||[]).map(function(t){return '• '+t.name+' — '+t.description;}).join('\\n');
  });
  fetch('/mcp',{method:'POST',headers:H(),body:JSON.stringify({jsonrpc:'2.0',id:2,method:'tools/call',params:{name:'verify_audit',arguments:{}}})}).then(function(r){if(fail(r))return;return r.json();}).then(function(j){if(!j)return;
    document.getElementById('events').textContent=j.result.content[0].text;
  });
}
function call(tool,args){
  return fetch('/mcp',{method:'POST',headers:H(),body:JSON.stringify({jsonrpc:'2.0',id:Date.now(),method:'tools/call',params:{name:tool,arguments:args||{}}})})
    .then(function(r){if(fail(r))return null;return r.json();})
    .then(function(j){return j&&j.result?JSON.parse(j.result.content[0].text):null;});
}
function createAuto(){
  var n=document.getElementById('aname').value.trim();
  var s;
  try{s=JSON.parse(document.getElementById('astep').value||'[]');}catch(e){document.getElementById('amsg').textContent='خطأ في JSON الخطوات: '+e.message;return;}
  call('create_automation',{name:n,steps:s}).then(function(j){
    if(!j){return;}
    document.getElementById('amsg').textContent=JSON.stringify(j,null,2);
    if(j.automation_id){document.getElementById('arun').value=j.automation_id;}
    loadLists();
  });
}
function runAuto(){
  var id=document.getElementById('arun').value.trim();
  if(!id){document.getElementById('amsg').textContent='اكتب automation_id';return;}
  document.getElementById('amsg').textContent='جاري التشغيل...';
  call('run_automation',{automation_id:id}).then(function(j){document.getElementById('amsg').textContent=JSON.stringify(j,null,2);loadLists();});
}
function loadLists(){
  call('list_automations',{}).then(function(j){
    if(!j)return;document.getElementById('alist').innerHTML=j.length?j.map(function(a){
      return '<div style="margin:3px 0">'+a.name+' ('+a.automation_id.slice(0,8)+') <button style="padding:3px 8px;font-size:11px;background:#7f1d1d" onclick="delAuto(\''+a.automation_id+'\')">حذف</button></div>';
    }).join(''):'لا توجد أتمتات بعد';
  });
  call('list_runs',{}).then(function(j){
    if(!j)return;document.getElementById('aruns').textContent=j.length?j.slice(0,5).map(function(r){return r.status+' @ '+r.started_at.slice(11,19);}).join(' · '):'لا تشغيلات بعد';
  });
}
function delAuto(id){
  if(!confirm('حذف هذه الأتمتة؟ ستبقى سجلات التشغيل في الـ audit.'))return;
  call('delete_automation',{automation_id:id,confirm:'DELETE'}).then(function(j){document.getElementById('amsg').textContent=JSON.stringify(j,null,2);loadLists();});
}
function delCmd(id){
  if(!confirm('حذف هذا الأمر؟'))return;
  call('delete_command',{command_id:id,confirm:'DELETE'}).then(function(j){document.getElementById('cmsg').textContent=JSON.stringify(j,null,2);loadCommands();});
}
function postCmd(){
  var t=document.getElementById('ctask').value.trim();
  if(!t){document.getElementById('cmsg').textContent='اكتب الأمر أولاً';return;}
  call('post_command',{task:t}).then(function(j){
    document.getElementById('cmsg').textContent=JSON.stringify(j,null,2);
    document.getElementById('ctask').value='';
    loadCommands();
  });
}
function loadCommands(){
  call('list_commands',{}).then(function(j){
    if(!j)return;
    document.getElementById('clist').innerHTML=j.length?j.slice(0,8).map(function(c){
      var col=c.status==='completed'?'#4ade80':(c.status==='failed'?'#f87171':'#fbbf24');
      return '<div style="margin:3px 0"><span style="color:'+col+'">●</span> '+c.status+' — '+c.task.slice(0,80)+' <button style="padding:3px 8px;font-size:11px;background:#7f1d1d" onclick="delCmd(\''+c.command_id+'\')">حذف</button>'+(c.result_json?'<pre>'+c.result_json.slice(0,200)+'</pre>':'')+'</div>';
    }).join(''):'لا أوامر بعد';
  });
}
load();loadLists();loadCommands();setInterval(function(){load();loadLists();loadCommands();},15000);
</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/" && request.method === "GET") {
      return new Response(LANDING, {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
      });
    }

    if ((path === "/ui" || path === "/ui.html") && request.method === "GET") {
      return new Response(UI_HTML, {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
      });
    }

    if (path === "/app" && request.method === "GET") {
      return new Response(CONSOLE, {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
      });
    }

    if (path === "/health" && request.method === "GET") {
      return json({ status: "ok", service: "ragy-cloud-engine", version: "1.0.0", ready: !!(env.RAGY_BRIDGE_TOKEN || "").trim() });
    }

    if (!rateOk(request)) return deny(env, "", "rate limit exceeded", 429, "cloud.rate.denied");

    if (!authorized(request, env)) return deny(env, "", "unauthorized", 401, "cloud.auth.denied");
    if (!originOk(request, env)) return deny(env, "", "origin not allowed", 403, "cloud.origin.denied");

    const requestId = request.headers.get("X-Request-Id") || "";

    if (path === "/mcp" && request.method === "POST") {
      let payload;
      try { payload = await request.json(); }
      catch { return deny(env, requestId, "invalid json", 400, "cloud.payload.denied"); }

      const method = payload?.method || "";
      const cached = idemGet(requestId, method + JSON.stringify(payload));
      if (cached === "CONFLICT") return deny(env, requestId, "request id reused with different payload", 409, "cloud.idempotency.conflict");
      if (cached !== "MISS") {
        return json(cached.response, 200, { "X-Idempotent-Hit": "true" });
      }

      let response;
      if (method === "initialize") {
        response = { jsonrpc: "2.0", id: payload.id, result: { protocolVersion: "2025-06-18", serverInfo: { name: "ragy-cloud", version: "1.0.0" }, tools: TOOLS } };
      } else if (method === "tools/list") {
        response = { jsonrpc: "2.0", id: payload.id, result: { tools: TOOLS } };
      } else if (method === "tools/call") {
        const result = await callTool(payload.params?.name, payload.params?.arguments, env);
        response = { jsonrpc: "2.0", id: payload.id, result };
      } else if (method === "ping") {
        response = { jsonrpc: "2.0", id: payload.id, result: {} };
      } else {
        response = { jsonrpc: "2.0", id: payload.id, error: { code: -32601, message: "method not found" } };
      }

      idemPut(requestId, method + JSON.stringify(payload), { response });
      await appendEvent(env.DB, "cloud.request.served", "ragy-cloud-engine", requestId || null, { method, ok: !response.error });
      return json(response);
    }

    if (path === "/tasks" && request.method === "GET") {
      const { results } = await env.DB.prepare("SELECT task_id, title, state, assigned_role, created_at FROM tasks ORDER BY created_at DESC LIMIT 100").all();
      return json({ tasks: results || [] });
    }

    // ---- Bridge endpoints (local Hermes poller ⇄ cloud outbox) ----
    if (path === "/bridge/claim" && request.method === "POST") {
      const { results } = await env.DB.prepare(
        "SELECT command_id,task,requested_by,created_at FROM commands WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
      ).all();
      const cmd = results?.[0];
      if (!cmd) return json({ claimed: false });
      const { success } = await env.DB.prepare(
        "UPDATE commands SET status='claimed', claimed_at=? WHERE command_id=? AND status='pending'"
      ).bind(new Date().toISOString(), cmd.command_id).run();
      await appendEvent(env.DB, "cloud.command.claimed", "hermes-poller", cmd.command_id, { task: cmd.task.slice(0, 200) });
      return json(success ? { claimed: true, command: cmd } : { claimed: false });
    }

    if (path === "/bridge/complete" && request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      const id = String(body?.command_id || "").trim();
      const resultJson = JSON.stringify(body?.result || {}).slice(0, 10000);
      const status = body?.status === "failed" ? "failed" : "completed";
      if (!id) return json({ error: "command_id required" }, 400);
      const { success } = await env.DB.prepare(
        "UPDATE commands SET status=?,result_json=?,completed_at=? WHERE command_id=? AND status='claimed'"
      ).bind(status, resultJson, new Date().toISOString(), id).run();
      await appendEvent(env.DB, status === "failed" ? "cloud.command.failed" : "cloud.command.completed",
                        "hermes-poller", id, { status });
      return json({ updated: success });
    }

    if (path === "/audit" && request.method === "GET") {
      return json(await verifyChain(env.DB));
    }

    return json({ error: "not found" }, 404);
  },
};
