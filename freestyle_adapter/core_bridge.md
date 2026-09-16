# PHASE 6B — CORE INTEGRATION BRIDGE (Minimal; Non-Destructive; Adapter Layer Only)

Bridge definition (adapter-level; does NOT overwrite core router):
- Main Router (core): evaluates task conditions; delegates to adapter when adapter policy conditions met (see router_policy.md 8 conditions).
- Adapter activation: adapter-level config file adapter_env.md (FREESTYLE_EXECUTION_ENABLED) controls adapter availability; core router does NOT change behavior unless adapter explicitly registered (adapter design preserves default LOCAL).
- Integration point: adapter can be loaded optionally; adapter does not require core mutation to function (verified: adapter operates independently using SDK binary and adapter-level state).
- Minimal change required for full activation: optional import/reference in core router (NOT performed in this phase to avoid core mutation; adapter design supports standalone operation).
- Gap documented: adapter operates independently; full core router integration requires additional core reference (future work; not required for controlled activation/test).

No core files overwritten; adapter bridge is documentation/design only.
