# Phase 11.2 tests for ExecutionQueue — Part 1 (ordering, IDs, empty, stats).
# Run: pytest tests/agent/execution/test_queue.py
from __future__ import annotations

import pytest

from agent.execution.queue import (
    ExecutionQueue,
    QueuePriority,
    EmptyQueueError,
    DuplicateExecutionIdError,
)
from agent.execution.workflow import ExecutionStateMachine


def test_empty_queue_len_zero():
    q = ExecutionQueue()
    assert len(q) == 0


def test_dequeue_empty_raises():
    q = ExecutionQueue()
    with pytest.raises(EmptyQueueError):
        q.dequeue()


def test_peek_empty_returns_none():
    q = ExecutionQueue()
    assert q.peek() is None


def test_enqueue_returns_item():
    q = ExecutionQueue()
    item = q.enqueue()
    assert item.execution_id
    assert len(q) == 1


def test_enqueue_dequeue_roundtrip():
    q = ExecutionQueue()
    item = q.enqueue(payload={"x": 1})
    got = q.dequeue()
    assert got.execution_id == item.execution_id
    assert got.payload == {"x": 1}
    assert len(q) == 0


def test_duplicate_id_raises():
    q = ExecutionQueue()
    item = q.enqueue()
    with pytest.raises(DuplicateExecutionIdError):
        q.enqueue(execution_id=item.execution_id)


def test_auto_id_unique():
    q = ExecutionQueue()
    a = q.enqueue()
    b = q.enqueue()
    assert a.execution_id != b.execution_id


def test_remove_existing():
    q = ExecutionQueue()
    item = q.enqueue(payload="keep")
    q.enqueue(payload="other")
    removed = q.remove(item.execution_id)
    assert removed is not None
    assert removed.payload == "keep"
    assert len(q) == 1


def test_remove_missing_returns_none():
    q = ExecutionQueue()
    assert q.remove("nonexistent") is None


def test_get_by_id():
    q = ExecutionQueue()
    item = q.enqueue(payload="v")
    assert q.get(item.execution_id).payload == "v"
    assert q.get("missing") is None


def test_clear_empties():
    q = ExecutionQueue()
    q.enqueue()
    q.enqueue()
    assert q.clear() == 2
    assert len(q) == 0
    with pytest.raises(EmptyQueueError):
        q.dequeue()


def test_fifo_ordering():
    q = ExecutionQueue()
    q.enqueue(payload=1)
    q.enqueue(payload=2)
    q.enqueue(payload=3)
    assert q.dequeue().payload == 1
    assert q.dequeue().payload == 2
    assert q.dequeue().payload == 3


def test_peek_does_not_remove():
    q = ExecutionQueue()
    q.enqueue(payload="only")
    assert q.peek().payload == "only"
    assert len(q) == 1