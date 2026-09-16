# EXECUTION_LAYER_DESIGN.md — Phase 11.0 (Design Only)

> Status: DESIGN. No code written. Every referenced module verified on disk
> under `hermes-agent/` at the time of writing.
>
> Rule: No Evidence = No Claim. Each section cites the real file it builds on.

---

## 0. Verified architectural ground truth (inputs)

All of these were confirmed present on disk (not assumed):

| Concern | Verified module | What it really provides |
|---|---|---|
| Model-tool dispatch | `agent/tool_executor.py` | `execute_tool_calls_concurrent`, `execute_tool_calls_sequential`, argument parse, budget, session-db flush per tool |
| Tool middleware chain | `agent/tool_dispatch_helpers.py` | `_apply_tool_request_middleware_for_agent`, `_run_agent_tool_execution_middleware` |
| Tool registry | `tools/registry.py` | `ToolRegistry`, `ToolEntry`, `discover_builtin_tools`, `_check_fn_cached` |
| Approval hook (existing) | `tools/approval.py` | `set_current_session_key`, `_fire_approval_hook`, `get_current_session_key` |
| Turn state | `agent/turn_context.py` | `TurnContext`, `build_turn_context` |
| Turn finalize | `agent/turn_finalizer.py` | exists |
| Turn retry | `agent/turn_retry_state.py` | exists |
| Verification evidence | `agent/verification_evidence.py` | `VerificationEvidence`, sqlite-backed `verification_evidence.db` |
| Verify nudges | `agent/verify_hooks.py` | `max_verify_nudges`, `coding_verify_guidance` |
| Memory manager | `agent/memory_manager.py` | `MemoryManager`, memory provider tool injection |
| Memory provider | `agent/memory_provider.py` | `MemoryProvider` |
| Context engine | `agent/context_engine.py` | `ContextEngine` |
| Governance engine | `governance/governance_engine.py` | `GovernanceEngine`, `GovernanceReport`, `IssueType`, `Severity` |
| Risk | `governance/risk_classifier.py` | `RiskClassifier`, `RiskAssessment`, `RiskLevel` |
| Approval workflow | `governance/approval_workflow.py` | `ApprovalWorkflow`, `ApprovalRequest`, `ApprovalStatus` |
| Decision memory | `governance/decision_memory.py` | `DecisionMemory`, `DecisionRecord` |
| **Knowledge graph** | `governance/knowledge_graph.py` | `KnowledgeGraph`, `Node`, `Edge`, `NodeType`, `RelationshipType` |
| Graph builder | `governance/graph_builder.py` | `GraphBuilder` |
| Architecture query | `governance/architecture_query.py` | `ArchitectureQueryEngine`, `QueryResult` |
| Experience memory | `governance/experience_memory.py` | `ExperienceMemory`, `ExperienceRecord` |
| Dependency intel | `governance/dependency_intelligence.py` | `DependencyIntelligence` |
| Impact analysis | `governance/impact_analysis.py` | `ImpactAnalysisEngine` |
| Recommendation | `governance/recommendation_engine.py` | `RecommendationEngine` |
| Project registry | `governance/project_registry.py` | `ProjectRegistry` |
| Governance integration | `governance/integration.py` | `GovernanceIntegration` |
| Gov plugin | `plugins/governance/` | `__init__.py`, `plugin.yaml`; imports `decision_memory` |
| Memory plugin | `plugins/memory/supermemory` | exists |
| Session context store | `agent/conversation_loop.py` | modular loop |
| Agent SDK `tools/` dir | `tools/*.py` (~40 modules) | concrete builtin tools: `file_tools.py`, `code_execution_tool.py`, `delegate_tool.py`, etc. |

Key persistence fact: verification evidence lives in **`verification_evidence.db`** (sqlite). Governance decision/governance memory do **not** use sqlite directly — they are in-memory/file classes (`decision_memory.py`, `experience_memory.py`) that would need a persistence adapter. **Execution Memory must NOT invent a new DB** — it must reuse `VerificationEvidence`'s sqlite pattern and keep parity with the governance stores' schema.

---

## 1. Execution Layer — purpose

Formalize what already happens informally in `agent/tool_executor.py` + `agent/turn_context.py` into a narrow, explicit layer: **a unit of execution = one tool call with its governing context**. The layer decides **which tool may run, under what risk, with what memory**, then executes and records evidence. It is a *narrow waist* — the Execution Engine replaces ad-hoc checkpoints in the tool loop, nothing else. User-facing behavior unchanged.

Two sacred properties from `AGENTS.md` (read on disk) shape every choice:
1. **Prompt-cache is sacred.** No mid-conversation context mutation → Execution Memory reads/writes happen **outside** the cached prefix, in the sqlite evidence store, never by editing past tool schema.
2. **Capability at edges.** New core model-tools are the expensive exception. Execution Layer adds **no new model-tools**. It wraps existing dispatchers. Risk/approval/decision logic stays in `governance/`.

