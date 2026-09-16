"""Decision Performance Intelligence Engine.

Records decisions, evaluates them against actual outcomes,
and generates performance metrics for decision quality.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DecisionRecord:
    """Record of a decision made during execution."""
    decision_id: str
    task_id: str
    selected_strategy: str
    confidence_before: float
    pattern_influence: Optional[Dict[str, Any]] = None
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    risk_level: str = "LOW"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "selected_strategy": self.selected_strategy,
            "confidence_before": self.confidence_before,
            "pattern_influence": self.pattern_influence,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DecisionRecord":
        return cls(
            decision_id=data.get("decision_id", ""),
            task_id=data.get("task_id", ""),
            selected_strategy=data.get("selected_strategy", "unknown"),
            confidence_before=data.get("confidence_before", 0.0),
            pattern_influence=data.get("pattern_influence"),
            expected_outcome=data.get("expected_outcome"),
            actual_outcome=data.get("actual_outcome"),
            risk_level=data.get("risk_level", "LOW"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {})
        )
    
    def is_successful(self) -> Optional[bool]:
        """Return True if outcome was success, False if failure, None if unknown."""
        if self.actual_outcome is None:
            return None
        return self.actual_outcome.lower() == "success"
    
    def is_accurate_prediction(self) -> Optional[bool]:
        """Check if expected outcome matched actual outcome."""
        if self.expected_outcome is None or self.actual_outcome is None:
            return None
        return self.expected_outcome.lower() == self.actual_outcome.lower()


@dataclass
class DecisionMetrics:
    """Performance metrics for decisions."""
    total_decisions: int = 0
    successful_decisions: int = 0
    failed_decisions: int = 0
    accurate_predictions: int = 0
    total_predictions: int = 0
    total_confidence: float = 0.0
    strategy_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    risk_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Overall success rate."""
        if self.total_decisions == 0:
            return 0.0
        return self.successful_decisions / self.total_decisions
    
    @property
    def failure_rate(self) -> float:
        """Overall failure rate."""
        if self.total_decisions == 0:
            return 0.0
        return self.failed_decisions / self.total_decisions
    
    @property
    def prediction_accuracy(self) -> float:
        """Accuracy of predictions."""
        if self.total_predictions == 0:
            return 0.0
        return self.accurate_predictions / self.total_predictions
    
    @property
    def average_confidence(self) -> float:
        """Average confidence across all decisions."""
        if self.total_decisions == 0:
            return 0.0
        return self.total_confidence / self.total_decisions
    
    def get_strategy_success_rate(self, strategy: str) -> float:
        """Success rate for a specific strategy."""
        stats = self.strategy_stats.get(strategy, {})
        attempts = stats.get("attempts", 0)
        successes = stats.get("successes", 0)
        if attempts == 0:
            return 0.0
        return successes / attempts
    
    def get_risk_success_rate(self, risk_level: str) -> float:
        """Success rate for a specific risk level."""
        stats = self.risk_stats.get(risk_level, {})
        attempts = stats.get("attempts", 0)
        successes = stats.get("successes", 0)
        if attempts == 0:
            return 0.0
        return successes / attempts
    
    def to_dict(self) -> dict:
        return {
            "total_decisions": self.total_decisions,
            "successful_decisions": self.successful_decisions,
            "failed_decisions": self.failed_decisions,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "accurate_predictions": self.accurate_predictions,
            "total_predictions": self.total_predictions,
            "prediction_accuracy": self.prediction_accuracy,
            "average_confidence": self.average_confidence,
            "strategy_stats": self.strategy_stats,
            "risk_stats": self.risk_stats
        }


