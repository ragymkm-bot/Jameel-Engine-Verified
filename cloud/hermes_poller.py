"""Hermes Poller — executes cloud commands locally through the real ExecutionEngine.

Reads pending commands from the RAGY Cloud outbox (/bridge/claim), executes them
with the local Hermes Execution Engine (allowlisted tools + human approval gate +
SHA-256 audit), then writes the verified result back (/bridge/complete).

Security:
- Token read from cloud/.dev-token (gitignored), never hardcoded.
- The engine's own policy/safe-zone still applies. Nothing bypassed.
- No external network except the configured RAGY worker URL.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer
from engine.execution_engine import ExecutionEngine, ExecutionResult

BASE = os.environ.get("RAGY_CLOUD_URL", "https://ragy-cloud-engine.aragy76.workers.dev").rstrip("/")
TOKEN_FILE = ROOT / "cloud" / ".dev-token"
INTERVAL = int(os.environ.get("RAGY_POLL_INTERVAL", "6"))
APPROVER = os.environ.get("RAGY_APPROVER", "local-console-user")
AUTO_APPROVE = os.environ.get("RAGY_AUTO_APPROVE", "0") == "1"  # opt-in, default fail-closed


def token() -> str:
    t = TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.exists() else ""
    if not t:
        raise RuntimeError("cloud/.dev-token missing — cannot authenticate to cloud")
    return t


def api(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token()}"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def build_engine() -> ExecutionEngine:
    policy = PolicyEnforcer(ROOT)
    data_dir = policy.require_project_path(ROOT / "runtime")
    audit = StructuredAuditLog(data_dir / "audit.jsonl", policy)
    return ExecutionEngine(
        project_root=ROOT,
        audit_log=audit,
        mcp_server=ROOT / "mcp_stdio_server.py",
        python_executable=Path(sys.executable),
        codex_entrypoint=ROOT / "tools" / "codex-app" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js",
    )


def run_once(engine: ExecutionEngine) -> bool:
    try:
        reply = api("/bridge/claim", {})
    except Exception as exc:
        print(f"[poll] claim error: {exc}", flush=True)
        return False
    if not reply.get("claimed"):
        return False
    cmd = reply["command"]
    cid, task = cmd["command_id"], cmd["task"]
    print(f"[exec] {cid}: {task}", flush=True)
    try:
        result: ExecutionResult = engine.execute(
            task_id=cid,
            description=task,
            approved=AUTO_APPROVE,
            approver=APPROVER if AUTO_APPROVE else None,
        )
        payload = {"status": result.status, "engine": ExecutionEngine.to_dict(result)}
        status = "completed" if result.status == "completed" else "failed"
    except Exception as exc:
        payload = {"status": "denied", "error": str(exc)[:500]}
        status = "failed"
    try:
        api("/bridge/complete", {"command_id": cid, "status": status, "result": payload})
        print(f"[done] {cid}: {status}", flush=True)
    except Exception as exc:
        print(f"[error] complete failed for {cid}: {exc}", flush=True)
    return True


def main() -> None:
    engine = build_engine()
    print(f"Hermes Poller ready → {BASE} | interval={INTERVAL}s | auto_approve={AUTO_APPROVE}", flush=True)
    while True:
        try:
            run_once(engine)
        except KeyboardInterrupt:
            print("\n[poll] stopped", flush=True)
            return
        except Exception as exc:
            print(f"[poll] unexpected: {exc}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
