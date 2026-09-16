# Phase 11.6 tests for ToolOrchestrator — Part 1 (resolution, validation, mock registry).
# Run: pytest tests/agent/execution/test_orchestrator.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pytest

from agent.execution.context import ExecutionContext
from agent.execution.governance_gate import GovernanceVerdict
from agent.execution.orchestrator import (
    ToolOrchestrator,
    OrchestrationResult,
    ApprovalRequiredError,
    InputValidationError,
    ToolNotFoundError,
)


def _ctx(**kw) -> ExecutionContext:
    return ExecutionContext.create(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


@dataclass
class FakeEntry:
    name: str
    toolset: str = "test"
    handler: Callable = lambda **kw: {"ok": True}
    check_fn: Optional[Callable] = None
    is_async: bool = False
    schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeRegistry:
    tools: Dict[str, FakeEntry]

    def get_entry(self, name: str) -> Optional[FakeEntry]:
        return self.tools.get(name)


def test_plan_resolves_tool():
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(tool_id="echo")
    res = orch.plan(ctx)
    assert res.success is True
    assert res.tool_name == "echo"
    assert res.toolset == "test"


def test_plan_missing_tool():
    reg = FakeRegistry(tools={})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(tool_id="missing")
    res = orch.plan(ctx)
    assert res.success is False
    assert res.error is not None
    assert "not found" in str(res.error)


def test_plan_invalid_params():
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(tool_id="echo", parameters="not-a-dict")
    res = orch.plan(ctx)
    assert res.success is False
    assert res.error is not None
    assert "mapping" in str(res.error)


def test_execute_blocks_without_approval():
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(tool_id="echo")
    with pytest.raises(ApprovalRequiredError):
        orch.execute(ctx)


def test_execute_proceeds_with_approval():
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(
        tool_id="echo",
        metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
    )
    res = orch.execute(ctx)
    assert res.success is True
    assert res.tool_name == "echo"
    assert res.result == {"ok": True}


def test_execute_tool_check_fn_false():
    def check_fn():
        return False

    reg = FakeRegistry(tools={"blocked": FakeEntry(name="blocked", check_fn=check_fn)})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(
        tool_id="blocked",
        metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
    )
    res = orch.execute(ctx)
    assert res.success is False
    assert res.error is not None
    assert "not available" in str(res.error)


def test_execute_tool_check_fn_raises():
    def boom():
        raise RuntimeError("check down")

    reg = FakeRegistry(tools={"boom": FakeEntry(name="boom", check_fn=boom)})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(
        tool_id="boom",
        metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
    )
    res = orch.execute(ctx)
    assert res.success is False
    assert res.error is not None
    assert "check_fn raised" in str(res.error)


def test_execute_handler_exception():
    def handler(**kw):
        raise ValueError("handler failed")

    reg = FakeRegistry(tools={"boom": FakeEntry(name="boom", handler=handler)})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(
        tool_id="boom",
        metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
    )
    res = orch.execute(ctx)
    assert res.success is False
    assert res.error is not None
    assert "ValueError" in str(res.error)


def test_execute_multiple_tools_concurrent():
    """Concurrent orchestrator.execute calls are isolated."""
    import threading

    results = []

    def run_tool(name):
        reg = FakeRegistry(tools={name: FakeEntry(name=name, handler=lambda **k: name)})
        orch = ToolOrchestrator(registry=reg)
        ctx = _ctx(
            tool_id=name,
            metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
        )
        res = orch.execute(ctx)
        results.append((name, res.success))

    threads = [threading.Thread(target=run_tool, args=(f"tool-{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(success for _, success in results)
    assert len(results) == 5


def test_plan_normalized_params():
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(tool_id="echo", parameters={"x": 1, "y": "two"})
    res = orch.plan(ctx)
    assert res.normalized == {"x": 1, "y": "two"}


def test_execute_async_tool_uses_asyncio():
    """async tool branch uses asyncio.run (mocked)."""
    import asyncio

    async def async_handler(**kw):
        await asyncio.sleep(0)
        return {"async": True}

    reg = FakeRegistry(tools={"async_tool": FakeEntry(name="async_tool", handler=async_handler, is_async=True)})
    orch = ToolOrchestrator(registry=reg)
    ctx = _ctx(
        tool_id="async_tool",
        metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}},
    )
    res = orch.execute(ctx)
    assert res.success is True
    assert res.result.get("async") is True
    assert res.is_async is True


def test_approval_marker_in_metadata_only():
    """Approval is read from metadata.governance.verdict."""
    reg = FakeRegistry(tools={"echo": FakeEntry(name="echo")})
    orch = ToolOrchestrator(registry=reg)

    # Wrong verdict -> blocked
    ctx1 = _ctx(tool_id="echo", metadata={"governance": {"verdict": "rejected"}})
    with pytest.raises(ApprovalRequiredError):
        orch.execute(ctx1)

    # Correct verdict -> allowed
    ctx2 = _ctx(tool_id="echo", metadata={"governance": {"verdict": GovernanceVerdict.APPROVED.value}})
    res = orch.execute(ctx2)
    assert res.success is True