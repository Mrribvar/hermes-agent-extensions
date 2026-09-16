# PHASE 5J — OBSERVABILITY / TIMELINE (Adapter-Level; Secret-Safe)

Timeline for delegated jobs (adapter-level; not core mutation):
CREATED -> QUEUED -> ASSIGNED -> RUNNING -> RESULT (SUCCEEDED/FAILED/TIMED_OUT/CANCELLED) -> VALIDATION -> CLEANUP -> COMPLETED

Log/record fields (secret-safe; no key, no full stdout with secrets, no .env content):
- job_id (adapter reference)
- status (current adapter state)
- vm_id (non-sensitive)
- created_at / started_at / completed_at (timestamps)
- command_reference (command label; not full secret-containing args if any — adapter avoids embedding secrets in commands by design)
- exit_code
- duration_seconds
- result_reference (reference to adapter-level result file; not full secret content)
- error_category (if failed/timeout)
- adapter_version / SDK_version (metadata; not secret)

Logs must be secret-safe: no API keys, no user tokens, no memory content, no environment variables beyond adapter-level metadata.
Adapter does not write to core Hermes logging infrastructure unless explicitly configured (adapter-level log file preferred to avoid mutation).
