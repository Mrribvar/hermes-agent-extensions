# HERMES CONFIG REFERENCE FOR VM (Phase 6)
Required configurations (adapter-level reference; no secret content embedded):
- Hermes package: hermes-agent (version 1.0.0 from package.json)
- Python: 3.x (compatible with .python-version; VM has 3.12.3)
- SDK: freestyle@0.2.13 (node binary at node_modules/freestyle/dist/cli/index.js)
- .env: protected by .gitignore; adapter loads FREESTYLE_API_KEY from .env for SDK calls (not saved in VM; not embedded in adapter output)
- Adapter: adapter_env.md (FREESTYLE_EXECUTION_ENABLED=false by default)
- No other Hermes secrets transmitted to VM. Only SDK-required environment variable used for adapter subprocess (not persistent in VM).
- Working directory: hermes-agent/ (adapter reference only; no core mutation)
- Data/state paths: adapter-level reference files (not core mutation); adapter manages its own state references (job IDs, VM IDs, results)
