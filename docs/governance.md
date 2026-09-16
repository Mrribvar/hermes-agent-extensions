# Governance Layer

**Location:** `governance/` (root modules) + `governance/execution/` (an
earlier execution sub-layer).
**Ownership:** Custom — additive on top of upstream Hermes Agent.
**Runtime:** Partially active (through the plugin).

## Purpose

Keep a durable, queryable model of what the agent decided, what risk it
carried, and what happened as a result. The governance layer is
**read-only** by design: it observes and records; it does not act.

## Modules

### Core

| Module | Responsibility |
|---|---|
| `governance_engine.py` | Top-level facade; wires the other modules together |
| `risk_classifier.py` | Assigns a risk level (SAFE / LOW / MEDIUM / HIGH) to an action |
| `approval_workflow.py` | Holds a MEDIUM-risk action for explicit approval before it runs |
| `decision_memory.py` | Append-only record of decisions with rationale and outcome |

### Graph & analysis

| Module | Responsibility |
|---|---|
| `knowledge_graph.py` | Typed graph of decisions, projects, modules, and configs |
| `graph_builder.py` | Builds cross-reference edges between graph nodes |
| `architecture_query.py` | Answers architecture questions by querying the graph |
| `dependency_intelligence.py` | Tracks who depends on what |
| `impact_analysis.py` | Estimates the blast radius of a proposed change |
| `recommendation_engine.py` | Turns analysis into concrete recommendations |

### Registry

| Module | Responsibility |
|---|---|
| `project_registry.py` | Project metadata, status, dependencies, health |

## How it attaches to Hermes

The layer is exposed to the runtime through a plugin:

```
plugins/governance/
├── __init__.py       # registers the hooks
└── plugin.yaml       # declares the hooks and describes the plugin
```

The plugin declares two hooks:

- **`post_tool_call`** — after every tool call, the layer can observe the
  result and update its memory.
- **`on_session_end`** — at the end of a session, the layer syncs its state to
  disk (the Knowledge Graph and decision records).

This is the only place where an extension enters the upstream tree — and it
does so as a plugin the upstream loader discovers, not as a modification of any
upstream file.

## Data model

The layer maintains a set of stores under the user's `HERMES_HOME`:

- `decisions.json` — decision records
- `knowledge_graph.json` — graph nodes and edges
- `projects.json` — project registry entries
- `experiences.json` — the store shared with the learning loop

These files are user data. **They are not shipped in this repository** — see
`.gitignore`, which excludes them explicitly.

## Safety properties

1. **Read-only by design.** The layer never mutates the agent's behavior. It
   records, classifies, and recommends.
2. **Fail-safe.** Every public call is wrapped so that a failure in the
   governance layer cannot block a turn.
3. **No autonomous action.** There is no POST/PUT/DELETE, no auto-approval,
   and no execution path in the layer. The design constraint is written into
   `governance/api_design.md`.

## Execution sub-layer (`governance/execution/`)

This is an **earlier** execution engine that predates `agent/execution/`. It
contains:

- `state_machine.py` — a 9-state lifecycle
- `execution_engine.py` — lifecycle controller
- `execution_queue.py` — FIFO queue
- `execution_memory.py` — persistence
- `tool_orchestrator.py` — tool resolution
- `context.py`, `events.py`, `recovery.py`, `governance_integration.py`

**Runtime: dormant.** No caller in the live runtime reaches this sub-layer. It
is included because it is part of the governance work and because a reader may
want to compare it with the newer `agent/execution/` implementation.

## Status

- **Partially active** — the plugin is registered; the hooks fire.
- The full module surface (graph analysis, recommendation, architecture query)
  is available but only exercised when something calls it.

See `PROJECT_STATUS.md` for the exact label and the evidence behind it.