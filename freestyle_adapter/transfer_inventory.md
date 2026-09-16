# TRANSFER INVENTORY — WHAT WOULD BE MOVED TO VM (Adapter-Level Design; Non-Mutation; No Secret Transfer)
Category: SOURCE -> Would include hermes-agent/ directory (core files unchanged by adapter)
Category: PYTHON ENV -> Would require Python 3.x compatible environment (VM has Python 3.12.3; compatible)
Category: PACKAGE METADATA -> package.json / setup files (non-sensitive metadata only)
Category: CONFIG -> adapter-level config only (adapter_env.md flag false; adapter-level references; NO .env content embedded)
Category: DATA/STATE -> adapter-level state references (job IDs, VM IDs, results); NO Hermes core state mutation; adapter manages independently
Category: SKILLS -> adapter-level docs only (freestyle_adapter/*.md; SKILL.md; not core skills overwritten)
Category: CREDENTIALS -> FREESTYLE_API_KEY only (.env protected; adapter loads securely; masked: [REDACTED_67_CHARS]; never embedded in adapter/reports/transfer)
Category: TOOLS -> adapter-level adapter.md / manifest.json / freestyle_executor.py / health_check.py (adapter layer; not core tools overwritten)
Category: LOGS -> adapter-level results only (controlled_workload_results.md; real_routing_results.md; no full stdout with secrets)
Category: CACHE/BUILD -> NOT included (non-essential for adapter-level runtime; adapter does not require build artifacts)
No mutation performed; adapter-level design only.
