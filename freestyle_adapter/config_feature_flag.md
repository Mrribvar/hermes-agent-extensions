# PHASE 4B — FEATURE FLAG (Non-Destructive Adapter Config)

FREESTYLE_EXECUTION_ENABLED = false  (default: disabled; preserves existing behavior)

To enable for controlled test:
- Set to true ONLY in adapter-level config or environment (not core mutation).
- Recommended: adapter reads .env line or adapter-level config file; not core config mutation.
- After change: restart/reload adapter (or Hermes run with adapter loaded) to pick up.
- Before activation: run regression tests with false (PASS expected).
- After activation: run controlled tests (PASS expected for safe tasks); default LOCAL preserved.
