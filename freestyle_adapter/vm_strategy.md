# PHASE 5E — VM STRATEGY (Adapter-Level Design)

Three modes (adapter-level design; does not change default behavior of existing VM or adapter):

1. EPHEMERAL
- Advantage: clean isolation; no persistence overhead; ideal for untrusted/short tasks; minimal resource retention.
- Risk: data lost after execution; no recovery of intermediate state; requires re-creation for each run.
- Cleanup: automatic delete_after execution; adapter applies delete policy.
- Security: minimum network; no persistent storage of secrets; VM destroyed after use.
- Cost: minimal retention; lower resource usage.
- Use case: quick tests, untrusted code, isolated build/test steps, disposable environments.

2. PERSISTENT
- Advantage: filesystem/state preserved; supports long-running tasks; allows multi-step workflows; pause/resume verified (Phase 2/4).
- Risk: resource retention; requires manual cleanup if not managed; larger footprint.
- Cleanup: manual or policy-based; adapter does not delete by default (current VM kept alive for persistence proof).
- Security: same isolation; secrets not stored on disk; adapter manages cleanup separately.
- Cost: sustained resource usage.
- Use case: development environments, long agent tasks, multi-step pipelines, persistent workspaces.

3. REUSABLE
- Advantage: same VM reused across multiple adapter executions; faster startup; shared environment.
- Risk: cross-task contamination; requires clean state between executions; potential security issues if not properly isolated.
- Cleanup: manual or periodic reset; adapter manages reuse tracking.
- Security: adapter must verify clean state before reuse; no secret leakage between tasks.
- Cost: shared resource; lower creation overhead but requires state management.
- Use case: repeated similar workloads; multi-task agent environments; development cycles with consistent environment.

Default: adapter preserves current behavior (current VM is persistent by design; adapter does not change default mode unless explicitly configured).
No mutation to adapter default; strategy is design documentation only.
