"""Tests for DecisionFeedbackLoop."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from governance.decision_performance_engine import DecisionPerformanceEngine
from governance.decision_store import DecisionStore
from governance.decision_feedback_loop import DecisionFeedbackLoop, DecisionFeedback


class TestDecisionFeedbackLoop:
    """Tests for DecisionFeedbackLoop."""
    
    @pytest.fixture
    def loop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            store = DecisionStore(storage_path=str(path))
            engine = DecisionPerformanceEngine(store=store, enabled=True)
            return DecisionFeedbackLoop(engine=engine, enabled=True)
    
    def test_process_decision_outcome_success(self, loop):
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.85,
            expected_outcome="success"
        )
        
        feedback = loop.process_decision_outcome(
            decision_id=decision_id,
            actual_outcome="success"
        )
        
        assert feedback is not None
        assert feedback.success is True
        assert feedback.confidence_accuracy > 0
        assert feedback.learning_signal_type == "HIGH_CONFIDENCE_SUCCESS"
        assert feedback.improvement_signal > 0
    
    def test_process_decision_outcome_failure(self, loop):
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.9,
            expected_outcome="success"
        )
        
        feedback = loop.process_decision_outcome(
            decision_id=decision_id,
            actual_outcome="failure"
        )
        
        assert feedback is not None
        assert feedback.success is False
        assert feedback.learning_signal_type == "HIGH_CONFIDENCE_FAILURE"
        assert feedback.improvement_signal < 0
    
    def test_process_decision_outcome_disabled(self, loop):
        loop.enabled = False
        
        feedback = loop.process_decision_outcome(
            decision_id="dec_001",
            actual_outcome="success"
        )
        
        assert feedback is None
    
    def test_process_decision_outcome_not_found(self, loop):
        feedback = loop.process_decision_outcome(
            decision_id="nonexistent",
            actual_outcome="success"
        )
        
        assert feedback is None
    
    def test_get_recent_feedback(self, loop):
        for i in range(3):
            decision_id = loop.engine.record_decision(
                task_id=f"task_{i}",
                strategy="strategy_001",
                confidence=0.8
            )
            loop.process_decision_outcome(
                decision_id=decision_id,
                actual_outcome="success" if i % 2 == 0 else "failure"
            )
        
        recent = loop.get_recent_feedback(limit=2)
        assert len(recent) == 2
    
    def test_get_feedback_by_decision(self, loop):
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.8
        )
        loop.process_decision_outcome(
            decision_id=decision_id,
            actual_outcome="success"
        )
        
        feedback = loop.get_feedback_by_decision(decision_id)
        assert feedback is not None
        assert feedback["decision_id"] == decision_id
        
        feedback = loop.get_feedback_by_decision("nonexistent")
        assert feedback is None
    
    def test_clear_feedback_history(self, loop):
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.8
        )
        loop.process_decision_outcome(decision_id, "success")
        
        assert len(loop.get_recent_feedback()) == 1
        
        loop.clear_feedback_history()
        assert len(loop.get_recent_feedback()) == 0
    
    def test_get_summary_stats(self, loop):
        for i in range(5):
            decision_id = loop.engine.record_decision(
                task_id=f"task_{i}",
                strategy="strategy_001",
                confidence=0.8
            )
            loop.process_decision_outcome(
                decision_id=decision_id,
                actual_outcome="success" if i < 3 else "failure"
            )
        
        stats = loop.get_summary_stats()
        assert stats["total"] == 5
        assert stats["positive_count"] == 3
        assert stats["negative_count"] == 2
        assert stats["avg_improvement"] > 0
    
    def test_get_summary_stats_empty(self, loop):
        stats = loop.get_summary_stats()
        assert stats["total"] == 0
        assert stats["positive_count"] == 0
        assert stats["avg_improvement"] == 0.0
    
    def test_improvement_signal_variations(self, loop):
        # HIGH_CONFIDENCE_SUCCESS
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.95
        )
        fb = loop.process_decision_outcome(decision_id, "success")
        assert fb.learning_signal_type == "HIGH_CONFIDENCE_SUCCESS"
        assert fb.improvement_signal == 0.8
        
        # LOW_CONFIDENCE_FAILURE
        decision_id = loop.engine.record_decision(
            task_id="task_002",
            strategy="strategy_001",
            confidence=0.3
        )
        fb = loop.process_decision_outcome(decision_id, "failure")
        assert fb.learning_signal_type == "LOW_CONFIDENCE_FAILURE"
        assert fb.improvement_signal == -0.2
        
        # LOW_CONFIDENCE_SUCCESS
        decision_id = loop.engine.record_decision(
            task_id="task_003",
            strategy="strategy_001",
            confidence=0.3
        )
        fb = loop.process_decision_outcome(decision_id, "success")
        assert fb.learning_signal_type == "LOW_CONFIDENCE_SUCCESS"
        assert fb.improvement_signal == 0.3
    
    def test_fail_safe_when_engine_fails(self, loop):
        loop.engine.evaluate_decision = MagicMock(side_effect=Exception("Engine failure"))
        
        feedback = loop.process_decision_outcome(
            decision_id="dec_001",
            actual_outcome="success"
        )
        
        assert feedback is None
    
    def test_process_decision_record(self, loop):
        # Create a record directly
        decision_id = loop.engine.record_decision(
            task_id="task_001",
            strategy="strategy_001",
            confidence=0.85
        )
        
        # Update with actual outcome
        loop.engine.evaluate_decision(decision_id, "success")
        
        # Process the existing record
        record = loop.engine.store.get_record(decision_id)
        feedback = loop.process_decision_record(record)
        
        assert feedback is not None
        assert feedback.decision_id == decision_id
        assert feedback.success is True
    
    def test_to_dict(self, loop):
        feedback = DecisionFeedback(
            decision_id="dec_001",
            task_id="task_001",
            success=True,
            confidence_accuracy=0.9,
            prediction_accuracy=True,
            improvement_signal=0.8,
            learning_signal_type="HIGH_CONFIDENCE_SUCCESS"
        )
        
        data = feedback.to_dict()
        assert data["decision_id"] == "dec_001"
        assert data["improvement_signal"] == 0.8
        assert data["learning_signal_type"] == "HIGH_CONFIDENCE_SUCCESS"
