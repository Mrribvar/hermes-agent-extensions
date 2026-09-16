# Phase 11.9 tests for ExecutionCoordinator (interface wiring).
# Tests end-to-end flow: submit -> context -> queue -> engine -> memory -> recovery.
from __future__ import annotations

import pytest

from agent.execution.interface import (
    ExecutionCoordinator,
    SubmitRequest,
    SubmitResult,
)
import threading
from agent.execution.context import ExecutionContext
from agent.execution.memory import ExecutionMemory, ExecutionRecord
from agent.execution.recovery import RecoveryAction
from agent.execution.orchestrator import ToolOrchestrator, OrchestrationResult


def _happy_orchestrator():
    """Orchestrator that always succeeds, isolating tests from real registry."""

    class HappyOrchestrator(ToolOrchestrator):
        def execute(self, ctx):
            return OrchestrationResult(
                success=True,
                tool_name=ctx.tool_id or "tool",
                result={"ok": True},
            )

    return HappyOrchestrator()


def _req(**kw) -> SubmitRequest:
    return SubmitRequest(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


def test_submit_success():
    coord = ExecutionCoordinator(auto_execute=True, orchestrator=_happy_orchestrator())
    req = _req(tool_id="echo")
    result = coord.submit(req)
    assert result.execution_id
    assert result.success is True
    assert result.status == "completed"
    # memory should have the record
    rec = coord.memory.get_execution(result.execution_id)
    assert rec is not None
    assert rec.state == "COMPLETED"


def test_submit_rejected_by_governance():
    class RejectGate:
        def evaluate(self, ctx):
            from agent.execution.governance_gate import GovernanceVerdict, GovernanceResult
            return GovernanceResult(verdict=GovernanceVerdict.REJECTED, reason="blocked")

    coord = ExecutionCoordinator(auto_execute=True, gate=RejectGate())
    req = _req(tool_id="echo")
    result = coord.submit(req)
    assert result.success is False
    assert result.status == "rejected"
    assert "rejected" in (result.error or "").lower()


def test_submit_requires_approval():
    class ApproveGate:
        def evaluate(self, ctx):
            from agent.execution.governance_gate import GovernanceVerdict, GovernanceResult
            return GovernanceResult(verdict=GovernanceVerdict.REQUIRES_APPROVAL, reason="needs review")

    coord = ExecutionCoordinator(auto_execute=True, gate=ApproveGate())
    req = _req(tool_id="echo")
    result = coord.submit(req)
    assert result.success is False
    assert result.status == "requires_approval"


def test_submit_missing_tool():
    """When orchestrator can't resolve tool, execution fails gracefully."""
    from agent.execution.orchestrator import ToolOrchestrator, OrchestrationResult

    class MissingToolOrchestrator(ToolOrchestrator):
        def execute(self, ctx):
            return OrchestrationResult(
                success=False, tool_name=ctx.tool_id,
                error=f"tool '{ctx.tool_id}' not found in registry",
            )

    coord = ExecutionCoordinator(
        auto_execute=True,
        orchestrator=MissingToolOrchestrator(),
    )
    req = _req(tool_id="nonexistent_tool_xyz")
    result = coord.submit(req)
    assert result.success is False
    assert "not found" in (result.error or "")


def test_get_status():
    coord = ExecutionCoordinator(auto_execute=True, orchestrator=_happy_orchestrator())
    req = _req(tool_id="echo")
    result = coord.submit(req)
    status = coord.get_status(result.execution_id)
    assert status is not None
    assert status["state"] == "COMPLETED"


def test_get_status_missing():
    coord = ExecutionCoordinator(auto_execute=True, orchestrator=_happy_orchestrator())
    assert coord.get_status("nonexistent") is None


def test_get_history():
    coord = ExecutionCoordinator(auto_execute=True, orchestrator=_happy_orchestrator())
    for i in range(3):
        coord.submit(_req(tool_id="echo", execution_id=f"h-{i}"))
    history = coord.get_history(limit=10)
    assert len(history) >= 3


def test_recovery_lookup():
    coord = ExecutionCoordinator(auto_execute=True)
    # submit a failed execution
    class FailOrchestrator:
        def execute(self, ctx):
            raise RuntimeError("tool failed")

    coord.orchestrator = FailOrchestrator()
    req = _req(tool_id="failing_tool")
    result = coord.submit(req)
    assert result.success is False

    # recovery should find it and recommend MANUAL_REVIEW (FAILED is terminal)
    plan = coord.recover(result.execution_id)
    assert plan is None  # terminal state


def test_recover_all():
    coord = ExecutionCoordinator(auto_execute=True)
    interrupted = coord.recover_all()
    assert isinstance(interrupted, list)


def test_concurrent_submits():
    coord = ExecutionCoordinator(auto_execute=True, orchestrator=_happy_orchestrator())
    results = []
    lock = threading.Lock()

    def submit(i):
        r = coord.submit(_req(execution_id=f"concurrent-{i}"))
        with lock:
            results.append(r)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert all(r.success for r in results)
    ids = {r.execution_id for r in results}
    assert len(ids) == 5  # all unique


def test_no_auto_execute_dry_run():
    coord = ExecutionCoordinator(auto_execute=False)
    req = _req(tool_id="echo")
    result = coord.submit(req)
    # enqueued but not executed (no executor wired)
    assert result.execution_id


def test_memory_failure_does_not_crash():
    """Even if memory persistence fails, submit returns a result."""
    from agent.execution.memory import InvalidRecordError

    class BrokenMemory:
        def save_execution(self, rec):
            raise InvalidRecordError("broken memory")
        def get_execution(self, eid): return None
        def list_executions(self, **kw): return []
        def search_by_project(self, **kw): return []
        def search_by_tool(self, **kw): return []
        def recent_failures(self, **kw): return []
        def update_state(self, **kw): return None

    coord = ExecutionCoordinator(auto_execute=True, memory=BrokenMemory())
    req = _req(tool_id="echo")
    result = coord.submit(req)
    # execution should still succeed despite memory failure
    assert result.execution_id


def test_submit_request_validation():
    """Invalid SubmitRequest (empty task_id) produces failed SubmitResult."""
    coord = ExecutionCoordinator(auto_execute=True)
    req = SubmitRequest(
        task_id="", session_id="s", user_id="u", project_id="p",
    )
    result = coord.submit(req)
    assert result.success is False
    assert "context validation failed" in (result.error or "")