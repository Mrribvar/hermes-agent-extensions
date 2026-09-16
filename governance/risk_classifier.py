"""
Risk Classification System - Hermes Phase 7

Classifies any change into risk levels:
- SAFE
- LOW RISK
- MEDIUM RISK
- HIGH RISK

Rules based on change type, scope, and impact.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    LOW = "LOW_RISK"
    MEDIUM = "MEDIUM_RISK"
    HIGH = "HIGH_RISK"


@dataclass
class RiskAssessment:
    """Result of risk classification for a single change"""
    change_id: str
    change_type: str
    risk_level: RiskLevel
    reason: str
    evidence: str
    rollback_available: bool = True
    rollback_method: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "rollback_available": self.rollback_available,
            "rollback_method": self.rollback_method
        }


class RiskClassifier:
    """
    Classifies changes by risk level.

    SAFE:
    - Report generation (no code change)
    - Snapshot creation (read-only)
    - Documentation updates
    - Log rotation

    LOW RISK:
    - Duplicate archive deletion
    - Temporary file cleanup
    - Cache invalidation
    - Non-critical config tweaks

    MEDIUM RISK:
    - Skill modification
    - New skill creation
    - Plugin configuration change
    - API endpoint addition (non-core)

    HIGH RISK:
    - Core system modification
    - Database migration
    - Authentication system change
    - Permission model change
    - Data schema modification
    """

    # Rules: (risk_level, patterns_in_change_type)
    SAFE_PATTERNS = [
        "report", "snapshot", "documentation", "doc", "log", "readme",
        "changelog", "archive_report", "status_report"
    ]

    LOW_RISK_PATTERNS = [
        "duplicate", "cleanup", "cache", "temp", "tmp", "archive_delete",
        "non_critical_config", "log_rotation", "backup_cleanup"
    ]

    MEDIUM_RISK_PATTERNS = [
        "skill", "plugin", "api", "endpoint", "feature", "ui", "config",
        "workflow", "automation", "integration"
    ]

    HIGH_RISK_PATTERNS = [
        "core", "database", "migration", "auth", "permission", "schema",
        "security", "infrastructure", "deployment", "production"
    ]

    def __init__(self):
        self.assessments: List[RiskAssessment] = []

    def classify(self, change_id: str, change_type: str,
                 details: str = "", scope: str = "local") -> RiskAssessment:
        """
        Classify a single change by risk level.

        Args:
            change_id: Unique identifier for the change
            change_type: Type/category of the change
            details: Additional description
            scope: Scope of the change (local, project, system, global)

        Returns:
            RiskAssessment with classification and reasoning
        """
        change_lower = change_type.lower()
        scope_lower = scope.lower()

        # Scope multiplier: system/global changes are riskier
        scope_multiplier = 1
        if scope_lower in ("system", "global"):
            scope_multiplier = 2

        # Check patterns in priority order (high to low)
        risk_level = self._check_patterns(change_lower, scope_multiplier)

        # Additional check: scope alone can elevate risk
        if scope_lower == "global" and risk_level.value in (RiskLevel.SAFE.value, RiskLevel.LOW.value):
            risk_level = RiskLevel.MEDIUM

        assessment = RiskAssessment(
            change_id=change_id,
            change_type=change_type,
            risk_level=risk_level,
            reason=self._generate_reason(risk_level, change_type, scope),
            evidence=details or f"Change type: {change_type}, Scope: {scope}",
            rollback_available=self._rollback_available(risk_level),
            rollback_method=self._rollback_method(risk_level)
        )

        self.assessments.append(assessment)
        return assessment

    def _check_patterns(self, change_lower: str, multiplier: int) -> RiskLevel:
        """Check change type against risk patterns"""
        # Check HIGH first
        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern in change_lower:
                return RiskLevel.HIGH

        # Check MEDIUM
        for pattern in self.MEDIUM_RISK_PATTERNS:
            if pattern in change_lower:
                if multiplier >= 2:
                    return RiskLevel.HIGH
                return RiskLevel.MEDIUM

        # Check LOW
        for pattern in self.LOW_RISK_PATTERNS:
            if pattern in change_lower:
                return RiskLevel.LOW

        # Check SAFE
        for pattern in self.SAFE_PATTERNS:
            if pattern in change_lower:
                return RiskLevel.SAFE

        # Default: MEDIUM for unknown types
        return RiskLevel.MEDIUM

    def _generate_reason(self, risk: RiskLevel, change_type: str, scope: str) -> str:
        """Generate human-readable reason for classification"""
        reasons = {
            RiskLevel.SAFE: f"Change '{change_type}' is read-only or documentation-level. No code or data modification.",
            RiskLevel.LOW: f"Change '{change_type}' affects non-critical resources. Cleanup or archive operation.",
            RiskLevel.MEDIUM: f"Change '{change_type}' modifies application behavior or capabilities. Requires review.",
            RiskLevel.HIGH: f"Change '{change_type}' at {scope} scope affects core system integrity. Requires approval."
        }
        return reasons.get(risk, f"Change '{change_type}' classified as {risk.value}")

    def _rollback_available(self, risk: RiskLevel) -> bool:
        """Determine if rollback is available for this risk level"""
        return risk.value != RiskLevel.HIGH.value  # HIGH risk may not have clean rollback

    def _rollback_method(self, risk: RiskLevel) -> str:
        """Return rollback method for risk level"""
        methods = {
            RiskLevel.SAFE: "No rollback needed (read-only operation)",
            RiskLevel.LOW: "Restore from backup or recreate file",
            RiskLevel.MEDIUM: "Revert skill/plugin config to previous version",
            RiskLevel.HIGH: "Database restore from snapshot + manual intervention"
        }
        return methods.get(risk, "Manual rollback required")

    def classify_batch(self, changes: List[Dict[str, Any]]) -> List[RiskAssessment]:
        """Classify multiple changes at once"""
        results = []
        for change in changes:
            assessment = self.classify(
                change_id=change.get("id", "unknown"),
                change_type=change.get("type", "unknown"),
                details=change.get("details", ""),
                scope=change.get("scope", "local")
            )
            results.append(assessment)
        return results

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of all assessments"""
        summary = {
            "total_assessed": len(self.assessments),
            "by_level": {
                RiskLevel.SAFE.value: 0,
                RiskLevel.LOW.value: 0,
                RiskLevel.MEDIUM.value: 0,
                RiskLevel.HIGH.value: 0
            }
        }
        for a in self.assessments:
            summary["by_level"][a.risk_level.value] += 1

        return summary