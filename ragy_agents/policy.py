"""Deny-by-default authorization and project-root checks."""

from __future__ import annotations

from pathlib import Path

from .exceptions import AuthorizationError
from .models import AgentRole, Capability


class PolicyEnforcer:
    """Enforces Phase 1 capabilities without exposing generic host operations."""

    _COORDINATOR_CAPABILITIES = frozenset(
        {
            Capability.TASK_CREATE,
            Capability.TASK_ASSIGN,
            Capability.TASK_TRANSITION,
            Capability.APPROVAL_REQUEST,
            Capability.APPROVAL_GRANT,
            Capability.AUDIT_APPEND,
        }
    )
    _ALWAYS_DENIED = frozenset(
        {
            Capability.NETWORK_CONNECT,
            Capability.PROVIDER_INVOKE,
            Capability.PROCESS_SPAWN,
            Capability.PACKAGE_INSTALL,
            Capability.EXTERNAL_EFFECT,
        }
    )

    def __init__(self, project_root: Path, allowed_paths: list[Path] | None = None) -> None:
        self.project_root = project_root.resolve()
        self.allowed_paths = [p.resolve() for p in (allowed_paths or [])]

    def require(self, actor: AgentRole, capability: Capability) -> None:
        if capability in self._ALWAYS_DENIED:
            raise AuthorizationError(f"Capability is denied in Phase 1: {capability.value}")
        if actor is not AgentRole.COORDINATOR:
            raise AuthorizationError(
                f"Only the coordinator may request Phase 1 capabilities; got {actor.value}"
            )
        if capability not in self._COORDINATOR_CAPABILITIES:
            raise AuthorizationError(f"Capability is not allowlisted: {capability.value}")

    def require_project_path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            # Check if path is in allowed additional paths
            for allowed in self.allowed_paths:
                try:
                    resolved.relative_to(allowed)
                    return resolved
                except ValueError:
                    continue
            raise AuthorizationError(f"Path is outside the project root: {resolved}")
        return resolved
