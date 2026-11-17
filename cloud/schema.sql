-- RAGY Cloud D1 schema (matches the existing empty ragy-tasks database).
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  state TEXT NOT NULL,
  assigned_role TEXT,
  attempt_count INTEGER NOT NULL,
  max_attempts INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  request_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  status TEXT NOT NULL,
  approver TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT
);

CREATE TABLE IF NOT EXISTS task_results (
  result_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  role TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  success INTEGER NOT NULL,
  review_decision TEXT,
  dry_run INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_hash TEXT NOT NULL,
  previous_hash TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  task_id TEXT,
  payload_json TEXT NOT NULL,
  timestamp TEXT NOT NULL
);
