// SHA-256 hash-chain audit — faithful port of ragy_agents/audit.py to Web Crypto.
// Canonical JSON = sort_keys=True, separators=(",", ":"), ensure_ascii=False.

function canonicalize(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalize).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map(k => JSON.stringify(k) + ":" + canonicalize(value[k])).join(",") + "}";
}

async function eventHash(eventWithoutHash) {
  const bytes = new TextEncoder().encode(canonicalize(eventWithoutHash));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function rowToEvent(row) {
  const event = {
    sequence: row.sequence,
    timestamp: row.timestamp,
    event_type: row.event_type,
    actor: row.actor,
    task_id: row.task_id ?? null,
    payload: JSON.parse(row.payload_json || "{}"),
    previous_hash: row.previous_hash ?? null,
  };
  event.event_hash = row.event_hash;
  return event;
}

export async function lastEvent(db) {
  const { results } = await db.prepare(
    "SELECT sequence, event_hash FROM audit_log ORDER BY sequence DESC LIMIT 1"
  ).all();
  return results && results.length ? results[0] : null;
}

export async function appendEvent(db, eventType, actor, taskId, payload) {
  const last = await lastEvent(db);
  const event = {
    sequence: (last?.sequence ?? 0) + 1,
    timestamp: new Date().toISOString(),
    event_type: eventType,
    actor: actor || "ragy-cloud-engine",
    task_id: taskId || null,
    payload: payload || {},
    previous_hash: last?.event_hash ?? null,
  };
  event.event_hash = await eventHash(event);
  await db.prepare(
    `INSERT INTO audit_log (sequence, event_hash, previous_hash, event_type, actor, task_id, payload_json, timestamp)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    event.sequence, event.event_hash, event.previous_hash, event.event_type,
    event.actor, event.task_id, JSON.stringify(event.payload), event.timestamp
  ).run();
  return event;
}

export async function verifyChain(db) {
  const { results } = await db.prepare(
    "SELECT * FROM audit_log ORDER BY sequence ASC"
  ).all();
  let previousHash = null;
  let expected = 1;
  for (const row of results || []) {
    const event = rowToEvent(row);
    const supplied = event.event_hash;
    delete event.event_hash;
    if (event.sequence !== expected) return { valid: false, checked: expected - 1, reason: "sequence mismatch" };
    if (event.previous_hash !== previousHash) return { valid: false, checked: expected - 1, reason: "predecessor mismatch" };
    if (supplied !== await eventHash(event)) return { valid: false, checked: expected - 1, reason: "hash mismatch" };
    previousHash = supplied;
    expected += 1;
  }
  return { valid: true, checked: expected - 1 };
}
