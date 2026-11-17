// WhatsApp Business Cloud API adapter — RAGY Cloud.
// Converts inbound WhatsApp messages into RAGY commands / Copilot questions.
// NO token in code. Meta webhook verification + HMAC signature required.
// NOT active until WHATSAPP_TOKEN + WHATSAPP_VERIFY_TOKEN secrets are set
// and the Meta webhook URL is registered (external action needs owner approval).

const META_GRAPH = "https://graph.facebook.com/v23.0";

export function verifyWebhook(url, env) {
  const mode = url.searchParams.get("hub.mode");
  const token = url.searchParams.get("hub.verify_token");
  const challenge = url.searchParams.get("hub.challenge");
  const expected = (env.WHATSAPP_VERIFY_TOKEN || "").trim();
  if (mode === "subscribe" && expected && token === expected) {
    return new Response(challenge || "", { status: 200, headers: { "Content-Type": "text/plain" } });
  }
  return new Response("forbidden", { status: 403 });
}

// Meta signs every webhook payload with X-Hub-Signature-256 = sha256=HMAC(app_secret, rawBody).
// We use WHATSAPP_APP_SECRET (separate from the access token). Fail-closed if missing.
export async function validSignature(request, rawBody, env) {
  const secret = (env.WHATSAPP_APP_SECRET || "").trim();
  if (!secret) return false;
  const sig = request.headers.get("X-Hub-Signature-256") || "";
  if (!sig.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody));
  const hex = [...new Uint8Array(mac)].map(b => b.toString(16).padStart(2, "0")).join("");
  return constantTimeEqual(sig.slice(7), hex);
}

function constantTimeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function extractMessages(payload) {
  const out = [];
  for (const entry of payload?.entry || []) {
    for (const change of entry?.changes || []) {
      if (change?.field !== "messages") continue;
      for (const msg of change?.value?.messages || []) {
        if (msg?.type !== "text" || !msg?.text?.body) continue;
        out.push({
          from: msg.from,
          text: msg.text.body.trim().slice(0, 4000),
          message_id: msg.id,
          timestamp: msg.timestamp,
        });
      }
    }
  }
  return out;
}

export async function sendText(to, text, env) {
  const token = (env.WHATSAPP_TOKEN || "").trim();
  const phoneId = (env.WHATSAPP_PHONE_ID || "").trim();
  if (!token || !phoneId) throw new Error("WhatsApp secrets not configured");
  const resp = await fetch(`${META_GRAPH}/${phoneId}/messages`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      messaging_product: "whatsapp", to,
      type: "text", text: { body: String(text).slice(0, 4000), preview_url: false },
    }),
  });
  if (!resp.ok) throw new Error(`Meta HTTP ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  return resp.json();
}

export function isConfigured(env) {
  return !!(env.WHATSAPP_TOKEN || "").trim() && !!(env.WHATSAPP_PHONE_ID || "").trim()
      && !!(env.WHATSAPP_VERIFY_TOKEN || "").trim() && !!(env.WHATSAPP_APP_SECRET || "").trim();
}
