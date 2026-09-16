# Execution Layer

**Location:** `agent/execution/`
**Ownership:** Custom — additive on top of upstream Hermes Agent.
**Runtime:** **Implemented but Dormant** — not wired into the live agent loop.

## Why this document exists

The Execution Layer is one of the largest pieces of custom work in this
repository, and it is also the one most likely to be misread. It is a complete,
tested system, and it currently does nothing at runtime. This document explains
both facts clearly.

## Purpose

Turn a single tool call into an explicit lifecycle:

1. A request enters with a task, a session, and a tool.
2. An immutable context is created from the request.
3. The context is queued.
4. The engine drives the lifecycle.
5. A governance gate decides whether the call may run.
6. If approved, an orchestrator resolves the tool and delegates to the real
   handler.
7. The outcome is persisted to SQLite.
8. On interruption, recovery can propose (never execute) a next step.

## Components

| Component | File | Responsibility |
|---|---|---|
| `ExecutionCoordinator` | `interface.py` | End-to-end entry point: `submit()`, `get_status()`, `get_history()`, `recover()`, `recover_all()` |
| `ExecutionContext` | `context.py` | Immutable per-execution snapshot (validation + serialization) |
| `ExecutionQueue` | `queue.py` | Priority FIFO, thread-safe, unique execution IDs |
| `ExecutionEngine` | `engine.py` | Coordinates lifecycle; delegates to an executor |
| `GovernanceGate` | `governance_gate.py` | Risk evaluation authority (SAFE/LOW → approved, MEDIUM → approval, HIGH → reject, unknown → fail-closed) |
| `ToolOrchestrator` | `orchestrator.py` | Resolves and validates a tool, then delegates to the real handler |
| `ExecutionMemory` | `memory.py` | SQLite persistence (`execution_memory.db`) |
| `ExecutionRecovery` | `recovery.py` | Detects interrupted executions and recommends a recovery action — never executes |
| `ExecutionStateMachine` | `workflow.py` | Enforces the nine legal states and their transitions |

## The lifecycle

```
CREATED → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
                              │                     ├ FAILED
                              │                     └ CANCELLED
                              └ REJECTED            └ PAUSED → RETRYING
```

Governance sits between `PENDING_APPROVAL` and `APPROVED`. If the verdict is
not `APPROVED`, the execution does not run.

## Public API

34 exports, grouped by component:

- **Workflow:** `ExecutionState`, `ExecutionStateMachine`, `InvalidTransitionError`, `StateTransition`
- **Queue:** `ExecutionQueue`, `QueueItem`, `QueuePriority`, `QueueStats`, `EmptyQueueError`, `DuplicateExecutionIdError`
- **Context:** `ExecutionContext`, `ContextValidationError`
- **Engine:** `ExecutionEngine`, `ExecutionResult`, `EngineError`
- **Governance:** `GovernanceGate`, `GovernanceResult`, `GovernanceVerdict`
- **Orchestrator:** `ToolOrchestrator`, `OrchestrationResult`, `InputValidationError`, `ApprovalRequiredError`, `ToolNotFoundError`, `ToolUnavailableError`
- **Memory:** `ExecutionMemory`, `ExecutionRecord`, `InvalidRecordError`
- **Recovery:** `ExecutionRecovery`, `RecoveryAction`, `RecoveryPlan`, `RecoveryError`
- **Interface:** `ExecutionCoordinator`, `SubmitRequest`, `SubmitResult`

## Persistence

`ExecutionMemory` uses a dedicated `execution_memory.db` (SQLite, WAL mode)
under the user's `HERMES_HOME`. The schema is `execution_records` plus a
`memory_meta` table for schema versioning.

The choice to reuse the SQLite pattern (rather than add a new database engine)
follows the same principle the upstream `verification_evidence` module uses.

## Recovery

Recovery is **recommendation-only**. Given an interrupted execution it returns
one of:

| Interrupted state | Recommended action |
|---|---|
| `RUNNING` | `RESUME` |
| `PAUSED` | `RETRY` |
| `PENDING_APPROVAL` | `MANUAL_REVIEW` |
| unknown | `MANUAL_REVIEW` |
| terminal (`COMPLETED` / `FAILED` / `CANCELLED`) | (none) |

It never changes state and never executes a task. This is deliberate: re-running
an interrupted execution could re-approve a dangerous action.

## Test coverage

The phase report documents **269 passing tests, 0 failures**, covering:

- State machine transitions
- Queue ordering and concurrency
- Context immutability
- Engine lifecycle
- Governance gate decisions
- Orchestrator delegation
- Memory persistence
- Recovery planning
- Coordinator integration (15 tests)

The tests live in `tests/agent/execution/` in this repository.

## Why it is dormant

Nothing in the live runtime calls `ExecutionCoordinator.submit()`:

- `run_agent.py` — no reference
- `cli.py` — no reference
- `gateway/run.py` — no reference

The layer is complete and tested but sits beside the live loop rather than
inside it. This was a deliberate choice: the wiring step was deferred until the
layer's contract was stable, and until the governance gate could be trusted to
make the right call on every tool path.

## What would make it active

Wiring `ExecutionCoordinator.submit()` into the tool dispatch point behind a
feature flag, plus an end-to-end test that exercises the real path — not a
mock.

## Relationship to HERALD

HERALD Intelligence (Phases 010–013) was designed to attach to this layer via
`intelligence_integration.py`. Because the Execution Layer is not wired, HERALD
has no caller and is consequently dormant as well. Wiring this layer is the
prerequisite for unblocking HERALD.