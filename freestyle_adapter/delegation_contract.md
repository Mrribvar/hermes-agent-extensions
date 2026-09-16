# PHASE 4F — DELEGATION CONTRACT

Interface fields (adapter-level; no secret storage):
- job_id: string (adapter identifier)
- task: dict or string (command description; no secret embedded)
- executor: "freestyle"
- vm_id: string (VM identifier; non-sensitive metadata)
- status: adapter lifecycle state (pending, running, completed, failed, cancelled, paused, retrying)
- started_at: ISO timestamp
- completed_at: ISO timestamp
- exit_code: integer or None
- stdout_reference: file path or identifier (not full stdout content; avoids secret exposure and storage bloat)
- stderr_reference: file path or identifier
- error_category: string (none, auth, network, sdk, vm_not_found, execution_error, timeout, unknown)
- artifacts: list of references (not content)
- cleanup_policy: "delete_after" | "persist" | "manual"

Secret rules:
- stdout/stderr references never include actual secret content.
- No .env content copied to contract or artifacts.
- Contract file contains only schema definition; no execution results or keys.
