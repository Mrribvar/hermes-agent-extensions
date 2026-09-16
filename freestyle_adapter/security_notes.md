# PHASE 3D — SECURITY MODEL (Adapter Layer)

Key handling:
- FREESTYLE_API_KEY loaded ONLY from .env (gitignored).
- Key NEVER printed, logged, dumped, or included in adapter/report files.
- Key masked in all outputs: [REDACTED_67_CHARS] (length confirmed, value never shown).
- .env protected by .gitignore; .env.example contains valueless line.

VM isolation:
- No Hermes secrets copied to VM (no memory content, no user profile, no other .env values).
- Only SDK-required environment set (FREESTYLE_API_KEY for subprocess call).
- Network: minimum access; no public access enabled by default for test VM.
- Untrusted code execution allowed ONLY when router policy activates Freestyle.

Rollback / cleanup:
- Adapter files: delete freestyle_adapter/ or disable adapter import.
- VM: delete via SDK command (delete not executed automatically to preserve persistence verification).
- .env: restore from .env.backup_before_bai or backup directory.
- Core Hermes unchanged — rollback requires no core file restoration.
