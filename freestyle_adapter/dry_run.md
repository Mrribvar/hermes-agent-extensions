# PHASE 3F — DRY RUN (No Execution; Routing Decision Only)

Task 1: "echo hello"
- Requires Linux VM? NO
- Untrusted code? NO
- Long-running / isolation needed? NO
- Dependency isolation? NO
- Router decision: LOCAL (default, not Freestyle)
- Reason: simple echo, no VM justification.

Task 2: "install a Python dependency and run a test"
- Requires Linux VM? POSSIBLE (if dependency isolation required)
- Untrusted code? NO (assumed safe dependency)
- Long-running? NO
- Dependency isolation? YES (if dependency must be isolated from Hermes environment)
- Router decision: FREESTYLE (only if dependency isolation is required); else LOCAL.
- In this dry-run (no explicit isolation request): LOCAL preferred; adapter available if isolation requested.

Task 3: "run unknown/untrusted code"
- Untrusted / unknown? YES
- Isolation required? YES (security policy)
- Router decision: FREESTYLE (adapter activates; no secrets passed to VM except SDK key; VM disposable/persistent per policy)
- Safety: adapter creates VM; command executed inside VM; result returned; no Hermes secrets exposed.

No destructive actions performed. No VM deleted. No real tasks executed beyond Phase 2 verification.
