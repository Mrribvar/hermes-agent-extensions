"""Execution Queue — Hermes Execution Layer.

Priority/FIFO queue with delayed execution and retry support.
In-memory only (no distributed queue yet).
Supports future scheduling.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass(order=True)
class QueuedTask:
    """A task waiting in the execution queue."""
    sort_priority: int       # negative for heap (lower number = higher priority)
    timestamp: float         # enqueue time for FIFO ordering within same priority
    execution_id: str        # hidden from comparison
    task_id: str
    context_data: Dict[str, Any] = field(compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "priority": TaskPriority(-self.sort_priority).name,
            "timestamp": self.timestamp,
            "context": self.context_data,
        }


class ExecutionQueue:
    """Thread-safe-ish priority + FIFO queue.

    Supports:
    - Priority queuing (CRITICAL > HIGH > NORMAL > LOW)
    - FIFO ordering within same priority
    - Delayed execution (enqueue_time in future)
    - Retry queue
    """

    def __init__(self):
        self._heap: List[QueuedTask] = []
        self._retry_queue: List[QueuedTask] = []
        self._processing_ids: set = set()  # currently executing

    def enqueue(
        self,
        task_id: str,
        context_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        delay_seconds: float = 0,
    ) -> str:
        """Enqueue a task. Returns execution_id."""
        import uuid
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        now = time.time() + delay_seconds

        entry = QueuedTask(
            sort_priority=-priority.value,
            timestamp=now,
            execution_id=execution_id,
            task_id=task_id,
            context_data=context_data,
        )
        heapq.heappush(self._heap, entry)
        return execution_id

    def dequeue_ready(self) -> Optional[QueuedTask]:
        """Dequeue next ready task (not delayed). Returns None if empty or none ready."""
        if not self._heap:
            return None

        now = time.time()
        # Collect all tasks ready now or overdue
        ready: List[QueuedTask] = []
        pending: List[QueuedTask] = []

        while self._heap:
            entry = heapq.heappop(self._heap)
            if entry.timestamp <= now:
                ready.append(entry)
            else:
                pending.append(entry)

        # Put back pending tasks
        for p in pending:
            heapq.heappush(self._heap, p)

        # If no ready tasks, peek earliest pending for next check
        if not ready and pending:
            return None

        return ready[0]

    def move_to_retry(self, execution_id: str) -> bool:
        """Move a processing task to retry queue."""
        if execution_id not in self._processing_ids:
            return False

        self._processing_ids.discard(execution_id)
        self._retry_queue.append(QueuedTask(
            sort_priority=0,
            timestamp=time.time(),
            execution_id=execution_id,
            task_id="",
            context_data={},
        ))
        return True

    def dequeue_retry(self) -> Optional[QueuedTask]:
        """Dequeue next retry task."""
        if not self._retry_queue:
            return None
        return self._retry_queue.pop(0)

    def mark_processing(self, execution_id: str) -> bool:
        """Mark a task as being processed."""
        if execution_id not in [e.execution_id for e in self._heap + self._retry_queue]:
            return False
        self._processing_ids.add(execution_id)
        return True

    def complete_task(self, execution_id: str) -> bool:
        """Mark a task as complete (remove from processing set)."""
        was_processing = execution_id in self._processing_ids
        self._processing_ids.discard(execution_id)
        return was_processing

    @property
    def pending_count(self) -> int:
        """Number of tasks awaiting execution."""
        return len(self._heap)

    @property
    def retry_count(self) -> int:
        """Number of tasks in retry queue."""
        return len(self._retry_queue)

    @property
    def processing_count(self) -> int:
        """Number of tasks currently executing."""
        return len(self._processing_ids)

    def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        now = time.time()
        ready = sum(1 for e in self._heap if e.timestamp <= now)
        return {
            "pending": ready,
            "delayed": len(self._heap) - ready,
            "retry": self.retry_count,
            "processing": self.processing_count,
        }
