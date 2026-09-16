# Phase 13.2.4 — Governance Integration Adapter.
#
# No governance built here. This adapter maps business actions to the risk /
# decision model that the (existing) governance system would apply.
#
# Required scenarios (from spec):
#   CREATE_PRODUCT  -> LOW    / ALLOW
#   UPDATE_PRICE    -> HIGH   / REQUIRE_APPROVAL
#   DELETE_PRODUCT  -> CRITICAL / BLOCK
#
# Additive only. Uses an internal mapping; does not touch governance/*.
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

from agent.business.events.event import RiskLevel


class GovernanceDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class GovernanceVerdict:
    action: str
    risk: RiskLevel
    decision: GovernanceDecision
    reason: str


def _risk_level(value: str):
    try:
        return RiskLevel(value.upper())
    except ValueError:
        return RiskLevel.LOW


class GovernanceAdapter:
    """Single source of truth for business-action risk/decision mapping."""

    # action -> (risk_level, decision)
    _MAP: Dict[str, tuple] = {
        "CREATE_PRODUCT": (RiskLevel.LOW, GovernanceDecision.ALLOW),
        "PRODUCT_CREATED": (RiskLevel.LOW, GovernanceDecision.ALLOW),
        "UPDATE_PRICE": (RiskLevel.HIGH, GovernanceDecision.REQUIRE_APPROVAL),
        "PRODUCT_PRICE_CHANGED": (RiskLevel.HIGH, GovernanceDecision.REQUIRE_APPROVAL),
        "DELETE_PRODUCT": (RiskLevel.CRITICAL, GovernanceDecision.BLOCK),
        "PRODUCT_DELETED": (RiskLevel.CRITICAL, GovernanceDecision.BLOCK),
        "CATEGORY_CREATED": (RiskLevel.LOW, GovernanceDecision.ALLOW),
        "CUSTOMER_CREATED": (RiskLevel.LOW, GovernanceDecision.ALLOW),
        "PRODUCT_UPDATED": (RiskLevel.MEDIUM, GovernanceDecision.REQUIRE_APPROVAL),
    }

    DEFAULT_RISK = RiskLevel.LOW
    DEFAULT_DECISION = GovernanceDecision.ALLOW

    def evaluate(self, action: str, actor: str = "system") -> GovernanceVerdict:
        """Return the governance verdict for a business action."""
        key = (action or "").strip().upper()
        risk, decision = self._MAP.get(key, (self.DEFAULT_RISK, self.DEFAULT_DECISION))
        reason = (
            f"risk={risk.value}, decision={decision.value} for action '{key}' by '{actor}'"
        )
        return GovernanceVerdict(
            action=key,
            risk=risk,
            decision=decision,
            reason=reason,
        )

    def risk_of(self, event_type: str) -> RiskLevel:
        return self.evaluate(event_type or "").risk

    def decision_of(self, event_type: str) -> GovernanceDecision:
        return self.evaluate(event_type or "").decision

    def known_actions(self) -> List[str]:
        return sorted(self._MAP.keys())


__all__ = ["GovernanceAdapter", "GovernanceDecision", "GovernanceVerdict"]