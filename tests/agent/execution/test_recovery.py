# Phase 11.8 tests for ExecutionRecovery.
# Tests: interrupted detection, context restoration, recovery planning, edge cases.
from __future__ import annotations

import os
import tempfile
import threading

import pytest

from agent.execution.memory import ExecutionMemory, ExecutionRecord
from agent.execution.recovery import ExecutionRecovery, RecoveryAction, RecoveryPlan, RecoveryError


def _db(path=None):
    if path is None:
        path = tempfile.mkdtemp()
    return ExecutionMemory(db_path=os.path.join(path, "recovery.db"))


def _rec(eid, state, **kw):
    return ExecutionRecord(execution_id=eid, state=state, **kw)


class TestFindInterrupted:
    def test_finds_running(self):
        m = _db()
        m.save_execution(_rec("r1", "RUNNING"))
        m.save_execution(_rec("c1", "COMPLETED"))
        rec = ExecutionRecovery(memory=m)
        found = rec.find_interrupted()
        ids = [r["execution_id"] for r in found]
        assert "r1" in ids
        assert "c1" not in ids

    def test_finds_pending_approval(self):
        m = _db()
        m.save_execution(_rec("p1", "PENDING_APPROVAL"))
        rec = ExecutionRecovery(memory=m)
        found = rec.find_interrupted()
        ids = [r["execution_id"] for r in found]
        assert "p1" in ids

    def test_finds_paused(self):
        m = _db()
        m.save_execution(_rec("ps1", "PAUSED"))
        rec = ExecutionRecovery(memory=m)
        found = rec.find_interrupted()
        ids = [r["execution_id"] for r in found]
        assert "ps1" in ids

    def test_no_interrupted(self):
        m = _db()
        m.save_execution(_rec("c1", "COMPLETED"))
        m.save_execution(_rec("f1", "FAILED"))
        m.save_execution(_rec("x1", "CANCELLED"))
        rec = ExecutionRecovery(memory=m)
        found = rec.find_interrupted()
        assert found == []

    def test_empty_memory(self):
        rec = ExecutionRecovery(memory=_db())
        assert rec.find_interrupted() == []

    def test_no_memory(self):
        rec = ExecutionRecovery(memory=None)
        assert rec.find_interrupted() == []


