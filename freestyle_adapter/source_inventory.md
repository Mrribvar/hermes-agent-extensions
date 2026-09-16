# SOURCE INVENTORY — WHAT WOULD BE MOVED (Adapter-Level Design; Non-Mutation; No Secret Transfer)
Hermes source directory: /path/to/hermes-agent (exists; non-sensitive metadata verified)
Package version: 1.0.0
Entry point: cli.py / run_agent.py (core files exist; adapter does not change them)
Gateway module: gateway (existing; adapter uses adapter-level reference only)
Dependencies (from package.json / setup): standard library + third-party packages (no secret package names)
Configuration needed (adapter-level; no secret content embedded): adapter_env.md (flag false); adapter-level config only
Credentials: FREESTYLE_API_KEY (.env only; adapter loads securely; masked [REDACTED_67_CHARS]; never embedded in adapter files/reports)
No .env content shown; no secret embedded; adapter-level inventory only.
No mutation performed.
