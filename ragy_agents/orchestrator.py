"""Core offline coordinator for the Phase 1 multi-agent workflow."""

from __future__ import annotations

from pathlib import Path

from .agents import (
    AgentBase,
    MockAutomationAgent,
    MockDeveloperAgent,
    MockQualityAgent,
    MockResearchAgent,
)
from .audit import StructuredAuditLog
from .exceptions import AgentExecutionError, ValidationError
from .models import AgentRole, ApprovalRequest, Task, TaskState
from .policy import PolicyEnforcer
from .task_manager import TaskManager


class CoreOrchestrator:
    """Owns task handoffs while keeping Mock Agents capability-free."""

    def __init__(
        self,
        project_root: Path,
        data_directory: Path,
        *,
        agents: dict[AgentRole, AgentBase] | None = None,
        allowed_paths: list[Path] | None = None,
    ) -> None:
        self.policy = PolicyEnforcer(project_root, allowed_paths)
        safe_data_directory = self.policy.require_project_path(data_directory)
        self.audit_log = StructuredAuditLog(safe_data_directory / "audit.jsonl", self.policy)
        self.task_manager = TaskManager(
            safe_data_directory / "state.sqlite3", self.policy, self.audit_log
        )
        self.agents = agents or {
            AgentRole.RESEARCH: MockResearchAgent(),
            AgentRole.DEVELOPER: MockDeveloperAgent(),
            AgentRole.QUALITY: MockQualityAgent(),
            AgentRole.AUTOMATION: MockAutomationAgent(),
        }
        self._validate_agents()

    def close(self) -> None:
        self.task_manager.close()

    def create_planned_task(
        self,
        title: str,
        description: str,
        *,
        max_attempts: int = 2,
    ) -> tuple[Task, ApprovalRequest]:
        """Create, plan, and pause a task at the mandatory human approval gate."""

        task = self.task_manager.create_task(title, description, max_attempts=max_attempts)
        self.task_manager.plan_task(task.task_id)
        approval = self.task_manager.request_approval(
            task.task_id, "Human approval is required before agent assignment."
        )
        return self.task_manager.get_task(task.task_id), approval

    def grant_human_approval(self, request_id: str, approver: str) -> ApprovalRequest:
        """Record an explicit human decision; callers must supply the approver identity."""

        return self.task_manager.grant_approval(request_id, approver)

    def assign_approved_task(self, task_id: str, role: AgentRole) -> Task:
        if role not in self.agents or role is AgentRole.QUALITY:
            raise ValidationError("Only registered non-review agents can receive work")
        return self.task_manager.assign_agent(task_id, role)

    def dispatch_assigned_task(self, task_id: str) -> Task:
        """Run one bounded, local Mock Agent attempt through the coordinator."""

        task = self.task_manager.start_work(task_id)
        if task.assigned_role is None:
            raise ValidationError("A working task has no assigned role")
        agent = self.agents.get(task.assigned_role)
        if agent is None:
            return self.task_manager.record_failure(task_id, "No registered agent for assigned role.")
        try:
            result = agent.execute(task)
        except AgentExecutionError as error:
            return self.task_manager.record_failure(task_id, str(error))
        return self.task_manager.record_result(result)

    def review_evidence(self, task_id: str) -> Task:
        """Require a separate quality role before accepting or rejecting evidence."""

        task = self.task_manager.start_review(task_id)
        quality_agent = self.agents[AgentRole.QUALITY]
        try:
            result = quality_agent.execute(task)
        except AgentExecutionError as error:
            raise ValidationError(f"Quality review failed: {error}") from error
        return self.task_manager.record_review(result)

    def close_if_accepted(self, task_id: str) -> Task:
        task = self.task_manager.get_task(task_id)
        if task.state is not TaskState.ACCEPTED:
            raise ValidationError("Only an accepted task can be closed")
        return self.task_manager.close_task(task_id)

    def _validate_agents(self) -> None:
        required_roles = {
            AgentRole.RESEARCH,
            AgentRole.DEVELOPER,
            AgentRole.QUALITY,
            AgentRole.AUTOMATION,
        }
        if set(self.agents) != required_roles:
            raise ValidationError("The coordinator requires exactly the four Phase 1 Mock Agent roles")
        for role, agent in self.agents.items():
            if agent.role is not role:
                raise ValidationError(f"Agent registration mismatch for role: {role.value}")
