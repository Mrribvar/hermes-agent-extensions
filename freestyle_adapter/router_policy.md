# PHASE 3C — ROUTING POLICY (Adapter Layer; Non-Destructive)

Policy applies ONLY when adapter is loaded. Default Hermes routing unchanged.

POLICY RULE (default = previous executor unless conditions met):

LOCAL (default):
- Short tasks (< 15 min estimated)
- Internal Hermes-only actions (memory, skills, config updates)
- No untrusted code
- No external dependency isolation needed
- No persistent Linux environment required

DESKTOP/MOBILE (existing Hermes local):
- Tasks requiring Hermes desktop environment, local file access, browser automation
- Internal agent work not needing VM isolation

FREESTYLE (adapter activates ONLY when at least one condition is true):
1. Task requires Linux VM (explicit request or detected from command pattern)
2. Dependency/package isolation required (pip install in sandbox, npm package test)
3. Untrusted / unknown code execution (user provides code without provenance)
4. Long-running execution (> 15 min or requires persistence across interruptions)
5. Disposable / persistent environment needed (snapshot/branch capability requested)
6. Docker / separate runtime environment required
7. Agent/tool execution outside main Hermes process (isolated sandbox)
8. Multi-tenant or isolated network environment (VPC isolation mentioned)

If NONE of conditions 1-8 met → default stays LOCAL/DESKTOP.
No automatic override of safe internal tasks to Freestyle.

SECURITY / NETWORK:
- Adapter creates VM without automatic public access unless explicitly configured.
- No Hermes secrets (memory, API keys beyond FREESTYLE_API_KEY, config tokens) copied to VM.
- Only FREESTYLE_API_KEY (required for SDK) is available; not written to VM disk or logs.
- Firewall/network policy: minimum-access by default; only ports needed for SDK communication open.

No core Hermes router file overwritten; adapter provides policy definition only.
