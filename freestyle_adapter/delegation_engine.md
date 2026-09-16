# PHASE 5B — DELEGATION ENGINE (Adapter Layer; Non-Mutating)

Engine is adapter-level design (not core mutation). It extends adapter contract to job lifecycle management.

Engine flow (logical; adapter layer):
1. Receive Hermes task (from adapter interface or future router integration).
2. Task Classification (adapter-level; can extend router policy): safe vs isolated vs untrusted.
3. Delegation Decision: if adapter policy activates Freestyle (8 conditions), proceed; else return to default (LOCAL).
4. Job Creation: generate job metadata (job_id, task descriptor, executor="freestyle", vm_id from adapter, cleanup_policy).
5. VM Selection/Creation: reuse existing VM (hermes-test-vm, persistent) or create new (slug-based, ephemeral/reusable per 5E).
6. Remote Execution: adapter -> SDK -> VM -> command; collect stdout/stderr/status.
7. Result Collection: adapter captures exit code, output references (not full secret content), duration.
8. Validation: adapter verifies result format and status (not content inspection for secrets).
9. State Update: adapter writes non-sensitive metadata to adapter-level state/reference (not core memory mutation unless configured separately).
10. Cleanup/Persistence: apply cleanup_policy (delete_after / persist / manual); for current Phase 5, VM preserved (not deleted) unless explicitly configured.

Methods in adapter design:
- create_delegated_job(task): returns job reference
- assign_vm(job_ref, vm_id_or_create): assigns VM
- execute_on_vm(job_ref, command): runs command; updates status
- get_job_state(job_ref): returns current adapter-level state
- collect_result(job_ref): returns result reference (not secret content)
- apply_timeout(job_ref, timeout_seconds): timeout tracking
- handle_failure(job_ref, error_category): state transition per 5G/5H
- retry_policy(job_ref, max_retries): limited retry (no infinite)
- cancel_job(job_ref): cancellation with state transition
- cleanup_job(job_ref, policy): delete or persist VM

No mutation to core Hermes execution engine or state machine. Adapter operates independently.
