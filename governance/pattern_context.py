"""Pattern Context — enriched decision context with pattern intelligence.

Provides structured pattern insights for decision-making systems.
All methods are advisory only and never modify core logic.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class PatternDecisionContext:
    """Decision context enriched with pattern intelligence.
    
    This is advisory only — never modifies core decision logic.
    """
    task_id: str
    matched_patterns: List[Dict[str, Any]] = field(default_factory=list)
    confidence_adjustment: float = 0.0
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pattern_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "matched_patterns": self.matched_patterns,
            "confidence_adjustment": self.confidence_adjustment,
            "risk_level": self.risk_level,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "pattern_count": self.pattern_count,
            "timestamp": self.timestamp
        }
    
    def has_risk(self) -> bool:
        """Check if risk level is MEDIUM or HIGH."""
        return self.risk_level in ["MEDIUM", "HIGH"]
    
    def has_high_risk(self) -> bool:
        """Check if risk level is HIGH."""
        return self.risk_level == "HIGH"
    
    def has_recommendation(self) -> bool:
        """Check if there are recommendations."""
        return len(self.recommendations) > 0
    
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0
    
    def get_primary_recommendation(self) -> Optional[str]:
        """Get the first recommendation if available."""
        return self.recommendations[0] if self.recommendations else None
    
    def get_primary_warning(self) -> Optional[str]:
        """Get the first warning if available."""
        return self.warnings[0] if self.warnings else None
    
    @classmethod
    def from_dict(cls, data: dict) -> "PatternDecisionContext":
        """Create from dictionary."""
        return cls(
            task_id=data.get("task_id", "unknown"),
            matched_patterns=data.get("matched_patterns", []),
            confidence_adjustment=data.get("confidence_adjustment", 0.0),
            risk_level=data.get("risk_level", "LOW"),
            recommendations=data.get("recommendations", []),
            warnings=data.get("warnings", []),
            pattern_count=data.get("pattern_count", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class PatternContextEnricher:
    """Enriches decision contexts with pattern intelligence.
    
    Uses PatternDecisionAdapter to add pattern insights to contexts.
    All methods are fail-safe and non-blocking.
    """
    
    def __init__(self, adapter=None, config=None, enabled: bool = True):
        if adapter is None:
            from governance.pattern_decision_adapter import PatternDecisionAdapter
            self.adapter = PatternDecisionAdapter()
        else:
            self.adapter = adapter
        
        if config is None:
            from governance.pattern_config import PatternConfig
            self.config = PatternConfig()
        else:
            self.config = config
        
        self.enabled = enabled
    
    def enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a decision context with pattern intelligence.
        
        Args:
            context: Original decision context
            
        Returns:
            Enriched context with pattern intelligence
        """
        if not self.enabled or not self.config.enabled:
            return context
        
        try:
            # Get pattern guidance
            guidance = self.adapter.get_pattern_guidance(context)
            
            # Create enhanced copy
            enhanced = dict(context)
            
            # Add pattern intelligence
            pattern_context = PatternDecisionContext(
                task_id=guidance.task_id,
                matched_patterns=guidance.matched_patterns,
                confidence_adjustment=guidance.confidence_adjustment,
                risk_level=guidance.risk_level,
                recommendations=guidance.recommendations,
                warnings=guidance.warnings,
                pattern_count=guidance.pattern_count
            )
            
            enhanced["pattern_context"] = pattern_context
            
            # Apply confidence adjustment if enabled
            if self.config.enable_confidence_adjustment and "confidence" in enhanced:
                adj = guidance.confidence_adjustment
                max_adj = self.config.max_confidence_adjustment
                adj = max(-max_adj, min(max_adj, adj))
                enhanced["confidence"] = min(
                    1.0,
                    max(0.0, enhanced["confidence"] + adj)
                )
            
            # Add risk level if enabled
            if self.config.enable_risk_detection:
                enhanced["risk_level"] = guidance.risk_level
            
            # Add warnings if enabled
            if self.config.enable_recommendations and guidance.warnings:
                enhanced["warnings"] = enhanced.get("warnings", []) + guidance.warnings[:2]
            
            return enhanced
            
        except Exception as e:
            # Fail-safe: return original context
            import logging
            logging.getLogger(__name__).error(f"Pattern enrichment failed: {e}")
            return context
    
    def enrich_strategy(
        self,
        strategy: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich a strategy with pattern intelligence."""
        if not self.enabled or not self.config.enabled:
            return strategy
        
        try:
            evaluation = self.adapter.evaluate_strategy(strategy, context)
            
            enhanced = dict(strategy)
            
            if self.config.enable_confidence_adjustment:
                enhanced["pattern_score"] = evaluation.pattern_score
            
            if self.config.enable_recommendations:
                enhanced["is_recommended"] = evaluation.is_recommended
                enhanced["is_risky"] = evaluation.is_risky
                
                if evaluation.warnings:
                    enhanced["warnings"] = enhanced.get("warnings", []) + evaluation.warnings
            
            return enhanced
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Strategy enrichment failed: {e}")
            return strategy
    
    def get_risk_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get risk assessment for a context."""
        if not self.enabled or not self.config.enabled:
            return {"risk_level": "LOW", "warnings": []}
        
        try:
            guidance = self.adapter.get_pattern_guidance(context)
            return {
                "risk_level": guidance.risk_level,
                "warnings": guidance.warnings,
                "pattern_count": guidance.pattern_count
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Risk assessment failed: {e}")
            return {"risk_level": "LOW", "warnings": []}
    
    def is_enabled(self) -> bool:
        """Check if enrichment is enabled."""
        return self.enabled and self.config.enabled
