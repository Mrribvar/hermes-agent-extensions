"""Pattern Intelligence Configuration.

Controls the behavior of Pattern Intelligence in decision-making.
All settings are advisory and never break core execution.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class PatternConfig:
    """Configuration for Pattern Intelligence integration."""
    
    # Master enable/disable
    enabled: bool = True
    
    # Feature-specific enables
    enable_confidence_adjustment: bool = True
    enable_risk_detection: bool = True
    enable_recommendations: bool = True
    enable_warnings: bool = True
    enable_strategy_scoring: bool = True
    
    # Safety settings
    fail_safe_mode: bool = True
    log_failures: bool = True
    
    # Bounds
    max_confidence_adjustment: float = 0.2  # -0.2 to 0.2
    min_pattern_confidence: float = 0.60
    min_evidence_count: int = 3
    
    # Risk thresholds
    risk_medium_threshold: int = 1  # 1+ failure patterns -> MEDIUM
    risk_high_threshold: int = 3    # 3+ failure patterns -> HIGH
    
    # Behavior
    never_block_execution: bool = True
    inject_guidance_as_metadata: bool = True
    
    # Storage
    store_enhanced_contexts: bool = False
    store_risk_assessments: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "enable_confidence_adjustment": self.enable_confidence_adjustment,
            "enable_risk_detection": self.enable_risk_detection,
            "enable_recommendations": self.enable_recommendations,
            "enable_warnings": self.enable_warnings,
            "enable_strategy_scoring": self.enable_strategy_scoring,
            "fail_safe_mode": self.fail_safe_mode,
            "log_failures": self.log_failures,
            "max_confidence_adjustment": self.max_confidence_adjustment,
            "min_pattern_confidence": self.min_pattern_confidence,
            "min_evidence_count": self.min_evidence_count,
            "risk_medium_threshold": self.risk_medium_threshold,
            "risk_high_threshold": self.risk_high_threshold,
            "never_block_execution": self.never_block_execution,
            "inject_guidance_as_metadata": self.inject_guidance_as_metadata,
            "store_enhanced_contexts": self.store_enhanced_contexts,
            "store_risk_assessments": self.store_risk_assessments
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PatternConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            enable_confidence_adjustment=data.get("enable_confidence_adjustment", True),
            enable_risk_detection=data.get("enable_risk_detection", True),
            enable_recommendations=data.get("enable_recommendations", True),
            enable_warnings=data.get("enable_warnings", True),
            enable_strategy_scoring=data.get("enable_strategy_scoring", True),
            fail_safe_mode=data.get("fail_safe_mode", True),
            log_failures=data.get("log_failures", True),
            max_confidence_adjustment=data.get("max_confidence_adjustment", 0.2),
            min_pattern_confidence=data.get("min_pattern_confidence", 0.60),
            min_evidence_count=data.get("min_evidence_count", 3),
            risk_medium_threshold=data.get("risk_medium_threshold", 1),
            risk_high_threshold=data.get("risk_high_threshold", 3),
            never_block_execution=data.get("never_block_execution", True),
            inject_guidance_as_metadata=data.get("inject_guidance_as_metadata", True),
            store_enhanced_contexts=data.get("store_enhanced_contexts", False),
            store_risk_assessments=data.get("store_risk_assessments", True)
        )
    
    def get_risk_level(self, failure_pattern_count: int) -> str:
        """Calculate risk level from failure pattern count."""
        if failure_pattern_count >= self.risk_high_threshold:
            return "HIGH"
        elif failure_pattern_count >= self.risk_medium_threshold:
            return "MEDIUM"
        else:
            return "LOW"
    
    def is_safe_for_execution(self, risk_level: str) -> bool:
        """Check if execution is safe for a risk level."""
        # Never block execution regardless of risk
        return True
    
    def get_confidence_adjustment_bound(self, adjustment: float) -> float:
        """Bound confidence adjustment."""
        return max(-self.max_confidence_adjustment, 
                   min(self.max_confidence_adjustment, adjustment))


# Singleton instance
_default_config: Optional[PatternConfig] = None


def get_pattern_config() -> PatternConfig:
    """Get the default pattern configuration."""
    global _default_config
    if _default_config is None:
        _default_config = PatternConfig()
    return _default_config


def reset_pattern_config() -> None:
    """Reset the default pattern configuration."""
    global _default_config
    _default_config = PatternConfig()
