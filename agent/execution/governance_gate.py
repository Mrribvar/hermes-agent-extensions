# Execution Layer — Phase 11.5: Governance Gate
#
# Connects the Execution Layer with Hermes Governance before RUNNING.
# Governance remains the authority; this gate is a thin adapter over existing
# governance modules (RiskClassifier, ApprovalWorkflow, DecisionMemory).
#
# No duplication of governance logic. No Tool Orchestrator / Execution Memory /
# Recovery yet.
#
# Existing modules reused:
#   governance/risk_classifier.py   -> RiskClassifier, RiskAssessment
#   governance/approval_workflow.py -> ApprovalWorkflow, ApprovalRequest
#   governance/decision_memory.py   -> DecisionMemory

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Dict

from .context import ExecutionContext
from .workflow import ExecutionState, ExecutionStateMachine, InvalidTransitionError

try:  # real governance modules when available
    from governance.risk_classifier import RiskClassifier, RiskLevel
    from governance.approval_workflow import ApprovalWorkflow, ApprovalStatus
    from governance.decision_memory import DecisionMemory
    _HAVE_GOVERNANCE = True
except Exception:  # pragma: no cover - graceful if governance not importable
    RiskClassifier = None  # type: ignore
    RiskLevel = None
    ApprovalWorkflow = None
    ApprovalStatus = None
    DecisionMemory = None
    _HAVE_GOVERNANCE = False

__all__ = [
    "GovernanceVerdict",
    "GovernanceResult",
    "GovernanceGate",
]


