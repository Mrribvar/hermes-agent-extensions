# Execution Layer package (Phase 11.1 foundation).
#
# Purely additive under agent/ — no existing execution systems modified.
# Backward compatible: existing agent import paths unchanged.
from __future__ import annotations

from .workflow import ExecutionState, ExecutionStateMachine, InvalidTransitionError, StateTransition
from .queue import (
    ExecutionQueue,
    QueueItem,
    QueuePriority,
    QueueStats,
    EmptyQueueError,
    DuplicateExecutionIdError,
)
from .context import ExecutionContext, ContextValidationError
from .engine import ExecutionEngine, ExecutionResult, EngineError
from .governance_gate import (
    GovernanceGate,
    GovernanceResult,
    GovernanceVerdict,
)
from .orchestrator import (
    ToolOrchestrator,
    OrchestrationResult,
    InputValidationError,
    ApprovalRequiredError,
    ToolNotFoundError,
    ToolUnavailableError,
)
from .memory import ExecutionMemory, ExecutionRecord, InvalidRecordError
from .recovery import ExecutionRecovery, RecoveryAction, RecoveryPlan, RecoveryError
from .interface import ExecutionCoordinator, SubmitRequest, SubmitResult

__all__ = [
    "ExecutionState",
    "ExecutionStateMachine",
    "InvalidTransitionError",
    "StateTransition",
    "ExecutionQueue",
    "QueueItem",
    "QueuePriority",
    "QueueStats",
    "EmptyQueueError",
    "DuplicateExecutionIdError",
    "ExecutionContext",
    "ContextValidationError",
    "ExecutionEngine",
    "ExecutionResult",
    "EngineError",
    "GovernanceGate",
    "GovernanceResult",
    "GovernanceVerdict",
    "ToolOrchestrator",
    "OrchestrationResult",
    "InputValidationError",
    "ApprovalRequiredError",
    "ToolNotFoundError",
    "ToolUnavailableError",
    "ExecutionMemory",
    "ExecutionRecord",
    "InvalidRecordError",
    "ExecutionRecovery",
    "RecoveryAction",
    "RecoveryPlan",
    "RecoveryError",
    "ExecutionCoordinator",
    "SubmitRequest",
    "SubmitResult",
]
