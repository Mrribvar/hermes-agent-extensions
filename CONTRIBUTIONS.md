# Contributions

A chronological timeline of the extension work in this repository. Every entry
is dated and names the artifacts it produced; nothing is listed without a
corresponding file in the tree.

**Timeframe:** August 2026 – September 2026
**Context:** Additive work on top of the upstream Hermes Agent runtime.

---

## Phase 7 — Governance Layer foundation
**Dates:** 2026-08-03 → 2026-08-04

Designed and implemented the first governance modules:

- `governance/governance_engine.py`
- `governance/risk_classifier.py`
- `governance/approval_workflow.py`
- `governance/project_registry.py`
- `governance/dependency_intelligence.py`
- `governance/impact_analysis.py`
- `governance/recommendation_engine.py`
- `governance/architecture_query.py`
- `governance/api_design.md`

Also produced `governance/knowledge_graph.py`, `governance/graph_builder.py`,
`governance/decision_memory.py`, and the `governance/__init__.py` export
surface. The design constrained the layer to read-only: no POST/PUT/DELETE and
no autonomous action until the layer was validated.

**Evidence:** file dates on 2026-08-03/04; the `governance/__init__.py` docstring
names the layer and exports the 16 classes.

---

## Phase 8 — Governance checkpoint
**Date:** 2026-08-03

`governance/checkpoint_phase8.md` records the checkpoint that marks governance
as complete and hands off to the intelligence phase. It documents the install
layout and the module state at that point.

**Evidence:** `governance/checkpoint_phase8.md`.

---

## Phase 10.7 — Production readiness
**Date:** 2026-08-04

Bridged the governance package into the Hermes plugin system:

- Registered `governance` as a first-class plugin with hooks
  `post_tool_call` and `on_session_end`.
- Added `governance` and `governance.*` to the packaging includes so the plugin
  loader discovers the package.
- Verified 15 tests pass on Python 3.13.

**Evidence:** `docs/PRODUCTION_READINESS_10.7.md`; `plugins/governance/plugin.yaml`
(that plugin lives in the source tree, not in this repository).

---

## Phase 10.8.2 / 10.8.3 — Memory & state health audit
**Date:** 2026-08-04

Ran a read-only audit of the runtime state and memory layer, and produced a
state-hygiene report. The audit found no corruption, no critical issues, and
two medium-severity data-quality issues (session-dump accumulation and a high
orphan rate in the knowledge graph).

**Evidence:** `docs/HEALTH_AUDIT_10.8.2.md`; `docs/STATE_HYGIENE_10.8.3.md`.

---

## Phase 11 — Execution Layer
**Dates:** 2026-08-05 → 2026-08-06

Designed and implemented a complete, additive execution layer under
`agent/execution/`:

- `workflow.py` — 9-state machine.
- `context.py` — immutable per-execution snapshot.
- `queue.py` — priority FIFO, thread-safe.
- `engine.py` — lifecycle coordinator.
- `governance_gate.py` — risk/approval authority.
- `orchestrator.py` — tool resolution + delegation.
- `memory.py` — SQLite-backed execution memory.
- `recovery.py` — recommendation-only recovery.
- `interface.py` — `ExecutionCoordinator` end-to-end entry point.

269 tests, 0 failures, no circular dependencies, 34 public exports.

**Evidence:** `docs/EXECUTION_LAYER_ARCHITECTURE.md`,
`docs/EXECUTION_LAYER_DESIGN.md`, `docs/EXECUTION_LAYER_FINAL_REPORT.md`,
`docs/EXECUTION_LAYER_README.md`, plus the code in `agent/execution/` and the
tests in `tests/agent/execution/`.

**Honest caveat:** the layer is not wired into the live runtime. This is
documented in `PROJECT_STATUS.md`.

---

## Phase 12 — AgentCore intelligence integration
**Dates:** 2026-08-06

Connected the pattern-intelligence and decision-performance layers into the
execution path via an `IntelligenceBridge`, and produced the integration audit.

**Evidence:** `herald/intelligence_integration_audit.md`,
`agent/execution/intelligence_integration.py`.

