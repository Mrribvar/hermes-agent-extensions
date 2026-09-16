"""
Governance Engine - Central coordination module for governance decisions.

Collects signals from:
- architecture_sentinel
- health_score_engine
- capability_registry
- change_detection

Produces Governance Reports with:
- issue type
- severity
- evidence
- recommendation
- action_required (manual_approval)
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class IssueType(str, Enum):
    DUPLICATE_SKILL = "duplicate_skill"
    BROKEN_DEPENDENCY = "broken_dependency"
    HEALTH_DEGRADATION = "health_degradation"
    CAPABILITY_GAP = "capability_gap"
    CONFIGURATION_ISSUE = "configuration_issue"
    SECURITY_VULNERABILITY = "security_vulnerability"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GovernanceReport:
    """Governance report for a single issue"""
    issue: str
    severity: Severity
    evidence: str
    recommendation: str
    action_required: str = "manual_approval"
    project: str = "hermes"
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue": self.issue,
            "severity": self.severity.value,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "action_required": self.action_required,
            "project": self.project,
            "timestamp": self.timestamp
        }


class GovernanceEngine:
    """Main governance coordination module"""

    def __init__(self):
        self.reports: List[GovernanceReport] = []
        self._signals = {
            "architecture_sentinel": [],
            "health_score_engine": [],
            "capability_registry": [],
            "change_detection": []
        }

    def collect_signal(self, source: str, data: Dict[str, Any]) -> None:
        """Collect signal from monitoring subsystem"""
        if source in self._signals:
            self._signals[source].append(data)

    def analyze(self) -> List[GovernanceReport]:
        """
        Analyze collected signals and generate governance reports.

        This is a placeholder implementation. Real implementation would:
        1. Parse architecture_sentinel data
        2. Check health_score_engine metrics
        3. Validate capability_registry completeness
        4. Review change_detection events
        5. Classify issues and assign severity
        6. Generate recommendations
        """
        reports = []

        # Example: Detect duplicate skills from change_detection
        if self._signals["change_detection"]:
            for change in self._signals["change_detection"]:
                if "duplicate_skill" in change.get("type", "").lower():
                    report = GovernanceReport(
                        issue=IssueType.DUPLICATE_SKILL.value,
                        severity=Severity.MEDIUM,
                        evidence=f"Change {change.get('id')}: {change.get('details')}",
                        recommendation="Archive or remove duplicate skill files. Keep one canonical version with version history.",
                        action_required="manual_approval",
                        project=change.get("project", "hermes")
                    )
                    reports.append(report)

        # Example: Health degradation from health_score_engine
        if self._signals["health_score_engine"]:
            for health_data in self._signals["health_score_engine"]:
                health = health_data.get("health_score", 0)
                if health < 70:
                    report = GovernanceReport(
                        issue=IssueType.HEALTH_DEGRADATION.value,
                        severity=Severity.HIGH if health < 50 else Severity.MEDIUM,
                        evidence=f"Health score {health}. Issues: {health_data.get('issues', [])}",
                        recommendation="Run diagnostic tools, review recent changes, and address failing components.",
                        action_required="manual_approval"
                    )
                    reports.append(report)

        self.reports = reports
        return reports

    def generate_full_report(self) -> Dict[str, Any]:
        """Generate comprehensive governance report"""
        self.analyze()

        return {
            "summary": {
                "total_issues": len(self.reports),
                "severity_distribution": {
                    "low": sum(1 for r in self.reports if r.severity == Severity.LOW),
                    "medium": sum(1 for r in self.reports if r.severity == Severity.MEDIUM),
                    "high": sum(1 for r in self.reports if r.severity == Severity.HIGH),
                    "critical": sum(1 for r in self.reports if r.severity == Severity.CRITICAL)
                },
                "projects_affected": list(set(r.project for r in self.reports))
            },
            "issues": [r.to_dict() for r in self.reports],
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate high-level recommendations from issues"""
        recommendations = []

        issues_by_project = {}
        for report in self.reports:
            if report.project not in issues_by_project:
                issues_by_project[report.project] = []
            issues_by_project[report.project].append(report)

        for project, issues in issues_by_project.items():
            high_severity = [i for i in issues if i.severity in (Severity.HIGH, Severity.CRITICAL)]
            if high_severity:
                recommendations.append(f"[{project.upper()}] Critical issues detected. Requires immediate attention.")

        return recommendations