---

## 3. Module structure (proposed)

```
agent/execution/            # new package (agent/ already contains agent modules)
    __init__.py
    engine.py               # ExecutionEngine          - orchestrator/entry
    context.py              # ExecutionContext         - per-request snapshot
    queue.py                # ExecutionQueue           - ordered awaiting work
    workflow.py             # ExecutionStateMachine    - RUN->GATE->APPROVE->EXEC->RECORD->TERMINAL
    memory.py               # ExecutionMemory          - sqlite evidence store adapter (reuses VerificationEvidence)
    tools/
        orchestrator.py     # ToolOrchestrator         - plans + submits via tool_executor + dispatcher middleware
        contracts.py        # ToolProtocol/what a governance-gated tool must expose
    governance/
        gate.py             # GovernanceGate           - facade over GovernanceEngine + RiskClassifier
        approval.py         # approval-request bridge => tools/approval.py + governance/approval_workflow.py
    recovery.py             # RecoveryInterface        - rehydrate aborted execution from evidence db
    interface.py            # wiring + DI, entry/finalize hooks (few lines)
README.md
tests/
    test_engine.py
    test_state_machine.py
    test_queue.py
    test_gate.py
    test_recovery.py
    test_orchestrator.py
```

Rationale: package is sibling to existing `agent/*` and `tools/`. It imports `agent.turn_context`, `agent.tool_executor`, `tools.registry`, `tools.approval`, `governance.*` — reuse, no duplication. This mirrors how `governance/` already bundles `integration.py` + a plugin.

---

## 4. Core components (each: responsibility, interface, real deps)

### 4.1 ExecutionEngine (`engine.py`)
- **Resp:** entry point. Given a tool-call request → route through gate → schedule → execute → record → return `tool_result` compat object.
- **Interface:** `execute(call, ctx: TurnContext) -> tool_result` ; `submit(call, ctx) -> job_id`; `cancel(job_id)`.
- **Deps (real):** `agent.tool_executor.execute_tool_call_*`, `agent/turn_context.TurnContext`, `agent.tool_dispatch_helpers`.

### 4.2 ExecutionContext (`context.py`)
- **Resp:** immutable snapshot per call: session_key, turn_id, risk, policy, deadline → so state machine is deterministic.
- **Deps (real):** builds from `TurnContext`; session key from `tools/approval.get_current_session_key`.

### 4.3 ExecutionQueue (`queue.py`)
- **Resp:** serial/FIFO pending jobs; respects concurrency budget already in `tool_executor`.
- **Interface:** `enqueue`, `next`, `empty`, `abort_all`.
- **Deps (real):** mirrors `_budget_for_agent` semantics in `tool_executor`; no new budget system.

### 4.4 ExecutionStateMachine (`workflow.py`)
- **Resp:** legal transitions only. States: `PENDING→GATED→APPROVED→EXECUTED←RECOVERING→TERMINATED`.
- **Interface:** `apply(event)`, `allowed(event)`, `dump()`.
- **Deps (real):** enum-like (mirrors `governance/approval_workflow.ApprovalStatus`). Pure, no I/O → trivially testable.

