# EXECUTOR CONTRACT (Phase 4A — Pre-Activation)

Adapter provides minimal interface matching Hermes execution abstraction (non-mutating to core):
- health_check(): bool / status
- create_vm(slug): {vm_id, status}
- execute(vm_id, [cmd...]): {exit_code, stdout_ref, stderr_ref, duration}
- pause(vm_id): {status}
- resume(vm_id): {status}
- cleanup(vm_id, delete=False): {deleted, reason}
- get_state(vm_id): {state, vm_id, created_at}

No secret exposure in any method return. stdout/stderr returned as references or truncated previews.
Key loaded from .env (not shown); masked in logs.
