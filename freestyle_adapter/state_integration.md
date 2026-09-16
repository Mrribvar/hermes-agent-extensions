# PHASE 3E — STATE INTEGRATION FORMAT (Adapter; Non-Destructive)

For each Freestyle execution, adapter records non-sensitive metadata only:
- executor = "freestyle"
- status: CREATED / PENDING / RUNNING / COMPLETED / FAILED / CANCELLED / PAUSED / RETRYING (maps to SDK state + adapter lifecycle)
- start_time: ISO timestamp
- end_time: ISO timestamp (if completed/failed)
- vm_id: non-sensitive VM identifier (e.g., slug or id fragment — NOT secret-linked)
- exit_code: integer
- duration_seconds: float (computed from start/end)
- error_category: NONE / AUTH / NETWORK / SDK / VM_NOT_FOUND / EXECUTION_ERROR / TIMEOUT / UNKNOWN

Secrets NEVER recorded: no API key, no VM memory content, no user credentials, no environment values beyond the above.
State storage: adapter writes to adapter-level JSON (or extends Hermes ExecutionMemory if configured); default adapter keeps its own state file to avoid core mutation.
