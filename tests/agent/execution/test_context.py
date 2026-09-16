# Phase 11.3 tests for ExecutionContext — Part 1 (creation, validation, immutable, serialization).
# Run: pytest tests/agent/execution/test_context.py
from __future__ import annotations

import json

import pytest

from agent.execution.context import (
    ExecutionContext,
    ContextValidationError,
)
from agent.execution.queue import QueuePriority


def _base(**kw):
    d = dict(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
    )
    d.update(kw)
    return d


def test_basic_creation():
    ctx = ExecutionContext(execution_id="e1", **_base())
    assert ctx.execution_id == "e1"
    assert ctx.task_id == "task-1"
    assert ctx.session_id == "sess-1"
    assert ctx.user_id == "user-1"
    assert ctx.project_id == "proj-1"


def test_defaults():
    ctx = ExecutionContext.create(**_base())
    assert ctx.skill_id == ""
    assert ctx.provider_id == ""
    assert ctx.tool_id == ""
    assert ctx.priority == QueuePriority.NORMAL
    assert ctx.retry_count == 0
    assert ctx.timeout_seconds is None
    assert ctx.correlation_id is None
    assert ctx.parent_execution_id is None
    assert ctx.parameters == {}
    assert ctx.metadata == {}


def test_create_auto_execution_id():
    a = ExecutionContext.create(**_base())
    b = ExecutionContext.create(**_base())
    assert a.execution_id
    assert a.execution_id != b.execution_id


def test_creation_validation_empty_execution_id():
    with pytest.raises(ContextValidationError):
        ExecutionContext(execution_id="", task_id="t", session_id="s", user_id="u", project_id="p")


def test_creation_validation_empty_task_id():
    with pytest.raises(ContextValidationError):
        ExecutionContext(execution_id="e", task_id="", session_id="s", user_id="u", project_id="p")


def test_creation_validation_negative_retry():
    with pytest.raises(ContextValidationError):
        ExecutionContext(execution_id="e", task_id="t", session_id="s", user_id="u", project_id="p", retry_count=-1)


def test_creation_validation_bad_timeout():
    with pytest.raises(ContextValidationError):
        ExecutionContext(execution_id="e", task_id="t", session_id="s", user_id="u", project_id="p", timeout_seconds=0)


def test_immutable_fields_cannot_be_updated():
    ctx = ExecutionContext.create(**_base())
    with pytest.raises(ContextValidationError):
        ctx.update_metadata(execution_id="changed")
    with pytest.raises(ContextValidationError):
        ctx.update_metadata(task_id="changed")


def test_update_metadata_returns_new_instance():
    ctx = ExecutionContext.create(**_base())
    nxt = ctx.update_metadata(metadata={"k": "v"})
    assert nxt is not ctx
    assert nxt.metadata == {"k": "v"}
    # original unchanged (immutable)
    assert ctx.metadata == {}


def test_update_metadata_keeps_identity():
    ctx = ExecutionContext.create(**_base())
    nxt = ctx.update_metadata(retry_count=1, timeout_seconds=30.0)
    assert nxt.execution_id == ctx.execution_id
    assert nxt.task_id == ctx.task_id
    assert nxt.retry_count == 1
    assert nxt.timeout_seconds == 30.0


def test_update_metadata_refreshes_updated_at():
    ctx = ExecutionContext.create(**_base())
    before = ctx.updated_at
    nxt = ctx.update_metadata(metadata={"a": 1})
    assert nxt.updated_at >= before


def test_add_execution_param():
    ctx = ExecutionContext.create(**_base())
    nxt = ctx.add_execution_param("temperature", 0.7)
    assert nxt.parameters == {"temperature": 0.7}
    assert ctx.parameters == {}  # original unchanged


def test_snapshot_is_mutable_copy():
    ctx = ExecutionContext.create(**_base())
    snap = ctx.snapshot()
    snap["execution_id"] = "CHANGED"
    snap["parameters"]["x"] = 1
    # mutating the snapshot must not affect the immutable context
    assert ctx.execution_id != "CHANGED"
    assert ctx.parameters.get("x") is None


def test_to_dict_priority_is_string():
    ctx = ExecutionContext.create(**_base(), priority=QueuePriority.HIGH)
    d = ctx.to_dict()
    assert d["priority"] == "HIGH"
    assert isinstance(d["priority"], str)


def test_to_from_json_roundtrip():
    ctx = ExecutionContext.create(
        **_base(),
        priority=QueuePriority.CRITICAL,
        parameters={"p": 1},
        metadata={"owner": "a"},
        parent_execution_id="par-0",
        correlation_id="corr-1",
        retry_count=2,
        timeout_seconds=10.0,
    )
    payload = ctx.to_json()
    rebuilt = ExecutionContext.from_json(payload)
    assert rebuilt == ctx
    assert rebuilt.priority == ctx.priority
    assert rebuilt.parent_execution_id == "par-0"
    assert rebuilt.retry_count == 2


def test_from_dict_roundtrip():
    ctx = ExecutionContext.create(**_base())
    rebuilt = ExecutionContext.from_dict(ctx.to_dict())
    assert rebuilt == ctx


def test_to_json_is_valid_json():
    ctx = ExecutionContext.create(**_base())
    obj = json.loads(ctx.to_json())
    assert obj["execution_id"] == ctx.execution_id


def test_standard_timestamps_present():
    ctx = ExecutionContext.create(**_base())
    assert ctx.created_at
    assert ctx.updated_at
    assert ctx.scheduled_at is None