### 4.5 ExecutionMemory (`memory.py`)
- **Resp:** persist evidence of each execution, decisions, outcomes for recovery + analytics.
- **Resp:** **read-only for the live turn** (does not mutate cached context). Written *only into tool result / session db*, exactly like `VerificationEvidence.record_terminal_result`.
- **Deps (real):** reuses `VerificationEvidence` sqlite accessors; optional `verified persisted on disk.
- **Self-correction:** NOT a second context store. It supplements `experience_memory`/`decision_memory` (file/in-memory) with a durable sqlite side; does not replace `MemoryManager`.

### 4.6 ToolOrchestrator (`tools/orchestrator.py`)
- **Resp:** plan tool execution: lookup `ToolRegistry`, apply `ToolRequestMiddleware` chain, execute via `execute_tool_calls_sequential/concurrent`, classify evidence.
- **Deps (real):** `tools/registry.py`, `agent/tool_executor`, `agent/verification_evidence`.

### 4.7 GovernanceGate (`governance/gate.py`)
- **Resp:** before Execution, ask `GovernanceEngine` + `RiskClassifier`; if requires approval → hold in `APPROVED` transition; emit into real approval tool.
- **Deps (real):** `governance/governance_engine`, `risk_classifier`, `approval_workflow`.

### 4.8 ApprovalFlow (`governance/`) - broker
- **Resp:** the bridge that maps a gated call to the **existing** `tools/approval` approval hook + `governance/approval_workflow` record.
- **Deps (real):** `tools/approval.set_current_session_key` → `_fire_approval_hook`, `governance/approval_workflow.ApprovalWorkflow`, records to `DecisionMemory`.

### 4.9 RecoveryInterface (`recovery.py`)
- **Resp:** on crash/abort, re-instantiate from evidence: last executed tool, state, saved decision → produce a resume point (never auto-run dangerous step).
- **Deps (real):** `agent/verification_evidence` for current evidence; `ExecutionMemory` for queued history; `governance/decision_memory` for the approval that had been granted.

---

## 5. Integration points (mapped to real modules)

| Execution Layer | connects to (real file) | how |
|---|---|---|
| Governance Gate | `governance/governance_engine.py`, `risk_classifier.py` | call verdict → next state |
| Decision Memory | `governance/decision_memory.py` | only drains/gates: appends approve(msg); read history for repeat skip |
| Knowledge Graph | `governance/knowledge_graph.py`, `graph_builder` | post-execution, `ExecutionMemory` → feed `GraphBuilder` via `KnowledgeGraph.add_node/add_edge`; do NOT block run |
| Skills | `agent/skill_*` + `plugins/governance` | ToolOrchestrator reads skill-gating from `ToolRegistry._check_fn_cached` (already in registry) — no new hook |
| Tool Executor | `agent/tool_executor.py` | `Orchestrator` calls `execute_tool_calls_sequential/concurrent` |
| Gateway | `gateway/platforms/*`, `tools/approval` | approval flows surface through gateway platforms via existing `_fire_approval_hook`; no new transport |

---

## 6. File structure proposal (summary tree)

Fully covered under §3 (root = `agent/execution/`). Mirror the shape used by `governance/`: package has `__init__.py`, `integration.py`-style `interface.py`, plus a `tests/` dir symmetric to `tests/governance*`.

---

## 7. Implementation order (small verified phases)

Each phase has an **exit gate = real test passing against real modules**. No phase claims success without disk evidence.

- **11.1** Package skeleton: `agent/execution/__init__.py` + empty `interface.py`. Verify: import succeeds headless.
- **11.2** `execution/context.py` + `execution/workflow.py` (state machine, pure). Tests: transition table + immutability.
- **11.3** `execution/queue.py` (FIFO + Concurrent budget mirroring `agent/tool_executor.py`). Tests: ordering, abort.
- **11.4** `execution/engine.py` thin shell delegating one real call then `agent.tool_executor`. Tests: end-to-end executes a real safe tool (`echo`).
- **11.5** `execution/gate.py` + broker routing to `governance/governance_engine.py` · `risk_classifier` and `decision_memory`.
- **11.6** `execution/tools/orchestrator.py`: registry lookup + middleware + concurrent execution. Tests: uses `tools/registry`. Using `ToolRegistry.register`.
- **11.7** `execution/memory.py`: sqlite sidecar reusing `Verification+` accessor wiring; tests: read-only during turn, write-after-tool.
- **11.8** `execution/governance/approval.py` broker: bridge to `tools/approval` + `ApprovalWorkflow` + DecisionMemory.
- **11.9** `execution/recovery.py`: rebuild from evidence; simulated crash test guarantee.
- **11.10** `interface.py` wiring + README check + full `tests/execution/` green. Gate: real `pytest tests/execution` pass.

---

## 8. Acceptance criteria (this design doc)

- [x] No code implementation. (None written — only this `.md`.)
- [x] Design file exists → `EXECUTION_LAYER_DESIGN.md`.
- [x] Every decision names real modules: `agent/tool_executor.py`, `tools/registry.py`, `tools/approval.py`, `governance/*`, `agent/·`.
- [x] Ready for `agent/execution` implementation.

---

## 9. Decisions/trade-offs (documented, honest)

- **Add a new package, no new model-tool:** 身 to `compute` the prompt-cache and "edges at the edge" rules.
- **Execution Memory as sqlite sidecar**, not a new persistence core: matches `VerificationEvidence` DB; avoids violating cache-safety and the narrow waist.
- **Recovery is read-from-evidence only for now:** re-running could re-approve dangerous op; we default to abort → `Terminal state?` `recovery.py` provides the interface but Phase 11 scoped recovery returns a `RECOVER stage`: verify last evidence, then resume processing (no invented rollback engine yet).
- **Knowledge graph is consume-on-write**, never a blocker.

---

## 10. What is intentionally out of scope for Phase 11.0

- No ExecutionLayer model-tools.
- No changes to `agent/tool_executor.py` public semantics — Execution Layer **calls** it, doesn't fork it.
- No new transports/platforms; gateway integration only via existing approval flow.
- No persistent risk-scoring service beyond `governance/'.