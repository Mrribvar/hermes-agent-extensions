"""Governance Integration — Hermes Execution Layer.

Before every execution:
  1. Risk Evaluation
  2. Permission Validation
  3. Approval Check
  4. Decision Registration
  5. Execution Logging

No execution may bypass Governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class GovernanceVerdict(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class GovernanceDecision:
    """Result of governance pre-execution check."""
    verdict: GovernanceVerdict
    execution_id: str
    risk_level: str
    reasons: List[str] = field(default_factory=list)
    approval_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "execution_id": self.execution_id,
            "risk_level": self.risk_level,
            "reasons": list(self.reasons),
            "approval_id": self.approval_id,
            "timestamp": self.timestamp,
        }


class GovernanceGate:
    """Gate that every execution must pass before running.

    Hooks (callables) are injected so the gate stays provider/tool
    independent.  If a hook raises, the gate denies — fail closed.
    """

    def __init__(self):
        self._risk_evaluator: Optional[Callable[[Dict[str, Any]], str]] = None
        self._permission_validator: Optional[Callable[[Dict[str, Any]], bool]] = None
        self._approval_checker: Optional[Callable[[Dict[str, Any]], GovernanceVerdict]] = None
        self._decision_registrar: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None
        self._log_handler: Optional[Callable[[Dict[str, Any]], None]] = None

    # --- hook injection ---

    def set_risk_evaluator(self, fn: Callable[[Dict[str, Any]], str]) -> None:
        """fn(context_dict) -> risk_level string."""
        self._risk_evaluator = fn

    def set_permission_validator(self, fn: Callable[[Dict[str, Any]], bool]) -> None:
        """fn(context_dict) -> bool (True = permitted)."""
        self._permission_validator = fn

    def set_approval_checker(self, fn: Callable[[Dict[str, Any]], GovernanceVerdict]) -> None:
        """fn(context_dict) -> GovernanceVerdict."""
        self._approval_checker = fn

    def set_decision_registrar(self, fn: Callable[[Dict[str, Any]], Optional[str]]) -> None:
        """fn(context_dict) -> approval_id or None."""
        self._decision_registrar = fn

    def set_log_handler(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        """fn(governance_decision_dict)."""
        self._log_handler = fn

    # --- gate ---

    def evaluate(self, execution_id: str, context: Dict[str, Any]) -> GovernanceDecision:
        """Run the full governance pipeline for one execution.

        Fail-closed: any hook error or denial blocks execution.
        """
        reasons: List[str] = []
        risk_level = "low"

        # 1. Risk evaluation
        try:
            if self._risk_evaluator:
                risk_level = self._risk_evaluator(context) or "low"
        except Exception as e:
            return self._deny(execution_id, risk_level, [f"risk evaluation error: {e}"])

        # 2. Permission validation
        try:
            if self._permission_validator and not self._permission_validator(context):
                return self._deny(execution_id, risk_level, ["permission denied"])
        except Exception as e:
            return self._deny(execution_id, risk_level, [f"permission error: {e}"])

        # 3. Approval check
        verdict = GovernanceVerdict.APPROVED
        approval_id = ""
        try:
            if self._approval_checker:
                verdict = self._approval_checker(context)
        except Exception as e:
            return self._deny(execution_id, risk_level, [f"approval check error: {e}"])

        if verdict == GovernanceVerdict.DENIED:
            return self._deny(execution_id, risk_level, ["governance denied"])

        # 4. Decision registration (if approved)
        try:
            if self._decision_registrar and verdict == GovernanceVerdict.APPROVED:
                approval_id = self._decision_registrar(context) or ""
        except Exception as e:
            return self._deny(execution_id, risk_level, [f"decision registration error: {e}"])

        decision = GovernanceDecision(
            verdict=verdict,
            execution_id=execution_id,
            risk_level=risk_level,
            reasons=reasons,
            approval_id=approval_id,
        )

        # 5. Logging
        if self._log_handler:
            try:
                self._log_handler(decision.to_dict())
            except Exception:
                pass

        return decision

    def _deny(self, execution_id: str, risk_level: str, reasons: List[str]) -> GovernanceDecision:
        decision = GovernanceDecision(
            verdict=GovernanceVerdict.DENIED,
            execution_id=execution_id,
            risk_level=risk_level,
            reasons=reasons,
        )
        if self._log_handler:
            try:
                self._log_handler(decision.to_dict())
            except Exception:
                pass
        return decision
