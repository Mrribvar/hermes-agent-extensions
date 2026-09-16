"""
Approval Workflow System - Hermes Phase 7

Before any operation, Hermes presents:
- Reason
- Evidence
- Risk
- Rollback plan

Waits for: APPROVE | REJECT
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """A single approval request for an operation"""
    request_id: str
    operation: str
    reason: str
    evidence: str
    risk_level: str
    rollback_plan: str
    requester: str = "hermes"
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "reason": self.reason,
            "evidence": self.evidence,
            "risk_level": self.risk_level,
            "rollback_plan": self.rollback_plan,
            "requester": self.requester,
            "status": self.status.value,
            "created_at": self.created_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
            "metadata": self.metadata
        }


class ApprovalWorkflow:
    """
    Approval workflow system.

    Flow:
    1. Hermes proposes a change (create ApprovalRequest)
    2. System displays: Reason, Evidence, Risk, Rollback
    3. Waits for user decision: APPROVE or REJECT
    4. Decision is recorded in decision_memory
    5. If approved, operation proceeds
    6. If rejected, operation is blocked
    """

    def __init__(self):
        self.requests: Dict[str, ApprovalRequest] = {}
        self.approval_callbacks: Dict[str, Callable] = {}

    def propose(self, operation: str, reason: str, evidence: str,
                risk_level: str, rollback_plan: str,
                metadata: Dict[str, Any] = None) -> ApprovalRequest:
        """
        Create a new approval request.

        Hermes calls this before any operation it wants to perform.
        Returns the request (status=PENDING) and displays the proposal.
        """
        import uuid
        request_id = f"approval_{uuid.uuid4().hex[:8]}"

        request = ApprovalRequest(
            request_id=request_id,
            operation=operation,
            reason=reason,
            evidence=evidence,
            risk_level=risk_level,
            rollback_plan=rollback_plan,
            metadata=metadata or {}
        )

        self.requests[request_id] = request

        # Display the proposal (Hermes speaks)
        self._display_proposal(request)

        return request

    def approve(self, request_id: str, approver: str = "user") -> bool:
        """Approve a pending request"""
        if request_id not in self.requests:
            raise ValueError(f"Request {request_id} not found")

        request = self.requests[request_id]
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} already {request.status.value}")

        request.status = ApprovalStatus.APPROVED
        request.approved_by = approver
        request.approved_at = datetime.now().isoformat()

        return True

    def reject(self, request_id: str, reason: str = "") -> bool:
        """Reject a pending request"""
        if request_id not in self.requests:
            raise ValueError(f"Request {request_id} not found")

        request = self.requests[request_id]
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} already {request.status.value}")

        request.status = ApprovalStatus.REJECTED
        request.rejection_reason = reason or "User rejected"

        return True

    def get_status(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get status of a specific request"""
        return self.requests.get(request_id)

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending requests"""
        return [r for r in self.requests.values() if r.status == ApprovalStatus.PENDING]

    def _display_proposal(self, request: ApprovalRequest) -> None:
        """Display the proposal to the user (Hermes speaks)"""
        print(f"""
{'='*60}
HERMES: من این تغییر را پیشنهاد می‌کند
{'='*60}
Operation: {request.operation}
Request ID: {request.request_id}

Reason:
  {request.reason}

Evidence:
  {request.evidence}

Risk: {request.risk_level}

Rollback:
  {request.rollback_plan}

Awaiting your decision:
  APPROVE - Execute this operation
  REJECT  - Block this operation
{'='*60}
""")

    def display_all_pending(self) -> None:
        """Display all pending requests for batch review"""
        pending = self.get_pending_requests()
        if not pending:
            print("No pending approval requests.")
            return

        print(f"\n{'='*60}")
        print(f"PENDING APPROVALS: {len(pending)}")
        print(f"{'='*60}")

        for req in pending:
            self._display_proposal(req)