# PHASE 6F — JOB LIFECYCLE VERIFICATION (Adapter-Level; Real VM; Non-Destructive)
VM: hermes-test-vm (id=vm-cb6659c1213e4b7db85154e833db16e5)
Lifecycle path (adapter-level state machine from 5C):
CREATED -> QUEUED -> ASSIGNED -> RUNNING -> SUCCEEDED -> CLEANUP -> COMPLETED

Verification steps (adapter-level; real VM used):
1. CREATED: adapter creates job reference (documented).
2. QUEUED: adapter assigns VM (existing VM reused; adapter policy allows reuse for persistence).
3. ASSIGNED: adapter confirms VM assignment (vm_id recorded).
4. RUNNING: adapter executes safe command through SDK (echo HERMES_DELEGATION_OK verified in Phase 4/5; re-verified safe here).
5. SUCCEEDED: adapter verifies exit code 0; result reference recorded.
6. CLEANUP: adapter applies cleanup_policy (persist by default; VM kept alive — verified).
7. COMPLETED: adapter records final state; metadata saved in adapter-level reference.
No mutation to core state; adapter manages own lifecycle tracking.
VM preserved (not deleted) per persistence verification.
