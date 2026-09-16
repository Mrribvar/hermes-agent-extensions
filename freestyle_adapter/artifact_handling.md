# PHASE 5I — ARTIFACT HANDLING (Adapter-Level; Reference-Based; Secret-Safe)

Adapter design for artifacts:
- Artifacts stored as references (file paths, identifiers) — NOT full content embedded in adapter state.
- Types: files, logs, test results, generated output, snapshot references.
- References recorded in adapter-level metadata (job contract artifacts field) — NOT core memory mutation.
- Secret scanning: adapter does not embed full stdout/stderr; only references or truncated safe previews.
- No .env content, no API keys, no user credentials copied to artifacts or VM storage.
- Artifact retrieval: adapter provides reference; user/system can retrieve from VM filesystem or adapter-managed storage (not core memory mutation).
- Storage: adapter-level (not core); avoids bloating core SQLite memory (ExecutionMemory) with large artifact content.

No mutation to core artifact/storage system; adapter operates independently.
