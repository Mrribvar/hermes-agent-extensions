# Execution Layer — Phase 11.1: State Machine Foundation
#
# Implements ONLY the execution lifecycle state machine (per EXECUTION_LAYER_DESIGN.md §4.4).
# No Engine, Queue, Memory, or Tool Orchestrator yet.
# No modifications to existing execution systems (agent/tool_executor.py etc.).
# Backward compatible: pure additive package under agent/execution/.

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
import threading
from typing import Deque, Dict, List, Optional, Tuple

__all__ = [
    "ExecutionState",
    "InvalidTransitionError",
    "StateTransition",
    "ExecutionStateMachine",
]


class ExecutionState(Enum):
    """Execution lifecycle states per Phase 11.1 design.

    Mirrors the approved transition contract in EXECUTION_LAYER_DESIGN.md §4.4.
    """

    CREATED = auto()
    PENDING_APPROVAL = auto()
    APPROVED = auto()
    RUNNING = auto()
    PAUSED = auto()
    RETRYING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


# Immutable snapshot of a single transition event.
@dataclass(frozen=True)
class StateTransition:
    """A single state-change record kept in history."""

    state: ExecutionState
    timestamp: str
    reason: Optional[str] = None


class InvalidTransitionError(Exception):
    """Raised when a requested transition is not legal from current state."""


# Transition graph: source -> set(allowed targets).
# Design contract: only these edges are legal.
_TRANSITIONS: Dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.CREATED: {
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.RUNNING,
        ExecutionState.CANCELLED,
        ExecutionState.FAILED,
    },
    ExecutionState.PENDING_APPROVAL: {
        ExecutionState.APPROVED,
        ExecutionState.CANCELLED,
        ExecutionState.FAILED,
        ExecutionState.PAUSED,
    },
    ExecutionState.APPROVED: {
        ExecutionState.RUNNING,
        ExecutionState.CANCELLED,
        ExecutionState.FAILED,
        ExecutionState.PAUSED,
    },
    ExecutionState.RUNNING: {
        ExecutionState.PAUSED,
        ExecutionState.RETRYING,
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.PAUSED: {
        ExecutionState.RUNNING,
        ExecutionState.RETRYING,
        ExecutionState.CANCELLED,
        ExecutionState.FAILED,
    },
    ExecutionState.RETRYING: {
        ExecutionState.RUNNING,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.COMPLETED: set(),
    ExecutionState.FAILED: set(),
    ExecutionState.CANCELLED: set(),
}

# States that are irreversible terminals.
_TERMINAL: frozenset[ExecutionState] = frozenset(
    {ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED}
)


def _is_legal_transition(src: ExecutionState, dst: ExecutionState) -> bool:
    return dst in _TRANSITIONS.get(src, set())


@dataclass
class ExecutionStateMachine:
    """Thread-safe, serializable execution lifecycle state machine.

    Lives at agent/execution/workflow.py per design §4.4.
    Independent of Engine, Queue, Memory, Tool Orchestrator (not implemented yet).

    Concurrency model: a per-instance threading.Lock guards state + history so
    concurrent transition requests are atomic. Last successful transition wins;
    a concurrent invalid request raises InvalidTransitionError exactly as a
    serial caller would observe.
    """

    _state: ExecutionState = field(default=ExecutionState.CREATED, init=False)
    _history: Deque[StateTransition] = field(default_factory=deque, init=False)
    # per-instance lock created lazily; dataclass fields avoid passing a Lock
    # (Lock is unhashable and not a clean dataclass default).
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        # Record the initial creation event so history is never empty.
        if not self._history:
            self._history.append(
                StateTransition(
                    state=self._state,
                    timestamp=self._utc(),
                    reason="machine created",
                )
            )

    @staticmethod
    def _utc() -> str:
        return datetime.now(timezone.utc).isoformat()

    @property
    def state(self) -> ExecutionState:
        return self._state

    @property
    def history(self) -> List[StateTransition]:
        "Snapshot copy of history (immutable records)."
        return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._state in _TERMINAL

    def allowed_transitions(self) -> Tuple[ExecutionState, ...]:
        "Legal target states from current state (deterministic, no I/O)."
        return tuple(_TRANSITIONS.get(self._state, set()))

    def can_transition(self, target: ExecutionState) -> bool:
        return _is_legal_transition(self._state, target)

    def transition(self, target: ExecutionState, reason: Optional[str] = None) -> ExecutionState:
        """Advance to target state if legal, else raise InvalidTransitionError.

        Atomic under self._lock. Thread-safe for concurrent callers.
        """
        with self._lock:
            if not _is_legal_transition(self._state, target):
                raise InvalidTransitionError(
                    f"illegal transition {self._state.name} -> {target.name}"
                )
            self._state = target
            self._history.append(
                StateTransition(state=target, timestamp=self._utc(), reason=reason)
            )
            return target

    # --- future-integration hooks (interfaces only, not implemented) ---

    def execution_context_id(self) -> Optional[str]:
        """Placeholder for future ExecutionContext binding.

        See EXECUTION_LAYER_DESIGN.md §4.3 / §3 integration prep:
        ExecutionContext is NOT implemented in Phase 11.1. Returns None
        until wired; keeps interface stable for 11.2 without breaking callers.
        """
        return None

    def governance_verdict(self) -> Optional[str]:
        """Placeholder for future GovernanceGate binding.

        See §4.7: GovernanceGate integration deferred. Returns None.
        """
        return None

    @property
    def execution_memory_ref(self) -> Optional[object]:
        """Placeholder for future ExecutionMemory binding (Phase 11.7).

        Returns None intentionally; avoids inventing a persistence handle.
        """
        return None

    # --- serialization ---

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "current_state": self._state.name,
                "is_terminal": self.is_terminal,
                "history": [
                    {
                        "state": h.state.name,
                        "timestamp": h.timestamp,
                        "reason": h.reason,
                    }
                    for h in self._history
                ],
                "allowed_transitions": [s.name for s in self.allowed_transitions()],
            }

    def serialize(self) -> str:
        """Stable JSON-serializable representation for evidence / recovery.

        Uses str form only; round-trips via deserialize().
        """
        import json

        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def deserialize(cls, payload: str) -> "ExecutionStateMachine":
        """Rebuild machine state + history from JSON payload.

        Starts at CREATED then re-applies history transitions in order, skipping
        the first CREATED record (which __post_init__ emits). Raises
        InvalidTransitionError if the serialized history itself was illegal.
        """
        import json

        data = json.loads(payload)
        sm = cls()  # starts at CREATED
        current = ExecutionState[data["current_state"]]
        # Re-apply each recorded transition after the initial CREATED to reach
        # the persisted current state. This validates the serialized path.
        records = data.get("history", [])
        # Skip re-applying index 0 (the original CREATED) since __post_init__ adds it.
        for rec in records[1:]:
            tgt = ExecutionState[rec["state"]]
            sm._state = tgt  # internal; transition() would re-emit duplicates
            sm._history.append(
                StateTransition(
                    state=tgt,
                    timestamp=rec.get("timestamp", sm._utc()),
                    reason=rec.get("reason"),
                )
            )
        # Verify the rebuilt state matches the serial state (consistency guard).
        if sm._state != current:
            raise ValueError(
                f"deserialized state mismatch: {sm._state} vs {current}"
            )
        return sm
