# Execution Layer — Phase 11.2: Execution Queue Foundation
#
# Implements ONLY the execution queue (per EXECUTION_LAYER_DESIGN.md §4.3).
# No Engine execution, no Governance wiring, no Memory persistence.
# Integrates with Phase 11.1 ExecutionStateMachine.
# Backward compatible: pure additive package under agent/execution/.

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Deque, Dict, List, Optional, Set
import threading
import uuid

from .workflow import ExecutionState, ExecutionStateMachine, InvalidTransitionError

__all__ = [
    "ExecutionQueue",
    "QueueItem",
    "QueuePriority",
    "QueueStats",
    "EmptyQueueError",
    "DuplicateExecutionIdError",
]


class QueuePriority(IntEnum):
    """Priority levels for queue ordering.

    Higher value = higher priority (processed first).
    """
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass(frozen=True)
class QueueItem:
    """An item in the execution queue.

    Each item wraps an ExecutionStateMachine and carries queue metadata.
    """
    execution_id: str
    priority: QueuePriority = QueuePriority.NORMAL
    state_machine: ExecutionStateMachine = field(default_factory=ExecutionStateMachine)
    payload: Optional[Any] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "QueueItem") -> bool:
        # For heap ordering: higher priority first, then earlier creation time
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at


class EmptyQueueError(Exception):
    """Raised when dequeuing from an empty queue."""


class DuplicateExecutionIdError(Exception):
    """Raised when enqueueing an item with an existing execution_id."""


@dataclass
class QueueStats:
    """Queue statistics snapshot."""
    total_items: int = 0
    by_priority: Dict[str, int] = field(default_factory=dict)
    by_state: Dict[str, int] = field(default_factory=dict)
    oldest_created_at: Optional[str] = None
    newest_created_at: Optional[str] = None


class ExecutionQueue:
    """Thread-safe, priority-aware execution queue.

    Per EXECUTION_LAYER_DESIGN.md §4.3: FIFO within priority, unique IDs,
    each item references an ExecutionStateMachine.

    Does NOT:
    - Execute tasks (that's Phase 11.3 Engine)
    - Wire Governance (Phase 11.5)
    - Persist (Phase 11.7 Memory)
    - Mutate state machines automatically
    """

    def __init__(self) -> None:
        # Main queue: list of items, kept sorted by priority then FIFO
        # Using list + sort is simple and sufficient for typical queue sizes.
        # For very high throughput, a heap would be better but adds complexity.
        self._items: List[QueueItem] = []
        self._ids: Set[str] = set()  # for O(1) duplicate detection
        self._lock = threading.RLock()

    def enqueue(
        self,
        *,
        execution_id: Optional[str] = None,
        priority: QueuePriority = QueuePriority.NORMAL,
        state_machine: Optional[ExecutionStateMachine] = None,
        payload: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueueItem:
        """Add an item to the queue.

        Args:
            execution_id: Unique ID. Auto-generated if None.
            priority: Queue priority (higher = processed first).
            state_machine: Pre-initialized state machine. New if None.
            payload: Arbitrary user data for the engine.
            metadata: Additional key-value metadata.

        Returns:
            The enqueued QueueItem.

        Raises:
            DuplicateExecutionIdError: if execution_id already exists.
        """
        if execution_id is None:
            execution_id = uuid.uuid4().hex
        with self._lock:
            if execution_id in self._ids:
                raise DuplicateExecutionIdError(
                    f"execution_id '{execution_id}' already in queue"
                )
            item = QueueItem(
                execution_id=execution_id,
                priority=priority,
                state_machine=state_machine or ExecutionStateMachine(),
                payload=payload,
                metadata=metadata or {},
            )
            self._items.append(item)
            # Sort so highest priority (then earliest created) comes first.
            self._items.sort(key=lambda i: (-i.priority.value, i.created_at))
            self._ids.add(execution_id)
            return item

    def dequeue(self) -> QueueItem:
        """Remove and return the highest-priority, earliest item.

        Raises:
            EmptyQueueError: if queue is empty.
        """
        with self._lock:
            if not self._items:
                raise EmptyQueueError("queue is empty")
            item = self._items.pop(0)
            self._ids.discard(item.execution_id)
            return item

    def peek(self) -> Optional[QueueItem]:
        """Return the next item without removing it, or None if empty."""
        with self._lock:
            return self._items[0] if self._items else None

    def remove(self, execution_id: str) -> Optional[QueueItem]:
        """Remove a specific item by ID.

        Returns:
            The removed QueueItem, or None if not found.
        """
        with self._lock:
            for i, item in enumerate(self._items):
                if item.execution_id == execution_id:
                    self._items.pop(i)
                    self._ids.discard(execution_id)
                    return item
            return None

    def clear(self) -> int:
        """Remove all items. Returns count cleared."""
        with self._lock:
            count = len(self._items)
            self._items.clear()
            self._ids.clear()
            return count

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, execution_id: str) -> bool:
        return execution_id in self._ids

    def get(self, execution_id: str) -> Optional[QueueItem]:
        """Get item by ID without removing."""
        with self._lock:
            for item in self._items:
                if item.execution_id == execution_id:
                    return item
            return None

    def stats(self) -> QueueStats:
        """Return queue statistics snapshot."""
        with self._lock:
            if not self._items:
                return QueueStats()
            by_priority: Dict[str, int] = {}
            by_state: Dict[str, int] = {}
            created_times = [item.created_at for item in self._items]
            for item in self._items:
                by_priority[item.priority.name] = by_priority.get(item.priority.name, 0) + 1
                state_name = item.state_machine.state.name
                by_state[state_name] = by_state.get(state_name, 0) + 1
            return QueueStats(
                total_items=len(self._items),
                by_priority=by_priority,
                by_state=by_state,
                oldest_created_at=min(created_times),
                newest_created_at=max(created_times),
            )

    # --- Future-integration hooks (stubs only, Phase 11.3+) ---

    def bind_engine(self, engine: object) -> None:
        """Placeholder for ExecutionEngine binding (Phase 11.3)."""
        # Intentionally empty; no-op until Engine exists.
        pass

    def bind_governance_gate(self, gate: object) -> None:
        """Placeholder for GovernanceGate binding (Phase 11.5)."""
        # Intentionally empty; no-op until GovernanceGate exists.
        pass

    def bind_execution_memory(self, memory: object) -> None:
        """Placeholder for ExecutionMemory binding (Phase 11.7)."""
        # Intentionally empty; no-op until ExecutionMemory exists.
        pass

    def drain_to_engine(self, engine: object) -> int:
        """Placeholder: pop items and submit to engine (Phase 11.3)."""
        # Returns 0; implementation deferred.
        return 0