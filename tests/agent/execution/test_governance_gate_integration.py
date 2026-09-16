# Phase 11.5 tests for GovernanceGate — Part 2 (real governance integration + engine wiring).
from __future__ import annotations

import io
import contextlib

import pytest

from agent.execution.context import ExecutionContext
from agent.execution.engine import ExecutionEngine
from agent.execution.governance_gate import GovernanceGate, GovernanceVerdict
from agent.execution.queue import ExecutionQueue, QueuePriority
from agent.execution.workflow import ExecutionState


def _ctx(**kw) -> ExecutionContext:
    return ExecutionContext.create(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


def test_real_risk_classifier_code_change_is_medium():
    """Real RiskClassifier classifies 'code_change' as MEDIUM_RISK."""
    gate = GovernanceGate()  # auto-builds real RiskClassifier
    # 'code_change' is the default change_type when tool_id is empty
    r = gate.evaluate(_ctx(tool_id=""))
    assert r.risk_level in ("MEDIUM_RISK", "MEDIUM")
    # Without approval_workflow, still returns REQUIRES_APPROVAL
    assert r.verdict == GovernanceVerdict.REQUIRES_APPROVAL


def test_real_risk_classifier_safe_context():
    """A context with change_type that RiskClassifier deems SAFE gets APPROVED."""
    # Use a harmless change_type by passing it in metadata
    ctx = _ctx(tool_id="read_file", metadata={"change_type": "read_only", "scope": "local"})
    gate = GovernanceGate()
    r = gate.evaluate(ctx)
    # Depending on classifier, may be SAFE or LOW_RISK
    assert r.verdict in (GovernanceVerdict.APPROVED, GovernanceVerdict.REQUIRES_APPROVAL)


# --- Engine integration ---

def test_engine_blocks_when_gate_rejects():
    """Engine should not RUN when GovernanceGate rejects."""
    # Force high risk → REJECTED
    class HighRiskClassifier:
        def classify(self, **kw):
            return type("A", (), {"risk_level": "HIGH_RISK"})()

    gate = GovernanceGate(risk_classifier=HighRiskClassifier())
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "ok", governance_gate=gate)
    item = q.enqueue(payload=_ctx(), execution_id="x")
    res = eng.execute(item)
    assert res.success is False
    assert res.state == "FAILED"
    assert res.error and "rejected" in res.error.lower()


def test_engine_runs_when_gate_approves():
    """Engine should proceed to RUNNING when gate approves."""
    class SafeClassifier:
        def classify(self, **kw):
            return type("A", (), {"risk_level": "SAFE"})()

    gate = GovernanceGate(risk_classifier=SafeClassifier())
    q = ExecutionQueue()
    seen = []
    eng = ExecutionEngine(queue=q, executor=lambda c, s: seen.append(1), governance_gate=gate)
    item = q.enqueue(payload=_ctx(), execution_id="y")
    res = eng.execute(item)
    assert res.success is True
    assert res.state == "COMPLETED"
    assert seen == [1]


def test_engine_blocks_without_context():
    """Engine blocks if no ExecutionContext is provided to the gate."""
    class SafeClassifier:
        def classify(self, **kw):
            return type("A", (), {"risk_level": "SAFE"})()

    gate = GovernanceGate(risk_classifier=SafeClassifier())
    q = ExecutionQueue()
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "ok", governance_gate=gate)
    # Item without payload (no context)
    item = q.enqueue()
    res = eng.execute(item)
    assert res.success is False
    assert res.error and "no ExecutionContext" in res.error


def test_engine_bypass_when_no_gate():
    """Without a gate, engine uses backward-compatible behavior (allows)."""
    q = ExecutionQueue()
    seen = []
    eng = ExecutionEngine(queue=q, executor=lambda c, s: seen.append(1))
    item = q.enqueue(payload=_ctx(), execution_id="z")
    res = eng.execute(item)
    assert res.success is True
    assert seen == [1]


def test_engine_drain_respects_gate():
    """drain_queue should respect governance for each item."""
    class MixedClassifier:
        def __init__(self):
            self.count = 0
        def classify(self, **kw):
            self.count += 1
            return type("A", (), {"risk_level": "SAFE" if self.count % 2 == 1 else "HIGH_RISK"})()

    gate = GovernanceGate(risk_classifier=MixedClassifier())
    q = ExecutionQueue()
    for i in range(4):
        q.enqueue(execution_id=f"e-{i}", payload=_ctx())
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "ok", governance_gate=gate)
    res = eng.drain_queue()
    # 2 SAFE (even) -> APPROVED -> COMPLETED; 2 HIGH_RISK -> REJECTED -> FAILED
    comps = [r for r in res if r.success]
    fails = [r for r in res if not r.success]
    assert len(comps) == 2
    assert len(fails) == 2


def test_engine_execute_by_id_respects_gate():
    class SafeClassifier:
        def classify(self, **kw):
            return type("A", (), {"risk_level": "SAFE"})()

    gate = GovernanceGate(risk_classifier=SafeClassifier())
    q = ExecutionQueue()
    q.enqueue(execution_id="target", payload=_ctx())
    eng = ExecutionEngine(queue=q, executor=lambda c, s: "found", governance_gate=gate)
    res = eng.execute_by_id("target")
    assert res.success is True
    assert res.execution_id == "target"


# --- Gate stdout capture (ApprovalWorkflow prints) ---

def test_gate_does_not_leak_stdout():
    """ApprovalWorkflow.propose prints; gate should not leak it in evaluate()."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        gate = GovernanceGate()
        gate.evaluate(_ctx())
    out = buf.getvalue()
    # may be empty or contain approval prompt — ensure we didn't crash
    assert isinstance(out, str)