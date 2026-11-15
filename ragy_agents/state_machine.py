"""The explicit, bounded task workflow state machine."""

from __future__ import annotations

from .exceptions import InvalidTransitionError
from .models import TaskState


_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.DRAFT: frozenset({TaskState.PLANNED}),
    TaskState.PLANNED: frozenset({TaskState.AWAITING_APPROVAL}),
    TaskState.AWAITING_APPROVAL: frozenset({TaskState.ASSIGNED}),
    TaskState.ASSIGNED: frozenset({TaskState.WORKING}),
    TaskState.WORKING: frozenset(
        {TaskState.EVIDENCE_SUBMITTED, TaskState.ASSIGNED, TaskState.BLOCKED}
    ),
    TaskState.EVIDENCE_SUBMITTED: frozenset({TaskState.UNDER_REVIEW}),
    TaskState.UNDER_REVIEW: frozenset({TaskState.ACCEPTED, TaskState.REJECTED}),
    TaskState.ACCEPTED: frozenset({TaskState.CLOSED}),
    TaskState.REJECTED: frozenset(),
    TaskState.BLOCKED: frozenset(),
    TaskState.CLOSED: frozenset(),
}


def assert_transition(current: TaskState, target: TaskState) -> None:
    """Raise when a workflow transition is not explicitly authorized."""

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(
            f"Illegal task transition: {current.value} -> {target.value}"
        )
