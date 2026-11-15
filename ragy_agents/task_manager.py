"""SQLite-backed task, approval, result, and audit coordination."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .audit import StructuredAuditLog
from .exceptions import ApprovalRequiredError, ValidationError
from .models import AgentResult, AgentRole, ApprovalRequest, Capability, Task, TaskState
from .policy import PolicyEnforcer
from .state_machine import assert_transition


class TaskManager:
    """The coordinator-owned, single-writer SQLite state store."""

    MAX_PAYLOAD_CHARS = 256 * 1024

    def __init__(
        self, database_path: Path, policy: PolicyEnforcer, audit_log: StructuredAuditLog
    ) -> None:
        self.policy = policy
        self.database_path = policy.require_project_path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log = audit_log
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
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
            """
        )
        self.connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _to_task(row: sqlite3.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            state=TaskState(row["state"]),
            assigned_role=AgentRole(row["assigned_role"]) if row["assigned_role"] else None,
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _require(self, capability: Capability, actor: AgentRole) -> None:
        self.policy.require(actor, capability)

    def _audit(self, event_type: str, task_id: str | None, payload: dict[str, object]) -> None:
        self._require(Capability.AUDIT_APPEND, AgentRole.COORDINATOR)
        self.audit_log.append(event_type, AgentRole.COORDINATOR.value, task_id, payload)

    def get_task(self, task_id: str) -> Task:
        row = self.connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValidationError(f"Unknown task: {task_id}")
        return self._to_task(row)

    def create_task(
        self,
        title: str,
        description: str,
        *,
        max_attempts: int = 2,
        actor: AgentRole = AgentRole.COORDINATOR,
    ) -> Task:
        self._require(Capability.TASK_CREATE, actor)
        if not title.strip() or not description.strip():
            raise ValidationError("Task title and description are required")
        if len(title) + len(description) > self.MAX_PAYLOAD_CHARS:
            raise ValidationError("Task payload exceeds the Phase 1 limit")
        if max_attempts < 1:
            raise ValidationError("max_attempts must be at least one")
        task_id = str(uuid.uuid4())
        now = self._now()
        self.connection.execute(
            """INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, title.strip(), description.strip(), TaskState.DRAFT.value, None, 0, max_attempts, now, now),
        )
        self.connection.commit()
        self._audit("task.created", task_id, {"state": TaskState.DRAFT.value})
        return self.get_task(task_id)

    def plan_task(self, task_id: str, *, actor: AgentRole = AgentRole.COORDINATOR) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        return self._transition(task_id, TaskState.PLANNED, "task.planned")

    def request_approval(
        self, task_id: str, reason: str, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> ApprovalRequest:
        self._require(Capability.APPROVAL_REQUEST, actor)
        task = self.get_task(task_id)
        assert_transition(task.state, TaskState.AWAITING_APPROVAL)
        if not reason.strip():
            raise ValidationError("Approval reason is required")
        now = self._now()
        request_id = str(uuid.uuid4())
        self.connection.execute(
            "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
            (TaskState.AWAITING_APPROVAL.value, now, task_id),
        )
        self.connection.execute(
            "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, task_id, reason.strip(), actor.value, "requested", None, now, None),
        )
        self.connection.commit()
        self._audit("task.transitioned", task_id, {"from": task.state.value, "to": TaskState.AWAITING_APPROVAL.value})
        self._audit("approval.requested", task_id, {"request_id": request_id, "reason": reason.strip()})
        return self.get_approval(request_id)

    def get_approval(self, request_id: str) -> ApprovalRequest:
        row = self.connection.execute(
            "SELECT * FROM approvals WHERE request_id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"Unknown approval request: {request_id}")
        return ApprovalRequest(
            request_id=row["request_id"],
            task_id=row["task_id"],
            reason=row["reason"],
            requested_by=row["requested_by"],
            status=row["status"],
            approver=row["approver"],
            created_at=row["created_at"],
            decided_at=row["decided_at"],
        )

    def grant_approval(
        self, request_id: str, approver: str, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> ApprovalRequest:
        self._require(Capability.APPROVAL_GRANT, actor)
        request = self.get_approval(request_id)
        if request.status != "requested":
            raise ValidationError(f"Approval request is already {request.status}")
        if not approver.strip():
            raise ValidationError("Human approver is required")
        now = self._now()
        self.connection.execute(
            "UPDATE approvals SET status = ?, approver = ?, decided_at = ? WHERE request_id = ?",
            ("approved", approver.strip(), now, request_id),
        )
        self.connection.commit()
        self._audit("approval.granted", request.task_id, {"request_id": request_id, "approver": approver.strip()})
        return self.get_approval(request_id)

    def _has_approval(self, task_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM approvals WHERE task_id = ? AND status = 'approved' LIMIT 1", (task_id,)
        ).fetchone()
        return row is not None

    def assign_agent(
        self, task_id: str, role: AgentRole, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> Task:
        self._require(Capability.TASK_ASSIGN, actor)
        if role is AgentRole.COORDINATOR:
            raise ValidationError("The coordinator cannot be assigned as a worker")
        task = self.get_task(task_id)
        assert_transition(task.state, TaskState.ASSIGNED)
        if not self._has_approval(task_id):
            raise ApprovalRequiredError("A human approval is required before assignment")
        now = self._now()
        self.connection.execute(
            "UPDATE tasks SET state = ?, assigned_role = ?, updated_at = ? WHERE task_id = ?",
            (TaskState.ASSIGNED.value, role.value, now, task_id),
        )
        self.connection.commit()
        self._audit("task.assigned", task_id, {"role": role.value})
        return self.get_task(task_id)

    def start_work(self, task_id: str, *, actor: AgentRole = AgentRole.COORDINATOR) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        task = self.get_task(task_id)
        assert_transition(task.state, TaskState.WORKING)
        if task.assigned_role is None:
            raise ValidationError("A task requires an assigned worker")
        now = self._now()
        self.connection.execute(
            "UPDATE tasks SET state = ?, attempt_count = ?, updated_at = ? WHERE task_id = ?",
            (TaskState.WORKING.value, task.attempt_count + 1, now, task_id),
        )
        self.connection.commit()
        self._audit("task.started", task_id, {"attempt": task.attempt_count + 1})
        return self.get_task(task_id)

    def record_result(
        self, result: AgentResult, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        task = self.get_task(result.task_id)
        if task.state is not TaskState.WORKING:
            raise ValidationError("Only a working task can submit evidence")
        if task.assigned_role is not result.role:
            raise ValidationError("Result role does not match the assigned role")
        if not result.success:
            return self.record_failure(result.task_id, result.summary, actor=actor)
        self._validate_result(result)
        self._store_result(result)
        return self._transition(result.task_id, TaskState.EVIDENCE_SUBMITTED, "evidence.submitted")

    def record_failure(
        self, task_id: str, reason: str, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        task = self.get_task(task_id)
        if task.state is not TaskState.WORKING:
            raise ValidationError("Only a working task can fail")
        target = TaskState.BLOCKED if task.attempt_count >= task.max_attempts else TaskState.ASSIGNED
        self._audit("agent.failed", task_id, {"attempt": task.attempt_count, "reason": reason})
        return self._transition(task_id, target, "task.retry_scheduled" if target is TaskState.ASSIGNED else "task.blocked")

    def start_review(self, task_id: str, *, actor: AgentRole = AgentRole.COORDINATOR) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        return self._transition(task_id, TaskState.UNDER_REVIEW, "review.started")

    def record_review(
        self, result: AgentResult, *, actor: AgentRole = AgentRole.COORDINATOR
    ) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        task = self.get_task(result.task_id)
        if task.state is not TaskState.UNDER_REVIEW:
            raise ValidationError("A review is not currently expected")
        if result.role is not AgentRole.QUALITY:
            raise ValidationError("Only the quality role may submit a review")
        if result.review_decision not in {TaskState.ACCEPTED, TaskState.REJECTED}:
            raise ValidationError("A review must accept or reject the task")
        self._validate_result(result)
        self._store_result(result)
        return self._transition(result.task_id, result.review_decision, "review.completed")

    def close_task(self, task_id: str, *, actor: AgentRole = AgentRole.COORDINATOR) -> Task:
        self._require(Capability.TASK_TRANSITION, actor)
        return self._transition(task_id, TaskState.CLOSED, "task.closed")

    def list_results(self, task_id: str) -> list[AgentResult]:
        rows = self.connection.execute(
            "SELECT * FROM task_results WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
        return [
            AgentResult(
                task_id=row["task_id"],
                role=AgentRole(row["role"]),
                summary=row["summary"],
                evidence=tuple(json.loads(row["evidence_json"])),
                success=bool(row["success"]),
                review_decision=TaskState(row["review_decision"]) if row["review_decision"] else None,
                dry_run=bool(row["dry_run"]),
            )
            for row in rows
        ]

    def _validate_result(self, result: AgentResult) -> None:
        if not result.summary.strip() or not result.evidence:
            raise ValidationError("Results require a summary and at least one evidence item")
        serialized = json.dumps(
            {"summary": result.summary, "evidence": result.evidence}, ensure_ascii=False
        )
        if len(serialized) > self.MAX_PAYLOAD_CHARS:
            raise ValidationError("Result payload exceeds the Phase 1 limit")

    def _store_result(self, result: AgentResult) -> None:
        self.connection.execute(
            "INSERT INTO task_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                result.task_id,
                result.role.value,
                result.summary,
                json.dumps(result.evidence, ensure_ascii=False),
                int(result.success),
                result.review_decision.value if result.review_decision else None,
                int(result.dry_run),
                self._now(),
            ),
        )
        self.connection.commit()

    def _transition(self, task_id: str, target: TaskState, event_type: str) -> Task:
        task = self.get_task(task_id)
        assert_transition(task.state, target)
        now = self._now()
        self.connection.execute(
            "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
            (target.value, now, task_id),
        )
        self.connection.commit()
        self._audit(event_type, task_id, {"from": task.state.value, "to": target.value})
        return self.get_task(task_id)
