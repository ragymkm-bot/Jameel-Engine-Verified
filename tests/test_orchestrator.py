from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ragy_agents.agents import (
    MockAutomationAgent,
    MockDeveloperAgent,
    MockQualityAgent,
    MockResearchAgent,
)
from ragy_agents.models import AgentRole, TaskState
from ragy_agents.orchestrator import CoreOrchestrator


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.temporary_directory = tempfile.TemporaryDirectory(dir=self.project_root / "tests")
        self.data_directory = Path(self.temporary_directory.name)
        self.orchestrator = CoreOrchestrator(self.project_root, self.data_directory)

    def tearDown(self) -> None:
        self.orchestrator.close()
        self.temporary_directory.cleanup()

    def _create_and_assign(self, role: AgentRole, *, max_attempts: int = 2):
        task, approval = self.orchestrator.create_planned_task(
            "Offline orchestration test", "Run a deterministic local Mock Agent.", max_attempts=max_attempts
        )
        self.assertEqual(task.state, TaskState.AWAITING_APPROVAL)
        self.orchestrator.grant_human_approval(approval.request_id, "test-human")
        return self.orchestrator.assign_approved_task(task.task_id, role)

    def test_distributes_research_task_and_preserves_evidence(self) -> None:
        task = self._create_and_assign(AgentRole.RESEARCH)
        evidence_task = self.orchestrator.dispatch_assigned_task(task.task_id)
        self.assertEqual(evidence_task.state, TaskState.EVIDENCE_SUBMITTED)
        results = self.orchestrator.task_manager.list_results(task.task_id)
        self.assertEqual(results[0].role, AgentRole.RESEARCH)
        self.assertIn("offline", results[0].summary.lower())

    def test_developer_task_requires_quality_review_before_closing(self) -> None:
        task = self._create_and_assign(AgentRole.DEVELOPER)
        evidence_task = self.orchestrator.dispatch_assigned_task(task.task_id)
        accepted = self.orchestrator.review_evidence(evidence_task.task_id)
        closed = self.orchestrator.close_if_accepted(accepted.task_id)
        self.assertEqual(closed.state, TaskState.CLOSED)

    def test_automation_agent_is_dry_run_only(self) -> None:
        task = self._create_and_assign(AgentRole.AUTOMATION)
        evidence_task = self.orchestrator.dispatch_assigned_task(task.task_id)
        result = self.orchestrator.task_manager.list_results(evidence_task.task_id)[0]
        self.assertTrue(result.dry_run)
        self.assertIn("no scheduled action", result.summary.lower())

    def test_agent_failure_blocks_after_bounded_attempts(self) -> None:
        failing_agents = {
            AgentRole.RESEARCH: MockResearchAgent(should_fail=True),
            AgentRole.DEVELOPER: MockDeveloperAgent(),
            AgentRole.QUALITY: MockQualityAgent(),
            AgentRole.AUTOMATION: MockAutomationAgent(),
        }
        self.orchestrator.close()
        self.orchestrator = CoreOrchestrator(
            self.project_root, self.data_directory, agents=failing_agents
        )
        task = self._create_and_assign(AgentRole.RESEARCH, max_attempts=2)
        retry = self.orchestrator.dispatch_assigned_task(task.task_id)
        self.assertEqual(retry.state, TaskState.ASSIGNED)
        blocked = self.orchestrator.dispatch_assigned_task(task.task_id)
        self.assertEqual(blocked.state, TaskState.BLOCKED)
        self.assertEqual(blocked.attempt_count, 2)

    def test_all_orchestrated_events_are_audited(self) -> None:
        task = self._create_and_assign(AgentRole.RESEARCH)
        self.orchestrator.dispatch_assigned_task(task.task_id)
        verification = self.orchestrator.audit_log.verify()
        events = self.orchestrator.audit_log.path.read_text(encoding="utf-8")
        self.assertTrue(verification.valid)
        for event_name in ("task.created", "approval.granted", "task.assigned", "evidence.submitted"):
            self.assertIn(event_name, events)

    def test_runtime_source_has_no_network_or_process_client_imports(self) -> None:
        prohibited_imports = ("import socket", "import urllib", "import http.client", "import subprocess")
        for source_path in (self.project_root / "ragy_agents").glob("*.py"):
            source = source_path.read_text(encoding="utf-8")
            for prohibited in prohibited_imports:
                self.assertNotIn(prohibited, source, f"{prohibited} found in {source_path.name}")
