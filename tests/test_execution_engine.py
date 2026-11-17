"""Tests for the Hermes Execution Engine — real execution, no mocks."""

from __future__ import annotations

import unittest
from pathlib import Path
import shutil

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.exceptions import AuthorizationError, ValidationError
from engine.execution_engine import (
    Capability,
    ExecutionEngine,
    ToolKind,
)
from ragy_agents.policy import PolicyEnforcer


class ExecutionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parent.parent
        data = self.root / "runtime" / ("test-engine-" + self.id().split(".")[-1])
        if data.exists():
            shutil.rmtree(data)
        data.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(data, ignore_errors=True))
        policy = PolicyEnforcer(self.root)
        safe = policy.require_project_path(data)
        self.audit = StructuredAuditLog(safe / "audit.jsonl", policy)
        self.engine = ExecutionEngine(
            project_root=self.root,
            audit_log=self.audit,
            mcp_server=self.root / "mcp_stdio_server.py",
            python_executable=Path(__import__("sys").executable),
            n8n_health_url="http://127.0.0.1:1/healthz",  # guaranteed offline
        )

    def test_plan_routes_to_mcp_for_read(self) -> None:
        steps = self.engine.plan("t-plan", "read README.md")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool, ToolKind.MCP)
        self.assertEqual(steps[0].capability, Capability.MCP_READ)

    def test_plan_refuses_unmatched_task(self) -> None:
        with self.assertRaises(ValidationError):
            self.engine.plan("t-unknown", "zzzz totally unknown action")

    def test_authorize_denies_capability_outside_tool_allowlist(self) -> None:
        from engine.execution_engine import Step

        step = Step("t-auth", "bad", ToolKind.MCP, Capability.N8N_STATUS, {})
        with self.assertRaises(AuthorizationError):
            self.engine._authorize(step)

    def test_execute_mcp_read_is_verified(self) -> None:
        result = self.engine.execute("t-mcp", "read README.md")
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.audit_valid)
        self.assertEqual(result.steps[0].verification["exit_code"], 0)
        self.assertIn("Jameel", result.steps[0].output)

    def test_execute_traversal_path_is_denied_in_step(self) -> None:
        from engine.execution_engine import Step

        step = Step("t-trav", "bad", ToolKind.MCP, Capability.MCP_READ,
                    {"path": "../windows/win.ini"})
        outcome = self.engine._run_mcp(step)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.verification["reason"], "path-outside-safe-zone")

    def test_approval_gate_blocks_external_effect(self) -> None:
        result = self.engine.execute("t-gate", "write code for X")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.steps, ())
        self.assertTrue(result.audit_valid)

    def test_offline_n8n_reports_failure_not_success(self) -> None:
        result = self.engine.execute("t-n8n", "check n8n status")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.steps[0].verification["http_status"], 0)
        self.assertTrue(result.audit_valid)

    def test_audit_chain_records_all_steps(self) -> None:
        self.engine.execute("t-chain", "read README.md")
        verification = self.audit.verify()
        self.assertTrue(verification.valid)
        self.assertGreaterEqual(verification.checked_events, 2)


if __name__ == "__main__":
    unittest.main()
