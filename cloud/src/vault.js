// RAGY Secrets Vault — AES-GCM encrypted secrets in D1.
// Key derived from RAGY_BRIDGE_TOKEN (already a Workers Secret) via SHA-256.
// Values are NEVER returned to any endpoint — only names + timestamps.
// Fail-closed: no bridge token → no encryption key → refuse all operations.

const encoder = new TextEncoder();

async function vaultKey(env) {
  const base = (env.RAGY_BRIDGE_TOKEN || "").trim();
  if (!base) throw new Error("vault unavailable: RAGY_BRIDGE_TOKEN missing");
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode("ragy-vault-v1:" + base));
  return crypto.subtle.importKey("raw", digest, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

export async function putSecret(env, keyName, value) {
  const name = String(keyName || "").trim().toUpperCase().replace(/[^A-Z0-9_]/g, "");
  if (!name) throw new Error("invalid secret name");
  if (typeof value !== "string" || !value.trim()) throw new Error("empty secret value");
  if (value.length > 8000) throw new Error("secret too large");
  const key = await vaultKey(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, encoder.encode(value.trim()));
  const hex = (arr) => [...arr].map(b => b.toString(16).padStart(2, "0")).join("");
  await env.DB.prepare(
    "INSERT INTO vault (key_name,iv,ciphertext,updated_at) VALUES (?,?,?,?) ON CONFLICT(key_name) DO UPDATE SET iv=excluded.iv,ciphertext=excluded.ciphertext,updated_at=excluded.updated_at"
  ).bind(name, hex(iv), hex(new Uint8Array(encrypted)), new Date().toISOString()).run();
  return { key_name: name, stored: true };
}

export async function getSecret(env, keyName) {
  const name = String(keyName || "").trim().toUpperCase();
  const { results } = await env.DB.prepare("SELECT * FROM vault WHERE key_name=?").bind(name).all();
  const row = results?.[0];
  if (!row) return null;
  const key = await vaultKey(env);
  const iv = new Uint8Array(row.iv.match(/.{2}/g).map(b => parseInt(b, 16)));
  const data = new Uint8Array(row.ciphertext.match(/.{2}/g).map(b => parseInt(b, 16)));
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, data);
  return new TextDecoder().decode(plain);
}

export async function listSecrets(env) {
  const { results } = await env.DB.prepare("SELECT key_name,updated_at FROM vault ORDER BY key_name").all();
  return (results || []).map(r => ({ key_name: r.key_name, updated_at: r.updated_at }));
}

export async function deleteSecret(env, keyName) {
  const name = String(keyName || "").trim().toUpperCase();
  await env.DB.prepare("DELETE FROM vault WHERE key_name=?").bind(name).run();
  return { key_name: name, deleted: true };
}
