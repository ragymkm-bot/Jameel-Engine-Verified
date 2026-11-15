"""Deterministic Mock Agents with no tool, filesystem, or network access."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .exceptions import AgentExecutionError
from .models import AgentResult, AgentRole, Task, TaskState


class AgentBase(ABC):
    """Minimal agent contract: receive one task and return structured evidence."""

    role: AgentRole

    @abstractmethod
    def execute(self, task: Task) -> AgentResult:
        """Return a deterministic result or raise AgentExecutionError."""


class _MockAgent(AgentBase):
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def _raise_if_configured(self) -> None:
        if self.should_fail:
            raise AgentExecutionError(f"Controlled {self.role.value} mock failure")


class MockResearchAgent(_MockAgent):
    role = AgentRole.RESEARCH

    def execute(self, task: Task) -> AgentResult:
        self._raise_if_configured()
        return AgentResult(
            task_id=task.task_id,
            role=self.role,
            summary="Offline mock research completed without external sources or network access.",
            evidence=("mock-research: local deterministic finding",),
        )


class MockDeveloperAgent(_MockAgent):
    role = AgentRole.DEVELOPER

    def execute(self, task: Task) -> AgentResult:
        self._raise_if_configured()
        return AgentResult(
            task_id=task.task_id,
            role=self.role,
            summary="Mock development proposal completed; no source files were changed.",
            evidence=("mock-development: simulated local validation",),
        )


class MockQualityAgent(_MockAgent):
    role = AgentRole.QUALITY

    def __init__(
        self, *, decision: TaskState = TaskState.ACCEPTED, should_fail: bool = False
    ) -> None:
        super().__init__(should_fail=should_fail)
        if decision not in {TaskState.ACCEPTED, TaskState.REJECTED}:
            raise ValueError("Mock quality decision must accept or reject")
        self.decision = decision

    def execute(self, task: Task) -> AgentResult:
        self._raise_if_configured()
        return AgentResult(
            task_id=task.task_id,
            role=self.role,
            summary=f"Mock quality review returned {self.decision.value}.",
            evidence=("mock-quality: role and state checks completed",),
            review_decision=self.decision,
        )


class MockAutomationAgent(_MockAgent):
    role = AgentRole.AUTOMATION

    def execute(self, task: Task) -> AgentResult:
        self._raise_if_configured()
        return AgentResult(
            task_id=task.task_id,
            role=self.role,
            summary="Mock automation produced a dry-run only; no scheduled action was created.",
            evidence=("mock-automation: idempotence assessed in dry-run",),
            dry_run=True,
        )
