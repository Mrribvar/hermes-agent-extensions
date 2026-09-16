# PHASE 5C — JOB STATE MACHINE (Adapter Layer; Non-Destructive Design)

Adapter-level state machine aligns with Hermes execution lifecycle (from EXECUTION_LAYER_ARCHITECTURE.md) without duplicating or mutating core.

States (adapter mapping):
CREATED -> QUEUED -> ASSIGNED -> RUNNING -> SUCCEEDED / FAILED / TIMED_OUT / CANCELLED -> CLEANUP -> COMPLETED

Transitions (validated; invalid transitions rejected):
- CREATED -> QUEUED (valid: job submitted to adapter queue)
- QUEUED -> ASSIGNED (valid: VM selected/created; adapter assigns)
- ASSIGNED -> RUNNING (valid: execution starts)
- RUNNING -> SUCCEEDED (valid: exit_code == 0, result verified, adapter validates)
- RUNNING -> FAILED (valid: exit_code != 0; adapter records error_category)
- RUNNING -> TIMED_OUT (valid: timeout exceeded; adapter applies timeout)
- RUNNING / ASSIGNED -> CANCELLED (valid: cancellation requested; adapter stops safely)
- SUCCEEDED / FAILED / TIMED_OUT / CANCELLED -> CLEANUP (valid: adapter applies cleanup_policy)
- CLEANUP -> COMPLETED (valid: cleanup finished; adapter records final state)

Invalid transitions (rejected):
- COMPLETED -> any other (terminal state)
- CLEANUP -> RUNNING / ASSIGNED (must complete before re-running)
- SUCCEEDED / FAILED / TIMED_OUT -> ASSIGNED (must go through QUEUED/CREATED for retry; adapter manages retry separately, not blind re-transition)

Integration with adapter: adapter uses this machine for delegation engine; core Hermes state machine unchanged. Adapter can extend core machine conceptually but does not overwrite core implementation.
