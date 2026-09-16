# Changelog

All notable changes to the extensions in this repository.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/)
once it has a first release.

## [Unreleased]

### Added

- **Governance layer** (`governance/`) — decision memory, risk classification,
  approval workflow, knowledge graph, project registry, dependency
  intelligence, impact analysis, recommendation engine, architecture query.
  Exposed through a plugin with `post_tool_call` and `on_session_end` hooks.
- **Execution Layer** (`agent/execution/`) — a governed, queued, persistent
  execution path with nine components and 269 passing tests. Not wired into
  the live loop.
- **Experience & Learning** (`agent/experience/`) — the Verification →
  Learning chain: a verified turn produces a persisted, outcome-tagged
  experience record.
- **Planner MVP** (`agent/planning.py`) — deterministic, LLM-free planner with
  a seed-only ownership guard. Feature-flagged, dormant by default.
- **HERALD Intelligence** (`herald/` plus the corresponding governance
  modules) — pattern intelligence, decision intelligence, execution
  integration, and persistence layer. Frozen and dormant.
- **Business Bridge** (`agent/business/`) — entity model plus an additive
  bridge into `ExecutionMemory`.
- **Freestyle adapter** (`freestyle_adapter/`) — non-destructive VM adapter
  scaffold. VM lifecycle not yet verified.
- **Original skills** (`skills/`) — `reelo`, `persian-writing`,
  `freestyle-docs`.
- **Documentation** — `ARCHITECTURE.md`, `PROJECT_STATUS.md`,
  `CONTRIBUTIONS.md`, `SECURITY.md`, and the walkthroughs under `docs/`.

### Known limitations

- Some modules import from upstream Hermes Agent and cannot run standalone.
- The Execution Layer and Planner MVP are implemented but dormant.
- HERALD is frozen and has no live caller.
- The Freestyle adapter's VM lifecycle has never been exercised.
- No CI, no packaging, no released version.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the full status table.