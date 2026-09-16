# Phase 11.1 tests for ExecutionStateMachine.
#
# These exercise ONLY the state machine (no Engine/Queue/Memory/Orchestrator).
# Run: pytest tests/agent/execution/test_state_machine.py
from __future__ import annotations

import threading
import json

import pytest

from agent.execution.workflow import (
    ExecutionStateMachine,
    ExecutionState,
    InvalidTransitionError,
    StateTransition,
)


# --- legal edge cases derived from the transition graph in workflow.py ---

def test_initial_state_is_created():
    sm = ExecutionStateMachine()
    assert sm.state == ExecutionState.CREATED
    assert not sm.is_terminal


def test_initial_history_has_created_entry():
    sm = ExecutionStateMachine()
    assert len(sm.history) == 1
    assert sm.history[0].state == ExecutionState.CREATED
    assert sm.history[0].reason == "machine created"


@pytest.mark.parametrize("src,dst", [
    # CREATED
    (ExecutionState.CREATED, ExecutionState.PENDING_APPROVAL),
    (ExecutionState.CREATED, ExecutionState.RUNNING),
    (ExecutionState.CREATED, ExecutionState.CANCELLED),
    (ExecutionState.CREATED, ExecutionState.FAILED),
    # PENDING_APPROVAL
    (ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED),
    (ExecutionState.PENDING_APPROVAL, ExecutionState.PAUSED),
    # APPROVED
    (ExecutionState.APPROVED, ExecutionState.RUNNING),
    # RUNNING
    (ExecutionState.RUNNING, ExecutionState.PAUSED),
    (ExecutionState.RUNNING, ExecutionState.RETRYING),
    (ExecutionState.RUNNING, ExecutionState.COMPLETED),
    (ExecutionState.RUNNING, ExecutionState.FAILED),
    (ExecutionState.RUNNING, ExecutionState.CANCELLED),
    # PAUSED
    (ExecutionState.PAUSED, ExecutionState.RUNNING),
    (ExecutionState.PAUSED, ExecutionState.RETRYING),
    # RETRYING
    (ExecutionState.RETRYING, ExecutionState.RUNNING),
    (ExecutionState.RETRYING, ExecutionState.FAILED),
])
def test_valid_single_transitions(src, dst):
    sm = _machine_at(src)
    assert sm.state == src
    sm.transition(dst)
    assert sm.state == dst
    # history records the new state as last entry
    assert sm.history[-1].state == dst


# Deterministic legal path to each non-terminal state.
_PATHS = {
    ExecutionState.CREATED: [],
    ExecutionState.PENDING_APPROVAL: [ExecutionState.PENDING_APPROVAL],
    ExecutionState.APPROVED: [ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED],
    ExecutionState.RUNNING: [ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING],
    ExecutionState.PAUSED: [ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING, ExecutionState.PAUSED],
    ExecutionState.RETRYING: [ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING, ExecutionState.RETRYING],
    ExecutionState.COMPLETED: [ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING, ExecutionState.COMPLETED],
    ExecutionState.FAILED: [
        ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING, ExecutionState.FAILED
    ],
    ExecutionState.CANCELLED: [
        ExecutionState.PENDING_APPROVAL, ExecutionState.APPROVED, ExecutionState.RUNNING, ExecutionState.CANCELLED
    ],
}


def _machine_at(target: ExecutionState) -> ExecutionStateMachine:
    """Return a fresh machine moved to target via a deterministic legal path."""
    sm = ExecutionStateMachine()
    for hop in _PATHS[target]:
        sm.transition(hop)
    return sm


@pytest.mark.parametrize("src,dst", [
    (ExecutionState.COMPLETED, ExecutionState.RUNNING),
    (ExecutionState.CANCELLED, ExecutionState.RUNNING),
    (ExecutionState.FAILED, ExecutionState.RUNNING),
    (ExecutionState.CREATED, ExecutionState.APPROVED),  # must route through PENDING_APPROVAL
    (ExecutionState.RUNNING, ExecutionState.APPROVED),
    (ExecutionState.COMPLETED, ExecutionState.PENDING_APPROVAL),
])
def test_invalid_transitions_raise(src, dst):
    sm = _machine_at(src)
    with pytest.raises(InvalidTransitionError):
        sm.transition(dst)
    # state unchanged after bad transition
    assert sm.state == src


def test_terminal_states_have_no_outgoing():
    for terminal in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
        sm = _machine_at(terminal)
        assert sm.is_terminal
        assert sm.allowed_transitions() == tuple()


def test_can_transition_reflects_graph():
    sm = ExecutionStateMachine()
    assert sm.can_transition(ExecutionState.PENDING_APPROVAL)
    assert not sm.can_transition(ExecutionState.COMPLETED)


