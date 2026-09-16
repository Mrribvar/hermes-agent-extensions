# INVENTORY SOURCE (Read-Only; No Secret; Non-Mutation)
Hermes source: /path/to/hermes-agent (verified; directory exists)
Executable reference: cli.py / run_agent.py (core files present; adapter does not modify)
Python version (system): Python 3.14.6 (system python; adapter uses this environment)
Package version: 1.0.0 (from package.json — non-sensitive)
Gateway command reference: gateway module (existing; adapter does not change entrypoint)
Config/state/data paths: adapter-level reference only; adapter creates adapter_env.md; adapter does not modify core config/state paths directly
Credentials required for runtime: FREESTYLE_API_KEY (adapter only; .env protected; .env.example valueless; adapter loads securely; key masked: [REDACTED_67_CHARS])
No other sensitive credentials copied to adapter; no .env content shown; no secret prefixes/suffixes shown.
Dependency manifest: package.json + setup files exist; adapter does not install new packages into core; adapter uses existing SDK (freestyle@0.2.13) installed in node_modules
No mutation performed: CONFIRMED; adapter layer only; feature flag false preserved; P7F untouched.
