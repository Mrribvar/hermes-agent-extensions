# PHASE 4D — FAILURE HANDLING (Documented; Non-Destructive Tests Only)

Scenarios (simulated; no destructive execution performed):

1. Freestyle API unavailable:
- Detection: health_check API_reachable FAIL or SDK call timeout.
- Error category: NETWORK / AUTH
- State transition: PENDING_APPROVAL -> FAILED (or RETRYING if retry configured; adapter does NOT use infinite retry)
- Retry behavior: adapter uses single attempt for this phase; retry can be configured but not infinite.
- Fallback: adapter does NOT fall back to LOCAL automatically (security: untrusted tasks must not silently fall back). For safe LOCAL tasks, router keeps LOCAL; adapter failure does not redirect.
- User-visible: execution failed; error category shown; no secret exposed.

2. VM creation failure:
- Detection: SDK create returns non-zero or result missing id.
- Error category: VM_NOT_FOUND / SDK
- State: FAILED; retry limited; no infinite retry.
- Fallback: fail-safe; task stops.

3. Command failure / non-zero exit:
- Detection: execute exit_code != 0
- Error category: EXECUTION_ERROR
- State: COMPLETED (with failure) or FAILED (per adapter mapping)
- Retry: configurable; default single attempt.
- Fallback: none (command failure is expected behavior for some tests; adapter returns result with exit code, does not suppress or fall back to LOCAL).

4. Timeout:
- Detection: subprocess timeout exceeded.
- Error category: TIMEOUT
- State: CANCELLED or FAILED (adapter-configurable; default CANCELLED for timeout)
- Retry: limited.
- Fallback: fail-safe; no automatic LOCAL redirect.

5. Malformed task:
- Detection: adapter receives invalid args, missing vm_id, or invalid command array.
- Error category: INPUT_ERROR / UNKNOWN
- State: FAILED immediately; no retry.
- Fallback: fail-safe stop; user-visible error message without secrets.

No infinite retries implemented. Adapter keeps failure handling minimal and safe.
