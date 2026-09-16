"""Decision Feedback Loop — Phase 011.

Processes decision outcomes and generates feedback signals based on
confidence accuracy and actual results.

Signal types:
  - HIGH_CONFIDENCE_SUCCESS (+0.8)
  - HIGH_CONFIDENCE_FAILURE (-0.8)
  - POSITIVE (+0.5)
  - NEGATIVE (-0.5)
  - LOW_CONFIDENCE_SUCCESS (+0.3)
  - LOW_CONFIDENCE_FAILURE (-0.2)
  - NEUTRAL (0.0)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_THRESHOLD = 0.7
LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class DecisionFeedback:
    """Feedback generated from a decision outcome."""
    decision_id: str
    task_id: str
    success: bool
    confidence_accuracy: float = 0.0
    prediction_accuracy: bool = False
    improvement_signal: float = 0.0
    learning_signal_type: str = "NEUTRAL"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "success": self.success,
            "confidence_accuracy": self.confidence_accuracy,
            "prediction_accuracy": self.prediction_accuracy,
            "improvement_signal": self.improvement_signal,
            "learning_signal_type": self.learning_signal_type,
            "metadata": self.metadata,
        }


class DecisionFeedbackLoop:
    """Processes decision outcomes and generates feedback signals."""

    def __init__(self, engine=None, enabled: bool = True):
        self.engine = engine
        self.enabled = enabled
        self._feedback_history: List[Dict[str, Any]] = []

    def process_decision_outcome(
        self,
        decision_id: str,
        actual_outcome: str,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[DecisionFeedback]:
        """Process a decision outcome and generate feedback."""
        if not self.enabled:
            return None

        try:
            # Evaluate the decision through the engine
            self.engine.evaluate_decision(
                decision_id=decision_id,
                actual_outcome=actual_outcome,
                duration_ms=duration_ms,
                metadata=metadata,
            )

            # Retrieve the record
            record = self.engine.store.get_record(decision_id)
            if record is None:
                return None

            return self.process_decision_record(record)

        except Exception as e:
            logger.warning(f"Feedback processing failed: {e}")
            return None

    def process_decision_record(self, record) -> Optional[DecisionFeedback]:
        """Generate feedback from a decision record."""
        success = record.actual_outcome == "success"
        confidence = record.confidence_before

        # Calculate confidence accuracy
        confidence_accuracy = 0.0
        if record.actual_outcome:
            expected_success = record.expected_outcome == "success"
            confidence_accuracy = 1.0 - abs(confidence - (1.0 if success else 0.0))

        # Prediction accuracy
        prediction_accuracy = False
        if record.expected_outcome and record.actual_outcome:
            prediction_accuracy = record.expected_outcome == record.actual_outcome

        # Determine signal type and improvement signal
        signal_type, improvement = self._classify_signal(confidence, success)

        feedback = DecisionFeedback(
            decision_id=record.decision_id,
            task_id=record.task_id,
            success=success,
            confidence_accuracy=confidence_accuracy,
            prediction_accuracy=prediction_accuracy,
            improvement_signal=improvement,
            learning_signal_type=signal_type,
        )

        # Store in history
        self._feedback_history.append(feedback.to_dict())

        return feedback

    def _classify_signal(self, confidence: float, success: bool) -> tuple:
        """Classify the feedback signal based on confidence and outcome."""
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            if success:
                return "HIGH_CONFIDENCE_SUCCESS", 0.8
            else:
                return "HIGH_CONFIDENCE_FAILURE", -0.8
        elif confidence < LOW_CONFIDENCE_THRESHOLD:
            if success:
                return "LOW_CONFIDENCE_SUCCESS", 0.3
            else:
                return "LOW_CONFIDENCE_FAILURE", -0.2
        else:
            # Medium confidence [0.5, 0.7)
            if success:
                return "POSITIVE", 0.5
            else:
                return "NEGATIVE", -0.5

    def get_recent_feedback(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent feedback entries."""
        return list(reversed(self._feedback_history[-limit:]))

    def get_feedback_by_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback for a specific decision."""
        for fb in reversed(self._feedback_history):
            if fb["decision_id"] == decision_id:
                return fb
        return None

    def clear_feedback_history(self) -> None:
        """Clear all feedback history."""
        self._feedback_history.clear()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics of feedback."""
        if not self._feedback_history:
            return {
                "total": 0,
                "positive_count": 0,
                "negative_count": 0,
                "avg_improvement": 0.0,
            }

        total = len(self._feedback_history)
        positive = sum(1 for fb in self._feedback_history if fb["success"])
        negative = total - positive
        avg_improvement = (
            sum(fb["improvement_signal"] for fb in self._feedback_history) / total
        )

        return {
            "total": total,
            "positive_count": positive,
            "negative_count": negative,
            "avg_improvement": avg_improvement,
        }
