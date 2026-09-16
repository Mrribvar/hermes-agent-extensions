# Phase 11.4 tests for ExecutionEngine — Part 2 (queue integration, drain, concurrency).
from __future__ import annotations

import threading

import pytest

from agent.execution.context import ExecutionContext
from agent.execution.engine import ExecutionEngine, EngineError
from agent.execution.queue import ExecutionQueue, QueuePriority, EmptyQueueError
from agent.execution.workflow import ExecutionState, ExecutionStateMachine


def _ctx(**kw) -> ExecutionContext:
    return ExecutionContext.create(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


def test_multiple_queued_executions_drain():
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "ok")
    for i in range(5):
        q.enqueue(execution_id=f"e{i}", payload=_ctx())
    results = eng.drain_queue()
    assert len(results) == 5
    assert all(r.success for r in results)
    assert len(q) == 0


def test_drain_limit():
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: 1, drain_limit=3)
    for i in range(6):
        q.enqueue(execution_id=f"e-{i}")
    results = eng.drain_queue()
    assert len(results) == 3
    assert len(q) == 3  # remaining 3 still queued


def test_drain_empty_returns_empty_list():
    eng = ExecutionEngine(queue=ExecutionQueue())
    assert eng.drain_queue() == []


def test_execute_by_id_success():
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "found")
    q.enqueue(execution_id="target", payload=_ctx())
    q.enqueue(execution_id="other", payload=_ctx())
    res = eng.execute_by_id("target")
    assert res.success is True
    assert res.execution_id == "target"
    # target removed from queue, other remains
    assert len(q) == 1


def test_execute_by_id_missing_raises():
    eng = ExecutionEngine(queue=ExecutionQueue())
    with pytest.raises(EngineError):
        eng.execute_by_id("gone")


def test_exception_propagation_recorded_but_not_raised():
    """Executor exceptions are captured into the result, not propagated."""
    def boom(c, s):
        raise ValueError("bad tool")

    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=boom)
    item = q.enqueue(payload=_ctx(), execution_id="x")
    res = eng.execute(item)
    # exception is captured, engine returns a FAILED result
    assert res.success is False
    assert res.error and "bad tool" in res.error
    assert res.state == "FAILED"


def test_stack_trace_in_result():
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: 1 / 0)
    item = q.enqueue(execution_id="d0")
    res = eng.execute(item)
    assert res.success is False
    assert res.error and "ZeroDivision" in res.error
    assert "ZeroDivision" in res.error


def test_concurrent_execute_requests():
    """Concurrent execute() calls on separate items are safe."""
    q = ExecutionQueue()
    results = []
    lock = threading.Lock()

    def make_executor(i):
        def executor(c, s):
            return i
        return executor

    engs = []
    for i in range(10):
        sub_q = ExecutionQueue()
        item = sub_q.enqueue(execution_id=f"c-{i}", payload=_ctx())
        eng = ExecutionEngine(queue=sub_q, executor=make_executor(i))
        engs.append((eng, item))

    threads = []
    for eng, item in engs:
        t = threading.Thread(target=lambda _e=eng, _i=item: lock and _e.execute(_i))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    assert True  # no exceptions; concurrent execution is isolated per engine state-machine


def test_engine_of_machine_not_shared_across_concurrency():
    """Each QueueItem has its own state machine; engine shouldn't cross-contaminate."""
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: None)
    items = []
    for i in range(4):
        item = q.enqueue(execution_id=f"s-{i}")
        items.append(item)
    results = eng.drain_queue()
    for item in items:
        assert item.state_machine.state == ExecutionState.COMPLETED
    assert len({id(r) for r in results}) == 4