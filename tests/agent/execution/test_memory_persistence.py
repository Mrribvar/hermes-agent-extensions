# Phase 11.7 tests for ExecutionMemory — Part 2 (persistence, concurrency, engine integration).
from __future__ import annotations

import os
import tempfile
import threading

import pytest

from agent.execution.context import ExecutionContext
from agent.execution.engine import ExecutionEngine
from agent.execution.memory import ExecutionMemory, ExecutionRecord
from agent.execution.queue import ExecutionQueue


def _db_dir():
    return tempfile.mkdtemp()


def _ctx(**kw):
    return ExecutionContext.create(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


def test_list_executions():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "list.db"))
    for i in range(5):
        m.save_execution(ExecutionRecord(execution_id=f"e{i}", state="COMPLETED", project_id="p"))
    items = m.list_executions(limit=3)
    assert len(items) == 3
    # all should be dicts with execution_id
    for d in items:
        assert "execution_id" in d


def test_list_executions_by_project():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "proj.db"))
    m.save_execution(ExecutionRecord(execution_id="p1", state="DONE", project_id="alpha"))
    m.save_execution(ExecutionRecord(execution_id="p2", state="DONE", project_id="beta"))
    items = m.search_by_project("alpha")
    ids = [d["execution_id"] for d in items]
    assert ids == ["p1"]


def test_search_by_tool():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "tool.db"))
    m.save_execution(ExecutionRecord(execution_id="t1", state="DONE", tool_id="echo"))
    m.save_execution(ExecutionRecord(execution_id="t2", state="DONE", tool_id="file"))
    items = m.search_by_tool("echo")
    assert len(items) == 1
    assert items[0]["execution_id"] == "t1"


def test_persistence_after_reconnect():
    """Records survive closing and reopening a new ExecutionMemory on the same path."""
    db_path = os.path.join(_db_dir(), "persist.db")
    m1 = ExecutionMemory(db_path=db_path)
    m1.save_execution(ExecutionRecord(execution_id="x1", state="DONE"))
    # close by losing all references
    del m1
    m2 = ExecutionMemory(db_path=db_path)
    got = m2.get_execution("x1")
    assert got is not None
    assert got.execution_id == "x1"


def test_concurrent_writes():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "concurrent.db"))
    n = 20
    errors = []
    barrier = threading.Barrier(n)

    def writer(i):
        barrier.wait()
        try:
            m.save_execution(ExecutionRecord(execution_id=f"c-{i}", state="DONE"))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    # all 20 should be persisted
    items = m.list_executions(limit=100)
    assert len(items) == n


def test_metadata_roundtrip():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "meta.db"))
    m.save_execution(
        ExecutionRecord(
            execution_id="m1",
            state="COMPLETED",
            metadata={"key": "val", "nested": {"a": 1}},
        )
    )
    got = m.get_execution("m1")
    assert got is not None
    assert got.metadata == {"key": "val", "nested": {"a": 1}}


def test_engine_with_memory_persists_terminal():
    """When memory is set, Engine.execute persists on completion."""
    db_path = os.path.join(_db_dir(), "engine.db")
    mem = ExecutionMemory(db_path=db_path)
    q = ExecutionQueue()
    ctx = _ctx()
    eng = ExecutionEngine(
        queue=q,
        executor=lambda c, s: "ok",
        memory=mem,
    )
    item = q.enqueue(payload=ctx, execution_id="eng1")
    res = eng.execute(item)
    assert res.success is True
    got = mem.get_execution("eng1")
    assert got is not None
    assert got.state == "COMPLETED"
    assert got.result_status == "success"


def test_engine_with_memory_persists_failure():
    """Engine failure is persisted with error_message."""
    db_path = os.path.join(_db_dir(), "engine-fail.db")
    mem = ExecutionMemory(db_path=db_path)
    q = ExecutionQueue()
    ctx = _ctx()
    eng = ExecutionEngine(
        queue=q,
        executor=lambda c, s: 1 / 0,
        memory=mem,
    )
    item = q.enqueue(payload=ctx, execution_id="eng-f1")
    res = eng.execute(item)
    assert res.success is False
    got = mem.get_execution("eng-f1")
    assert got is not None
    assert got.state == "FAILED"
    assert got.result_status == "failed"
    assert got.error_message is not None


def test_engine_without_memory_does_not_crash():
    """Engine with memory=None (default) runs fine with no persistence."""
    q = ExecutionQueue()
    ctx = _ctx()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "ok")
    item = q.enqueue(payload=ctx, execution_id="nm1")
    res = eng.execute(item)
    assert res.success is True


def test_search_by_project_and_tool_combined():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "combined.db"))
    m.save_execution(ExecutionRecord(execution_id="c1", state="D", project_id="A", tool_id="x"))
    m.save_execution(ExecutionRecord(execution_id="c2", state="D", project_id="B", tool_id="x"))
    m.save_execution(ExecutionRecord(execution_id="c3", state="D", project_id="A", tool_id="y"))
    by_tool = m.search_by_tool("x")
    assert len(by_tool) == 2
    by_proj = m.search_by_project("A")
    assert len(by_proj) == 2


def test_update_state_multiple_fields():
    m = ExecutionMemory(db_path=os.path.join(_db_dir(), "multi.db"))
    m.save_execution(ExecutionRecord(execution_id="u1", state="PENDING"))
    updated = m.update_state(
        "u1",
        state="COMPLETED",
        result_status="success",
        duration_ms=42,
        error_message=None,
        completed_at="2026-08-05T12:00:00Z",
    )
    assert updated is not None
    assert updated["state"] == "COMPLETED"
    assert updated["duration_ms"] == 42