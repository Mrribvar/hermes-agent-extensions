"""Execution Engine — Hermes Execution Layer.

Central controller responsible for:
- task lifecycle
- execution scheduling
- execution context
- execution orchestration

Every execution passes through Governance before running.
No component executes tools directly.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from governance.execution.state_machine import (
    ExecutionState,
    validate_transition,
    is_terminal,
)
from governance.execution.context import ExecutionContext
from governance.execution.events import (
    ExecutionEventType,
    ExecutionEvent,
    ExecutionEventBus,
)
from governance.execution.execution_memory import ExecutionMemory
from governance.execution.execution_queue import ExecutionQueue
from governance.execution.governance_integration import (
    GovernanceGate,
    GovernanceVerdict,
)
from governance.execution.tool_orchestrator import ToolOrchestrator, BaseTool


class ExecutionEngine:
    """The single controller for all executions.

    Playbook for a task:
      1. create_execution(ctx) -> creates ExecutionContext + registers with
         ExecutionMemory (state PENDING), enqueues.
      2. approve(exec_id)     -> woken from queue, state APPROVED.
      3. run(exec_id)         -> Governance gate check, then execute via
         ToolOrchestrator. NOT autonomous — requires prior approval.
    """

    def __init__(
        self,
        memory: Optional[ExecutionMemory] = None,
        queue: Optional[ExecutionQueue] = None,
        gate: Optional[GovernanceGate] = None,
        orchestrator: Optional[ToolOrchestrator] = None,
        bus: Optional[ExecutionEventBus] = None,
    ):
        self.memory = memory or ExecutionMemory()
        self.queue = queue or ExecutionQueue()
        self.gate = gate or GovernanceGate()
        self.orchestrator = orchestrator or ToolOrchestrator()
        self.bus = bus or ExecutionEventBus()
        self._states: Dict[str, ExecutionState] = {}
        self._contexts: Dict[str, ExecutionContext] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_execution(self, context: ExecutionContext) -> str:
        """Register a new execution. State: PENDING."""
        exec_id = context.execution_id
        gr = self.gate.evaluate(exec_id, context.to_dict())
        # Pre-registration risk gate only — does not run the tool.
        self._states[exec_id] = ExecutionState.PENDING
        self._contexts[exec_id] = context

        self.memory.create(
            execution_id=exec_id,
            task_id=context.task_id,
            action=context.parameters.get("action", ""),
            tool=context.parameters.get("tool", ""),
            inputs=context.parameters,
            risk_level=context.risk_level,
            governance_approval=context.governance_approval,
        )

        self.queue.enqueue(context.task_id, context.to_dict())
        return exec_id

    def approve(self, exec_id: str) -> bool:
        """Approve an execution. State: PENDING -> APPROVED."""
        if exec_id not in self._states:
            return False
        try:
            validate_transition(self._states[exec_id], ExecutionState.APPROVED)
        except ValueError:
            return False
        self._states[exec_id] = ExecutionState.APPROVED
        return True

    def run(self, exec_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """Run an approved execution.

        Requires state APPROVED (no autonomous execution). Runs through:
          Governance gate -> Tool Orchestrator -> Execution Memory -> Events
        """
        if exec_id not in self._states:
            return {"success": False, "error": "unknown execution"}
        if self._states[exec_id] != ExecutionState.APPROVED:
            return {"success": False, "error": "execution not approved"}

        ctx = self._contexts[exec_id]

        # 1. Governance gate (full check)
        decision = self.gate.evaluate(exec_id, ctx.to_dict())
        if decision.verdict != GovernanceVerdict.APPROVED:
            self._states[exec_id] = ExecutionState.FAILED
            self.memory.fail(exec_id, "governance denied")
            self._emit(exec_id, ExecutionEventType.EXECUTION_FAILED, {"reason": "governance"})
            return {"success": False, "error": decision.to_dict()}

        # 2. Transition to RUNNING
        self._states[exec_id] = ExecutionState.RUNNING
        self.memory.start(exec_id)
        self._emit(exec_id, ExecutionEventType.EXECUTION_STARTED)
        started = time.perf_counter()

        try:
            tool_name = ctx.parameters.get("tool", "")
            params = ctx.parameters.get("params", {})
            timeout_ms = ctx.timeout_seconds * 1000 if ctx.timeout_seconds > 0 else None

            # 3. Execute through orchestrator (may be a custom handler in tests)
            if handler:
                output = handler(ctx)
            else:
                result = self.orchestrator.execute(
                    tool_name, params, ctx.to_dict(), timeout_ms=timeout_ms
                )
                if not result.success:
                    raise RuntimeError(result.error or "tool execution failed")
                output = result.output

            duration_ms = int((time.perf_counter() - started) * 1000)

            # 4. Complete
            self._states[exec_id] = ExecutionState.COMPLETED
            self.memory.complete(exec_id, outputs=output, duration_ms=duration_ms)
            self._emit(exec_id, ExecutionEventType.EXECUTION_COMPLETED, {"duration_ms": duration_ms})
            return {"success": True, "execution_id": exec_id, "output": output}

        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._states[exec_id] = ExecutionState.FAILED
            self.memory.fail(exec_id, str(e))
            self._emit(exec_id, ExecutionEventType.EXECUTION_FAILED, {"error": str(e)})
            return {"success": False, "error": str(e), "execution_id": exec_id}

    # ------------------------------------------------------------------
    # Lifecycle controls
    # ------------------------------------------------------------------

    def pause(self, exec_id: str) -> bool:
        """RUNNING -> PAUSED."""
        if exec_id not in self._states:
            return False
        try:
            validate_transition(self._states[exec_id], ExecutionState.PAUSED)
        except ValueError:
            return False
        self._states[exec_id] = ExecutionState.PAUSED
        self._emit(exec_id, ExecutionEventType.EXECUTION_PAUSED)
        return True

    def resume(self, exec_id: str) -> bool:
        """PAUSED -> RUNNING."""
        if exec_id not in self._states:
            return False
        try:
            validate_transition(self._states[exec_id], ExecutionState.RUNNING)
        except ValueError:
            return False
        self._states[exec_id] = ExecutionState.RUNNING
        self._emit(exec_id, ExecutionEventType.EXECUTION_RESUMED)
        return True

    def cancel(self, exec_id: str) -> bool:
        """Cancel an execution. Prevents terminal states."""
        if exec_id not in self._states:
            return False
        try:
            validate_transition(self._states[exec_id], ExecutionState.CANCELLED)
        except ValueError:
            return False
        self._states[exec_id] = ExecutionState.CANCELLED
        self.memory.cancel(exec_id)
        self._emit(exec_id, ExecutionEventType.EXECUTION_CANCELLED)
        return True

    def retry(self, exec_id: str) -> bool:
        """Mark execution for retry. RUNNING/FAILED context accepted."""
        if exec_id not in self._states:
            return False
        try:
            validate_transition(self._states[exec_id], ExecutionState.RETRYING)
        except ValueError:
            return False
        # bump context retry count
        ctx = self._contexts[exec_id]
        ctx.retry_count += 1
        self._states[exec_id] = ExecutionState.RETRYING
        self._emit(exec_id, ExecutionEventType.EXECUTION_RETRIED, {"retry_count": ctx.retry_count})
        return True

    def get_state(self, exec_id: str) -> Optional[ExecutionState]:
        return self._states.get(exec_id)

    def get_context(self, exec_id: str) -> Optional[ExecutionContext]:
        return self._contexts.get(exec_id)

    def list_executions(self) -> List[str]:
        return list(self._states.keys())

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _emit(self, exec_id: str, event_type: ExecutionEventType, data: Dict[str, Any] = None):
        ctx = self._contexts.get(exec_id)
        event = ExecutionEvent(
            event_type=event_type,
            execution_id=exec_id,
            task_id=ctx.task_id if ctx else "",
            data=data or {},
        )
        self.bus.emit(event)