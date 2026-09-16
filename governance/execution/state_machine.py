"""Execution State Machine — Hermes Execution Layer.

Lifecycle management for execution tasks.
State transitions are validated. Invalid transitions are rejected.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class ExecutionState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid transitions: current -> set of allowed next states
_TRANSITIONS: Dict[ExecutionState, Set[ExecutionState]] = {
    ExecutionState.PENDING: {
        ExecutionState.APPROVED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.APPROVED: {
        ExecutionState.RUNNING,
        ExecutionState.CANCELLED,
    },
    ExecutionState.RUNNING: {
        ExecutionState.PAUSED,
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
        ExecutionState.RETRYING,
    },
    ExecutionState.PAUSED: {
        ExecutionState.RUNNING,
        ExecutionState.CANCELLED,
    },
    ExecutionState.RETRYING: {
        ExecutionState.RUNNING,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.COMPLETED: set(),     # terminal
    ExecutionState.FAILED: set(),        # terminal
    ExecutionState.CANCELLED: set(),     # terminal
}


def is_valid_transition(current: ExecutionState, next_state: ExecutionState) -> bool:
    """Check if transition from current to next_state is allowed."""
    allowed = _TRANSITIONS.get(current, set())
    return next_state in allowed


def validate_transition(current: ExecutionState, next_state: ExecutionState) -> None:
    """Validate transition. Raises ValueError if invalid."""
    if not is_valid_transition(current, next_state):
        raise ValueError(
            f"Invalid state transition: {current.value} -> {next_state.value}. "
            f"Allowed from {current.value}: "
            f"{[s.value for s in _TRANSITIONS.get(current, set())]}"
        )


def is_terminal(state: ExecutionState) -> bool:
    """Check if state is terminal (no outgoing transitions)."""
    return len(_TRANSITIONS.get(state, set())) == 0


def can_start(state: ExecutionState) -> bool:
    """Check if execution can start (is approved)."""
    return state == ExecutionState.APPROVED
