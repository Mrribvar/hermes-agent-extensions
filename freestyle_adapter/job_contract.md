# PHASE 5D — JOB CONTRACT (Adapter-Level Design; Aligned with Adapter Architecture)

Contract fields (adapter-level job metadata; no secrets stored):
- job_id: adapter identifier (string; unique within adapter)
- task_id: reference to Hermes task (optional reference; adapter does not store full Hermes internal data)
- executor: "freestyle" (adapter identifier; distinguishes from LOCAL/DESKTOP)
- vm_id: VM identifier (slug or id; non-sensitive metadata)
- status: adapter state machine state (CREATED, QUEUED, ASSIGNED, RUNNING, SUCCEEDED, FAILED, TIMED_OUT, CANCELLED, CLEANUP, COMPLETED)
- created_at: ISO timestamp
- started_at: ISO timestamp (execution start)
- completed_at: ISO timestamp (final state reached)
- exit_code: integer (command exit code; not a secret)
- timeout: integer (timeout seconds; not a secret)
- error_category: string from adapter mapping (NONE, AUTH, NETWORK, SDK, VM_NOT_FOUND, EXECUTION_ERROR, TIMEOUT, UNKNOWN)
- artifacts: list of artifact references (file paths or identifiers; not content; no secrets embedded)
- cleanup_policy: string ("delete_after", "persist", "manual")

Rules:
- Secret fields (API keys, user tokens, passwords) NEVER included in contract.
- stdout/stderr never stored as full content in contract; only references or truncated safe previews.
- Contract file is design document only; adapter does not write contracts to core memory or modify core schema.
