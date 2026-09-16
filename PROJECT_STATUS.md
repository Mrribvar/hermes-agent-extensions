# Project Status

**Last updated:** 2026-09-16
**Repository:** Hermes Agent — Extensions & Architecture Work
**Upstream:** [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT License)

---

## How to read this file

The **Runtime** column distinguishes five states, and they are not
interchangeable:

| Label | Meaning |
|---|---|
| **Active** | Reachable from the live agent loop and exercised during real use. |
| **Partially Active** | A subset of the module is reachable; the rest is not. |
| **Implemented but Dormant** | Code exists, tests pass, but nothing in the live runtime calls it. |
| **Frozen / Dormant** | Deliberately frozen at a checkpoint; the entry point is not invoked. |
| **Partially Integrated** | Some callers exist; the full intended path is not connected. |
| **Not Verified** | Code exists but the critical path has never been exercised end to end. |
| **Upstream** | Belongs to Nous Research's Hermes Agent, not to this repository. |

---

## Status table

| Component | Ownership | Runtime | Evidence |
|---|---|---|---|
| Hermes Agent core loop (`run_agent.py`, `agent/`) | **Upstream (Nous Research)** | Active | Upstream project |
| CLI (`cli.py`, `hermes_cli/`) | **Upstream (Nous Research)** | Active | Upstream project |
| Messaging gateway (`gateway/`, 20+ platforms) | **Upstream (Nous Research)** | Active | Upstream project |
| Tool registry & tools (`tools/`, `toolsets.py`) | **Upstream (Nous Research)** | Active | Upstream project |
| Desktop / TUI / web (`apps/`, `ui-tui/`, `web/`) | **Upstream (Nous Research)** | Active | Upstream project |
| Verification evidence (`agent/verification_evidence.py`) | **Upstream (Nous Research)** | Active | Upstream project; used as the substrate for the learning loop below |
| Governance layer (`governance/*.py`) | Custom | **Partially Active** | Plugin `plugins/governance` registers `post_tool_call` and `on_session_end` hooks |
| Governance execution sub-layer (`governance/execution/`) | Custom | **Dormant** | No caller in the live runtime |
| Verification → Learning (`agent/experience/`) | Custom (on upstream substrate) | **Active** | `verification_evidence.db` has real events; `experiences.json` has real records including `VERIFIED` |
| Execution Layer (`agent/execution/`) | Custom | **Implemented but Dormant** | 269 tests pass (phase report); zero references in `run_agent.py` / `cli.py` / `gateway/run.py` |
| Planner MVP (`agent/planning.py`) | Custom | **Implemented but Dormant** | Hook exists in `turn_context.py`; flag `planning.enabled` absent from config → defaults to `false` |
| HERALD Intelligence (Phases 010–013) | Custom | **Frozen / Dormant** | `docs/HERALD_INTELLIGENCE_FREEZE.md` marks phases FROZEN; entry point `ExecutionCoordinator.submit()` is not called in production |
| Business Bridge (`agent/business/`) | Custom | **Partially Integrated** | Bridge code exists and is tested; not wired into the live loop |
| Freestyle adapter (`freestyle_adapter/`) | Custom | **Not Verified** | `manifest.json` records `vm_creation: NOT ATTEMPTED`, `command_execution_on_vm: NOT ATTEMPTED`, `vm_lifecycle_pause_resume: NOT ATTEMPTED`; only docs-connectivity tested |
| Skills — `reelo`, `persian-writing`, `freestyle-docs` | Custom | **Active** | Loaded and used by the agent |
| Reports & architecture docs (`docs/`) | Custom | **Documentation** | Static files |

---

## Explicit non-claims

To be unambiguous about what this repository does **not** claim:

- It does **not** claim ownership of Hermes Agent.
- It does **not** claim that the Execution Layer is in production use — it is
  not wired into the live loop.
- It does **not** claim that HERALD intelligence is running — it is frozen and
  dormant.
- It does **not** claim that the Freestyle adapter has provisioned a real VM —
  the VM lifecycle has never been exercised.
- It does **not** claim any users, downloads, stars, revenue, or integrations.
- It does **not** include any upstream source code, credentials, personal data,
  VPN configuration, or private infrastructure details.

---

## What is verified

Three things in this repository are backed by direct, observable evidence:

1. **The Verification → Learning chain works.** A `verification_evidence.db`
   with real events (id 1–4, including a `passed` event with exit code 0) and a
   `governance/experiences.json` with real records — the most recent of which
   is tagged `successful` / `VERIFIED` — proves the chain fires end to end.
   The upstream `verification_evidence` module provides the substrate; the
   wiring into `finalize_turn` → `lifecycle_learning` → `experience` is
   custom.

2. **The Execution Layer is tested.** The phase report documents 269 passing
   tests across the nine components plus an integration coordinator suite.

3. **The Governance plugin is registered.** `plugins/governance/plugin.yaml`
   declares `post_tool_call` and `on_session_end` hooks and the module is
   loadable.

Everything else is labelled with its real state above.

---

## Future state (what would move a label)

| Component | What would move it to Active |
|---|---|
| Execution Layer | Wiring `ExecutionCoordinator.submit()` into the tool loop behind a feature flag, plus an end-to-end runtime test. |
| Planner MVP | Setting `planning.enabled: true` in `config.yaml` and confirming the planner seeds a non-empty `TodoStore` while the seed-guard correctly refuses to overwrite a model-owned list. |
| HERALD | Giving it a real caller (through the wired Execution Layer or as a standalone CLI command). |
| Freestyle adapter | Running the full VM lifecycle against a real Freestyle account: create → exec → pause → resume → cleanup. |
| Business Bridge | Wiring the bridge into the same live path as the Execution Layer. |