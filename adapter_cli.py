"""Hermes Adapter CLI — submit a task with request/correlation IDs and bounded approval.

  python adapter_cli.py --task "read README.md"
  python adapter_cli.py --task "write code" --approve --approver "bashmohands ragy"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer
from engine.execution_engine import ExecutionEngine
from engine.hermes_adapter import HermesAdapter


def main() -> int:
    p = argparse.ArgumentParser(description="Hermes Adapter (SEQ 007 T1–T2)")
    p.add_argument("--task", required=True)
    p.add_argument("--request-id", default=str(uuid.uuid4()))
    p.add_argument("--correlation-id", default=str(uuid.uuid4()))
    p.add_argument("--approve", action="store_true")
    p.add_argument("--approver", default="local-console-user")
    p.add_argument("--data-dir", default="runtime")
    args = p.parse_args()

    root = Path(__file__).resolve().parent
    data = root / args.data_dir
    policy = PolicyEnforcer(root)
    audit = StructuredAuditLog(policy.require_project_path(data) / "audit.jsonl", policy)
    engine = ExecutionEngine(
        project_root=root, audit_log=audit,
        mcp_server=root / "mcp_stdio_server.py",
        python_executable=Path(sys.executable),
        codex_entrypoint=root / "tools" / "codex-app" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js",
    )
    adapter = HermesAdapter(engine, audit)

    if args.approve:
        adapter.grant_approval(args.request_id, args.approver, args.task)
    out = adapter.submit(
        args.task,
        request_id=args.request_id,
        correlation_id=args.correlation_id,
        approver=args.approver if args.approve else None,
    )
    print(json.dumps({
        "request_id": out.request_id,
        "correlation_id": out.correlation_id,
        "task_id": out.task_id,
        "status": out.status,
        "idempotent_hit": out.idempotent_hit,
        "audit_valid": out.result.get("audit_valid"),
        "audit_sequence": out.result.get("audit_sequence"),
        "approved_by": out.result.get("approved_by"),
    }, ensure_ascii=False, indent=2))
    return 0 if out.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
