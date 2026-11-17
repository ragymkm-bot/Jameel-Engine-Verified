"""Tests for Hermes Adapter — correlation, idempotency, approval TTL (real engine, no mocks)."""

from __future__ import annotations

import shutil
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.exceptions import ValidationError
from ragy_agents.policy import PolicyEnforcer
from engine.execution_engine import ExecutionEngine
from engine.hermes_adapter import AdapterError, HermesAdapter


class HermesAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parent.parent
        data = self.root / "runtime" / ("test-adapter-" + self.id().split(".")[-1])
        if data.exists():
            shutil.rmtree(data)
        data.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(data, ignore_errors=True))
        policy = PolicyEnforcer(self.root)
        safe = policy.require_project_path(data)
        self.audit = StructuredAuditLog(safe / "audit.jsonl", policy)
        self.engine = ExecutionEngine(
            project_root=self.root, audit_log=self.audit,
            mcp_server=self.root / "mcp_stdio_server.py",
            python_executable=Path(sys.executable),
            n8n_health_url="http://127.0.0.1:1/healthz",
        )
        self.adapter = HermesAdapter(self.engine, self.audit)

    def test_submit_returns_correlation_and_request_ids(self) -> None:
        r = self.adapter.submit("read README.md", request_id="req-A", correlation_id="corr-A")
        self.assertEqual(r.request_id, "req-A")
        self.assertEqual(r.correlation_id, "corr-A")
        self.assertEqual(r.status, "completed")
        self.assertTrue(r.result["audit_valid"])

    def test_idempotent_duplicate_does_not_re_execute(self) -> None:
        first = self.adapter.submit("read README.md", request_id="req-B")
        second = self.adapter.submit("read README.md", request_id="req-B")
        self.assertFalse(first.idempotent_hit)
        self.assertTrue(second.idempotent_hit)
        self.assertEqual(first.result["status"], second.result["status"])
        events = self.audit.path.read_text(encoding="utf-8")
        self.assertIn("adapter.idempotent.hit", events)

    def test_same_request_id_different_payload_is_rejected(self) -> None:
        self.adapter.submit("read README.md", request_id="req-C")
        with self.assertRaises(AdapterError):
            self.adapter.submit("check n8n status", request_id="req-C")

    def test_sensitive_task_without_approval_is_blocked(self) -> None:
        r = self.adapter.submit("write code for X", request_id="req-D")
        self.assertEqual(r.status, "blocked")

    def test_approval_is_bound_to_payload_and_approver(self) -> None:
        self.adapter.grant_approval("req-E", "bashmohands ragy", "write code for X")
        with self.assertRaises(ValidationError):
            self.adapter.grant_approval("req-E", "  ", "write code for X")
        events = self.audit.path.read_text(encoding="utf-8")
        self.assertIn("adapter.approval.granted", events)

    def test_approval_ttl_expires_and_cannot_be_replayed(self) -> None:
        self.adapter.grant_approval("req-F", "bashmohands ragy", "write code for X", ttl=1)
        time.sleep(1.2)
        r = self.adapter.submit("write code for X", request_id="req-F", approver="bashmohands ragy")
        self.assertEqual(r.status, "blocked")
        events = self.audit.path.read_text(encoding="utf-8")
        self.assertIn("adapter.approval.expired", events)

    def test_audit_chain_valid_after_all_operations(self) -> None:
        self.adapter.submit("read README.md", request_id="req-G")
        self.assertTrue(self.audit.verify().valid)


if __name__ == "__main__":
    unittest.main()
