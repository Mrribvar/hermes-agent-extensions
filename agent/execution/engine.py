# Execution Layer — Phase 11.5: Governance Gate integration
#
# Per EXECUTION_LAYER_DESIGN.md §4.1: coordinator only. Manages lifecycle,
# validates context, interacts with state machine, delegates to an injected
# executor callable. Does NOT execute tasks itself.
#
# Dependencies:
#   Phase 11.1 - ExecutionStateMachine
#   Phase 11.2 - ExecutionQueue, QueueItem
#   Phase 11.3 - ExecutionContext
#   Phase 11.5 - GovernanceGate
#   agent.tool_executor (via injected executor, never called directly)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import time
import uuid
from .context import ExecutionContext, ContextValidationError
from .governance_gate import GovernanceGate, GovernanceResult, GovernanceVerdict
from .queue import ExecutionQueue, QueueItem, EmptyQueueError, DuplicateExecutionIdError
from .workflow import (
    ExecutionState,
    ExecutionStateMachine,
    InvalidTransitionError,
    StateTransition,
)

__all__ = [
    "ExecutionEngine",
    "ExecutionResult",
    "EngineError",
]


# The executor signature accepted by the engine.
# Strong type alias for the callable that executes one tool call given a context.
ExecutorFn = Callable[
    [ExecutionContext, ExecutionStateMachine],
    Any,
]


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a single execution, stored for Engine consumers."""

    execution_id: str
    success: bool
    details: Any = None
    error: Optional[str] = None
    state: str = ""
    result: Optional[Any] = None
    duration_seconds: float = 0.0
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EngineError(Exception):
    """Base error for execution engine failures."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExecutionEngine:
    """Coordinates execution lifecycle.

    Responsibilities:
      - Accept QueueItem with ExecutionContext
      - Validate ExecutionContext
      - Drive ExecutionStateMachine through lifecycle
      - Delegate to injected executor callable
      - Collect outcome and return ExecutionResult

    Does NOT:
      - Execute tasks directly (uses injected executor)
      - Implement Governance (Phase 11.5)
      - Persist execution memory (Phase 11.7)
      - Recover from crashes (Phase 11.8)
    """

    queue: ExecutionQueue = field(default_factory=ExecutionQueue)
    executor: Optional[ExecutorFn] = None
    governance_gate: Optional[GovernanceGate] = None
    memory: Optional[Any] = None  # ExecutionMemory (Phase 11.7); None = no persistence
    # Maximum items to drain in a single drain call (None = unlimited).
    drain_limit: Optional[int] = None

    # -- Core execution lifecycle ----------------------------------------

    def execute(self, item: QueueItem) -> ExecutionResult:
        """Execute a single QueueItem through the full lifecycle.

        1. Validate ExecutionContext if present (in payload).
        2. Transition state machine through CREATED -> PENDING_APPROVAL ->
           APPROVED -> RUNNING -> COMPLETED/FAILED.
        3. Delegate the actual execution to the injected executor.
        4. Record outcome and return.
        """
        ctx: Optional[ExecutionContext] = None
        state_machine = item.state_machine
        exec_id = item.execution_id
        started = time.monotonic()

        # Phase 0: Validate context (if present in payload)
        if item.payload is not None and hasattr(item.payload, "execution_id"):
            ctx = item.payload
            try:
                # validation is done by the frozen dataclass __post_init__;
                # already validated when created. Re-check quickly:
                if not ctx.execution_id:
                    raise ContextValidationError("execution_id must be non-empty")
            except ContextValidationError as e:
                return self._fail(item, str(e), started)

        # Phase 1: CREATED -> PENDING_APPROVAL
        try:
            if state_machine.state == ExecutionState.CREATED:
                state_machine.transition(
                    ExecutionState.PENDING_APPROVAL,
                    reason="engine: pending approval",
                )
        except InvalidTransitionError as e:
            return self._fail(item, str(e), started)

        # Phase 2: Governance Gate -> APPROVED / REJECTED / REQUIRES_APPROVAL
        # Governance is the authority. No execution proceeds past this point
        # without a governance verdict.
        if self.governance_gate is not None and ctx is None:
            # No context provided -> cannot evaluate; block (never silent pass).
            try:
                state_machine.transition(
                    ExecutionState.FAILED,
                    reason="governance: no ExecutionContext to evaluate",
                )
            except InvalidTransitionError:
                pass
            return self._fail(
                item,
                "governance: no ExecutionContext to evaluate",
                started,
            )

        gate = self.governance_gate
        if gate is not None and ctx is not None:
            gresult = gate.evaluate(ctx)
            if gresult.verdict == GovernanceVerdict.APPROVED:
                # Authority approved -> continue to RUNNING.
                try:
                    state_machine.transition(
                        ExecutionState.APPROVED,
                        reason=f"governance approved: {gresult.reason}",
                    )
                except InvalidTransitionError as e:
                    return self._fail(item, str(e), started)
            else:
                # REJECTED / REQUIRES_APPROVAL / FAILED_VALIDATION -> do NOT run.
                # Mark FAILED; execution stays blocked.
                try:
                    state_machine.transition(
                        ExecutionState.FAILED,
                        reason=f"governance {gresult.verdict.value}: {gresult.reason}",
                    )
                except InvalidTransitionError:
                    pass
                result = ExecutionResult(
                    execution_id=exec_id,
                    success=False,
                    error=f"governance {gresult.verdict.value}: {gresult.reason}",
                    state=state_machine.state.name,
                    duration_seconds=round(time.monotonic() - started, 4),
                    details={"governance": gresult},
                )
                self._record_terminal(item, result, ctx)
                return result
        else:
            # No gate configured -> historical behavior: allow (backward comp).
            # State machine still moves APPROVED so RUNNING transition works.
            if state_machine.state == ExecutionState.PENDING_APPROVAL:
                try:
                    state_machine.transition(
                        ExecutionState.APPROVED,
                        reason="engine: no governance gate configured (bypass)",
                    )
                except InvalidTransitionError as e:
                    return self._fail(item, str(e), started)

        # Phase 3: APPROVED -> RUNNING
        try:
            state_machine.transition(
                ExecutionState.RUNNING,
                reason="engine: execution started",
            )
        except InvalidTransitionError as e:
            return self._fail(item, str(e), started)

        # Phase 4: Delegate to executor
        result: Optional[Any] = None
        error: Optional[str] = None
        try:
            if self.executor is not None:
                result = self.executor(ctx or item, state_machine)
            else:
                # No executor configured: treat as dry-run success.
                result = {"_engine_noop": True}
        except Exception as e:
            error = f"executor raised {type(e).__name__}: {e}"
            # Phase 5: mark FAILED
            try:
                state_machine.transition(
                    ExecutionState.FAILED,
                    reason=error,
                )
            except InvalidTransitionError:
                pass  # already terminal
            duration = time.monotonic() - started
            result = ExecutionResult(
                execution_id=exec_id,
                success=False,
                error=error,
                state=state_machine.state.name,
                duration_seconds=round(duration, 4),
            )
            self._record_terminal(item, result, ctx or item)
            return result

        # Phase 5: RUNNING -> COMPLETED
        try:
            state_machine.transition(
                ExecutionState.COMPLETED,
                reason="engine: execution completed",
            )
        except InvalidTransitionError as e:
            error = f"transition to COMPLETED failed: {e}"
            duration = time.monotonic() - started
            result = ExecutionResult(
                execution_id=exec_id,
                success=False,
                error=error,
                state=state_machine.state.name,
                duration_seconds=round(duration, 4),
            )
            self._record_terminal(item, result, ctx or item)
            return result

        duration = time.monotonic() - started
        result = ExecutionResult(
            execution_id=exec_id,
            success=True,
            result=result,
            state=state_machine.state.name,
            duration_seconds=round(duration, 4),
        )
        self._record_terminal(item, result, ctx or item)
        return result

    def _record_terminal(self, item: QueueItem, result: ExecutionResult, ctx: object) -> None:
        """Persist final execution record to ExecutionMemory (if configured)."""
        if self.memory is None:
            return
        try:
            from .memory import ExecutionRecord
            has_ctx = hasattr(ctx, "task_id")
            rec = ExecutionRecord(
                execution_id=item.execution_id,
                state=result.state or item.state_machine.state.name,
                task_id=getattr(ctx, "task_id", "") if has_ctx else "",
                session_id=getattr(ctx, "session_id", "") if has_ctx else "",
                user_id=getattr(ctx, "user_id", "") if has_ctx else "",
                project_id=getattr(ctx, "project_id", "") if has_ctx else "",
                tool_id=getattr(ctx, "tool_id", "") if has_ctx else "",
                governance_verdict="",
                started_at=None,
                completed_at=_utc_now(),
                duration_ms=int(result.duration_seconds * 1000) if result.duration_seconds else None,
                result_status="success" if result.success else "failed",
                error_message=result.error,
                metadata={"governance": result.details} if getattr(result, "details", None) else {},
            )
            self.memory.save_execution(rec)
        except Exception:
            pass  # never let persistence failure block execution

    def _fail(self, item: QueueItem, error: str, started: float) -> ExecutionResult:
        """Transition to FAILED and return result."""
        try:
            item.state_machine.transition(
                ExecutionState.FAILED,
                reason=error,
            )
        except InvalidTransitionError:
            pass
        result = ExecutionResult(
            execution_id=item.execution_id,
            success=False,
            error=error,
            state=item.state_machine.state.name,
            duration_seconds=round(time.monotonic() - started, 4),
        )
        self._record_terminal(item, result, item)
        return result

    # -- Queue integration ------------------------------------------------

    def execute_next(self) -> ExecutionResult:
        """Dequeue the highest-priority item and execute it.

        Raises:
            EmptyQueueError: if queue is empty.
        """
        item = self.queue.dequeue()
        result = self.execute(item)
        return result

    def execute_by_id(self, execution_id: str) -> ExecutionResult:
        """Execute the item with the given ID (if still in queue)."""
        item = self.queue.remove(execution_id)
        if item is None:
            raise EngineError(f"execution_id '{execution_id}' not in queue")
        result = self.execute(item)
        return result

    def drain_queue(self) -> List[ExecutionResult]:
        """Execute all items currently in the queue, respecting drain_limit.

        Returns list of ExecutionResult in order of completion.
        """
        results: List[ExecutionResult] = []
        limit = self.drain_limit
        count = 0
        while True:
            if limit is not None and count >= limit:
                break
            try:
                item = self.queue.dequeue()
            except EmptyQueueError:
                break
            count += 1
            result = self.execute(item)
            results.append(result)
        return results

    # -- Future hooks ----------------------------------------------------

    def bind_state_machine(self, sm: ExecutionStateMachine) -> None:
        """Placeholder — future hook, no-op."""
        pass

    def bind_context(self, ctx: ExecutionContext) -> None:
        """Placeholder — future hook, no-op."""
        pass