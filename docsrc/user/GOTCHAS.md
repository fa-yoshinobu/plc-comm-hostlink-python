# Gotchas

Use this page only for library-specific caveats.

Use the shared
[KV Host Link Troubleshooting & Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/troubleshooting-codes/)
page for common connection, profile, address-shape, write-permission, and PLC
error-code symptoms.

## Current library-specific caveats

| Area | Symptom | Guidance |
| --- | --- | --- |
| State-changing outcome | Timeout, cancellation, close, transport loss, or malformed confirmation occurs after a request may have been sent. | Treat `HostLinkOutcomeUnknownError` as unknown PLC state. Inspect `reason`, reconcile state explicitly, and do not blindly retry. |
| Named aggregate timing | A large or mixed `read_named` result changes while it is being collected. | The helper may use multiple caller-ordered read requests in one FIFO turn; it is not an atomic PLC-time observation. |
| Bit-in-word write | Old code imports `write_bit_in_word`. | The unsafe public RMW helper was removed without an alias; use PLC-side atomic behavior or exclusive word ownership. |
