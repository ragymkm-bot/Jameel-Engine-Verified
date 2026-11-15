"""Structured, locally tamper-evident JSON Lines audit logging."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exceptions import AuditIntegrityError
from .models import AuditVerification
from .policy import PolicyEnforcer


class StructuredAuditLog:
    """Append-only writer with a SHA-256 predecessor hash chain.

    The chain is locally tamper-evident after comparison with a trusted anchor.
    It does not defend against full local replacement by a privileged attacker.
    """

    def __init__(self, path: Path, policy: PolicyEnforcer) -> None:
        self.path = policy.require_project_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        verification = self.verify()
        if not verification.valid:
            raise AuditIntegrityError(verification.reason or "Audit log verification failed")
        self._next_sequence = verification.checked_events + 1
        self._previous_hash = self._last_hash()

    @staticmethod
    def _canonical_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _event_hash(cls, event_without_hash: dict[str, Any]) -> str:
        return hashlib.sha256(
            cls._canonical_json(event_without_hash).encode("utf-8")
        ).hexdigest()

    def append(
        self, event_type: str, actor: str, task_id: str | None, payload: dict[str, Any]
    ) -> dict[str, Any]:
        event = {
            "sequence": self._next_sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "task_id": task_id,
            "payload": payload,
            "previous_hash": self._previous_hash,
        }
        event["event_hash"] = self._event_hash(event)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(self._canonical_json(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._previous_hash = event["event_hash"]
        self._next_sequence += 1
        return event

    def verify(self) -> AuditVerification:
        previous_hash: str | None = None
        expected_sequence = 1
        try:
            with self.path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    supplied_hash = event.pop("event_hash", None)
                    if event.get("sequence") != expected_sequence:
                        return AuditVerification(
                            False, expected_sequence - 1, f"Sequence mismatch at line {line_number}"
                        )
                    if event.get("previous_hash") != previous_hash:
                        return AuditVerification(
                            False,
                            expected_sequence - 1,
                            f"Predecessor mismatch at line {line_number}",
                        )
                    if supplied_hash != self._event_hash(event):
                        return AuditVerification(
                            False, expected_sequence - 1, f"Hash mismatch at line {line_number}"
                        )
                    previous_hash = supplied_hash
                    expected_sequence += 1
        except (OSError, json.JSONDecodeError, TypeError) as error:
            return AuditVerification(False, expected_sequence - 1, str(error))
        return AuditVerification(True, expected_sequence - 1)

    def _last_hash(self) -> str | None:
        last_hash: str | None = None
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_hash = json.loads(line)["event_hash"]
        return last_hash
