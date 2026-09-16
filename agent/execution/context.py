# Execution Layer — Phase 11.3: Execution Context Foundation
#
# Implements ONLY the Execution Context (per EXECUTION_LAYER_DESIGN.md §4.2).
# No execution logic, no governance logic, no engine.
# References ExecutionStateMachine and ExecutionQueue by type only (no runtime wiring).
# Backward compatible: pure additive package under agent/execution/.

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import json
import uuid

from .queue import QueuePriority
from .workflow import ExecutionStateMachine, ExecutionState

__all__ = [
    "ExecutionContext",
    "ContextValidationError",
]


class ContextValidationError(Exception):
    """Raised when ExecutionContext data fails validation."""


# Immutable field names that cannot be changed via update_metadata / replace.
_IMMUTABLE = frozenset(
    {
        "execution_id",
        "task_id",
        "session_id",
        "user_id",
        "project_id",
        "skill_id",
        "provider_id",
        "tool_id",
        "priority",
        "correlation_id",
        "parent_execution_id",
    }
)


# Timing limit: timeout must be positive.
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable snapshot of execution context.

    Per EXECUTION_LAYER_DESIGN.md §4.2: immutable per-request snapshot so the
    state machine and engine have deterministic inputs.

    Backed by a frozen dataclass -> truly immutable after construction.
    Updates produce a NEW instance via update_metadata() / derive() copies.
    """

    execution_id: str
    task_id: str
    session_id: str
    user_id: str
    project_id: str
    # Optional identity fields default to "" (empty string) rather than None,
    # keeping the model flat and JSON-serializable.
    skill_id: str = ""
    provider_id: str = ""
    tool_id: str = ""
    priority: QueuePriority = QueuePriority.NORMAL
    # execution parameters: generic key/value bag.
    parameters: Dict[str, Any] = field(default_factory=dict)
    # generic metadata.
    metadata: Dict[str, Any] = field(default_factory=dict)
    # timestamps (ISO 8601 UTC).
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    # retry / timing.
    retry_count: int = 0
    timeout_seconds: Optional[float] = None
    # lineage.
    correlation_id: Optional[str] = None
    parent_execution_id: Optional[str] = None

    def __post_init__(self) -> None:
        # trampoline: frozen dataclass still runs validation after construction.
        self._validate()

    def _validate(self) -> None:
        for fld in ("execution_id", "task_id", "session_id", "user_id", "project_id"):
            if not getattr(self, fld):
                raise ContextValidationError(f"{fld} must be non-empty")
        if self.retry_count < 0:
            raise ContextValidationError("retry_count must be >= 0")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ContextValidationError("timeout_seconds must be > 0 when set")
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ContextValidationError("execution_id must be a non-empty string")

    # --- validation-friendly helpers ---

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        session_id: str,
        user_id: str,
        project_id: str,
        execution_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "ExecutionContext":
        """Create a context, auto-generating execution_id if not provided."""
        if execution_id is None:
            execution_id = uuid.uuid4().hex
        return cls(
            execution_id=execution_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            **kwargs,
        )

    # --- immutability: snapshot access ---

    def snapshot(self) -> Dict[str, Any]:
        """Return a mutable deep copy of this context as a plain dict.

        Nested dicts (parameters, metadata) are copied so that mutating
        the snapshot never mutates the frozen context.
        """
        return {
            **vars(self),
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
        }

    # --- metadata update helpers (return new context; never mutate self) ---

    def update_metadata(self, **values: Any) -> "ExecutionContext":
        """Return a new context with updated metadata (non-immutable keys only)."""
        forbidden = _IMMUTABLE.intersection(values.keys())
        if forbidden:
            raise ContextValidationError(
                f"cannot update immutable fields: {sorted(forbidden)}"
            )
        new = replace(self, **values)
        # refresh updated_at
        new = replace(new, updated_at=_now_iso())
        return new

    def add_execution_param(self, key: str, value: Any) -> "ExecutionContext":
        fresh = dict(self.parameters)
        fresh[key] = value
        return self.update_metadata(parameters=fresh)

    # --- serialization / deserialization ------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict (no object references)."""
        d = dict(vars(self))
        d["priority"] = self.priority.name
        # ensure nested dicts are copied (avoids aliasing)
        d["parameters"] = dict(self.parameters)
        d["metadata"] = dict(self.metadata)
        return d

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionContext":
        """Deserialize from a to_dict()-style dict."""
        data = dict(data)
        prio = data.pop("priority", None)
        if prio is not None:
            prio = QueuePriority[prio] if isinstance(prio, str) else QueuePriority(prio)
        kwargs: Dict[str, Any] = dict(data)
        if prio is not None:
            kwargs["priority"] = prio
        return cls(**kwargs)

    @classmethod
    def from_json(cls, payload: str) -> "ExecutionContext":
        import json

        return cls.from_dict(json.loads(payload))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ExecutionContext(execution_id={self.execution_id!r}, task_id={self.task_id!r}, state fields immutable)"