class GovernanceVerdict(str, Enum):
    """Authority verdict returned to the Execution Engine."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_APPROVAL = "requires_approval"
    FAILED_VALIDATION = "failed_validation"


@dataclass(frozen=True)
class GovernanceResult:
    """Full verdict object carrying a decision and supporting evidence."""

    verdict: GovernanceVerdict
    reason: str
    risk_level: str = "SAFE"
    change_type: Optional[str] = None
    scope: Optional[str] = None
    approval_request_id: Optional[str] = None
    recorded_decision_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.verdict == GovernanceVerdict.APPROVED


@dataclass
class GovernanceGate:
    """Evaluates an ExecutionContext and returns an execution verdict.

    Flow:
      context -> risk classifier -> (approval when high risk) -> verdict

    Governance remains the authority: this gate never makes policy decisions
    itself; it maps context to existing governance signals and surfaces the
    resulting verdict. All logic lives in the governance.* modules.
    """

    risk_classifier: Optional[Any] = None
    approval_workflow: Optional[Any] = None
    decision_memory: Optional[Any] = None
    # Risk levels that require an approval stop (governance blocks RUNNING).
    require_approval_levels: tuple = field(
        default_factory=lambda: ("MEDIUM_RISK",)
    )
    # Risk levels that are auto-approved (never gated).
    auto_approve_levels: tuple = field(
        default_factory=lambda: ("SAFE", "LOW_RISK")
    )
    # Risk levels that are hard-rejected without rollback evidence.
    reject_levels: tuple = field(
        default_factory=lambda: ("HIGH_RISK",)
    )

    def __post_init__(self) -> None:
        # Build real governance adapters if not injected.
        if self.risk_classifier is None and RiskClassifier is not None:
            self.risk_classifier = RiskClassifier()
        if self.approval_workflow is None and ApprovalWorkflow is not None:
            self.approval_workflow = ApprovalWorkflow()
        if self.decision_memory is None and DecisionMemory is not None:
            # DecisionMemory requires a storage_path.
            try:
                self.decision_memory = DecisionMemory(storage_path=":memory:")
            except Exception:
                self.decision_memory = None

    def evaluate(self, ctx: ExecutionContext) -> GovernanceResult:
        """Evaluate the context and return a verdict.

        Verdicts:
          APPROVED          - safe/low risk, RUNNING allowed.
          REQUIRES_APPROVAL - medium/high risk; engine must NOT run until
                              an ApprovalRequest is approved.
          REJECTED          - governance hard-rejected the change.
          FAILED_VALIDATION - could not evaluate (missing signal / classifier
                              unavailable).
        """
        # 1) Context structural validation is upstream (ExecutionContext is
        #    already validated at creation). Here we validate risk signal
        #    presence instead.
        if not ctx or not getattr(ctx, "execution_id", None):
            return GovernanceResult(
                verdict=GovernanceVerdict.FAILED_VALIDATION,
                reason="no valid ExecutionContext",
            )

        # 2) No governance adapters present -> cannot gate safely; default to
        #    approval-required so we never bypass the authority silently.
        if self.risk_classifier is None:
            return GovernanceResult(
                verdict=GovernanceVerdict.REQUIRES_APPROVAL,
                reason="governance unavailable; blocking until review",
            )

        # 3) Classify risk via RiskClassifier (real governance logic).
        change_id = ctx.execution_id
        change_type = (
            ctx.tool_id if ctx.tool_id else ctx.metadata.get("change_type", "code_change")
        )
        scope = ctx.metadata.get("scope", "unknown")
        details = {
            "task_id": ctx.task_id,
            "project_id": ctx.project_id,
            "parameters": ctx.parameters,
        }
        try:
            assessment = self.risk_classifier.classify(
                change_id=change_id,
                change_type=change_type,
                details=details,
                scope=scope,
            )
        except Exception as e:
            return GovernanceResult(
                verdict=GovernanceVerdict.FAILED_VALIDATION,
                reason=f"risk classification failed: {e}",
            )

        risk_val = getattr(assessment, "risk_level", "")
        risk_name = risk_val if isinstance(risk_val, str) else getattr(risk_val, "value", "SAFE")

        # 3) policy decision (governance authority).
        if risk_name in self.auto_approve_levels:
            return GovernanceResult(
                verdict=GovernanceVerdict.APPROVED,
                reason=f"risk {risk_name} auto-approved",
                risk_level=risk_name,
                change_type=change_type,
                scope=scope,
            )

        if risk_name in self.require_approval_levels:
            req_id = None
            if self.approval_workflow is not None:
                try:
                    req = self.approval_workflow.propose(
                        operation=change_type,
                        reason="execution requires governance approval",
                        evidence=str(details),
                        risk_level=risk_name,
                        rollback_plan=ctx.metadata.get("rollback_plan", ""),
                        metadata={"execution_id": ctx.execution_id},
                    )
                    req_id = getattr(req, "request_id", None)
                except Exception:
                    req_id = None
            return GovernanceResult(
                verdict=GovernanceVerdict.REQUIRES_APPROVAL,
                reason=f"risk {risk_name} requires approval",
                risk_level=risk_name,
                change_type=change_type,
                scope=scope,
                approval_request_id=req_id,
            )

        # HIGH (reject_levels) -> hard reject (no evidence of rollback safety).
        if risk_name in self.reject_levels:
            return GovernanceResult(
                verdict=GovernanceVerdict.REJECTED,
                reason=f"risk {risk_name} rejected without rollback",
                risk_level=risk_name,
                change_type=change_type,
                scope=scope,
            )

        # Unknown risk level -> block (conservative fail-closed).
        return GovernanceResult(
            verdict=GovernanceVerdict.REQUIRES_APPROVAL,
            reason=f"unknown risk {risk_name}; blocking until review",
            risk_level=risk_name,
            change_type=change_type,
            scope=scope,
        )

    # -- approval helpers -------------------------------------------------

    def check_approval_status(self, request_id: str) -> Optional[str]:
        """Return 'pending'|'approved'|'rejected'|None via ApprovalWorkflow."""
        if self.approval_workflow is None:
            return None
        try:
            req = self.approval_workflow.get_status(request_id)
            if req is None:
                return None
            return getattr(getattr(req, "status", None), "value", str(req.status))
        except Exception:
            return None

    def record_decision(self, result: GovernanceResult, outcome: str) -> None:
        """Persist a decision to DecisionMemory if available."""
        if self.decision_memory is None:
            return
        try:
            self.decision_memory.record(
                decision=result.reason,
                reason=result.reason,
                impact=result.scope or "",
                rollback=result.change_type or "",
                result=outcome,
                metadata={"execution_id": result.metadata.get("execution_id", "")},
            )
        except Exception:
            pass