def test_history_records_each_state():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL, reason="review needed")
    sm.transition(ExecutionState.APPROVED, reason="approved by gate")
    sm.transition(ExecutionState.RUNNING, reason="executor took over")
    sm.transition(ExecutionState.COMPLETED)
    states = [h.state for h in sm.history]
    assert states == [
        ExecutionState.CREATED,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.APPROVED,
        ExecutionState.RUNNING,
        ExecutionState.COMPLETED,
    ]


def test_history_timestamp_present_and_ordered():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.RUNNING)
    sm.transition(ExecutionState.COMPLETED)
    ts = [h.timestamp for h in sm.history]
    assert ts[0] <= ts[1] <= ts[2]
    assert all(h.timestamp for h in sm.history)


def test_transition_reason_stored():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL, reason="manual gate")
    assert sm.history[-1].reason == "manual gate"


def test_history_snapshot_is_copy():
    sm = ExecutionStateMachine()
    snap = sm.history
    snap.clear()  # mutate snapshot
    # internal history intact
    assert len(sm.history) == 1


def test_valid_ladder_to_complete():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL)
    sm.transition(ExecutionState.APPROVED)
    sm.transition(ExecutionState.RUNNING)
    sm.transition(ExecutionState.COMPLETED)
    assert sm.state == ExecutionState.COMPLETED
    assert sm.is_terminal


# --- concurrency: concurrent valid writers cannot violate monotonic state ---
def test_concurrent_transitions_atomic():
    """All threads target APPROVED simultaneously; exactly one wins."""
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL)

    results = {"ok": 0, "err": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()
        try:
            sm.transition(ExecutionState.APPROVED, reason="worker")
            with lock:
                results["ok"] += 1
        except InvalidTransitionError:
            with lock:
                results["err"] += 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # exactly one wins, four rejected due to monotonic advancement
    assert results["ok"] == 1
    assert results["err"] == 4
    assert sm.state == ExecutionState.APPROVED
    approved_entries = [h for h in sm.history if h.state == ExecutionState.APPROVED]
    assert len(approved_entries) == 1


def test_concurrent_transitions_to_same_state():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL)

    winners = []
    lock = threading.Lock()
    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()
        try:
            sm.transition(ExecutionState.APPROVED, reason="race")
            with lock:
                winners.append("ap")
        except InvalidTransitionError:
            with lock:
                winners.append("rejected")

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # exactly one wins; four rejected due to monotonic state
    assert winners.count("ap") == 1
    assert winners.count("rejected") == 4
    assert sm.state == ExecutionState.APPROVED
    # history should record precisely one APPROVED entry beyond CREATED+PENDING
    approved_entries = [h for h in sm.history if h.state == ExecutionState.APPROVED]
    assert len(approved_entries) == 1


# --- serialization ---

def test_serialize_round_trip():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL, reason="a")
    sm.transition(ExecutionState.APPROVED)
    sm.transition(ExecutionState.RUNNING)
    sm.transition(ExecutionState.COMPLETED)

    payload = sm.serialize()
    rebuilt = ExecutionStateMachine.deserialize(payload)
    assert rebuilt.state == sm.state
    assert rebuilt.is_terminal
    assert len(rebuilt.history) == len(sm.history)
    # history parity
    for a, b in zip(sm.history, rebuilt.history):
        assert a.state == b.state
        assert a.reason == b.reason


def test_serialize_is_json():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.RUNNING)
    payload = sm.serialize()
    data = json.loads(payload)  # must be valid JSON
    assert data["current_state"] == "RUNNING"
    assert data["is_terminal"] is False
    assert "CREATED" in data["history"][0]["state"]


def test_deserialize_invalid_payload_rejected():
    # unknown state name -> KeyError (enum lookup); malformed JSON -> json error.
    bad = json.dumps({"current_state": "BOGUS", "history": []})
    with pytest.raises((ValueError, KeyError, TypeError)):
        ExecutionStateMachine.deserialize(bad)
    with pytest.raises((ValueError, TypeError)):
        ExecutionStateMachine.deserialize("not json at all")


def test_to_dict_shape():
    sm = ExecutionStateMachine()
    sm.transition(ExecutionState.PENDING_APPROVAL)
    d = sm.to_dict()
    assert set(d.keys()) == {"current_state", "is_terminal", "history", "allowed_transitions"}
    assert d["current_state"] == "PENDING_APPROVAL"


# --- future-integration hook placeholders return None / not implemented ---

def test_future_hooks_not_yet_implemented():
    sm = ExecutionStateMachine()
    # Phase 11.1 must NOT accidentally wire real integrations.
    assert sm.execution_context_id() is None
    assert sm.governance_verdict() is None
    assert sm.execution_memory_ref is None
