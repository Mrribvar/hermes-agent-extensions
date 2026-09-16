# PHASE 3J — ROLLBACK PROCEDURE

Simple rollback (no core restoration needed since adapter is non-mutating to Hermes core):

1. Disable adapter: remove import/reference to freestyle_adapter from any integration point (currently adapter is standalone; no core import exists).
2. Delete adapter files: rm -rf hermes-agent/freestyle_adapter/
3. Optional: delete docs skill files: rm -rf .hermes/skills/freestyle-docs/
4. Restore .env: cp .env.backup_before_bai .env (if previous key needs restoration) OR keep current real key.
5. Delete VM (optional): node node_modules/freestyle/dist/cli/index.js vm delete vm-cb6659c1213e4b7db85154e833db16e5
6. Backup preserved: .hermes/backup-pre-freestyle-20260910_040058/ (never deleted)

No Hermes core files modified; rollback requires no core file restoration.
P7F / NOINDEX unchanged.
No unrelated features changed.
