"""Typed domain models shared by the offline coordinator and Mock Agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskState(str, Enum):
    DRAFT = "Draft"
    PLANNED = "Planned"
    AWAITING_APPROVAL = "AwaitingApproval"
    ASSIGNED = "Assigned"
    WORKING = "Working"
    EVIDENCE_SUBMITTED = "EvidenceSubmitted"
    UNDER_REVIEW = "UnderReview"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    BLOCKED = "Blocked"
    CLOSED = "Closed"


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    RESEARCH = "research"
    DEVELOPER = "developer"
    QUALITY = "quality"
    AUTOMATION = "automation"


class Capability(str, Enum):
    TASK_CREATE = "task.create"
    TASK_ASSIGN = "task.assign"
    TASK_TRANSITION = "task.transition"
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_GRANT = "approval.grant"
    AUDIT_APPEND = "audit.append"
    NETWORK_CONNECT = "network.connect"
    PROVIDER_INVOKE = "provider.invoke"
    PROCESS_SPAWN = "process.spawn"
    PACKAGE_INSTALL = "package.install"
    EXTERNAL_EFFECT = "external.effect"


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    description: str
    state: TaskState
    assigned_role: AgentRole | None
    attempt_count: int
    max_attempts: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    role: AgentRole
    summary: str
    evidence: tuple[str, ...]
    success: bool = True
    review_decision: TaskState | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    task_id: str
    reason: str
    requested_by: str
    status: str
    approver: str | None
    created_at: str
    decided_at: str | None


@dataclass(frozen=True)
class AuditVerification:
    valid: bool
    checked_events: int
    reason: str | None = None
