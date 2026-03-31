# TODO: Host Link Communication Python

This file tracks the remaining tasks and issues for the Host Link Communication (Keyence KV) library.

## 1. Protocol Implementation Gaps
- [ ] **Expansion Unit Access**: Add high-level helpers for accessing buffer memory in expansion units.

## 2. Testing & Validation

## 3. Documentation & Maintenance

## 4. Cross-Stack API Alignment

- [ ] **Keep helper naming aligned with the managed stacks**: Preserve the shared high-level contract around `open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`, `read_named`, and `poll`.
- [ ] **Review public address helper exposure**: Decide whether Host Link address parse/normalize/format helpers should be promoted into a documented utility API so applications do not need private copies.
- [ ] **Keep protocol-specific options explicit**: Preserve transport and framing details as explicit client options while keeping the high-level helper shape parallel to the other language stacks.
- [ ] **Preserve semantic atomicity by default**: Do not silently split reads or writes that callers would reasonably treat as one logical value or one logical block. Protocol-defined boundaries are acceptable, but fallback retries that change semantics should be opt-in and explicitly named.
- [ ] **Preserve semantic atomicity by default**: Do not silently split reads or writes that callers would reasonably treat as one logical value or one logical block. Protocol-defined boundaries are acceptable, but fallback retries that change semantics should be opt-in and explicitly named.

## 4. Cross-Stack API Alignment

- [ ] **Keep helper naming aligned with the managed stacks**: Preserve the shared high-level contract around `open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`, `read_named`, and `poll`.
- [ ] **Review public address helper exposure**: Decide whether Host Link address parse/normalize/format helpers should be promoted into a documented utility API so applications do not need private copies.
- [ ] **Keep protocol-specific options explicit**: Preserve transport and framing details as explicit client options while keeping the high-level helper shape parallel to the other language stacks.

