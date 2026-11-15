"""Domain-specific errors for the offline core."""


class RagyAgentsError(Exception):
    """Base class for expected application errors."""


class AuthorizationError(RagyAgentsError):
    """Raised when a role or capability is not allowed."""


class InvalidTransitionError(RagyAgentsError):
    """Raised when a task attempts an illegal workflow transition."""


class ApprovalRequiredError(RagyAgentsError):
    """Raised when a task has not received its required approval."""


class ValidationError(RagyAgentsError):
    """Raised when task or agent data fails validation."""


class AuditIntegrityError(RagyAgentsError):
    """Raised when an existing audit log fails integrity verification."""


class AgentExecutionError(RagyAgentsError):
    """Raised by a mock agent to simulate a controlled execution failure."""
