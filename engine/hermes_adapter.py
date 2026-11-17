"""Hermes Adapter — correlation, idempotency, approval-with-TTL over ExecutionEngine.

Wraps the existing engine WITHOUT modifying it. Adds what SEQ 007 identified as gaps:
- Task correlation: request_id, correlation_id, unique task_id.
- Idempotency: duplicate request_id + same payload returns the cached result, no re-execution.
- Approval gate with TTL: approval is bound to a request, has an expiry, records approver,
  and cannot be replayed from an old approval.
- Every decision is appended to the same SHA-256 audit chain.

Local-only. No network, no secrets, no infrastructure. Implementation of SEQ 007 T1–T2.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.exceptions import AuthorizationError, RagyAgentsError, ValidationError

from .execution_engine import ExecutionEngine, ExecutionResult


class AdapterError(RagyAgentsError):  # type: ignore[name-defined]
    """Adapter-level rejection (duplicate, expired approval, bad request)."""


@dataclass(frozen=True)
class ApprovalGrant:
    request_id: str
    approver: str
    granted_at: float
    expires_at: float
    payload_hash: str


@dataclass(frozen=True)
class AdapterResult:
    request_id: str
    correlation_id: str
    task_id: str
    status: str
    result: dict[str, Any]
    idempotent_hit: bool


class HermesAdapter:
    """Single entry point for submitting RAGY tasks from any upstream (Notion, future Gateway)."""

    APPROVAL_TTL_SECONDS = 300  # 5 minutes; an old approval cannot authorize a new request

    def __init__(self, engine: ExecutionEngine, audit_log: StructuredAuditLog) -> None:
        self.engine = engine
        self.audit = audit_log
        self._grants: dict[str, ApprovalGrant] = {}
        self._completed: dict[str, tuple[str, dict[str, Any]]] = {}  # request_id -> (payload_hash, result)

    @staticmethod
    def _payload_hash(description: str) -> str:
        return hashlib.sha256(description.encode("utf-8")).hexdigest()

    def grant_approval(self, request_id: str, approver: str, description: str, *, ttl: int | None = None) -> ApprovalGrant:
        """A human approves one specific request. Records who and when; bounded TTL."""
        if not approver or not approver.strip():
            raise ValidationError("An approver identity is required")
        now = time.time()
        grant = ApprovalGrant(
            request_id=request_id,
            approver=approver.strip(),
            granted_at=now,
            expires_at=now + (ttl if ttl is not None else self.APPROVAL_TTL_SECONDS),
            payload_hash=self._payload_hash(description),
        )
        self._grants[request_id] = grant
        self.audit.append(
            "adapter.approval.granted", "hermes-adapter", request_id,
            {"approver": grant.approver, "expires_at": grant.expires_at,
             "payload_hash": grant.payload_hash, "ttl_seconds": grant.expires_at - grant.granted_at},
        )
        return grant

    def _valid_approval(self, request_id: str, description: str, approver: str | None) -> bool:
        """Approval must exist, be unexpired, match the payload, and match the approver."""
        grant = self._grants.get(request_id)
        if grant is None:
            return False
        now = time.time()
        if now >= grant.expires_at:
            self.audit.append("adapter.approval.expired", "hermes-adapter", request_id,
                              {"approver": grant.approver, "expired_at": grant.expires_at})
            self._grants.pop(request_id, None)
            return False
        if grant.payload_hash != self._payload_hash(description):
            self.audit.append("adapter.approval.mismatch", "hermes-adapter", request_id,
                              {"reason": "payload changed after approval"})
            return False
        if approver is not None and grant.approver != approver.strip():
            self.audit.append("adapter.approval.approver_mismatch", "hermes-adapter", request_id,
                              {"reason": "approver identity mismatch"})
            return False
        return True

    def submit(
        self,
        description: str,
        *,
        request_id: str | None = None,
        correlation_id: str | None = None,
        approver: str | None = None,
    ) -> AdapterResult:
        """Submit one task. Returns a verifiable result with correlation metadata."""
        request_id = request_id or str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        payload_hash = self._payload_hash(description)

        # 1) Idempotency: same request_id + same payload -> cached result, no new execution.
        cached = self._completed.get(request_id)
        if cached is not None:
            cached_hash, cached_result = cached
            if cached_hash == payload_hash:
                self.audit.append("adapter.idempotent.hit", "hermes-adapter", request_id,
                                  {"correlation_id": correlation_id, "payload_hash": payload_hash})
                return AdapterResult(request_id, correlation_id, cached_result["task_id"],
                                     cached_result["status"], cached_result, True)
            raise AdapterError("request_id reused with a different payload")

        # 2) Approval gate with TTL, bound to this request and payload.
        approved = self._valid_approval(request_id, description, approver)
        approver_value = approver or (self._grants[request_id].approver if approved else None)

        task_id = f"req-{request_id}"
        self.audit.append(
            "adapter.request.received", "hermes-adapter", request_id,
            {"correlation_id": correlation_id, "task_id": task_id,
             "payload_hash": payload_hash, "approved": approved},
        )

        # 3) Delegate execution to the unchanged engine.
        result: ExecutionResult = self.engine.execute(
            task_id, description, approved=approved, approver=approver_value
        )
        result_dict = ExecutionEngine.to_dict(result)
        result_dict.update({
            "request_id": request_id,
            "correlation_id": correlation_id,
            "approved_by": approver_value,
        })

        # 4) Cache only terminal results; blocked/denied can be retried after approval.
        if result.status in ("completed", "failed"):
            self._completed[request_id] = (payload_hash, result_dict)
            if approved:
                self._grants.pop(request_id, None)  # single-use: no replay of an old approval

        self.audit.append(
            "adapter.result", "hermes-adapter", request_id,
            {"correlation_id": correlation_id, "status": result.status,
             "approved_by": approver_value, "audit_valid": result.audit_valid},
        )
        return AdapterResult(request_id, correlation_id, task_id, result.status, result_dict, False)
