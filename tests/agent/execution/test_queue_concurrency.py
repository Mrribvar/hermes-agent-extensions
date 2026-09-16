# Phase 11.2 tests for ExecutionQueue — Part 2 (priority, concurrency, state, stats).
from __future__ import annotations

import threading

import pytest

from agent.execution.queue import ExecutionQueue, QueuePriority, EmptyQueueError
from agent.execution.workflow import ExecutionStateMachine


def test_priority_ordering_high_first():
    q = ExecutionQueue()
    q.enqueue(payload="low", priority=QueuePriority.LOW)
    q.enqueue(payload="high", priority=QueuePriority.HIGH)
    q.enqueue(payload="normal", priority=QueuePriority.NORMAL)
    assert q.dequeue().payload == "high"
    assert q.dequeue().payload == "normal"
    assert q.dequeue().payload == "low"


def test_priority_fifo_within_same_level():
    q = ExecutionQueue()
    q.enqueue(payload="a", priority=QueuePriority.HIGH)
    q.enqueue(payload="b", priority=QueuePriority.HIGH)
    q.enqueue(payload="c", priority=QueuePriority.HIGH)
    assert q.dequeue().payload == "a"
    assert q.dequeue().payload == "b"
    assert q.dequeue().payload == "c"


def test_critical_before_high():
    q = ExecutionQueue()
    q.enqueue(payload="hi", priority=QueuePriority.HIGH)
    q.enqueue(payload="cr", priority=QueuePriority.CRITICAL)
    assert q.dequeue().payload == "cr"


def test_item_references_state_machine():
    q = ExecutionQueue()
    sm = ExecutionStateMachine()
    item = q.enqueue(state_machine=sm)
    assert item.state_machine is sm
    assert item.state_machine.state is sm.state


def test_default_item_gets_fresh_state_machine():
    q = ExecutionQueue()
    item = q.enqueue()
    assert isinstance(item.state_machine, ExecutionStateMachine)


def test_queue_does_not_mutate_state_machine():
    q = ExecutionQueue()
    sm = ExecutionStateMachine()
    q.enqueue(state_machine=sm)
    q.enqueue(state_machine=sm)
    # enqueue/dequeue must not advance the state machine automatically
    assert sm.state.name == "CREATED"


def test_stats_empty():
    q = ExecutionQueue()
    s = q.stats()
    assert s.total_items == 0
    assert s.by_priority == {}
    assert s.by_state == {}


def test_stats_counts():
    q = ExecutionQueue()
    q.enqueue(priority=QueuePriority.HIGH)
    q.enqueue(priority=QueuePriority.HIGH)
    q.enqueue(priority=QueuePriority.LOW)
    s = q.stats()
    assert s.total_items == 3
    assert s.by_priority == {"HIGH": 2, "LOW": 1}
    assert s.by_state == {"CREATED": 3}


def test_metadata_keys():
    q = ExecutionQueue()
    q.enqueue(metadata={"owner": "alice"})
    q.enqueue(metadata={"owner": "bob"})
    s = q.stats()
    assert s.oldest_created_at is not None
    assert s.newest_created_at is not None
    assert s.oldest_created_at <= s.newest_created_at


def test_concurrent_enqueue():
    q = ExecutionQueue()
    n = 50
    barrier = threading.Barrier(n)

    def worker():
        barrier.wait()
        q.enqueue()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(q) == n
    # all ids unique
    ids = {item.execution_id for item in q._items}
    assert len(ids) == n


def test_concurrent_dequeue():
    q = ExecutionQueue()
    n = 50
    for _ in range(n):
        q.enqueue()

    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait()
        while True:
            try:
                item = q.dequeue()
            except EmptyQueueError:
                break
            with lock:
                results.append(item.execution_id)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == n
    assert len(q) == 0


def test_concurrent_enqueue_dequeue_no_duplicates():
    q = ExecutionQueue()
    n = 200
    producer_lk = threading.Lock()

    def producer():
        for _ in range(n):
            q.enqueue()

    def consumer(seen):
        while True:
            try:
                item = q.dequeue()
                seen[item.execution_id] = seen.get(item.execution_id, 0) + 1
            except EmptyQueueError:
                break

    px = [threading.Thread(target=producer) for _ in range(2)]
    seen = {}
    cs = [threading.Thread(target=consumer, args=(seen,)) for _ in range(2)]
    for t in cs:
        t.start()
    for t in px:
        t.start()
    for t in px:
        t.join()
    for t in cs:
        t.join()

    total = sum(seen.values())
    assert total <= 2 * n
    # no id appears more than once in total processed (duplicates impossible)
    assert all(v == 1 for v in seen.values())


def test_queue_length_thread_safe():
    q = ExecutionQueue()
    n = 100
    threads = [threading.Thread(target=q.enqueue) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(q) == n


def test_enqueue_priority_default_normal():
    q = ExecutionQueue()
    item = q.enqueue()
    assert item.priority == QueuePriority.NORMAL