# Phase 11.5 tests for GovernanceGate — Part 1 (unit tests with mock adapters).
# Verifies verdict branching only; no real governance module logic exercised here.
# Run: pytest tests/agent/execution/test_governance_gate.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from agent.execution.context import ExecutionContext
from agent.execution.governance_gate import (
    GovernanceGate,
    GovernanceResult,
    GovernanceVerdict,
)
from agent.execution.queue import QueuePriority
from agent.execution.workflow import ExecutionStateMachine


def _ctx(**kw) -> ExecutionContext:
    return ExecutionContext.create(
        task_id="task-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="proj-1",
        **kw,
    )


@dataclass
class FakeAssessment:
    risk_level: str  # a real RiskLevel member.name string


class FakeRiskClassifier:
    def __init__(self, level: str):
        self.level = level
        self.called = 0

    def classify(self, change_id, change_type, details, scope):
        self.called += 1
        return FakeAssessment(risk_level=self.level)


class FakeApprovalWorkflow:
    def __init__(self):
        self.proposed = 0
        self.request_id = "approval-fake-001"

    def propose(self, operation, reason, evidence, risk_level, rollback_plan, metadata=None):
        self.proposed += 1
        return FakeRequest(self.request_id)

    def get_status(self, request_id):
        return FakeRequest(request_id, status="approved")


@dataclass
class FakeRequest:
    request_id: str
    status: str = "pending"


# --- Verdict branching (mock adapters) ---

def test_approved_on_safe_risk():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("SAFE"))
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.APPROVED
    assert r.risk_level == "SAFE"
    assert r.approval_request_id is None


def test_approved_on_low_risk():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("LOW_RISK"))
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.APPROVED
    assert r.risk_level == "LOW_RISK"


def test_requires_approval_on_medium_risk():
    aw = FakeApprovalWorkflow()
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("MEDIUM_RISK"), approval_workflow=aw)
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.REQUIRES_APPROVAL
    assert r.risk_level == "MEDIUM_RISK"
    assert r.approval_request_id == "approval-fake-001"
    assert aw.proposed == 1


def test_rejected_on_high_risk():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("HIGH_RISK"))
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.REJECTED
    assert r.risk_level == "HIGH_RISK"


def test_failed_validation_when_no_context_id():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("SAFE"))
    r = gate.evaluate(None)  # type: ignore
    assert r.verdict == GovernanceVerdict.FAILED_VALIDATION


def test_requires_approval_when_classifier_missing():
    gate = GovernanceGate(risk_classifier=None)
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.REQUIRES_APPROVAL


def test_classifier_failure_returns_failed_validation():
    class Boom:
        def classify(self, **kw):
            raise RuntimeError("classifier down")
    gate = GovernanceGate(risk_classifier=Boom())
    r = gate.evaluate(_ctx())
    assert r.verdict == GovernanceVerdict.FAILED_VALIDATION
    assert "classifier down" in r.reason


# --- Gate does not mutate the context ---

def test_gate_does_not_change_state_machine():
    sm = ExecutionStateMachine()
    ctx = _ctx()
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("SAFE"))
    gate.evaluate(ctx)
    assert sm.state.name == "CREATED"


def test_gate_result_is_frozen():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("SAFE"))
    r = gate.evaluate(_ctx())
    assert isinstance(r, GovernanceResult)


# --- Approval status helper ---

def test_check_approval_status():
    aw = FakeApprovalWorkflow()
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("MEDIUM_RISK"), approval_workflow=aw)
    r = gate.evaluate(_ctx())
    assert r.approval_request_id is not None
    status = gate.check_approval_status(r.approval_request_id)
    assert status == "approved"


def test_record_decision_noop_without_memory():
    gate = GovernanceGate(risk_classifier=FakeRiskClassifier("SAFE"))
    r = gate.evaluate(_ctx())
    gate.record_decision(r, "approved")  # should not raise (no memory)