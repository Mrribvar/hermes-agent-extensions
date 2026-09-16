# EXECUTION_LAYER_README.md
# Execution Layer — User Guide (Phase 11)

## Overview

The Execution Layer (`agent/execution/`) formalizes how Hermes runs a tool
call through a governed, persistent lifecycle. It wraps the existing
`agent.tool_executor` and `tools/` registry with:

- An explicit state machine
- A priority queue
- Immutable execution context
- Governance gating (risk + approval)
- Tool orchestration
- Persistent execution memory (SQLite)
- Crash recovery planning

All components are **additive** — no existing Hermes behavior is changed.
Backward compatible: every component degrades to a safe default when omitted.

## Quick Start

```python
from agent.execution import (
    ExecutionCoordinator,
    SubmitRequest,
    ExecutionMemory,
    ToolOrchestrator,
)

# 1. Memory (SQLite, auto-created under HERMES_HOME)
memory = ExecutionMemory()

# 2. Coordinator wires everything together
coord = ExecutionCoordinator(
    memory=memory,
    orchestrator=ToolOrchestrator(),
)

# 3. Submit work
result = coord.submit(SubmitRequest(
    task_id="task-1",
    session_id="sess-1",
    user_id="user-1",
    project_id="proj-1",
    tool_id="read_file",
    parameters={"path": "/tmp/x.txt"},
))
print(result.status)  # completed / failed / rejected / requires_approval

# 4. Query
status = coord.get_status(result.execution_id)
history = coord.get_history(limit=20)

# 5. Recovery (recommendation only — never auto-executes)
plans = coord.recover_all()
```

## Execution Lifecycle

```
SubmitRequest
   └─ ExecutionContext creation
        └─ enqueue (ExecutionQueue)
             └─ Engine.execute
                  ├─ CREATED
                  ├─ PENDING_APPROVAL
                  ├─ GovernanceGate.evaluate(ctx)
                  │    ├─ APPROVED → RUNNING
                  │    ├─ REQUIRES_APPROVAL → FAILED (blocked)
                  │    └─ REJECTED → FAILED (blocked)
                  ├─ RUNNING → ToolOrchestrator → real handler
                  ├─ COMPLETED
                  │  └─ persisted to ExecutionMemory
                  └─ FAILED
```
Governance is the authority. If no gate is wired, the engine allows
(backward compatible bypass). Recovery never changes state — it only
recommends a RecoveryAction.

## Recovery Recommendation Actions

| State (interrupted) | Recommended Action |
|---|---|
| RUNNING | `RESUME` |
| PAUSED | `RETRY` |
| PENDING_APPROVAL | `MANUAL_REVIEW` |
| unknown state | `MANUAL_REVIEW` |
| COMPLETED / FAILED / CANCELLED | (none — terminal) |

## Governance Integration

- `GovernanceGate` uses `GovernanceEngine + RiskClassifier + ApprovalWorkflow`
- Risk levels:
  - SAFE / LOW → APPROVED
  - MEDIUM → REQUIRES_APPROVAL (proposes ApprovalRequest)
  - HIGH → REJECTED
  - unknown/missing → REQUIRES_APPROVAL (fail-closed)
- ToolOrchestrator requires `metadata["governance"]["verdict"] == "approved"` before executing.

## Storage

`ExecutionMemory` uses a dedicated `execution_memory.db` (SQLite, WAL mode)
under HERMES_HOME. Schema: `execution_records` (execution_id PK, task_id,
session_id, user_id, project_id, tool_id, state, governance_verdict,
started_at, completed_at, duration_ms, result_status, error_message, metadata)
plus `memory_meta` for schema versioning.

## Testing

```bash
pytest tests/agent/execution/ -q          # Phase 11 suite
```

## Requirements / Dependencies

- Python 3.10+
- Standard library (sqlite3, dataclasses, enum, threading, uuid, json)
- Governance modules under `governance/` (optional — verified by unit tests with mocks)
- `tools/registry.py` + `agent/tool_executor.py` (delegation targets)

## Compatibility

- No existing Hermes runtime module is modified.
- All existing behavior preserved via optional dependency wiring.
- Existing tests for tool_executor / governance / turn_context remain green.