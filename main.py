"""Run one fully local, Mock Agent workflow without network or API access."""

from __future__ import annotations

import argparse
from pathlib import Path

from ragy_agents.models import AgentRole, TaskState
from ragy_agents.orchestrator import CoreOrchestrator


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline Ragy AI Agents demo.")
    parser.add_argument(
        "--data-dir",
        default="runtime",
        help="Project-relative directory for SQLite state and the audit log (default: runtime).",
    )
    parser.add_argument(
        "--role",
        choices=("research", "developer", "automation"),
        default="research",
        help="Mock Agent role to dispatch after approval.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Record an explicit local human approval and dispatch the selected Mock Agent.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent
    data_directory = project_root / arguments.data_dir
    orchestrator = CoreOrchestrator(project_root, data_directory)
    try:
        task, approval = orchestrator.create_planned_task(
            "Local Mock Agent demonstration",
            "Demonstrate an offline, approval-gated workflow with no external effects.",
        )
        print(f"Task {task.task_id} is awaiting human approval: {approval.request_id}")
        if not arguments.approve:
            print("No agent was dispatched. Re-run with --approve after a human decision.")
            return 0
        role = AgentRole(arguments.role)
        orchestrator.grant_human_approval(approval.request_id, "local-console-user")
        orchestrator.assign_approved_task(task.task_id, role)
        task = orchestrator.dispatch_assigned_task(task.task_id)
        if task.state is TaskState.EVIDENCE_SUBMITTED:
            task = orchestrator.review_evidence(task.task_id)
        if task.state is TaskState.ACCEPTED:
            task = orchestrator.close_if_accepted(task.task_id)
        print(f"Task completed in state: {task.state.value}")
        print(f"Audit verification: {orchestrator.audit_log.verify().valid}")
        return 0
    finally:
        orchestrator.close()


if __name__ == "__main__":
    raise SystemExit(main())
