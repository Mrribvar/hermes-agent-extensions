# Architecture — Extended Walkthrough

This document goes deeper than `ARCHITECTURE.md`. It explains the boundary
between upstream Hermes Agent and the extensions in this repository, and the
design trade-offs behind each extension.

## 1. The substrate

Hermes Agent (upstream, Nous Research, MIT) provides:

- **The conversation loop** — `run_agent.py` holds the `AIAgent` class, which
  owns the turn loop and calls into `agent/` for everything else.
- **Turn state** — `agent/turn_context.py` builds the per-turn `TurnContext`.
- **Tool dispatch** — `agent/tool_executor.py` runs tool calls; `tools/registry.py`
  holds the registered tools.
- **Verification evidence** — `agent/verification_evidence.py` records every
  terminal result and exposes a status API. The database is
  `verification_evidence.db`.
- **Memory** — `agent/memory_manager.py` and `agent/memory_provider.py`.
- **Gateway** — `gateway/` provides one adapter per platform.

None of these files are in this repository. They are the substrate the
extensions attach to.

## 2. The extension contract

Every extension in this repository follows the same three rules:

### Rule 1 — Additive only

Extensions live in new directories. No upstream file is modified. The only
addition inside the upstream tree is a plugin directory
(`plugins/governance/`), discovered by the upstream plugin loader.

### Rule 2 — Cache-safe

The prompt cache is the most expensive thing in a long conversation. Anything
that mutates past context, swaps the toolset mid-conversation, or rebuilds the
system prompt invalidates the cache and multiplies cost. Extensions therefore:

- never touch the system prompt;
- never edit past messages;
- write only to side stores (`TodoStore`, SQLite memory, JSON stores).

### Rule 3 — Fail-safe

Every cross-boundary call is wrapped in `try/except`. Failures degrade to
`None`, `{}`, or `False` and never block a turn. This is what makes the
extensions safe to leave installed even when dormant.

## 3. Extension by extension

### 3.1 Governance layer (`governance/`)

**Attaches at:** the plugin system. `plugins/governance/plugin.yaml` declares
two hooks — `post_tool_call` and `on_session_end` — so the layer sees every
tool result and every session end.

**Responsibility:** maintain a durable, queryable model of decisions, risks,
approvals, and project state.

**Key modules:**

| Module | Responsibility |
|---|---|
| `governance_engine.py` | Top-level facade |
| `risk_classifier.py` | Assign a risk level to an action |
| `approval_workflow.py` | Hold a medium-risk action for approval |
| `decision_memory.py` | Append-only record of decisions |
| `knowledge_graph.py` | Typed graph of decisions, projects, modules |
| `graph_builder.py` | Cross-reference builder |
| `project_registry.py` | Project metadata + status |
| `dependency_intelligence.py` | Who depends on whom |
| `impact_analysis.py` | Blast radius of a change |
| `recommendation_engine.py` | Turn analysis into recommendations |
| `architecture_query.py` | Query the graph by architecture question |

**Execution sub-layer** (`governance/execution/`) — a separate, earlier
execution engine (`execution_engine.py`, `state_machine.py`,
`tool_orchestrator.py`) that predates `agent/execution/`. It has no caller in
the live runtime.

### 3.2 Experience & Learning (`agent/experience/`)

**Attaches at:** `finalize_turn` (`turn_finalizer.py`) and
`conversation_loop.py`.

**Responsibility:** close the loop between verification and learning.

**The chain:**

1. A tool run records a terminal result via the upstream
   `verification_evidence` module. The database gets a new event.
2. At the end of the turn, `finalize_turn` reads the current
   `verification_status`. If the latest verification event is fresh (not
   stale) and passed, the outcome is `VERIFIED`.
3. `lifecycle_learning.observe_lifecycle` receives the turn-end event with the
   verification outcome and extracts a structured experience.
4. `extractor.py` turns the turn into an `ExperienceRecord`.
5. The record is appended to `experiences.json`.
6. On a later turn, `recall_integration.py` can recall the most relevant prior
   experience and inject it as advisory context (never as user input, never as
   verification evidence).

**Why it is safe:** the recall is marked as advisory in the prompt text, is
gated on confidence ≥ 0.7 and on `result == success`, and never overrides the
model's decision.

### 3.3 Execution Layer (`agent/execution/`)

**Attaches at:** the tool dispatch point — *intended*, not yet wired.

**Responsibility:** turn a single tool call into an explicit, governed,
persistent lifecycle.

**The lifecycle:**

```
CREATED → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
                             │                       ├ FAILED
                             │                       └ CANCELLED
                             └ REJECTED              └ PAUSED → RETRYING
```

**The nine components:**

