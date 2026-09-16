# Architecture

This document shows how the extensions in this repository sit on top of the
upstream Hermes Agent runtime, and what each layer is responsible for.

## High-level placement

```mermaid
graph TB
    Nous["Nous Research"]
    HA["Hermes Agent (upstream, MIT License)"]

    Core["Core Agent<br/>run_agent.py · agent/"]
    Tools["Tools<br/>tools/ · toolsets.py"]
    Gateway["Gateway<br/>gateway/ · 20+ platforms"]
    Memory["Memory<br/>memory_manager · memory_provider"]
    Verif["Verification Evidence<br/>agent/verification_evidence.py"]

    Ext["Extensions (this repository)"]

    Gov["Governance<br/>governance/ · governance/execution/"]
    Exp["Experience & Learning<br/>agent/experience/"]
    Exec["Execution Layer<br/>agent/execution/"]
    Plan["Planning<br/>agent/planning.py"]
    Biz["Business Bridge<br/>agent/business/"]
    Herald["HERALD Intelligence<br/>herald/ · governance/decision_*"]
    Ops["Operational Tooling<br/>skills/ · docs/"]

    Nous --> HA
    HA --> Core
    HA --> Tools
    HA --> Gateway
    HA --> Memory
    HA --> Verif

    Core --> Ext
    Tools --> Ext
    Verif --> Ext

    Ext --> Gov
    Ext --> Exp
    Ext --> Exec
    Ext --> Plan
    Ext --> Biz
    Ext --> Herald
    Ext --> Ops

    classDef upstream fill:#1e3a5f,stroke:#4a90d9,color:#fff
    classDef ext fill:#3d2f5c,stroke:#9b7fd4,color:#fff
    classDef root fill:#2d2d2d,stroke:#888,color:#fff

    class Nous,HA root
    class Core,Tools,Gateway,Memory,Verif upstream
    class Ext,Gov,Exp,Exec,Plan,Biz,Herald,Ops ext
```

## Layer responsibilities

### Upstream (Nous Research)

| Layer | What it provides | Where |
|---|---|---|
| Core Agent | Conversation loop, turn context, tool dispatch, prompt building | `run_agent.py`, `agent/` |
| Tools | Tool registry, built-in tools, toolset definitions | `tools/`, `toolsets.py` |
| Gateway | Platform adapters, session management, inbound/outbound routing | `gateway/` |
| Memory | Persistent memory provider, memory manager | `agent/memory_manager.py`, `agent/memory_provider.py` |
| Verification Evidence | SQLite-backed record of verification events + status API | `agent/verification_evidence.py` |

The extensions attach at three points: the core agent (for the learning and
planning wiring), the tool registry (for the execution layer's orchestrator),
and the verification-evidence database (for the learning loop's substrate).

### Extensions (this repository)

| Extension | Responsibility | Attaches at | Runtime |
|---|---|---|---|
| Governance | Decision memory, risk classification, approval workflow, knowledge graph, project registry, impact analysis, recommendation engine, architecture query | Plugin: `post_tool_call`, `on_session_end` | Partially active |
| Experience & Learning | Verify → Finalize → Learn → Persist → Recall | `finalize_turn`, `conversation_loop` | Active |
| Execution Layer | Governed, queued, persistent execution of a single tool call | Tool dispatch (intended; not yet wired) | Dormant |
| Planning | Deterministic goal → step list, seeded into `TodoStore` | `turn_context.py` hook | Dormant (flag off) |
| Business Bridge | Business entities → `ExecutionMemory` | `ExecutionMemory` API | Partial |
| HERALD Intelligence | Decision-performance loop with persistence | `ExecutionCoordinator.submit()` | Frozen / dormant |
| Operational Tooling | Original skills, architecture docs, phase reports | Skill system, filesystem | Active (skills) |

## Data-flow diagrams

### Verification → Learning (active)

```mermaid
sequenceDiagram
    participant Agent as AIAgent turn
    participant Tools as tool_executor
    participant Verif as verification_evidence (upstream)
    participant Final as turn_finalizer (custom wiring)
    participant Learn as lifecycle_learning (custom)
    participant Store as experiences.json

    Agent->>Tools: run test command
    Tools->>Verif: record_terminal_result(...)
    Verif-->>Tools: verification_status = passed/failed
    Agent->>Final: finalize_turn(...)
    Final->>Verif: read verification_status
    Verif-->>Final: {status: passed, stale: false}
    Final->>Learn: observe_lifecycle(turn_end, verification=passed)
    Learn->>Store: append ExperienceRecord(result=successful, outcome=VERIFIED)
```

### Execution Layer (dormant — the intended path)

```mermaid
flowchart LR
    Submit[SubmitRequest] --> Ctx[ExecutionContext]
    Ctx --> Q[ExecutionQueue]
    Q --> Eng[ExecutionEngine]
    Eng --> Gate[GovernanceGate]
    Gate -->|APPROVED| Orc[ToolOrchestrator]
    Gate -->|REQUIRES_APPROVAL / REJECTED| Fail[FAILED - blocked]
    Orc --> Real[real tool handler]
    Real --> Mem[ExecutionMemory - SQLite]
    Mem --> Rec[ExecutionRecovery - recommendation only]

    classDef dormant fill:#4a1f1f,stroke:#c05c5c,color:#fff
    class Submit,Ctx,Q,Eng,Gate,Orc,Real,Mem,Rec dormant
```

*The flow is correct and tested, but no production code calls
`ExecutionCoordinator.submit()` yet. See `PROJECT_STATUS.md`.*

### Planning (dormant — the intended path)

```mermaid
flowchart LR
    Turn[build_turn_context] --> Check{planning.enabled?}
    Check -->|false - default| Skip[no-op]
    Check -->|true| Trivial{is_trivial_prompt?}
    Trivial -->|yes| Skip
    Trivial -->|no| StoreEmpty{TodoStore empty?}
    StoreEmpty -->|no - model owns list| Skip
    StoreEmpty -->|yes| Planner[Planner.plan]
    Planner --> Merge[merge steps into TodoStore]

    classDef dormant fill:#4a1f1f,stroke:#c05c5c,color:#fff
    class Planner,Merge dormant
```

## Boundary contracts

Every extension respects three boundary rules:

1. **No upstream file is modified.** Extensions live in new directories. The
   only change to the upstream tree is the addition of a plugin directory
   (`plugins/governance/`) that the upstream plugin loader discovers.

2. **The prompt cache is sacred.** No extension mutates past conversation
   context, swaps toolsets mid-conversation, or rebuilds the system prompt.
   Planning writes only to the `TodoStore`, never to the system prompt.

3. **Fail-safe.** Intelligence and governance calls are wrapped in
   `try/except` and degrade to safe defaults (`None`, `{}`, `False`). No
   extension can block a turn.

## Dependency notes

Some extensions import from upstream and therefore cannot run standalone:

| Module | Upstream imports |
|---|---|
| `agent/execution/orchestrator.py` | `tools.registry` |
| `agent/experience/listener.py` | `agent.verification_evidence` (via the wiring layer) |
| `agent/business/bridge/memory_bridge.py` | `agent.execution.memory` (this repo) |
| `governance/graph_builder.py` | `hermes_constants` |

This is a deliberate choice: reusing upstream infrastructure keeps the
extensions small. It also means the correct way to run them is inside a Hermes
Agent checkout — see the Development section in `README.md`.

## Cross-cutting principles

See [`docs/architecture.md`](docs/architecture.md) for a longer walkthrough of
each boundary and the design trade-offs behind them.