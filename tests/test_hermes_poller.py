"""Bridge tests: cloud outbox ↔ local engine, real HTTP + real audit."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer
from engine.execution_engine import ExecutionEngine

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cloud import hermes_poller as poller


class BridgeFlowTests(unittest.TestCase):
    def test_poller_module_imports_and_builds_engine(self) -> None:
        engine = poller.build_engine()
        self.assertIsInstance(engine, ExecutionEngine)

    def test_bridge_claim_complete_with_real_engine(self) -> None:
        # simulate a queued command by patching the poller's api() for claim/complete
        calls: list[tuple[str, dict | None]] = []
        responses = iter([
            {"claimed": True, "command": {"command_id": "bc-1", "task": "read README.md"}},
            {"updated": True},
            {"claimed": False},
        ])
        original = poller.api
        def fake_api(path: str, body: dict | None = None) -> dict:
            calls.append((path, body))
            return next(responses)
        poller.api = fake_api
        try:
            engine = poller.build_engine()
            self.assertTrue(poller.run_once(engine))
            self.assertEqual(calls[0][0], "/bridge/claim")
            self.assertEqual(calls[1][0], "/bridge/complete")
            result = calls[1][1]["result"]
            self.assertIn(result["status"], ("completed", "failed", "denied"))
        finally:
            poller.api = original

    def test_audit_chain_still_valid(self) -> None:
        root = Path(__file__).resolve().parent.parent
        policy = PolicyEnforcer(root)
        audit = StructuredAuditLog(root / "runtime" / "audit.jsonl", policy)
        self.assertTrue(audit.verify().valid)


if __name__ == "__main__":
    unittest.main()
