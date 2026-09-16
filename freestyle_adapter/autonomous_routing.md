# PHASE 6E — AUTONOMOUS ROUTING (Adapter-Level; Non-Destructive; No Real Destructive Execution)
Router policy (from router_policy.md) applied to 3 hypothetical tasks:
TASK A: 'Calculate 17 x 23 and return the result.'
  Conditions: no Linux VM needed; no isolation; no untrusted code; no long-running.
  Router decision: LOCAL (default; adapter does NOT activate)
  Reason: no justification for VM activation; safe task.

TASK B: 'Create an isolated Linux environment, install a temporary Python dependency, run a test, then return the result.'
  Conditions: dependency isolation = true; isolated environment = true.
  Router decision: FREESTYLE (adapter activates; conditions 2 and 5 met)
  Reason: isolation required; adapter activates safely.

TASK C: 'Run a clearly marked harmless untrusted-code simulation in an isolated environment and return its output.'
  Conditions: untrusted code = true; isolated environment = true.
  Router decision: FREESTYLE (adapter activates; conditions 3 and 5 met)
  Reason: untrusted code requires isolation; adapter activates safely.

No secrets in routing log. Feature flag false preserved; adapter activates only with justification.
No destructive tasks executed; decisions documented only.
