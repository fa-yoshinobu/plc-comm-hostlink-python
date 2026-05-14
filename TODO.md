# TODO: Host Link Communication Python

This file tracks the remaining tasks and issues for the Host Link Communication (Keyence KV) library.

## 1. Protocol Implementation Gaps
- [x] **Expansion Unit Access helper surface**: Add high-level helpers for accessing buffer memory in expansion units, backed by low-level `URD` / `UWR` methods and stub tests.
- [x] **Expansion Unit Access live validation**: Verified `URD` / `UWR` against a
  KV-X500 at `192.168.250.100:8501` on 2026-05-14 with expansion units `0`,
  `1`, and `2` using same-value writeback/readback.

## 2. Cross-Stack API Alignment

- [x] **Keep helper naming aligned with the managed stacks**: Preserve the shared high-level contract around `open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`, `read_named`, and `poll`.
- [x] **Review public address helper exposure**: Promote Host Link address parse/normalize/format helpers into documented utility APIs so applications do not need private copies.
- [x] **Keep protocol-specific options explicit**: Preserve transport and framing details as explicit client options while keeping the high-level helper shape parallel to the other language stacks.
- [x] **Preserve semantic atomicity by default**: Do not silently split reads or writes that callers would reasonably treat as one logical value or one logical block. Protocol-defined boundaries are acceptable, but fallback retries that change semantics should be opt-in and explicitly named.

