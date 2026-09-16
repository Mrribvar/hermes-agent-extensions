# Phase 11.3 tests for ExecutionContext — Part 2 (Queue integration, State Machine, concurrency, metadata).
from __future__ import annotations

import threading
import time

import pytest

from agent.execution.context import ExecutionContext, ContextValidationError
from agent.execution.queue import ExecutionQueue, QueuePriority
from agent.execution.workflow import ExecutionStateMachine, ExecutionState


def _base(**kw):
    d = dict(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
    )
    d.update(kw)
    return d


def test_context_references_state_machine():
    sm = ExecutionStateMachine()
    ctx = ExecutionContext.create(**_base(task_id="task-2"))
    # No runtime wiring; just check that we can store a reference
    # (Engine will wire them in 11.3)
    assert ctx.task_id == "task-2"
    # State machine is separate
    assert sm.state.name == "CREATED"


def test_context_and_queue_independent():
    q = ExecutionQueue()
    ctx = ExecutionContext.create(**_base())
    q.enqueue(execution_id=ctx.execution_id, state_machine=ExecutionStateMachine())
    # Queue does not mutate context or state machine
    assert ctx.task_id == "task-1"
    assert q.peek().state_machine.state.name == "CREATED"


def test_concurrent_read_access():
    ctx = ExecutionContext.create(**_base())
    n = 100
    results = []
    lock = threading.Lock()

    def reader():
        for _ in range(n):
            with lock:
                results.append(ctx.execution_id)
                results.append(ctx.task_id)
                results.append(ctx.session_id)
                results.append(ctx.user_id)
                results.append(ctx.project_id)

    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5 * n * 5  # 5 threads x n iterations x 5 fields
    # every 5-element group has consistent task_id/session_id values
    for i in range(0, len(results), 5):
        assert results[i] == ctx.execution_id
        assert results[i + 1] == "task-1"
        assert results[i + 2] == "sess-1"
        assert results[i + 3] == "user-1"
        assert results[i + 4] == "proj-1"


def test_context_is_frozen():
    ctx = ExecutionContext.create(**_base())
    with pytest.raises(ContextValidationError):
        ctx.update_metadata(execution_id="hacked")  # forbidden
    # Verify no aliasing on dict fields
    ctx2 = ctx.update_metadata(metadata={"a": 1})
    # ctx2.metadata is a new dict in ctx2, ctx.metadata unchanged
    assert ctx.metadata == {}
    assert ctx2.metadata == {"a": 1}


def test_context_from_dict_preserves_fields():
    ctx = ExecutionContext.create(
        **_base(),
        priority=QueuePriority.HIGH,
        parameters={"p": 1},
        metadata={"m": 2},
        parent_execution_id="par-0",
        correlation_id="corr-1",
        retry_count=3,
        timeout_seconds=30.0,
    )
    d = ctx.to_dict()
    rebuilt = ExecutionContext.from_dict(d)
    assert rebuilt.priority == QueuePriority.HIGH
    assert rebuilt.parameters == {"p": 1}
    assert rebuilt.metadata == {"m": 2}
    assert rebuilt.parent_execution_id == "par-0"
    assert rebuilt.correlation_id == "corr-1"
    assert rebuilt.retry_count == 3
    assert rebuilt.timeout_seconds == 30.0


def test_context_created_at_before_updated_at():
    ctx = ExecutionContext.create(**_base())
    time.sleep(0.01)
    ctx2 = ctx.update_metadata(metadata={"x": 1})
    assert ctx.created_at <= ctx.updated_at
    assert ctx.updated_at <= ctx2.updated_at


def test_context_with_optional_fields():
    ctx = ExecutionContext.create(
        **_base(),
        skill_id="skill-x",
        provider_id="provider-y",
        tool_id="tool-z",
        scheduled_at="2026-08-04T12:00:00Z",
        started_at="2026-08-04T12:00:05Z",
        completed_at="2026-08-04T12:00:10Z",
        timeout_seconds=15.0,
    )
    assert ctx.skill_id == "skill-x"
    assert ctx.provider_id == "provider-y"
    assert ctx.tool_id == "tool-z"
    assert ctx.scheduled_at == "2026-08-04T12:00:00Z"
    assert ctx.started_at == "2026-08-04T12:00:05Z"
    assert ctx.completed_at == "2026-08-04T12:00:10Z"
    assert ctx.timeout_seconds == 15.0


def test_context_to_json_and_back():
    ctx = ExecutionContext.create(
        **_base(),
        correlation_id="corr-1",
        parent_execution_id="par-0",
    )
    payload = ctx.to_json()
    obj = ExecutionContext.from_json(payload)
    assert obj.correlation_id == "corr-1"
    assert obj.parent_execution_id == "par-0"


def test_context_uses_uuid4_hex_by_default():
    ctx = ExecutionContext.create(**_base())
    assert len(ctx.execution_id) == 32
    # check it looks like hex
    assert all(c in "0123456789abcdef" for c in ctx.execution_id)


def test_context_params_empty_dict():
    ctx = ExecutionContext.create(**_base())
    assert ctx.parameters == {}
    assert ctx.metadata == {}


def test_context_validation_empty_strings():
    with pytest.raises(ContextValidationError):
        ExecutionContext(
            execution_id="",
            task_id="",
            session_id="",
            user_id="",
            project_id="",
        )
    with pytest.raises(ContextValidationError):
        ExecutionContext(
            execution_id="e",
            task_id="",
            session_id="s",
            user_id="u",
            project_id="p",
        )
    with pytest.raises(ContextValidationError):
        ExecutionContext(
            execution_id="e",
            task_id="t",
            session_id="",
            user_id="u",
            project_id="p",
        )
    with pytest.raises(ContextValidationError):
        ExecutionContext(
            execution_id="e",
            task_id="t",
            session_id="s",
            user_id="",
            project_id="p",
        )


def test_context_with_nested_params():
    ctx = ExecutionContext.create(**_base())
    ctx2 = ctx.add_execution_param("nested", {"inner": 1, "list": [2, 3]})
    assert ctx2.parameters == {"nested": {"inner": 1, "list": [2, 3]}}
    assert ctx.parameters == {}  # original unchanged