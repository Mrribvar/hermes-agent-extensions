# PHASE 5H — RECOVERY (Adapter-Level Design; Deterministic; Non-Destructive)

Recovery must be deterministic; adapter defines recovery logic, not blind resume.

Recovery flow (adapter-level):
1. Detect interruption (adapter checks VM state; SDK get verifies).
2. Evaluate recoverability (adapter checks if VM exists, state, and job metadata is consistent).
3. Apply retry policy (limited retries; configured; never infinite).
4. Select replacement VM if current unavailable (adapter creates new VM with same or different slug; policy-based).
5. Resume/restart job according to job semantics (adapter restarts from beginning or from last known safe state — adapter design; not blind resume of partial execution).
6. Update adapter-level state (status, vm_id, started/completed times, exit code after final attempt).
7. Final state: SUCCEEDED / FAILED / CANCELLED / TIMED_OUT (per adapter state machine); then CLEANUP -> COMPLETED.

No assumption that partial job execution can be safely resumed. Adapter treats interrupted jobs as requiring full or partial restart based on job semantics and adapter policy.
No mutation to core Hermes recovery modules; adapter manages its own recovery logic.