| Component | File | Responsibility |
|---|---|---|
| `ExecutionCoordinator` | `interface.py` | End-to-end entry point |
| `ExecutionContext` | `context.py` | Immutable per-execution snapshot |
| `ExecutionQueue` | `queue.py` | Priority FIFO, thread-safe |
| `ExecutionEngine` | `engine.py` | Lifecycle coordinator |
| `GovernanceGate` | `governance_gate.py` | Risk/approval authority |
| `ToolOrchestrator` | `orchestrator.py` | Resolve + delegate tool |
| `ExecutionMemory` | `memory.py` | SQLite persistence |
| `ExecutionRecovery` | `recovery.py` | Recommendation-only |
| `ExecutionStateMachine` | `workflow.py` | Legal transitions |

**Why it is dormant:** nothing in `run_agent.py`, `cli.py`, or `gateway/run.py`
calls `ExecutionCoordinator.submit()`. The layer is complete and tested but
sits beside the live loop rather than inside it. This is deliberate — the
wiring was deferred until the layer's contract was stable.

### 3.4 Planner MVP (`agent/planning.py`)

**Attaches at:** `turn_context.py` (a hook after context is built).

**Responsibility:** derive a small, ordered plan from a goal without an LLM
call.

**Design:**

- Fully deterministic — no network, no model call, no I/O beyond the
  `TodoStore`.
- Gated on `planning.enabled` (default `false`).
- Skips trivial prompts.
- **Seed-only ownership:** if the `TodoStore` is not empty, the planner returns
  `None` immediately. The model is the permanent owner of the list; the planner
  may only seed an empty one.
- Writes only into the `TodoStore`, never into the system prompt.

**Why it is dormant:** the hook is present but the flag is `false` in the
shipped config, so the default runtime behavior is unchanged.

### 3.5 HERALD Intelligence (`herald/`, `governance/decision_*`)

**Attaches at:** `ExecutionCoordinator.submit()` — which is not called.

**Responsibility:** a self-observing decision loop. Each decision is recorded
before execution, evaluated after, and used to generate a feedback signal.

**Phases:**

| Phase | Module | Purpose |
|---|---|---|
| 010 | `pattern_context.py` | Detect patterns from the codebase |
| 011 | `decision_performance_engine.py`, `decision_store.py`, `decision_feedback_loop.py` | Record, evaluate, score decisions |
| 012 | `intelligence_integration.py` | Bridge into the Execution Layer |
| 013 | `intelligence_store.py`, `intelligence_persistence.py` | Persist the loop across sessions |

**Why it is dormant:** because the Execution Layer is not wired, the bridge
into it is not called. The phases are documented as FROZEN at checkpoint 013.5.

### 3.6 Business Bridge (`agent/business/`)

**Attaches at:** `ExecutionMemory` (the Execution Layer's persistence module).

**Responsibility:** a small entity model (Product, Category, Customer,
BusinessEntity) with an additive bridge into `ExecutionMemory`. The bridge
writes business events into the same SQLite store the Execution Layer uses.

**Why it is partial:** the bridge works, but because the Execution Layer is not
wired into the live loop, the bridge is not exercised during normal operation.

### 3.7 Freestyle adapter (`freestyle_adapter/`)

**Attaches at:** the execution boundary — as an alternative executor.

**Responsibility:** allow a workload to run on an external Freestyle VM instead
of locally. The adapter:

- lives in its own directory and never touches upstream;
- reads its API key from `.env` and never logs or copies it;
- exposes `health_check`, `create_vm`, `execute`, `pause`, `resume`, `cleanup`.

**Why it is not verified:** the adapter's own `manifest.json` records that VM
creation, command execution on a VM, and the pause/resume lifecycle have never
been attempted. Only the docs-connectivity path (`curl` against the Freestyle
docs endpoint) has been tested.

### 3.8 Operational tooling (`skills/`, `docs/`)

Three original skills and a set of architecture/phase reports. The skills are
active — they are loaded and used by the agent during real sessions.

## 4. Design trade-offs

**Why so much is dormant.** Every dormant layer was built to a real design
contract and tested, but the wiring step was deliberately kept last. This
avoids changing default runtime behavior before the contract was proven.

**Why HERALD wasn't wired through the Execution Layer.** The Execution Layer
was intended as HERALD's caller. Since the Execution Layer is not on the live
path, HERALD has no caller. The correct fix is to wire the Execution Layer
first, then let HERALD ride on it — not to add a separate HERALD caller.

**Why the planner writes only to the TodoStore.** The system prompt and the
past conversation must remain byte-stable to preserve the prompt cache. The
TodoStore is a side store that is not part of the prompt prefix, so writing to
it is safe.

**Why the Execution Layer adds no new core tool.** Every model tool is sent on
every API call. Adding a tool costs every user on every turn. The Execution
Layer wraps the existing tool dispatch point instead.

## 5. What a reader should take away

- The upstream Hermes Agent is the substrate; this repository is a set of
  attachments.
- Two attachments are active: the governance plugin and the learning loop.
- The rest are implemented, tested, and dormant — by design, waiting on a
  wiring step that is documented in `PROJECT_STATUS.md`.
- Nothing here modifies upstream, and nothing here claims ownership of it.