"""Hermes Execution Engine — task intake → planning → tool router → bounded execution → audit → verified result.

Design rules (non-negotiable):
- Hermes is the ONLY executor. MCP / n8n / Codex are tools, not peers.
- Every tool has an explicit capability allowlist; everything else is denied.
- Every operation appends to the tamper-evident SHA-256 audit chain.
- Human approval is mandatory before any external-effect tool runs.
- Results carry a verification handle (exit code / HTTP status / audit sequence).
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404 - used ONLY with fixed argv lists, never shell=True
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.exceptions import AuthorizationError, RagyAgentsError, ValidationError


class ToolKind(str, Enum):
    MCP = "mcp"
    N8N = "n8n"
    CODEX = "codex"


class Capability(str, Enum):
    """Per-tool capabilities. Nothing outside an adapter's allowlist can run."""

    MCP_LIST = "mcp.list_files"
    MCP_READ = "mcp.read_file"
    N8N_STATUS = "n8n.status"
    CODEX_VERSION = "codex.version"
    CODEX_PROMPT = "codex.prompt"


# Capability -> requires explicit human approval. Read-only tools never do.
APPROVAL_REQUIRED: frozenset[Capability] = frozenset(
    {Capability.CODEX_PROMPT}
)

# Tool -> capabilities it is allowed to perform.
TOOL_ALLOWLIST: dict[ToolKind, frozenset[Capability]] = {
    ToolKind.MCP: frozenset({Capability.MCP_LIST, Capability.MCP_READ}),
    ToolKind.N8N: frozenset({Capability.N8N_STATUS}),
    ToolKind.CODEX: frozenset({Capability.CODEX_VERSION, Capability.CODEX_PROMPT}),
}

# Task keywords -> (tool, capability). Pure routing metadata, no execution.
ROUTES: tuple[tuple[tuple[str, ...], ToolKind, Capability], ...] = (
    (("list", "قائمة", "ملفات", "files"), ToolKind.MCP, Capability.MCP_LIST),
    (("read", "اقرأ", "قراءة", "محتوى"), ToolKind.MCP, Capability.MCP_READ),
    (("n8n", "automation", "اتمتة", "ويب هوك", "webhook"), ToolKind.N8N, Capability.N8N_STATUS),
    (("codex", "كود", "اكتب", "اكتب كود", "write", "build", "generate", "نفذ"), ToolKind.CODEX, Capability.CODEX_PROMPT),
    (("version", "إصدار", "تحقق", "status"), ToolKind.CODEX, Capability.CODEX_VERSION),
)


class EngineError(RagyAgentsError):
    """Raised when the engine cannot complete a bounded operation."""


@dataclass(frozen=True)
class Step:
    step_id: str
    description: str
    tool: ToolKind
    capability: Capability
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    step_id: str
    tool: ToolKind
    capability: Capability
    ok: bool
    verification: dict[str, Any]
    output: str
    error: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    status: str  # completed | blocked | denied | failed
    steps: tuple[StepResult, ...]
    audit_sequence: int
    audit_valid: bool


