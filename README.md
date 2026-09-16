# Hermes Agent — Extensions & Architecture Work

**Additive extensions, experiments, and operational tooling built on top of
[Hermes Agent](https://github.com/NousResearch/hermes-agent).**

---

## Upstream Attribution

> **Hermes Agent is an open-source project by [Nous Research](https://nousresearch.com),
> released under the MIT License.**
>
> This repository contains **only** additive extensions, experiments,
> architecture work, and operational tooling developed on top of the upstream
> Hermes Agent. **No upstream source code is included here** — not the core
> agent loop, CLI, gateway, tools, UI, or the upstream verification subsystem.
> The upstream project is referenced by link and described at the boundary
> where these extensions attach to it.
>
> Nothing in this repository claims ownership of Hermes Agent.

---

## What is this?

A collection of independent extension layers and experimental modules that
add **governance, execution control, learning loops, and planning** on top of
the upstream Hermes Agent runtime. Each module is designed to be additive:
it introduces new files under new directories and does not modify any upstream
file.

The work spans roughly **August–September 2026** and was developed against a
real single-node Hermes deployment used for day-to-day operations.

This repository exists to document and share that work — both as a reference
for anyone building on Hermes and as evidence of engineering contribution for
evaluation purposes.

---

## Relationship to Hermes Agent

Hermes Agent provides the agent core, the CLI, the messaging gateway, the tool
registry, the memory system, the skill system, and the verification-evidence
subsystem. Those are the **substrate**.

This repository is the **extension layer** on top of that substrate:

- It imports from upstream (for example `tools.registry`, `agent.tool_executor`,
  `agent.verification_evidence`) but does not fork or modify it.
- It is installed alongside a Hermes checkout, not as a replacement for it.
- It is dormant by default where it could change runtime behavior (feature flags
  default to `false`).
- Where a module is not currently reachable from the live runtime path, that is
  stated explicitly in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

---

## Motivation

The upstream Hermes Agent is a general-purpose runtime. Running it in a
production-like personal-operations setting surfaced a set of concerns that
general-purpose agents often leave implicit:

- **Who approved this action, and on what evidence?** → Governance layer.
- **Did the work actually get verified, or was it just claimed?** → Verification
  → Learning pipeline.
- **Can a tool call be queued, gated, retried, and recovered deterministically?**
  → Execution Layer.
- **Can a plan be derived without an LLM call and without polluting the prompt
  cache?** → Planner MVP.
- **Where should an autonomous workload actually run — locally, or in an
  isolated VM?** → Freestyle adapter.

Each extension answers one of those questions. None of them grow the core.

---

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full diagram (Mermaid) showing
how the extension layer sits on top of upstream Hermes Agent, and
[`docs/architecture.md`](docs/architecture.md) for the layer-by-layer walkthrough.

Short version:

```
Nous Research
    │
    ▼
Hermes Agent (upstream, MIT)
    ├── Core Agent        (run_agent.py, agent/)
    ├── Tools             (tools/, toolsets.py)
    ├── Gateway           (gateway/, 20+ platform adapters)
    ├── Memory            (memory_manager, memory_provider)
    └── Verification Evidence  (agent/verification_evidence.py)
              │
              ▼
    Extensions (this repo)
        ├── Governance             governance/, governance/execution/
        ├── Experience & Learning  agent/experience/
        ├── Execution Layer        agent/execution/
        ├── Planning               agent/planning.py
        ├── Business Bridge        agent/business/
        ├── HERALD Intelligence    herald/ + governance/decision_*
        └── Operational Tooling    skills/, docs/, scripts/
```

---

## Custom Contributions

### Governance Layer

`governance/` — Decision Memory, Risk Classification, Approval Workflow,
Knowledge Graph, Project Registry, Impact Analysis, Recommendation Engine,
Architecture Query. Exposed to the runtime through a plugin
(`plugins/governance`) that hooks `post_tool_call` and `on_session_end`.

**Status:** Active (via plugin) — see `PROJECT_STATUS.md`.

### Verification → Learning

`agent/experience/` — a closed loop from a canonical verification event (a
pytest run recorded by the upstream `verification_evidence` subsystem) through
`finalize_turn` → `lifecycle_learning` → a persisted `experience` record tagged
with the verification outcome.

**Status:** Active, evidence-backed — real `VERIFIED` records exist on disk
during development.

### Execution Layer

`agent/execution/` — an explicit, governed, persistent execution path:
`ExecutionCoordinator` → `ExecutionContext` → `ExecutionQueue` →
`ExecutionEngine` → `GovernanceGate` → `ToolOrchestrator` →
`ExecutionMemory` → `ExecutionRecovery`. Nine-state lifecycle, priority FIFO
queue, SQLite-backed memory, recovery-as-recommendation.

**Status:** Implemented and tested (269 passing tests in the phase report), but
**not currently wired into the live agent loop**. See `PROJECT_STATUS.md`.

### Planning

`agent/planning.py` — a deterministic, LLM-free planner that turns a goal
string into an ordered list of `Step` objects and merges them into the existing
per-session `TodoStore`, guarded so the model retains permanent ownership of the
list (`seed-only` merge).

**Status:** Feature-flagged, dormant by default. The hook exists in
`turn_context.py`; the flag is `false` in the shipped config.

### HERALD Intelligence

`herald/` + `governance/decision_*` + `governance/intelligence_*` — Pattern
Intelligence (Phase 010), Decision Intelligence (Phase 011), Execution
Integration (Phase 012), and Persistence Layer (Phase 013). The design goal was
a self-observing decision loop; the phases are documented as FROZEN and are
currently dormant because their runtime entry point
(`ExecutionCoordinator.submit()`) is not called from the live loop.

**Status:** Frozen / dormant.

### Business Bridge

`agent/business/` — a small entity model (Product, Category, Customer,
BusinessEntity) with an additive bridge into `ExecutionMemory`. Intended to
give the Execution Layer a business-domain view without coupling the two.

**Status:** Implemented / partially integrated.

### Freestyle Adapter

`freestyle_adapter/` — a non-destructive adapter scaffold for running workloads
on external Freestyle VMs. Security-first: the key lives in `.env`, is never
logged, and is never copied into the VM.

**Status:** Adapter scaffold; VM lifecycle not yet verified.

### Operational Tooling

`skills/` — three original skills (`reelo`, `persian-writing`,
`freestyle-docs`). `docs/` — architecture and phase reports. Additional
maintenance scripts live outside the repository (they contain deployment-
specific paths) and are described in `docs/operations.md` conceptually, not
shipped.

---

## Upstream vs. Custom

| Component | Ownership | Runtime status |
|---|---|---|
| Core agent loop, CLI, gateway, tools, UI | **Upstream (Nous Research)** | Active |
| `verification_evidence.py` (evidence DB + API) | **Upstream (Nous Research)** | Active |
| `governance/` + `governance/execution/` | Custom | Active (via plugin) |
| `agent/experience/` + Verification→Learning wiring | Custom (on upstream substrate) | Active, evidence-backed |
| `agent/execution/` | Custom | Implemented — dormant (not wired) |
| `agent/planning.py` | Custom | Feature-flagged — dormant |
| HERALD Intelligence (Phases 010–013) | Custom | Frozen — dormant |
| `agent/business/` | Custom | Partial |
| `freestyle_adapter/` | Custom | Not verified (scaffold) |
| `skills/` (reelo, persian-writing, freestyle-docs) | Custom | Active |

Full table with evidence in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

---

## Current Status

**This is an engineering repository, not a released product.**

- No released version.
- No CI pipeline yet.
- No PyPI / package distribution.
- No published benchmarks or users.

What it does have: real, tested code with a documented architectural boundary
against upstream, plus an honest status table that distinguishes *active* from
*implemented-but-dormant* from *scaffolded*.

See [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

---

## Known Limitations

1. **Upstream dependencies.** Some modules import from upstream
   (`tools.registry`, `agent.tool_executor`, `agent.verification_evidence`,
   `hermes_constants`). They cannot be imported in isolation — they must be
   placed alongside a Hermes Agent checkout.
2. **Execution Layer not wired.** The layer is tested but not called from
   `run_agent.py` / `gateway/run.py`.
3. **HERALD dormant.** Phases 010–013 are frozen and their entry point is not
   invoked at runtime.
4. **Freestyle VM lifecycle unverified.** Only the docs-connectivity path is
   tested; VM create/exec/pause/resume have never been exercised end to end.
5. **No CI, no published tests baseline.** Tests are copied from the source
   tree; running them requires the upstream Hermes checkout.
6. **No packaging.** No `pyproject.toml` / `setup.py` for the extensions
   themselves yet.

---

## Roadmap

Short and honest — this is what would make the repository usable to an outside
developer, in order:

1. **Wire the Execution Layer into the live runtime** behind a feature flag,
   with an end-to-end test that exercises the real path.
2. **Package the extensions** as an installable plugin for Hermes Agent, with a
   documented install flow.
3. **Add CI** that runs the copied tests against a pinned upstream Hermes
   checkout.
4. **Unblock HERALD** by giving it a real caller — either through the Execution
   Layer once wired, or as a standalone CLI command.
5. **Prove the Freestyle adapter** end to end (VM create → exec → pause →
   resume → cleanup) against a real Freestyle account.

Nothing in this list is committed to a date.

---

## Security

All extensions follow the upstream Hermes security principles and add no
telemetry. The full policy, the five pre-publish checks, and the definition of
what must never enter the repository are in [`SECURITY.md`](SECURITY.md).

Key points:

- No `.env`, keys, tokens, or credentials in the tree.
- No VPN or infrastructure artifacts.
- No personal memory files or runtime databases.
- No absolute paths tied to a specific deployment.

---

## Development

Because the modules import from upstream, development is easiest inside a
working Hermes Agent checkout:

```bash
# 1. Have a Hermes Agent checkout available (upstream, MIT).
#    See https://github.com/NousResearch/hermes-agent for install instructions.

# 2. Clone this repository alongside it.
git clone <this-repo> ~/hermes-agent-extensions

# 3. Symlink or copy the extension directories into the Hermes tree
#    (e.g. as a plugin, once packaging is done), or add this repo to
#    PYTHONPATH when running tests from within the Hermes checkout.
```

Running the copied tests requires the upstream tree:

```bash
cd /path/to/hermes-agent
python -m pytest /path/to/hermes-agent-extensions/tests/ -q
```

The tests under `tests/` are copied verbatim from the source tree where they
were written; they depend on the upstream modules they exercise.

### Layout

```
hermes-agent-extensions/
├── README.md               ← this file
├── PROJECT_STATUS.md       ← honest status table
├── ARCHITECTURE.md         ← Mermaid architecture diagram
├── CONTRIBUTIONS.md        ← timeline of work
├── SECURITY.md             ← security policy + publish checks
├── LICENSE                 ← MIT for this repo
├── .gitignore
├── governance/             ← governance layer + execution sub-layer
├── agent/
│   ├── experience/         ← Verification → Learning
│   ├── execution/          ← Execution Layer
│   ├── business/           ← Business Bridge
│   └── planning.py         ← Planner MVP
├── herald/                 ← HERALD intelligence docs
├── freestyle_adapter/      ← VM adapter scaffold
├── skills/                 ← original skills
├── docs/                   ← extended architecture docs + phase reports
└── tests/                  ← tests for the custom modules
```

---

## Project Philosophy

Three principles shaped every decision in this repository, and they are the
same principles that make the repository honest:

**1. No Evidence = No Claim.**
Every status label, every "active", every "verified" in these documents is
backed by a file on disk, a test run, or an observable runtime trace. Where
there is no evidence, the label is `Dormant` or `Not Verified` — never
"probably works".

**2. Additive, Never Invasive.**
No upstream file is modified. No extension swaps the system prompt, mutates
past context, or rebuilds the toolset mid-conversation. The upstream prompt
cache is treated as sacred, and every extension either avoids the cached
prefix entirely or runs outside the conversation loop.

**3. Capability Lives at the Edges.**
The core agent is a narrow waist. Every extension here is a new directory, a
new file, or a new plugin — never a new core tool. This keeps the substrate
small and keeps the extensions replaceable.

---

## Links

- Upstream Hermes Agent: <https://github.com/NousResearch/hermes-agent>
- Upstream documentation: <https://hermes-agent.nousresearch.com/docs>
- Nous Research: <https://nousresearch.com>

## License

MIT — see [`LICENSE`](LICENSE). This applies to the extensions in this
repository only. Hermes Agent itself is separately licensed by Nous Research
under MIT.