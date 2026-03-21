# API Unification Policy

This document defines the public API rules for the KEYENCE KV Host Link Python library.
It is a design policy document. It does not claim that every rule is implemented yet.

## Purpose

- Keep the Host Link Python API internally consistent between sync and async clients.
- Keep operation names aligned with the Host Link .NET library where the operation class is the same.
- Avoid hiding protocol-specific distinctions behind overly generic names.

## Public API Shape

The canonical client classes are:

- `KvHostLinkClient` — low-level client
- `AsyncKvHostLinkClient` — async wrapper
- `KvHostLinkDeviceClient` — high-level string-address client
- `AsyncKvHostLinkDeviceClient` — async high-level client

### High-Level Canonical Names

- `read`
- `write`
- `read_many`
- `write_many`
- `read_dword`
- `write_dword`
- `read_dwords`
- `write_dwords`
- `read_float32`
- `write_float32`
- `read_float32s`
- `write_float32s`
- `resolve_device`
- `read_clock`
- `write_clock`
- `read_cpu_status`

### Low-Level Canonical Names

- `read_words`
- `write_words`
- `read_bits`
- `write_bits`
- `read_dwords`
- `write_dwords`
- `read_float32s`
- `write_float32s`
- `send_raw`

## Sync and Async Parity Rules

The async client must mirror the sync client.

- The async method name stays identical to the sync method name.
- The async method returns the same logical result shape.
- Argument names and ordering stay aligned.
- Missing async parity is considered backlog, not a reason to rename the sync API.

## Cross-Language Parity Rules

When an equivalent operation exists in the Host Link .NET library, semantic names must stay aligned.

Examples:

- `read_words` ↔ `ReadWordsAsync`
- `read_dwords` ↔ `ReadDWordsAsync`
- `read_float32s` ↔ `ReadFloat32sAsync`
- `read_clock` ↔ `ReadClockAsync`

## 32-Bit Value Rules

- `dword` means a raw 32-bit unsigned value stored across two PLC words (low-word-first).
- Signed 32-bit helpers, if added later, should be named `read_int32` / `write_int32`.
- Floating-point helpers must use `float32` in the public name.

## dtype Codes

Typed access methods use these codes:

| Code | Type |
| --- | --- |
| `U` | unsigned 16-bit |
| `S` | signed 16-bit |
| `D` | unsigned 32-bit |
| `L` | signed 32-bit |
| `F` | IEEE 754 float32 |

Do not use `W`, `I`, or other legacy codes.

## Documentation Rules

README, samples, and generated docs must describe the canonical names from this document.
If a sync method exists and async parity is not yet implemented, document the gap as backlog.
