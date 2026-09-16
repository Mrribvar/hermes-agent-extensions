# TRANSFER CONFIRMATION (Adapter-Level; Non-Mutation)
Source: hermes-agent directory (exists; version 1.0.0; adapter does not modify core files)
Config: adapter-level only (adapter_env.md; feature flag false; adapter-level references)
Data/state: adapter-level references only (adapter manages job state independently; not core mutation)
Credentials: FREESTYLE_API_KEY (.env only; adapter loads securely; masked; never embedded)
No mutation: adapter-level only; no file copied to VM yet (transfer design documented; actual file transfer deferred to controlled activation)
P7F: untouched; feature flag false; adapter clean.
