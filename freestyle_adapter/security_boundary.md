# PHASE 4H — SECURITY BOUNDARY (Non-Destructive Documentation)

LOCAL:
- Trusted execution within Hermes environment.
- No isolation from main process.
- Full access to local files/config (subject to Hermes security policy).

FREESTYLE (adapter activation):
- Isolated VM environment (full Linux VM, root access within VM only).
- No Hermes secrets copied to VM (except SDK key required for operation, set as subprocess env — not saved to VM disk, not logged).
- Key masked in all outputs: [REDACTED_67_CHARS].
- Network: minimum access; public access only when explicitly configured; adapter default does not open public ports.
- Untrusted code runs ONLY when router policy activates adapter (8 conditions); default stays LOCAL for safe tasks.
- Failure: fail-safe; adapter does not redirect untrusted tasks back to LOCAL silently.
- Rollback: adapter deletion + optional VM delete; no core restoration needed.

Credentials policy:
- Only FREESTYLE_API_KEY available in adapter (from .env, gitignored).
- No user data, memory content, Telegram tokens, or other Hermes credentials transmitted.
- .env never displayed; backup files protected; adapter/report/skill directories verified clean (grep scan PASS).

No mutation to Hermes security model; adapter operates as independent boundary.
