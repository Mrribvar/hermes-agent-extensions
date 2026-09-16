# EXECUTION_LAYER_ARCHITECTURE.md
# Execution Layer — Production Architecture (Phase 11)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Execution Layer (agent/execution/)              │
│                                                                     │
│   ExecutionCoordinator (interface.py)                               │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │ submit()  execute()  get_status()  get_history()        │       │
│   │ recover()  recover_all()                                │       │
│   └─────────────────────────────────────────────────────────┘       │
│                              │                                      │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────┐         │
│  │Execution   │──▶│ExecutionQueue │──▶│ ExecutionEngine     │        │
│  │Context     │   │ (FIFO+prio)   │   │ (coordinator only) │        │
│  └────────────┘   └──────────────┘   └─────────┬──────────┘         │
│                                                │                    │
│            ┌───────────────────────────────────┼───────────────┐    │
│            │                                   │               │    │
│     ┌──────▼──────┐                   ┌────────▼────────┐      │    │
│     │GovernanceGate │                 │   ToolOrchestrator │    │    │
│     │  authority   │                 │  (plans + routes) │    │    │
│     └─────────────┘                  └────────┬──────────┘      │    │
│                                               │                 │    │
│     ┌──────────────┐                        ┌──▼───────────┐    │    │
│     │ExecutionState│                        │ tools/registry│   │    │
│     │  Machine     │                        │ + tool_executor│   │    │
│     └──────────────┘                        └──────────────┘    │    │
│                                               │                    │
│     ┌────────────────┐                 ┌──────▼──────┐            │
│     │ ExecutionMemory │◀───persist──────│   result    │            │
│     │  (SQLite)       │                 └─────────────┘            │
│     └────────────────┘                                            │
│     ┌────────────────┐                                            │
│     │ ExecutionRecovery │◀───read─────── (recommendation only)    │
│     └────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Module | Responsibility |
|---|---|---|
| `ExecutionState` | workflow.py | 9-state lifecycle enum |
| `ExecutionStateMachine` | workflow.py | state transitions, history, serialization |
| `ExecutionQueue` | queue.py | FIFO + priority, unique IDs, thread-safe |
| `ExecutionContext` | context.py | immutable per-execution snapshot |
| `ExecutionEngine` | engine.py | coordinates lifecycle, delegates to executor |
| `GovernanceGate` | governance_gate.py | evaluates risk, returns verdict (authority) |
| `ToolOrchestrator` | orchestrator.py | resolves, validates, delegates tool calls |
| `ExecutionMemory` | memory.py | persistent SQLite store of execution records |
| `ExecutionRecovery` | recovery.py | detects interruption, recommends recovery |
| `ExecutionCoordinator` | interface.py | end-to-end integration entry point |

## Dependency Map

```
interface (ExecutionCoordinator)
 ├── context (ExecutionContext)
 ├── queue (ExecutionQueue)
 ├── engine (ExecutionEngine)
 │    ├── governance_gate (GovernanceGate)
 │    ├── memory (ExecutionMemory)
 │    └── orchestrator (ToolOrchestrator)
 │          └── tools.registry + tool_executor
 ├── memory (ExecutionMemory)
 └── recovery (ExecutionRecovery) → memory

No circular imports. Verified all modules load independently.
```

## Public API (34 exports)

- Workflow: `ExecutionState`, `ExecutionStateMachine`, `InvalidTransitionError`, `StateTransition`
- Queue: `ExecutionQueue`, `QueueItem`, `QueuePriority`, `QueueStats`, `EmptyQueueError`, `DuplicateExecutionIdError`
- Context: `ExecutionContext`, `ContextValidationError`
- Engine: `ExecutionEngine`, `ExecutionResult`, `EngineError`
- Governance: `GovernanceGate`, `GovernanceResult`, `GovernanceVerdict`
- Orchestrator: `ToolOrchestrator`, `OrchestrationResult`, `InputValidationError`, `ApprovalRequiredError`, `ToolNotFoundError`, `ToolUnavailableError`
- Memory: `ExecutionMemory`, `ExecutionRecord`, `InvalidRecordError`
- Recovery: `ExecutionRecovery`, `RecoveryAction`, `RecoveryPlan`, `RecoveryError`
- Interface: `ExecutionCoordinator`, `SubmitRequest`, `SubmitResult`

## Lifecycle

```
CREATED → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
                                            │ → FAILED
                                            └ → CANCELLED
                                            │ → PAUSED → RETRYING
```

Governance is checked between PENDING_APPROVAL and APPROVED; execution is
blocked if the verdict is not APPROVED. Recovery is recommendation-only and
never auto-executes tasks.