class ExecutionEngine:
    """The single control point. Callers submit tasks; the engine owns execution."""

    def __init__(
        self,
        project_root: Path,
        audit_log: StructuredAuditLog,
        *,
        mcp_server: Path,
        python_executable: Path,
        n8n_health_url: str = "http://127.0.0.1:5690/healthz",
        codex_entrypoint: Path | None = None,
        submitter: str = "hermes",
    ) -> None:
        self.project_root = project_root.resolve()
        self.audit = audit_log
        self.mcp_server = self._inside_project(mcp_server)
        self.python = python_executable
        self.n8n_url = n8n_health_url
        self.codex_entrypoint = codex_entrypoint
        self.submitter = submitter
        if not self.python.exists():
            raise ValidationError(f"Python executable not found: {self.python}")

    def _inside_project(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise AuthorizationError(f"Tool path outside project root: {resolved}") from exc
        return resolved

    # ---- 1. INTAKE + 2. PLANNING -----------------------------------------
    def plan(self, task_id: str, description: str) -> list[Step]:
        text = description.lower()
        matched = [s for s in ROUTES if any(k in text for k in s[0])]
        if not matched:
            raise ValidationError("No tool route matched this task; refusing to guess")
        _, tool, capability = matched[0]
        return [
            Step(
                step_id=f"{task_id}-s1",
                description=description,
                tool=tool,
                capability=capability,
                params={"text": description},
            )
        ]

    # ---- 3. TOOL SELECTION + 4. BOUNDED EXECUTION -------------------------
    def _authorize(self, step: Step) -> None:
        allowed = TOOL_ALLOWLIST.get(step.tool, frozenset())
        if step.capability not in allowed:
            raise AuthorizationError(
                f"Capability {step.capability.value} is not allowed for {step.tool.value}"
            )

    def _run_mcp(self, step: Step) -> StepResult:
        if step.capability is Capability.MCP_LIST:
            method, args = "list_files", {}
        elif step.capability is Capability.MCP_READ:
            target = str(step.params.get("path", "README.md"))
            # Safe-zone: only a relative name inside the project.
            if Path(target).is_absolute() or ".." in Path(target).parts:
                return StepResult(
                    step.step_id, step.tool, step.capability, False,
                    {"reason": "path-outside-safe-zone"}, "", "Absolute/traversal path denied"
                )
            method, args = "read_file", {"path": target}
        else:
            raise EngineError("Unsupported MCP capability")

        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": method, "arguments": args},
        }
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [str(self.python), str(self.mcp_server)],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )
        ok = proc.returncode == 0 and bool(proc.stdout.strip())
        return StepResult(
            step.step_id, step.tool, step.capability, ok,
            {"exit_code": proc.returncode, "server": self.mcp_server.name},
            proc.stdout.strip()[:2000], proc.stderr.strip()[:500] or None,
        )

    def _run_n8n(self, step: Step) -> StepResult:
        try:
            with urllib.request.urlopen(self.n8n_url, timeout=5) as resp:
                status = resp.status
                body = resp.read(200).decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as exc:
            return StepResult(
                step.step_id, step.tool, step.capability, False,
                {"http_status": 0}, "", f"n8n unreachable: {exc}"
            )
        return StepResult(
            step.step_id, step.tool, step.capability, status == 200,
            {"http_status": status, "url": self.n8n_url}, body, None,
        )

    def _run_codex(self, step: Step) -> StepResult:
        if self.codex_entrypoint is None or not self.codex_entrypoint.exists():
            return StepResult(
                step.step_id, step.tool, step.capability, False,
                {"reason": "codex-not-installed"}, "", "Codex entrypoint unavailable"
            )
        argv = [str(self.python), str(self.codex_entrypoint), "exec", "--skip-git-repo-check"]
        if step.capability is Capability.CODEX_VERSION:
            argv.append("--version")
        else:
            prompt = str(step.params.get("text", ""))
            if not prompt.strip():
                return StepResult(
                    step.step_id, step.tool, step.capability, False,
                    {"reason": "empty-prompt"}, "", "Refusing empty prompt"
                )
            argv.append(prompt)
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)  # noqa: S603
        return StepResult(
            step.step_id, step.tool, step.capability, proc.returncode == 0,
            {"exit_code": proc.returncode},
            proc.stdout.strip()[:2000], proc.stderr.strip()[:500] or None,
        )

    def _execute_step(self, step: Step) -> StepResult:
        self._authorize(step)
        if step.tool is ToolKind.MCP:
            return self._run_mcp(step)
        if step.tool is ToolKind.N8N:
            return self._run_n8n(step)
        return self._run_codex(step)

    # ---- 5. AUDIT + 6. VERIFIED RESULT -----------------------------------
    def execute(
        self,
        task_id: str,
        description: str,
        *,
        approved: bool = False,
        approver: str | None = None,
    ) -> ExecutionResult:
        steps = self.plan(task_id, description)
        results: list[StepResult] = []

        for step in steps:
            self.audit.append(
                "engine.step.planned", self.submitter, task_id,
                {"step_id": step.step_id, "tool": step.tool.value,
                 "capability": step.capability.value},
            )
            if step.capability in APPROVAL_REQUIRED and not approved:
                self.audit.append(
                    "engine.approval.blocked", self.submitter, task_id,
                    {"step_id": step.step_id, "capability": step.capability.value},
                )
                return ExecutionResult(task_id, "blocked", tuple(results),
                                       self.audit._next_sequence - 1,
                                       self.audit.verify().valid)

            try:
                result = self._execute_step(step)
            except (AuthorizationError, EngineError) as exc:
                self.audit.append(
                    "engine.step.denied", self.submitter, task_id,
                    {"step_id": step.step_id, "reason": str(exc)},
                )
                return ExecutionResult(task_id, "denied", tuple(results),
                                       self.audit._next_sequence - 1,
                                       self.audit.verify().valid)
            results.append(result)
            self.audit.append(
                "engine.step.executed", self.submitter, task_id,
                {"step_id": step.step_id, "ok": result.ok,
                 "verification": result.verification,
                 "approved_by": approver if approved else None},
            )

        status = "completed" if all(r.ok for r in results) else "failed"
        self.audit.append(
            "engine.result", self.submitter, task_id,
            {"status": status, "steps": len(results)},
        )
        verification = self.audit.verify()
        return ExecutionResult(
            task_id, status, tuple(results),
            self.audit._next_sequence - 1, verification.valid,
        )

    @staticmethod
    def to_dict(result: ExecutionResult) -> dict[str, Any]:
        return {
            "task_id": result.task_id,
            "status": result.status,
            "steps": [
                {"step_id": r.step_id, "tool": r.tool.value,
                 "capability": r.capability.value, "ok": r.ok,
                 "verification": r.verification, "output": r.output,
                 "error": r.error}
                for r in result.steps
            ],
            "audit_sequence": result.audit_sequence,
            "audit_valid": result.audit_valid,
        }
