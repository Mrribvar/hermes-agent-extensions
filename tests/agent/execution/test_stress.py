# Phase 11.10 stress tests — Execution Layer concurrency/load verification.
from __future__ import annotations

import os
import tempfile
import threading

from agent.execution.interface import ExecutionCoordinator, SubmitRequest


def _req(**kwargs) -> SubmitRequest:
    return SubmitRequest(
        project_id="stress-proj",
        session_id="stress-sess",
        task_id="stress-task",
        user_id="user",
        tool_id="echo",
        **kwargs,
    )


def _memory(path):
    from agent.execution.memory import ExecutionMemory

    return ExecutionMemory(db_path=path)


def _happy_orchestrator():
    from agent.execution.orchestrator import ToolOrchestrator, OrchestrationResult

    class Happy(ToolOrchestrator):
        def execute(self, ctx):
            return OrchestrationResult(success=True, tool_name="echo", result={"ok": 1})

    return Happy()


def test_stress_many_sequential_submits():
    """50 sequential submits all complete correctly and persist."""
    db = os.path.join(tempfile.mkdtemp(), "s.db")
    coord = ExecutionCoordinator(
        memory=_memory(db),
        orchestrator=_happy_orchestrator(),
        auto_execute=True,
    )
    for i in range(50):
        res = coord.submit(_req(execution_id=f"seq-{i}"))
        assert res.success, res
    history = coord.get_history(limit=100)
    assert len(history) >= 50


def test_stress_concurrent_submits():
    """100 concurrent submits: all succeed, persisted, unique IDs."""
    db = os.path.join(tempfile.mkdtemp(), "c.db")
    coord = ExecutionCoordinator(
        memory=_memory(db),
        orchestrator=_happy_orchestrator(),
        auto_execute=True,
    )
    results = []
    errs = []
    lock = threading.Lock()

    def worker(i):
        try:
            r = coord.submit(_req(execution_id=f"conc-{i}"))
            with lock:
                results.append(r)
        except Exception as e:  # pragma: no cover
            with lock:
                errs.append(str(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errs == [], errs
    assert len(results) == 100
    assert all(r.success for r in results)
    assert len({r.execution_id for r in results}) == 100  # all unique


def test_stress_memory_concurrent_writes():
    """500 concurrent sqlite writes without corruption."""
    from agent.execution.memory import ExecutionMemory, ExecutionRecord

    mem = _memory(os.path.join(tempfile.mkdtemp(), "mem.db"))
    errs = []
    lock = threading.Lock()
    barrier = threading.Barrier(5)

    def worker(chunk):
        barrier.wait()
        for i in chunk:
            try:
                mem.save_execution(ExecutionRecord(execution_id=f"wm-{i}", state="DONE"))
            except Exception as e:  # pragma: no cover
                with lock:
                    errs.append(str(e))

    chunks = [list(range(a, a + 100)) for a in range(0, 500, 100)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errs == [], errs
    assert len(mem.list_executions(limit=1000)) == 500


def test_stress_recovery_scan():
    """Finding interrupted executions across many records is correct."""
    from agent.execution.memory import ExecutionRecord
    from agent.execution.recovery import ExecutionRecovery

    mem = _memory(os.path.join(tempfile.mkdtemp(), "r.db"))
    for i in range(200):
        state = "RUNNING" if i % 10 == 0 else "COMPLETED"
        mem.save_execution(ExecutionRecord(execution_id=f"r-{i}", state=state))
    rec = ExecutionRecovery(memory=mem)
    found = rec.find_interrupted()
    # i in {0,10,...,190} -> 20 RUNNING records
    assert len(found) == 20