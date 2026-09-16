"""Intelligence Integration for Agent Execution.

ADDITIVE ONLY — Connects Phase 010 Pattern Intelligence and Phase 011
Decision Performance Intelligence into the Hermes execution pipeline.

Phase HERALD-INTELLIGENCE-012
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceContext:
    """Container for intelligence data gathered during execution."""

    pattern_guidance: Optional[Dict[str, Any]] = None
    confidence_adjustment: float = 0.0
    risk_level: str = "LOW"
    recommendations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    decision_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_guidance": self.pattern_guidance,
            "confidence_adjustment": self.confidence_adjustment,
            "risk_level": self.risk_level,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "decision_id": self.decision_id,
        }

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class IntelligenceBridge:
    """Bridge connecting intelligence layers to execution.

    ADDITIVE ONLY — Never blocks execution; all calls are wrapped in
    try/except with fail-safe fallbacks.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._pattern_adapter = None
        self._pattern_enricher = None
        self._performance_engine = None
        self._feedback_loop = None
        self._init_intelligence_components()

    def _init_intelligence_components(self) -> None:
        """Initialize intelligence components if available."""
        try:
            from governance.pattern_decision_adapter import PatternDecisionAdapter
            from governance.pattern_context import PatternContextEnricher
            from governance.decision_performance_engine import DecisionPerformanceEngine
            from governance.decision_feedback_loop import DecisionFeedbackLoop

            self._pattern_adapter = PatternDecisionAdapter()
            self._pattern_enricher = PatternContextEnricher()
            self._performance_engine = DecisionPerformanceEngine()
            self._feedback_loop = DecisionFeedbackLoop(
                engine=self._performance_engine,
            )
        except ImportError as e:
            logger.debug(f"Intelligence components not available: {e}")
            self._pattern_adapter = None
            self._pattern_enricher = None
            self._performance_engine = None
            self._feedback_loop = None

    def on_before_execution(
        self,
        task_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None,
        confidence: float = 0.5,
    ) -> IntelligenceContext:
        """Called before execution — applies pattern intelligence.

        Returns:
            IntelligenceContext with pattern guidance, confidence adjustment,
            risk assessment, and recommendations.
        """
        if not self.enabled:
            return IntelligenceContext()

        ctx = IntelligenceContext()

        try:
            if self._pattern_adapter is not None:
                guidance = self._pattern_adapter.get_recommendation_with_patterns(
                    task=task, context=context or {},
                )
                if guidance:
                    ctx.pattern_guidance = guidance
                    if isinstance(guidance, dict):
                        ctx.confidence_adjustment = guidance.get("confidence_adjustment", 0.0)
                        ctx.risk_level = guidance.get("risk_level", "LOW")
                        ctx.recommendations = guidance.get("recommendations", [])
                        ctx.warnings = guidance.get("warnings", [])
        except Exception as e:
            logger.warning(f"Pattern intelligence failed (non-blocking): {e}")

        return ctx

    def record_decision(
        self,
        task_id: str,
        strategy: str,
        confidence: float,
        pattern_guidance: Optional[Dict[str, Any]] = None,
        risk_level: str = "LOW",
        expected_outcome: Optional[str] = None,
    ) -> Optional[str]:
        """Record a decision before execution.

        Returns:
            decision_id or None if disabled/failed
        """
        if not self.enabled or self._performance_engine is None:
            return None

        try:
            return self._performance_engine.record_decision(
                task_id=task_id,
                strategy=strategy,
                confidence=confidence,
                pattern_influence=pattern_guidance,
                risk_level=risk_level,
                expected_outcome=expected_outcome,
            )
        except Exception as e:
            logger.warning(f"Decision recording failed (non-blocking): {e}")
            return None

    def evaluate_decision(
        self,
        decision_id: str,
        actual_outcome: str,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a decision after execution.

        Returns:
            Evaluation result or None if disabled/failed
        """
        if not self.enabled or self._performance_engine is None:
            return None

        try:
            return self._performance_engine.evaluate_decision(
                decision_id=decision_id,
                actual_outcome=actual_outcome,
                duration_ms=duration_ms,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Decision evaluation failed (non-blocking): {e}")
            return None

    def generate_feedback(
        self,
        decision_id: str,
        actual_outcome: str,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate feedback from a decision outcome.

        Returns:
            Feedback dict or None if disabled/failed
        """
        if not self.enabled or self._feedback_loop is None:
            return None

        try:
            feedback = self._feedback_loop.process_decision_outcome(
                decision_id=decision_id,
                actual_outcome=actual_outcome,
                duration_ms=duration_ms,
                metadata=metadata,
            )
            if feedback:
                return feedback.to_dict()
            return None
        except Exception as e:
            logger.warning(f"Feedback generation failed (non-blocking): {e}")
            return None

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from decision engine."""
        if not self.enabled or self._performance_engine is None:
            return {}

        try:
            metrics = self._performance_engine.get_metrics()
            return metrics.to_dict() if metrics else {}
        except Exception as e:
            logger.warning(f"Metrics retrieval failed (non-blocking): {e}")
            return {}


# Singleton instance
_intelligence_bridge: Optional[IntelligenceBridge] = None


def get_intelligence_bridge() -> IntelligenceBridge:
    """Get the singleton intelligence bridge instance."""
    global _intelligence_bridge
    if _intelligence_bridge is None:
        _intelligence_bridge = IntelligenceBridge()
    return _intelligence_bridge