---

## Phase 13 — Intelligence persistence
**Date:** 2026-08-06

Added an append-only, versioned store for intelligence data plus a connector
into the Agent Memory Layer.

**Evidence:** `herald/intelligence_persistence_layer.md`,
`herald/decision_performance_intelligence.md`.

---

## Phase 13.1 / 13.2 — Business bridge
**Date:** 2026-08-05 → 2026-08-06

Built the business entity model (`agent/business/`) and its bridge into
`ExecutionMemory`.

**Evidence:** `docs/PHASE_13.2_BUSINESS_BRIDGE_REPORT.md`, `agent/business/`.

---

## Phase 14.0 — Experience intelligence layer
**Dates:** 2026-08-09 → 2026-08-15

Built `agent/experience/` — the layer that observes turn endings, extracts an
experience record, evaluates it, and makes prior experiences recallable:

- `listener.py` — subscribes to turn-end events.
- `evaluator.py` — scores experiences.
- `extractor.py` — turns a turn into a structured record.
- `lifecycle_learning.py` — the hook that runs after each turn.
- `recall_integration.py` — pre-turn recall of prior experiences.

This is the layer that makes the Verification → Learning chain observable.

**Evidence:** the code in `agent/experience/`, the tests in
`tests/agent/experience/`, and a live `verification_evidence.db` plus
`experiences.json` showing real records including a `VERIFIED` outcome.

---

## HERALD Intelligence freeze
**Date:** 2026-08-06

Froze Phases 010–013 at checkpoint 013.5, documenting the frozen file
inventory, test baseline (301 passing), known limitations, technical debt, and
risks in `herald/HERALD_INTELLIGENCE_FREEZE.md`.

**Evidence:** `herald/HERALD_INTELLIGENCE_FREEZE.md`,
`herald/HERALD_INTELLIGENCE_BACKUP_METADATA.json`.

---

## Freestyle adapter
**Date:** 2026-09-10

Built a non-destructive adapter scaffold for running workloads on external
Freestyle VMs. The design keeps the adapter as its own directory, reads its
key from `.env`, and never touches upstream Hermes.

**Evidence:** `freestyle_adapter/` — the phase reports
(`HERMES_PRIME_PHASE3_REPORT.md` … `HERMES_PRIME_PHASE6_REPORT.md`), the
contracts (`EXECUTOR_CONTRACT.md`, `ROLLBACK.md`), and the code
(`freestyle_executor.py`, `health_check.py`). The adapter's own manifest
records `vm_creation: NOT ATTEMPTED` — the VM lifecycle has not been exercised.

---

## Planner MVP and seed guard
**Dates:** 2026-09-16

Implemented `agent/planning.py`: a deterministic planner that turns a goal into
steps and merges them into the session `TodoStore`, guarded so the planner only
seeds an empty list and never overwrites a model-owned one. Wired into
`turn_context.py` behind the `planning.enabled` flag (default `false`).

**Evidence:** `agent/planning.py`; the `maybe_plan_turn` entry point and the
`store.has_items()` guard are both present in the code.

---

## Original skills
**Dates:** 2026-08 → 2026-09

Wrote three original skills that ship with this repository:

- `skills/persian-writing/` — Persian orthography, register, ZWNJ rules,
  document layout, plus deterministic cleanup and lint scripts.
- `skills/reelo/` — a ten-role think tank plus a mandatory edit-plan step for
  turning an existing video into a reel.
- `skills/freestyle-docs/` — a reference for when and how to use Freestyle VMs.

**Evidence:** `skills/`.

---

## How the phases relate

The phases were not a single project; they were independent extensions that
share the same design contract (additive, fail-safe, cache-safe). Some of them
connect to each other:

- Phase 11 (Execution Layer) was intended as the caller for the HERALD phases
  (10–13). Since the Execution Layer is not wired into the live runtime, HERALD
  is dormant.
- Phase 14.0 (Experience) attaches directly to the upstream `turn_finalizer`
  and is the one extension that is fully active.

This dependency is visible in `ARCHITECTURE.md`.