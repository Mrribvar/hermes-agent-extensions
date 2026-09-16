# FREESTYLE EXECUTION ARCHITECTURE (Phase 3 Integration)

1. ARCHITECTURE
- Hermes core execution layer (ExecutionCoordinator, ExecutionEngine, ExecutionStateMachine, ExecutionMemory) remains untouched.
- Adapter layer: hermes-agent/freestyle_adapter/ provides clean interface without core mutation.
- Adapter components: adapter.md, manifest.json, freestyle_executor.py, health_check.py, router_policy.md, ARCHITECTURE_AUDIT.md, PHASE2_REPORT.md, dry_run.md, live_router_test_result.md, FREESTYLE_EXECUTION_ARCHITECTURE.md (this file)

2. ROUTER POLICY
- Default: LOCAL / DESKTOP (existing Hermes behavior preserved).
- FREESTYLE activates ONLY when at least one of 8 conditions is met (see router_policy.md): Linux VM needed, dependency isolation, untrusted code, long-running, disposable/persistent env, Docker/runtime isolation, agent outside main process, multi-tenant/network isolation.
- Safety: adapter never overrides safe internal tasks to VM; only activates with explicit justification.

3. EXECUTOR CONTRACT
- Class: FreestyleExecutor (freestyle_executor.py)
- Methods: health_check(), create_vm(), execute(), pause(), resume(), cleanup()
- Uses SDK binary: node node_modules/freestyle/dist/cli/index.js
- Key loaded from .env; never logged, never included in output.

4. SECURITY MODEL
- Key stored ONLY in .env (gitignored); .env.example has valueless line.
- Key masked as [REDACTED_67_CHARS] in all outputs; never shown in adapter/report/backup.
- No Hermes secrets copied to VM; only SDK-required environment variable set for subprocess.
- Network: minimum access by default; no automatic public access.

5. VM LIFECYCLE
- Create: slug-based identification; metadata only (id, state, createdAt) recorded.
- Execute: remote command via SDK exec; stdout/stderr/status returned.
- Pause: freeze memory; state verified via SDK get.
- Resume: restore to running; state verified.
- Cleanup: optional delete; default preserves VM for persistence verification.

6. FAILURE HANDLING
- SDK errors caught by adapter; return FAIL status with exit code.
- Auth errors: credentials_configured check fails if .env missing or empty.
- Network errors: API_reachable check fails.
- VM creation failure: adapter returns FAIL; no core mutation.
- No automatic rollback of core files needed (no mutation occurred).

7. ROLLBACK
- Remove adapter directory: rm -rf hermes-agent/freestyle_adapter
- Delete docs skill: rm -rf .hermes/skills/freestyle-docs (optional)
- Restore .env: cp .env.backup_before_bai .env (or restore from backup directory)
- Stop/remove VM: node ... vm delete vm-cb6659c1213e4b7db85154e833db16e5 (optional)
- No core restoration needed.

8. HEALTH CHECK
- Script: health_check.py (6 checks: SDK, credentials, API reachability, VM creation available, command execution, lifecycle)
- Output: PASS/FAIL per check; no secrets displayed.

9. EXAMPLES
- Health check: python hermes-agent/freestyle_adapter/health_check.py
- VM creation (adapter): adapter creates VM with slug; records id/state.
- Command execution: adapter -> SDK exec -> VM -> result returned.
- Lifecycle test: pause -> get state (paused) -> resume -> get state (running) — verified.
- Dry-run policy: task evaluated by conditions; default stays LOCAL unless justification met.

NO SECRETS DISPLAYED. NO CORE OVERWRITTEN. ADAPTER ONLY.
