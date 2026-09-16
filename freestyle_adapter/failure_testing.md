# PHASE 5G — FAILURE TESTING (Simulated; Non-Destructive; Documented Only)

No destructive actions performed. No VM deleted. No real failures forced (only documented scenarios based on adapter design and SDK behavior from previous phases).

1. Command exit != 0:
- Adapter captures non-zero exit code.
- Error category: EXECUTION_ERROR
- State: FAILED (adapter state machine defines transition from RUNNING to FAILED on non-zero exit)
- Retry: adapter applies retry policy (configured; default limited; no infinite retry)
- Cleanup: adapter applies cleanup_policy after final state (COMPLETED after CLEANUP or FAILED after CLEANUP, depending on policy)
- Fallback: fail-safe; adapter does NOT redirect to LOCAL automatically (security: untrusted tasks must not silently fall back)
- User-visible: execution failed; error category; exit code; no secret shown.

2. Timeout:
- Adapter applies timeout (timeout_seconds from job contract).
- State transition: RUNNING -> TIMED_OUT (if timeout exceeded); then to CLEANUP (per adapter design)
- Retry: limited retry may be applied based on adapter policy (not infinite).
- Fallback: none; task stops safely.

3. VM unavailable:
- Adapter detects VM not reachable (SDK get returns error or connection failure).
- Error category: VM_NOT_FOUND / NETWORK
- State: FAILED or RETRYING (adapter retry policy applies; not infinite)
- Fallback: adapter does not redirect to LOCAL; task fails safely.
- Recovery: adapter can create new VM (if retry policy and ephemerality/reuse permits) or mark unrecoverable.

4. API unavailable:
- Adapter detects SDK/auth/network failure.
- Error category: AUTH / NETWORK / SDK
- State: FAILED; retry limited.
- Fallback: none; adapter stops safely.

5. Invalid task:
- Adapter validates task format before execution (command array present; vm_id valid or creatable).
- Error category: INPUT_ERROR / UNKNOWN
- State: FAILED (immediate; no retry)
- Fallback: fail-safe stop.

6. Cancellation:
- Cancellation request triggers adapter state transition from any non-terminal state to CANCELLED.
- Cleanup applied per policy.
- No blind resume; adapter requires new job/assignment after cancellation.