class DecisionPerformanceEngine:
    """Core engine for recording and evaluating decisions."""
    
    def __init__(self, store=None, enabled: bool = True):
        if store is None:
            from governance.decision_store import DecisionStore
            self.store = DecisionStore()
        else:
            self.store = store
        self.enabled = enabled
        self._metrics: Optional[DecisionMetrics] = None
    
    def record_decision(
        self,
        task_id: str,
        strategy: str,
        confidence: float,
        pattern_influence: Optional[Dict[str, Any]] = None,
        expected_outcome: Optional[str] = None,
        risk_level: str = "LOW",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Record a decision before execution.
        
        Returns:
            decision_id if recording succeeded, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            decision_id = f"dec_{uuid.uuid4().hex[:12]}"
            record = DecisionRecord(
                decision_id=decision_id,
                task_id=task_id,
                selected_strategy=strategy,
                confidence_before=confidence,
                pattern_influence=pattern_influence,
                expected_outcome=expected_outcome,
                risk_level=risk_level,
                metadata=metadata or {}
            )
            self.store.add_record(record)
            return decision_id
        except Exception as e:
            logger.error(f"Failed to record decision: {e}")
            return None
    
    def evaluate_decision(
        self,
        decision_id: str,
        actual_outcome: str,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a decision after execution.
        
        Returns:
            Evaluation result or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            record = self.store.get_record(decision_id)
            if record is None:
                logger.warning(f"Decision {decision_id} not found")
                return None
            
            # Update with actual outcome
            record.actual_outcome = actual_outcome
            if duration_ms is not None:
                record.duration_ms = duration_ms
            if metadata:
                record.metadata.update(metadata)
            
            self.store.update_record(record)
            
            # Generate evaluation
            evaluation = self._evaluate_record(record)
            return evaluation
            
        except Exception as e:
            logger.error(f"Failed to evaluate decision {decision_id}: {e}")
            return None
    
    def get_metrics(self, refresh: bool = False) -> DecisionMetrics:
        """Get performance metrics."""
        if self._metrics is None or refresh:
            self._metrics = self._calculate_metrics()
        return self._metrics
    
    def get_recent_decisions(self, limit: int = 50) -> List[DecisionRecord]:
        """Get recent decisions."""
        try:
            records = self.store.get_all_records()
            return records[-limit:]
        except Exception as e:
            logger.error(f"Failed to get recent decisions: {e}")
            return []
    
    def get_decision_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """Get a decision by ID."""
        try:
            return self.store.get_record(decision_id)
        except Exception as e:
            logger.error(f"Failed to get decision {decision_id}: {e}")
            return None
    
    def _evaluate_record(self, record: DecisionRecord) -> Dict[str, Any]:
        """Evaluate a single decision record."""
        is_success = record.is_successful()
        is_accurate = record.is_accurate_prediction()
        
        # Calculate confidence accuracy
        confidence_accuracy = None
        if is_success is not None:
            # If confidence is high, success should be more likely
            # Simplified: compare confidence to success/failure
            confidence_accuracy = abs(record.confidence_before - (1.0 if is_success else 0.0))
            confidence_accuracy = 1.0 - confidence_accuracy  # Higher is better
        
        return {
            "decision_id": record.decision_id,
            "task_id": record.task_id,
            "strategy": record.selected_strategy,
            "confidence": record.confidence_before,
            "expected": record.expected_outcome,
            "actual": record.actual_outcome,
            "is_success": is_success,
            "is_accurate": is_accurate,
            "confidence_accuracy": confidence_accuracy,
            "risk_level": record.risk_level,
            "duration_ms": record.duration_ms
        }
    
    def _calculate_metrics(self) -> DecisionMetrics:
        """Calculate metrics from stored decisions."""
        metrics = DecisionMetrics()
        
        try:
            records = self.store.get_all_records()
        except Exception as e:
            logger.error(f"Failed to get records for metrics: {e}")
            return metrics
        
        for record in records:
            metrics.total_decisions += 1
            metrics.total_confidence += record.confidence_before
            
            if record.is_successful():
                metrics.successful_decisions += 1
            elif record.is_successful() is False:
                metrics.failed_decisions += 1
            
            # Prediction accuracy
            if record.expected_outcome and record.actual_outcome:
                metrics.total_predictions += 1
                if record.is_accurate_prediction():
                    metrics.accurate_predictions += 1
            
            # Strategy stats
            strategy = record.selected_strategy
            if strategy not in metrics.strategy_stats:
                metrics.strategy_stats[strategy] = {"attempts": 0, "successes": 0}
            metrics.strategy_stats[strategy]["attempts"] += 1
            if record.is_successful():
                metrics.strategy_stats[strategy]["successes"] += 1
            
            # Risk stats
            risk = record.risk_level
            if risk not in metrics.risk_stats:
                metrics.risk_stats[risk] = {"attempts": 0, "successes": 0}
            metrics.risk_stats[risk]["attempts"] += 1
            if record.is_successful():
                metrics.risk_stats[risk]["successes"] += 1
        
        return metrics
    
    def reset_metrics_cache(self) -> None:
        """Reset the metrics cache."""
        self._metrics = None
