# Gotchas

Use this page only for library-specific caveats.

Use the shared
[KV Host Link Troubleshooting & Codes](https://plc-comm-docs-site.fa-labo.com/plc-setup/kv/troubleshooting-codes/)
page for common connection, profile, address-shape, write-permission, and PLC
error-code symptoms.

## Current library-specific caveats

| Area | Symptom | Guidance |
| --- | --- | --- |
| State-changing outcome | Timeout, cancellation, close, transport loss, or malformed confirmation occurs after a request may have been sent. | Treat `HostLinkOutcomeUnknownError` as unknown PLC state. Inspect `reason`, reconcile state explicitly, and do not blindly retry. |
| Named aggregate timing | A large or mixed `read_named` result changes while it is being collected. | The helper may use multiple caller-ordered read requests in one FIFO turn; it is not an atomic PLC-time observation. |
| Bit-in-word write | `write_bit_in_word` or `write_bit_in_expansion_unit_buffer` can overwrite another change to the same word. | They are explicit two-request, non-PLC-atomic operations. Use PLC-side coordination or exclusive whole-word ownership, and never automatically retry an outcome-unknown result. |
