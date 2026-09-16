# PHASE 6G — CONTROLLED FAILURE TEST (Non-Destructive; Safe Command)
VM: hermes-test-vm (id=vm-cb6659c1213e4b7db85154e833db16e5)
Command: bash -c 'false' (harmless; returns exit 1; no destructive effect)
Exit code: 1 (expected non-zero for failure test)
Stdout (no secrets): 
State: FAILED (adapter-level; error_category: EXECUTION_ERROR)
Retry: adapter applies limited retry (not infinite)
Cleanup: adapter applies cleanup_policy after final state (persist default; VM kept alive for verification)
Recovery: adapter evaluates recoverability; can select/restart VM if needed (not performed automatically in this safe test)
No destructive operation performed; VM preserved.
