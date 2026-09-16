# GATEWAY REFERENCE (Adapter-Level; Non-Destructive; Read-Only)
Hermes gateway reference (from core): gateway module (existing; adapter does not change entrypoint)
Termux gateway process: python3.11 /hermes gateway run --external-supervisor (PID 23916; confirmed in Termux; adapter-level verification)
Adapter gateway reference: adapter-level contract refers to gateway functionality without overriding core; adapter-level gateway execution deferred to adapter (not executed inside VM in this safe diagnostic/test scope)
No mutation: adapter-level reference only; no core gateway file overwritten; adapter-level documentation only.
No destructive action: adapter-level verification only; no restart; no mutation.
