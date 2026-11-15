from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.exceptions import ApprovalRequiredError, AuthorizationError
from ragy_agents.models import AgentResult, AgentRole, Capability, TaskState
from ragy_agents.policy import PolicyEnforcer
from ragy_agents.task_manager import TaskManager


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.temporary_directory = tempfile.TemporaryDirectory(dir=self.project_root / "tests")
        self.data_directory = Path(self.temporary_directory.name)
        self.policy = PolicyEnforcer(self.project_root)
        self.audit = StructuredAuditLog(self.data_directory / "audit.jsonl", self.policy)
        self.manager = TaskManager(self.data_directory / "state.sqlite3", self.policy, self.audit)

    def tearDown(self) -> None:
        self.manager.close()
        self.temporary_directory.cleanup()

    def _approved_task(self, *, max_attempts: int = 2):
        task = self.manager.create_task("Offline task", "Validate the local workflow.", max_attempts=max_attempts)
        self.manager.plan_task(task.task_id)
        approval = self.manager.request_approval(task.task_id, "Human review is required.")
        self.manager.grant_approval(approval.request_id, "test-human")
        return self.manager.assign_agent(task.task_id, AgentRole.RESEARCH)

    def test_creates_task_and_records_audit_event(self) -> None:
        task = self.manager.create_task("Create task", "Create a local task record.")
        self.assertEqual(task.state, TaskState.DRAFT)
        self.assertTrue(self.audit.verify().valid)

    def test_requires_human_approval_before_assignment(self) -> None:
        task = self.manager.create_task("Approval", "Require a human decision.")
        self.manager.plan_task(task.task_id)
        self.manager.request_approval(task.task_id, "Assignment has a gate.")
        with self.assertRaises(ApprovalRequiredError):
            self.manager.assign_agent(task.task_id, AgentRole.RESEARCH)

    def test_transitions_from_evidence_through_independent_review(self) -> None:
        task = self._approved_task()
        self.assertEqual(task.state, TaskState.ASSIGNED)
        self.manager.start_work(task.task_id)
        self.manager.record_result(
            AgentResult(
                task_id=task.task_id,
                role=AgentRole.RESEARCH,
                summary="Mock research completed.",
                evidence=("mock-evidence",),
            )
        )
        self.manager.start_review(task.task_id)
        accepted = self.manager.record_review(
            AgentResult(
                task_id=task.task_id,
                role=AgentRole.QUALITY,
                summary="Evidence meets the phase-one contract.",
                evidence=("review-check",),
                review_decision=TaskState.ACCEPTED,
            )
        )
        self.assertEqual(accepted.state, TaskState.ACCEPTED)
        self.assertEqual(self.manager.close_task(task.task_id).state, TaskState.CLOSED)

    def test_denies_network_capability(self) -> None:
        with self.assertRaises(AuthorizationError):
            self.policy.require(AgentRole.COORDINATOR, Capability.NETWORK_CONNECT)
        with self.assertRaises(AuthorizationError):
            self.policy.require(AgentRole.DEVELOPER, Capability.TASK_CREATE)

    def test_failure_attempts_are_bounded(self) -> None:
        task = self._approved_task(max_attempts=2)
        self.manager.start_work(task.task_id)
        retry = self.manager.record_failure(task.task_id, "Controlled mock failure.")
        self.assertEqual(retry.state, TaskState.ASSIGNED)
        self.manager.start_work(task.task_id)
        blocked = self.manager.record_failure(task.task_id, "Second controlled mock failure.")
        self.assertEqual(blocked.state, TaskState.BLOCKED)
        self.assertEqual(blocked.attempt_count, 2)

    def test_detects_modified_audit_event(self) -> None:
        self.manager.create_task("Audit", "Verify a local hash chain.")
        event = json.loads(self.audit.path.read_text(encoding="utf-8").splitlines()[0])
        event["payload"] = {"state": "tampered"}
        self.audit.path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        verification = self.audit.verify()
        self.assertFalse(verification.valid)
        self.assertIn("Hash mismatch", verification.reason or "")
