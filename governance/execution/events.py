"""Execution Events — Hermes Execution Layer.

Event types emitted during execution lifecycle.
These will later power Workflow Engine and Multi-Agent communication.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable


class ExecutionEventType(str, Enum):
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_RETRIED = "execution_retried"


@dataclass
class ExecutionEvent:
    """A single execution event."""
    event_type: ExecutionEventType
    execution_id: str
    task_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class ExecutionEventBus:
    """In-process event bus for execution events.

    Supports subscribe/unsubscribe pattern for future consumers
    (Workflow Engine, Multi-Agent, Monitoring).
    No distributed messaging — single-process only.
    """

    def __init__(self):
        self._subscribers: Dict[ExecutionEventType, List[Callable]] = {
            et: [] for et in ExecutionEventType
        }

    def subscribe(self, event_type: ExecutionEventType, handler: Callable) -> None:
        """Register a handler for an event type."""
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: ExecutionEventType, handler: Callable) -> None:
        """Remove a handler."""
        try:
            self._subscribers[event_type].remove(handler)
        except ValueError:
            pass

    def emit(self, event: ExecutionEvent) -> None:
        """Publish an event to all subscribers."""
        for handler in self._subscribers[event.event_type]:
            try:
                handler(event)
            except Exception:
                # Never let a handler break the bus
                pass

    def clear(self) -> None:
        """Remove all subscribers (for test isolation)."""
        for et in self._subscribers:
            self._subscribers[et].clear()