class TestRecoverExecution:
    def test_running_resumes(self):
        m = _db()
        m.save_execution(_rec("r1", "RUNNING"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("r1")
        assert plan is not None
        assert plan.action == RecoveryAction.RESUME
        assert plan.execution_id == "r1"
        assert plan.original_state == "RUNNING"

    def test_pending_approval_manual_review(self):
        m = _db()
        m.save_execution(_rec("p1", "PENDING_APPROVAL"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("p1")
        assert plan is not None
        assert plan.action == RecoveryAction.MANUAL_REVIEW

    def test_paused_retries(self):
        m = _db()
        m.save_execution(_rec("ps1", "PAUSED"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("ps1")
        assert plan is not None
        assert plan.action == RecoveryAction.RETRY

    def test_completed_returns_none(self):
        m = _db()
        m.save_execution(_rec("c1", "COMPLETED"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("c1")
        assert plan is None

    def test_failed_returns_none(self):
        m = _db()
        m.save_execution(_rec("f1", "FAILED"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("f1")
        assert plan is None

    def test_cancelled_returns_none(self):
        m = _db()
        m.save_execution(_rec("x1", "CANCELLED"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("x1")
        assert plan is None

    def test_missing_execution_raises(self):
        rec = ExecutionRecovery(memory=_db())
        with pytest.raises(RecoveryError):
            rec.recover_execution("nonexistent")

    def test_no_memory_raises(self):
        rec = ExecutionRecovery(memory=None)
        with pytest.raises(RecoveryError):
            rec.recover_execution("e1")


class TestRebuildContext:
    def test_rebuilds_running(self):
        m = _db()
        m.save_execution(_rec(
            "r1", "RUNNING",
            task_id="t1", session_id="s1", user_id="u1",
            project_id="p1", tool_id="echo",
            metadata={"key": "val"},
        ))
        rec = ExecutionRecovery(memory=m)
        ctx = rec.rebuild_context("r1")
        assert ctx is not None
        assert ctx["execution_id"] == "r1"
        assert ctx["task_id"] == "t1"
        assert ctx["tool_id"] == "echo"
        assert ctx["metadata"] == {"key": "val"}

    def test_returns_none_for_missing(self):
        rec = ExecutionRecovery(memory=_db())
        assert rec.rebuild_context("missing") is None

    def test_returns_none_without_memory(self):
        rec = ExecutionRecovery(memory=None)
        assert rec.rebuild_context("e1") is None

    def test_rebuilds_with_empty_fields(self):
        m = _db()
        m.save_execution(_rec("minimal", "RUNNING"))
        rec = ExecutionRecovery(memory=m)
        ctx = rec.rebuild_context("minimal")
        assert ctx is not None
        assert ctx["task_id"] == ""
        assert ctx["tool_id"] == ""
        assert ctx["metadata"] == {}


class TestGetRecoveryPlan:
    def test_plan_includes_context(self):
        m = _db()
        m.save_execution(_rec("r1", "RUNNING", task_id="t1", project_id="p1"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.get_recovery_plan("r1")
        assert plan.action == RecoveryAction.RESUME
        assert "context" in plan.details
        assert plan.details["context"]["task_id"] == "t1"

    def test_raises_for_terminal(self):
        m = _db()
        m.save_execution(_rec("c1", "COMPLETED"))
        rec = ExecutionRecovery(memory=m)
        with pytest.raises(RecoveryError):
            rec.get_recovery_plan("c1")

    def test_raises_for_missing(self):
        rec = ExecutionRecovery(memory=_db())
        with pytest.raises(RecoveryError):
            rec.get_recovery_plan("nope")


class TestConcurrentRecovery:
    def test_concurrent_find_interrupted(self):
        m = _db()
        for i in range(10):
            state = "RUNNING" if i % 3 == 0 else "COMPLETED"
            m.save_execution(_rec(f"e{i}", state))
        rec = ExecutionRecovery(memory=m)
        results = []
        lock = threading.Lock()

        def worker():
            found = rec.find_interrupted()
            with lock:
                results.append(len(found))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 4 for r in results)

    def test_concurrent_recover_execution(self):
        m = _db()
        m.save_execution(_rec("r1", "RUNNING"))
        rec = ExecutionRecovery(memory=m)
        plans = []
        lock = threading.Lock()

        def worker():
            p = rec.recover_execution("r1")
            with lock:
                plans.append(p)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(p.action == RecoveryAction.RESUME for p in plans)
        assert len(plans) == 10


class TestCorruptedMemoryEntry:
    def test_corrupted_metadata_does_not_crash(self):
        """A record with invalid JSON metadata must not break recovery."""
        m = _db()
        conn = m._connect()
        try:
            conn.execute(
                "INSERT INTO execution_records "
                "(execution_id, state, metadata) VALUES (?,?,?)",
                ("corrupt", "RUNNING", "{broken json"),
            )
            conn.commit()
        finally:
            conn.close()
        rec = ExecutionRecovery(memory=m)
        # find_interrupted must not raise
        found = rec.find_interrupted()
        ids = [r["execution_id"] for r in found]
        assert "corrupt" in ids
        # get_execution degrades gracefully (empty metadata)
        got = m.get_execution("corrupt")
        assert got is not None
        assert got.metadata == {}
        # recovery plan still works
        plan = rec.recover_execution("corrupt")
        assert plan is not None
        assert plan.action == RecoveryAction.RESUME

    def test_corrupt_unknown_state_manual_review(self):
        """An execution with an unrecognized state maps to MANUAL_REVIEW."""
        m = _db()
        m.save_execution(ExecutionRecord(execution_id="weird", state="IN_FLIGHT"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("weird")
        assert plan is not None
        assert plan.action == RecoveryAction.MANUAL_REVIEW


class TestNoAutomaticExecution:
    def test_recovery_plan_does_not_modify_memory(self):
        m = _db()
        m.save_execution(_rec("r1", "RUNNING"))
        rec = ExecutionRecovery(memory=m)
        plan = rec.recover_execution("r1")
        # State must remain RUNNING — recovery plans, doesn't change state
        got = m.get_execution("r1")
        assert got is not None
        assert got.state == "RUNNING"
        assert plan is not None
        assert plan.action == RecoveryAction.RESUME


class TestRecoveryPlanSerialization:
    def test_to_dict(self):
        plan = RecoveryPlan(
            execution_id="e1",
            state="RUNNING",
            action=RecoveryAction.RESUME,
            reason="test",
            original_state="RUNNING",
        )
        d = plan.to_dict()
        assert d["execution_id"] == "e1"
        assert d["action"] == "resume"
        assert d["reason"] == "test"

    def test_plan_is_frozen(self):
        plan = RecoveryPlan(
            execution_id="e1",
            state="RUNNING",
            action=RecoveryAction.RESUME,
            reason="immutable",
        )
        with pytest.raises(AttributeError):
            plan.execution_id = "changed"  # type: ignore
