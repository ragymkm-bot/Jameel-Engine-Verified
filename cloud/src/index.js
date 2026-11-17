// RAGY Cloud Engine — Cloudflare Worker.
// Bearer auth + Origin allowlist + bounded idempotency + SHA-256 audit.
// No secrets in source. Fail-closed when the token secret is missing.

import { appendEvent, verifyChain } from "./audit.js";

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
  { name: "verify_audit", description: "Verify the SHA-256 audit chain" },
];

async function callTool(name, args, env) {
  if (name === "list_tasks") {
    const { results } = await env.DB.prepare("SELECT task_id, title, state, assigned_role, created_at FROM tasks ORDER BY created_at DESC LIMIT 50").all();
    return { content: [{ type: "text", text: JSON.stringify(results || [], null, 2) }] };
  }
  if (name === "get_task") {
    const { results } = await env.DB.prepare("SELECT * FROM tasks WHERE task_id = ?").bind(args?.task_id || "").all();
    return { content: [{ type: "text", text: JSON.stringify(results?.[0] || { error: "not found" }, null, 2) }] };
  }
  if (name === "verify_audit") {
    const v = await verifyChain(env.DB);
    return { content: [{ type: "text", text: JSON.stringify(v) }] };
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
  .then(function(x){document.getElementById('out').textContent=x.ok&&x.j.valid?('متصل ✅ — السجل سليم ('+x.j.checked+' حدث). جاهز للوحة التحكم.'):('فشل: '+JSON.stringify(x.j));})
  .catch(function(e){document.getElementById('out').textContent='خطأ اتصال: '+e.message;});
}
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

    if (path === "/audit" && request.method === "GET") {
      return json(await verifyChain(env.DB));
    }

    return json({ error: "not found" }, 404);
  },
};
