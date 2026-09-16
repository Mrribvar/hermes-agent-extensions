# CONFIG SAFE (Adapter-Level; Non-Secret; Non-Mutation)
Adapter-level config only (adapter_env.md; feature flag false; adapter-level references).
No .env content embedded; no secret embedded; no mutation to core config/state.
Paths mapped: adapter-level references only (not Android/Termux-specific paths in core).
VM equivalent: working directory adapter-level; no mutation.
