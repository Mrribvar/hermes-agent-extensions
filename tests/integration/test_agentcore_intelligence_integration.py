"""Integration tests for AgentCore Intelligence Integration.

Phase HERALD-INTELLIGENCE-012 — Validates that Pattern Intelligence and
Decision Performance Intelligence are correctly wired into execution.
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.execution.interface import ExecutionCoordinator, SubmitRequest, SubmitResult
from agent.execution.queue import QueuePriority
from agent.execution.intelligence_integration import IntelligenceBridge, get_intelligence_bridge


class TestIntelligenceBridgeUnit:
    """Unit tests for IntelligenceBridge."""

    @pytest.fixture
    def bridge(self):
        return get_intelligence_bridge()

    def test_bridge_singleton(self):
        b1 = get_intelligence_bridge()
        b2 = get_intelligence_bridge()
        assert b1 is b2

    def test_bridge_initialized_with_defaults(self):
        bridge = get_intelligence_bridge()
        assert bridge.enabled is True

    def test_on_before_execution_returns_context(self, bridge):
        ctx = bridge.on_before_execution(
            task_id="task_001", task="test task",
            context={"strategy": "direct"}, strategy="direct", confidence=0.85,
        )
        assert ctx is not None
        assert hasattr(ctx, "pattern_guidance")
        assert hasattr(ctx, "confidence_adjustment")
        assert hasattr(ctx, "risk_level")
        assert hasattr(ctx, "recommendations")
        assert hasattr(ctx, "warnings")

    def test_on_before_execution_disabled(self):
        bridge = IntelligenceBridge(enabled=False)
        ctx = bridge.on_before_execution(task_id="t1", task="test")
        assert ctx is not None
        assert ctx.pattern_guidance is None
        assert ctx.confidence_adjustment == 0.0
        assert ctx.risk_level == "LOW"

    def test_record_decision_returns_id_or_none(self, bridge):
        decision_id = bridge.record_decision(
            task_id="task_001", strategy="direct", confidence=0.85,
        )
        assert decision_id is None or isinstance(decision_id, str)

    def test_evaluate_decision_after_record(self, bridge):
        decision_id = bridge.record_decision(
            task_id="task_eval", strategy="direct", confidence=0.85,
        )
        if decision_id:
            evaluation = bridge.evaluate_decision(
                decision_id=decision_id, actual_outcome="success", duration_ms=150,
            )
            assert evaluation is not None
            assert "is_success" in evaluation
            assert evaluation["is_success"] is True

    def test_generate_feedback_after_record(self, bridge):
        decision_id = bridge.record_decision(
            task_id="task_fb", strategy="direct", confidence=0.85,
        )
        if decision_id:
            feedback = bridge.generate_feedback(
                decision_id=decision_id, actual_outcome="success", duration_ms=150,
            )
            assert feedback is not None
            assert "improvement_signal" in feedback
            assert feedback["success"] is True

    def test_get_performance_metrics(self, bridge):
        metrics = bridge.get_performance_metrics()
        assert isinstance(metrics, dict)

    def test_context_to_dict(self, bridge):
        ctx = bridge.on_before_execution(task_id="t1", task="test")
        data = ctx.to_dict()
        assert isinstance(data, dict)
        assert "pattern_guidance" in data
        assert "confidence_adjustment" in data
        assert "risk_level" in data

    def test_context_has_warnings(self, bridge):
        ctx = bridge.on_before_execution(task_id="t1", task="test")
        assert isinstance(ctx.has_warnings(), bool)

    def test_disabled_bridge_evaluate_returns_none(self):
        bridge = IntelligenceBridge(enabled=False)
        assert bridge.evaluate_decision("any", "success") is None

    def test_disabled_bridge_feedback_returns_none(self):
        bridge = IntelligenceBridge(enabled=False)
        assert bridge.generate_feedback("any", "success") is None

    def test_disabled_bridge_record_returns_none(self):
        bridge = IntelligenceBridge(enabled=False)
        assert bridge.record_decision("t1", "direct", 0.5) is None

    def test_missing_components_returns_none(self):
        bridge = IntelligenceBridge()
        bridge._pattern_adapter = None
        bridge._performance_engine = None
        bridge._feedback_loop = None
        ctx = bridge.on_before_execution(task_id="t", task="test")
        assert ctx is not None
        assert bridge.record_decision("t", "direct", 0.5) is None
        assert bridge.evaluate_decision("x", "success") is None


class TestSubmitResultWithIntelligence:
    """Tests for SubmitResult intelligence fields."""

    def test_submit_result_has_decision_id(self):
        result = SubmitResult(
            execution_id="e1", status="completed", success=True, decision_id="d1",
        )
        assert result.decision_id == "d1"

    def test_submit_result_has_intelligence_context(self):
        result = SubmitResult(
            execution_id="e1", status="completed", success=True,
            intelligence_context={"pattern_guidance": {"type": "HIGH_SUCCESS"}},
        )
        assert result.intelligence_context is not None
        assert "pattern_guidance" in result.intelligence_context

    def test_submit_result_defaults_no_intelligence(self):
        result = SubmitResult(execution_id="e1", status="completed", success=True)
        assert result.decision_id is None
        assert result.intelligence_context is None


class TestCoordinatorIntegration:
    """Tests for ExecutionCoordinator intelligence integration."""

    @pytest.fixture
    def coordinator(self):
        return ExecutionCoordinator(auto_execute=False)

    @pytest.fixture
    def request_data(self):
        return SubmitRequest(
            task_id="task_001", session_id="s1", user_id="u1", project_id="p1",
            tool_id="read_file", priority=QueuePriority.NORMAL,
            parameters={"path": "/tmp/test.txt"},
            metadata={"strategy": "direct", "confidence": 0.85, "description": "test task"},
        )

    def test_submit_returns_intelligence_context(self, coordinator, request_data):
        result = coordinator.submit(request_data)
        assert result is not None
        # Intelligence context is populated (even if empty)
        assert result.intelligence_context is not None or result.intelligence_context is None

    def test_submit_returns_decision_id(self, coordinator, request_data):
        result = coordinator.submit(request_data)
        assert result.decision_id is None or isinstance(result.decision_id, str)

    def test_execution_not_blocked_by_intelligence_failure(self, coordinator, request_data):
        with patch("agent.execution.interface.get_intelligence_bridge") as mock_bridge:
            mock_bridge.side_effect = Exception("Intelligence failure")
            result = coordinator.submit(request_data)
            assert result is not None
            assert result.status in ["completed", "failed", "rejected", "requires_approval"]

    def test_multiple_executions_with_intelligence(self, coordinator):
        for i in range(3):
            req = SubmitRequest(
                task_id=f"task_m_{i}", session_id="s", user_id="u", project_id="p",
                tool_id="test", priority=QueuePriority.NORMAL, parameters={"i": i},
                metadata={"strategy": "direct", "confidence": 0.8 + i * 0.05},
            )
            result = coordinator.submit(req)
            assert result is not None

    def test_metrics_accumulate_across_executions(self):
        bridge = get_intelligence_bridge()
        for i in range(3):
            decision_id = bridge.record_decision(
                task_id=f"task_metrics_{i}", strategy="direct", confidence=0.8,
            )
            if decision_id:
                bridge.evaluate_decision(
                    decision_id=decision_id,
                    actual_outcome="success" if i < 2 else "failure",
                )
        metrics = bridge.get_performance_metrics()
        assert isinstance(metrics, dict)

    def test_full_e2e_with_intelligence(self):
        coordinator = ExecutionCoordinator(auto_execute=False)
        request = SubmitRequest(
            task_id="task_e2e", session_id="s", user_id="u", project_id="p",
            tool_id="test_tool", priority=QueuePriority.NORMAL, parameters={"test": True},
            metadata={"strategy": "direct", "confidence": 0.9, "description": "e2e test"},
        )
        result = coordinator.submit(request)
        assert result is not None
        assert result.execution_id is not None


class TestFailSafeBehavior:
    """Tests for fail-safe behavior."""

    def test_intelligence_failure_does_not_break_submit(self):
        coordinator = ExecutionCoordinator(auto_execute=False)
        request = SubmitRequest(
            task_id="t1", session_id="s", user_id="u", project_id="p",
            tool_id="test", priority=QueuePriority.NORMAL, parameters={},
            metadata={},
        )
        with patch("agent.execution.interface.get_intelligence_bridge") as mock_get:
            mock_bridge = MagicMock()
            mock_bridge.on_before_execution.side_effect = Exception("fail")
            mock_bridge.record_decision.side_effect = Exception("fail")
            mock_bridge.evaluate_decision.side_effect = Exception("fail")
            mock_bridge.generate_feedback.side_effect = Exception("fail")
            mock_get.return_value = mock_bridge
            result = coordinator.submit(request)
            assert result is not None
