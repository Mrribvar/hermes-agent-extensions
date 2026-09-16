"""Execution Recovery — Phase 11.8: detect interrupted executions and restore state.

Detects incomplete executions via ExecutionMemory, rebuilds execution
context, and provides recovery recommendations. Recovery NEVER executes
tasks automatically — it only restores state and plans recovery.

Architecture:
    ExecutionMemory  -> detect incomplete records
    ExecutionRecovery -> plan recovery (RESUME/RETRY/ROLLBACK/CANCEL/MANUAL_REVIEW)
    ExecutionEngine  -> can execute recovery plan (separate step, not here)

Rules:
    - Governance remains authority (no bypass)
    - No automatic execution
    - No modification to existing memory systems
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionRecovery",
    "RecoveryAction",
    "RecoveryPlan",
    "RecoveryError",
]


class RecoveryAction(str, Enum):
    """Recovery recommendation — each maps to a specific remediation."""
    RESUME = "resume"
    RETRY = "retry"
    ROLLBACK = "rollback"
    CANCEL = "cancel"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class RecoveryPlan:
    """Immutable recovery plan for a single interrupted execution."""
    execution_id: str
    state: str
    action: RecoveryAction
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    original_state: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "state": self.state,
            "action": self.action.value,
            "reason": self.reason,
            "details": dict(self.details),
            "original_state": self.original_state,
            "created_at": self.created_at,
        }


class RecoveryError(Exception):
    """Raised when recovery operations fail."""
    pass


@dataclass
class ExecutionRecovery:
    """Detects interrupted executions and provides recovery recommendations.

    Never executes tasks. Governance remains the authority for any
    recovery action that involves re-running execution.
    """
    memory: Any = None  # ExecutionMemory (Phase 11.7)

    def find_interrupted(self) -> List[Dict[str, Any]]:
        """Find all executions in non-terminal states.

        Scans ExecutionMemory for RUNNING, PENDING_APPROVAL, PAUSED
        states which indicate interrupted executions.
        """
        if self.memory is None:
            return []

        non_terminal_states = {"RUNNING", "PENDING_APPROVAL", "PAUSED"}
        interrupted: List[Dict[str, Any]] = []

        try:
            # Scan by state index
            conn = self.memory._connect()
            try:
                for state in non_terminal_states:
                    rows = conn.execute(
                        "SELECT * FROM execution_records WHERE state = ?",
                        (state,),
                    ).fetchall()
                    for row in rows:
                        interrupted.append(dict(row))
            finally:
                conn.close()
        except Exception as e:
            logger.warning("find_interrupted failed: %s", e)

        return interrupted

    def recover_execution(self, execution_id: str) -> Optional[RecoveryPlan]:
        """Build a recovery plan for a specific interrupted execution.

        Does NOT execute — only plans. Returns None if execution is
        terminal (COMPLETED/FAILED/CANCELLED) or not found.
        """
        if self.memory is None:
            raise RecoveryError("no memory configured")

        rec = self.memory.get_execution(execution_id)
        if rec is None:
            raise RecoveryError(f"execution '{execution_id}' not found")

        state = rec.state

        # Terminal states — nothing to recover
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            return None

        # Choose recovery action based on state
        if state == "RUNNING":
            return RecoveryPlan(
                execution_id=execution_id,
                state=state,
                action=RecoveryAction.RESUME,
                reason="execution was running when interrupted; safe to resume",
                original_state=state,
                details={"error_message": rec.error_message or ""},
            )

        if state == "PENDING_APPROVAL":
            return RecoveryPlan(
                execution_id=execution_id,
                state=state,
                action=RecoveryAction.MANUAL_REVIEW,
                reason="approval expired; requires manual governance review",
                original_state=state,
                details={"governance_verdict": rec.governance_verdict or ""},
            )

        if state == "PAUSED":
            return RecoveryPlan(
                execution_id=execution_id,
                state=state,
                action=RecoveryAction.RETRY,
                reason="execution was paused; may retry with fresh governance check",
                original_state=state,
                details={},
            )

        # Unknown state — conservative
        return RecoveryPlan(
            execution_id=execution_id,
            state=state,
            action=RecoveryAction.MANUAL_REVIEW,
            reason=f"unrecognized state '{state}'; requires manual review",
            original_state=state,
        )

    def rebuild_context(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Rebuild execution context snapshot from memory.

        Returns a dict of context fields that can be used to create
        a new ExecutionContext for recovery execution.
        """
        if self.memory is None:
            return None

        rec = self.memory.get_execution(execution_id)
        if rec is None:
            return None

        return {
            "execution_id": rec.execution_id,
            "task_id": rec.task_id,
            "session_id": rec.session_id,
            "user_id": rec.user_id,
            "project_id": rec.project_id,
            "tool_id": rec.tool_id,
            "state": rec.state,
            "governance_verdict": rec.governance_verdict,
            "metadata": rec.metadata,
        }

    def get_recovery_plan(self, execution_id: str) -> RecoveryPlan:
        """Convenience wrapper: plan + rebuild context in one call.

        Raises RecoveryError if execution not found or memory unavailable.
        """
        plan = self.recover_execution(execution_id)
        if plan is None:
            raise RecoveryError(
                f"execution '{execution_id}' is terminal or not found"
            )

        ctx = self.rebuild_context(execution_id)
        return RecoveryPlan(
            execution_id=plan.execution_id,
            state=plan.state,
            action=plan.action,
            reason=plan.reason,
            original_state=plan.original_state,
            details={**plan.details, "context": ctx or {}},
        )
