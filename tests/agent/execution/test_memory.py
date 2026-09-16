# Phase 11.7 tests for ExecutionMemory — Part 1 (save/retrieve/update/failures/invalid).
from __future__ import annotations

import os
import tempfile

import pytest

from agent.execution.memory import (
    ExecutionMemory,
    ExecutionRecord,
    InvalidRecordError,
)


def _db():
    d = tempfile.mkdtemp()
    return ExecutionMemory(db_path=os.path.join(d, "exec.db"))


def test_save_and_retrieve():
    m = _db()
    rec = ExecutionRecord(
        execution_id="e1", state="COMPLETED", tool_id="echo",
        project_id="p1", result_status="success",
    )
    rid = m.save_execution(rec)
    assert rid == "e1"
    got = m.get_execution("e1")
    assert got is not None
    assert got.state == "COMPLETED"
    assert got.execution_id == "e1"


def test_retrieve_missing_returns_none():
    m = _db()
    assert m.get_execution("nope") is None


def test_update_state_patches_record():
    m = _db()
    m.save_execution(ExecutionRecord(execution_id="e1", state="RUNNING", tool_id="echo", project_id="p1"))
    updated = m.update_state(
        "e1",
        state="COMPLETED",
        result_status="success",
        duration_ms=120,
    )
    assert updated is not None
    assert updated["state"] == "COMPLETED"
    assert updated["duration_ms"] == 120


def test_update_state_missing_returns_none():
    m = _db()
    assert m.update_state("missing", state="FAILED") is None


def test_failure_storage_and_recent_failures():
    m = _db()
    m.save_execution(ExecutionRecord(execution_id="ok1", state="COMPLETED", project_id="p", result_status="success"))
    m.save_execution(ExecutionRecord(execution_id="bad1", state="FAILED", project_id="p", result_status="failed", error_message="boom"))
    m.save_execution(ExecutionRecord(execution_id="bad2", state="CANCELLED", project_id="p", result_status="cancelled"))
    fails = m.recent_failures()
    ids = {f["execution_id"] for f in fails}
    assert {"bad1", "bad2"} <= ids
    assert "ok1" not in ids


def test_save_overwrites_existing():
    m = _db()
    m.save_execution(ExecutionRecord(execution_id="e1", state="RUNNING", tool_id="t1"))
    m.save_execution(ExecutionRecord(execution_id="e1", state="COMPLETED", tool_id="t1", result_status="success"))
    got = m.get_execution("e1")
    assert got is not None
    assert got.state == "COMPLETED"
    assert got.result_status == "success"


def test_invalid_execution_id_rejected():
    m = _db()
    with pytest.raises(InvalidRecordError):
        m.save_execution(ExecutionRecord(execution_id="", state="RUNNING"))
    with pytest.raises(InvalidRecordError):
        m.get_execution("")
    with pytest.raises(InvalidRecordError):
        m.update_state("", state="FAILED")


def test_schema_version_meta_present():
    m = _db()
    conn = m._connect()
    try:
        row = conn.execute("SELECT value FROM memory_meta WHERE key='schema_version'").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["value"] == "1"