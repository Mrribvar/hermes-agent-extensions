# Intelligence Persistence Layer — Phase HERALD-INTELLIGENCE-013

## Goal

Make decision-performance intelligence durable. Prior phases (010–012)
recorded decisions, evaluations, feedback, and strategy metrics **in memory**
and in the decision store's own JSON file. This phase adds a dedicated,
append-only, versioned **IntelligenceStore** and a **connector** that bridges
the live decision pipeline into it and into the Agent Memory Layer — all
additively, fail-safely, and without touching any existing Phase 010/011 code.

## Architecture

```
DecisionPerformanceEngine
        |  (existing store + DecisionFeedbackLoop)
        v
IntelligenceStore  <----------------- IntelligencePersistenceConnector
   |  (append-only, versioned JSON)
   v
Agent Memory Layer (ExecutionMemory)   <- additive metadata on existing record
```

- **DecisionPerformanceEngine** (Phase 011) — *unchanged*, read-only source.
- **IntelligenceStore** (this phase) — append-only, versioned, fail-safe JSON
  store with 5 isolated sections.
- **IntelligencePersistenceConnector** (this phase) — reads decisions,
  evaluations, feedback, metrics, and confidence from the engine/loop and
  appends them to the store; optionally attaches a summary into an existing
  Agent Memory Layer record without altering its other fields.

## Data Model

The store persists a single JSON document:

```json
{
  "format_version": 1,
  "created_at": "...",
  "updated_at": "...",
  "sections": {
    "decisions":            [],
    "evaluations":          [],
    "feedback":             [],
    "strategy_metrics":     [],
    "confidence_history":   []
  }
}
```

Each record is stored as a dict captured by `to_dict()`. Phase 013 is entirely
`additive` — nothing about the stored model changed prior behavior.

## Storage Location

All persistence is additive. The store defaults to
`Path.home()/.hermes/governance/intelligence.json` but honors an explicit
`storage_path` (used by tests to isolate instances).

## The Five Sections

| Section             | Stores                                                |
|---------------------|-------------------------------------------------------|
| `decisions`         | strategy, confidence, risk, expected/actual outcome   |
| `evaluations`       | post-execution evaluation (is_success, accuracy, ...)  |
| `feedback`          | DecisionFeedback signal (improvement_signal, type)     |
| `strategy_metrics`  | per-strategy performance metric snapshots              |
| `confidence_history`| confidence values recorded over time                   |

## Guarantees

### Additive only

- New files only (`governance/intelligence_store.py`,
  `governance/intelligence_persistence.py`, tests, docs).
- No existing file modified; frozen Phase 010/011 components untouched.

### Append-only

- Records are only ever appended. No public API edits or deletes a record.
- `read_*` returns deep copies so callers cannot mutate stored state.

### Fail-safe

- Every public method degrades to `False`/`None`/`{}`/`[]` on error instead of
  raising; a corrupt or unreadable store file logs a warning and starts fresh.
- The connector never reads from the engine's own store to write; it only
  reads via the engine's public API, so it can't corrupt the live pipeline.
- A `enabled=False` connector is a total no-op.

### Migration-safe

- The on-disk doc carries a `format_version`.
- `register_migration(from_version)` + `_MIGRATIONS` let older dumps migrate
  run forward additively (v0 -> v1 handled).
- A **newer** on-disk version than supported is opened read-only, flagged via
  `format_errors`, and never overwritten or destroyed.
- Corrupt / non-dict / missing files start fresh without raising.

### Restart continuity

- A brand-new store instance at the same path reloads prior records.
- Append-only trail is ordered across restarts: `signals[0]` is the first
  session's signal, `signals[-1]` the last.

## Integration: Agent Memory Layer

`IntelligencePersistenceConnector.attach_to_execution_memory(memory, exec_id, summary)`
performs a read-modify-write on an existing execution record:

```python
# record.metadata["intelligence"] = {**summary, "attached_at": <utc>}
record.metadata["intelligence"] = {**existing_intelligence, **summary, "attached_at": now}
```

All pre-existing metadata is preserved; the intelligence summary is merged
under the `intelligence` key only. The real `ExecutionMemory` was verified:
an execution record's `task_id`/state survived, and the intelligence dict was
attached.

## Fail-safe execution integration

The connector is designed to sit alongside the existing
`IntelligenceBridge` (Phase 012) pipeline. Enabling persistence is purely a
matter of wiring:

```python
store       = IntelligenceStore()               # appends to ~/.hermes/...
connector   = IntelligencePersistenceConnector(store=store)
connector.sync_from_engine(bridge._performance_engine)
connector.sync_feedback_from_loop(bridge._feedback_loop)
```

No execution code needs to change; persistence is additive and cannot raise.

## Tests

`tests/governance/test_intelligence_persistence.py` (33 tests):

- Append-only semantics (7)
- Restart continuity (4)
- Migration safety (8)
- Connector: engine -> store -> memory layer (14)
- End-to-end: full session + restart, corrupt-store resilience (2)

## Acceptance Criteria (this phase)

- Decision performance data persists across sessions — **done**
- Append-only intelligence storage — **done** (5 isolated append-only sections)
- Stores decisions / evaluations / feedback / strategy metrics / confidence — **done**
- Connects to Agent Memory Layer — **done** (verified against real ExecutionMemory)
- Never blocks execution — **done** (fail-safe, additive, try/except on all calls)
- No regression — **done** (frozen modules untouched; regression suite green)

## Next recommended phase

Phase 014: **Restart-time warm-up** — a `restore`/`warmup` API that reloads the
persisted store into the live bridge at boot so decisions made yesterday
inform today's guidance immediately, plus optional capped-dedupe for
unbounded growth.