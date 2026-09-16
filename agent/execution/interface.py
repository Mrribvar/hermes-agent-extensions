"""Execution Layer Interface Wiring — Phase 11.9: ExecutionCoordinator.

End-to-end integration of all Execution Layer components. This is a thin
coordinator that *composes* existing components — it does NOT redesign them,
duplicate logic, or change their public APIs.

Flow:
    Request
      -> Context Creation       (ExecutionContext)
      -> Queue                  (ExecutionQueue)
      -> Engine                 (ExecutionEngine)
      -> Governance             (GovernanceGate)
      -> Approval               (GovernanceGate verdict)
      -> Tool Resolution        (ToolOrchestrator)
      -> Execution              (ToolOrchestrator delegates to real tool handler)
      -> Memory Persistence     (ExecutionMemory)
      -> Recovery info exposed  (ExecutionRecovery)

Governance remains the authority. Recovery remains recommendation-only.
Backward compatible: every component here can be omitted; defaults preserve
prior behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from .context import ExecutionContext, ContextValidationError
from .queue import ExecutionQueue, QueueItem, QueuePriority, EmptyQueueError
from .engine import ExecutionEngine, ExecutionResult, EngineError
from .governance_gate import GovernanceGate, GovernanceResult, GovernanceVerdict
from .orchestrator import ToolOrchestrator, OrchestrationResult
from .memory import ExecutionMemory, ExecutionRecord, InvalidRecordError
from .recovery import (
    ExecutionRecovery,
    RecoveryAction,
    RecoveryPlan,
    RecoveryError,
)
from .intelligence_integration import get_intelligence_bridge, IntelligenceContext

logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionCoordinator",
    "SubmitRequest",
    "SubmitResult",
]


@dataclass(frozen=True)
class SubmitRequest:
    """Input describing an execution the Coordinator should run."""

    task_id: str
    session_id: str
    user_id: str
    project_id: str
    tool_id: str = ""
    execution_id: Optional[str] = None
    priority: QueuePriority = QueuePriority.NORMAL
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmitResult:
    """Outcome of a coordinator.submit(). Mirrors ExecutionResult plus status."""

    execution_id: str
    status: str  # completed / failed / rejected / requires_approval / queued
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    governance_verdict: str = ""
    recovery_action: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    decision_id: Optional[str] = None
    intelligence_context: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionCoordinator:
    """End-to-end coordinator for the Execution Layer.

    Attributes (all optional; None/omitted means default wiring):
        queue:        ExecutionQueue
        engine:       ExecutionEngine      (built if None)
        gate:         GovernanceGate
        orchestrator: ToolOrchestrator
        memory:       ExecutionMemory
        recovery:     ExecutionRecovery
    """

    queue: ExecutionQueue = field(default_factory=ExecutionQueue)
    engine: Optional[ExecutionEngine] = None
    gate: Optional[GovernanceGate] = None
    orchestrator: Optional[ToolOrchestrator] = None
    memory: Optional[ExecutionMemory] = None
    recovery: Optional[ExecutionRecovery] = None
    # When True, tools actually execute (delegated via orchestrator). When
    # False, the coordinator plans but does not run (dry run).
    auto_execute: bool = True

    def __post_init__(self) -> None:
        if self.memory is None:
            self.memory = ExecutionMemory()
        if self.recovery is None:
            self.recovery = ExecutionRecovery(memory=self.memory)
        if self.orchestrator is None:
            self.orchestrator = ToolOrchestrator()
        if self.engine is None:
            self.engine = ExecutionEngine(
                queue=self.queue,
                governance_gate=self.gate,
                memory=self.memory,
            )

    # -- public API ------------------------------------------------------

    def submit(self, request: SubmitRequest) -> SubmitResult:
        """Submit an execution: create context, enqueue, run, persist.

        Flow:
            context -> queue -> engine -> governance -> orchestrator -> memory

        Returns SubmitResult. Governance rejection / missing tool / failures
        are captured into SubmitResult (never raised for expected outcomes).
        """
        ctx: Optional[ExecutionContext] = None
        intel_ctx: Optional[IntelligenceContext] = None
        decision_id: Optional[str] = None

        # -- ADDITIVE: Pattern Intelligence before context creation --
        try:
            bridge = get_intelligence_bridge()
            intel_ctx = bridge.on_before_execution(
                task_id=request.task_id,
                task=f"{request.tool_id} {request.metadata.get('description', '')}",
                context=request.metadata,
                strategy=request.metadata.get("strategy", "unknown"),
                confidence=request.metadata.get("confidence", 0.5),
            )
        except Exception as e:
            logger.warning(f"Pattern intelligence pre-execution failed (non-blocking): {e}")
            intel_ctx = IntelligenceContext()

        # Merge intelligence metadata into request for context
        extra_metadata = {}
        if intel_ctx and intel_ctx.pattern_guidance:
            extra_metadata["intelligence"] = intel_ctx.to_dict()
            extra_metadata["pattern_guidance"] = intel_ctx.pattern_guidance
            extra_metadata["intel_risk_level"] = intel_ctx.risk_level
            extra_metadata["intel_recommendations"] = intel_ctx.recommendations
            extra_metadata["intel_warnings"] = intel_ctx.warnings

        # Merge with existing metadata
        merged_metadata = dict(request.metadata)
        if extra_metadata:
            for k, v in extra_metadata.items():
                if k not in merged_metadata:
                    merged_metadata[k] = v

        try:
            ctx = ExecutionContext.create(
                task_id=request.task_id,
                session_id=request.session_id,
                user_id=request.user_id,
                project_id=request.project_id,
                execution_id=request.execution_id,
                tool_id=request.tool_id,
                priority=request.priority,
                parameters=dict(request.parameters),
                metadata=merged_metadata,
            )
        except ContextValidationError as e:
            return SubmitResult(
                execution_id=request.execution_id or "",
                status="failed",
                success=False,
                error=f"context validation failed: {e}",
            )

        # -- ADDITIVE: Record decision before execution --
        try:
            bridge = get_intelligence_bridge()
            strategy = request.metadata.get("strategy", "unknown")
            confidence = request.metadata.get("confidence", 0.5)
            risk_level = intel_ctx.risk_level if intel_ctx else "LOW"
            pattern_guidance = intel_ctx.pattern_guidance if intel_ctx else None

            decision_id = bridge.record_decision(
                task_id=request.task_id,
                strategy=strategy,
                confidence=confidence,
                pattern_guidance=pattern_guidance,
                risk_level=risk_level,
                expected_outcome="success",
            )
        except Exception as e:
            logger.warning(f"Decision recording failed (non-blocking): {e}")
            decision_id = None

        # enqueue
        item = self.queue.enqueue(
            execution_id=ctx.execution_id,
            priority=ctx.priority,
            payload=ctx,
        )

        # If orchestration is wired, hook the orchestrator into the engine as
        # the executor so the actual tool runs through it.
        eng = self.engine
        if eng is None:
            return SubmitResult(
                execution_id=ctx.execution_id,
                status="failed",
                success=False,
                error="engine not configured",
                decision_id=decision_id,
                intelligence_context=intel_ctx.to_dict() if intel_ctx else None,
            )
        if self.auto_execute:
            eng.executor = self._build_orchestrator_executor(item, ctx)

        # run through engine + governance
        import time
        start_time = time.time()
        result = eng.execute_by_id(ctx.execution_id)
        duration_ms = int((time.time() - start_time) * 1000)

        # -- ADDITIVE: Evaluate decision after execution --
        try:
            bridge = get_intelligence_bridge()
            if decision_id:
                outcome = "success" if result.success else "failure"
                bridge.evaluate_decision(
                    decision_id=decision_id,
                    actual_outcome=outcome,
                    duration_ms=duration_ms,
                    metadata={
                        "execution_id": ctx.execution_id,
                        "tool_id": request.tool_id,
                        "error": result.error,
                    },
                )
                bridge.generate_feedback(
                    decision_id=decision_id,
                    actual_outcome=outcome,
                    duration_ms=duration_ms,
                    metadata={
                        "execution_id": ctx.execution_id,
                        "tool_id": request.tool_id,
                        "success": result.success,
                    },
                )
        except Exception as e:
            logger.warning(f"Decision evaluation failed (non-blocking): {e}")

        # persist (engine already persists via self.engine.memory if configured)
        if eng.memory is not None:
            self._persist_result(ctx, result)

        status, verdict, rec_action = self._classify(result)
        return SubmitResult(
            execution_id=ctx.execution_id,
            status=status,
            success=result.success,
            result=result.result,
            error=result.error,
            governance_verdict=verdict,
            recovery_action=rec_action,
            details={"engine_state": result.state or ""},
            decision_id=decision_id,
            intelligence_context=intel_ctx.to_dict() if intel_ctx else None,
        )

    def execute(self, request: SubmitRequest) -> SubmitResult:
        """Alias for submit; explicit synchronous execution."""
        return self.submit(request)

    def get_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return current execution status from memory (or None if unknown)."""
        if self.memory is None:
            return None
        rec = self.memory.get_execution(execution_id)
        if rec is None:
            return None
        return rec.to_dict()

    def get_history(self, limit: int = 100, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return execution history from memory."""
        if self.memory is None:
            return []
        return self.memory.list_executions(limit=limit, project_id=project_id)

    def recover(self, execution_id: str) -> Optional[RecoveryPlan]:
        """Expose recovery recommendation (never executes)."""
        if self.recovery is None:
            return None
        try:
            return self.recovery.get_recovery_plan(execution_id)
        except RecoveryError:
            return None

    def recover_all(self) -> List[Dict[str, Any]]:
        """List all interrupted executions found."""
        if self.recovery is None:
            return []
        return self.recovery.find_interrupted()

    # -- internals -------------------------------------------------------

    def _build_orchestrator_executor(self, item: QueueItem, ctx: ExecutionContext):
        """Return a callable that routes through the ToolOrchestrator."""
        orch = self.orchestrator
        if orch is None:
            def noop_executor(c_payload: Any, state_machine: Any) -> Any:
                return {"orchestrated": False, "success": False, "error": "orchestrator not configured"}
            return noop_executor

        def executor(c_payload: Any, state_machine: Any) -> Any:
            # c_payload is the ExecutionContext from the queue item
            target = c_payload if isinstance(c_payload, ExecutionContext) else ctx
            assert orch is not None  # narrowed above
            # Evaluate governance approval marker fresh from the gate.
            # The Orchestrator.execute() checks ctx.metadata["governance"]["verdict"],
            # so we must carry it forward.
            gate = self.gate
            if gate is not None:
                gv = gate.evaluate(target)
                md = dict(target.metadata)
                md["governance"] = {
                    "verdict": gv.verdict.value,
                    "reason": getattr(gv, "reason", ""),
                }
                target = target.update_metadata(metadata=md)
            else:
                # No governance gate configured — match the Engine's no-op
                # "bypass" behavior so the Orchestrator's approval check passes.
                md = dict(target.metadata)
                md["governance"] = {
                    "verdict": GovernanceVerdict.APPROVED.value,
                    "reason": "no governance gate configured (bypass)",
                }
                target = target.update_metadata(metadata=md)
            try:
                orc_result = orch.execute(target)
                if not orc_result.success:
                    # A failed orchestration must propagate as an execution
                    # failure so the Engine records FAILED (not COMPLETED).
                    raise RuntimeError(orc_result.error or "tool orchestration failed")
                return {
                    "orchestrated": True,
                    "tool": orc_result.tool_name,
                    "success": True,
                    "result": orc_result.result,
                    "error": None,
                }
            except Exception as e:
                raise RuntimeError(str(e))

        return executor

    def _persist_result(self, ctx: ExecutionContext, result: ExecutionResult) -> None:
        """Persist the execution outcome to ExecutionMemory."""
        if self.memory is None:
            return
        try:
            rec = ExecutionRecord(
                execution_id=ctx.execution_id,
                state=result.state or "COMPLETED" if result.success else "FAILED",
                task_id=ctx.task_id,
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                project_id=ctx.project_id,
                tool_id=ctx.tool_id,
                governance_verdict=ctx.metadata.get("governance_verdict", ""),
                result_status="success" if result.success else "failed",
                error_message=result.error,
                metadata=ctx.metadata,
            )
            self.memory.save_execution(rec)
        except Exception as e:
            logger.warning("persist failed (non-fatal): %s", e)

    def _classify(self, result: ExecutionResult) -> tuple:
        """Map an ExecutionResult to (status, governance_verdict, recovery_action)."""
        if result.success:
            return ("completed", "", None)

        err = result.error or ""
        if "rejected" in err.lower():
            return ("rejected", "REJECTED", "manual_review")
        if "requires_approval" in err.lower() or "requires approval" in err.lower():
            return ("requires_approval", "REQUIRES_APPROVAL", "manual_review")
        return ("failed", "", None)