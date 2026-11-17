"""Hermes Execution Engine CLI — submit a task, get a verified result.

Usage:
  python engine_cli.py --task "list files"
  python engine_cli.py --task "read README.md"
  python engine_cli.py --task "check n8n status"
  python engine_cli.py --task "write code for X" --approve --approver "bashmohands ragy"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ragy_agents.audit import StructuredAuditLog
from engine.execution_engine import ExecutionEngine
from ragy_agents.policy import PolicyEnforcer


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Execution Engine")
    parser.add_argument("--task", required=True, help="Task description in Arabic or English")
    parser.add_argument("--task-id", default="task-cli")
    parser.add_argument("--approve", action="store_true", help="Grant human approval for external-effect tools")
    parser.add_argument("--approver", default="local-console-user")
    parser.add_argument("--data-dir", default="runtime")
    parser.add_argument("--python", help="Python executable path (defaults to current interpreter)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    data_dir = root / args.data_dir
    policy = PolicyEnforcer(root)
    safe_dir = policy.require_project_path(data_dir)
    audit = StructuredAuditLog(safe_dir / "audit.jsonl", policy)

    python_path = Path(args.python) if args.python else Path(__import__("sys").executable)
    engine = ExecutionEngine(
        project_root=root,
        audit_log=audit,
        mcp_server=root / "mcp_stdio_server.py",
        python_executable=python_path,
        codex_entrypoint=root / "tools" / "codex-app" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js",
    )

    from ragy_agents.exceptions import ValidationError as _ValidationError
    try:
        result = engine.execute(
            args.task_id,
            args.task,
            approved=args.approve,
            approver=args.approver if args.approve else None,
        )
    except _ValidationError as exc:
        print(json.dumps({"task_id": args.task_id, "status": "denied", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(ExecutionEngine.to_dict(result), ensure_ascii=False, indent=2))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
