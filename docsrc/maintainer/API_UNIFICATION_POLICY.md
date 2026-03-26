# API Unification Policy

This document defines the current public API policy for `plc-comm-hostlink-python`.

## Purpose

- Keep the Python API internally consistent between sync and async clients.
- Keep behavior aligned with `plc-comm-hostlink-dotnet` where the operation class is equivalent.
- Document intentional cross-language design differences explicitly.

## Current Public Surface

The current public low-level clients are:

- `HostLinkClient`
- `AsyncHostLinkClient`

The current exported high-level helpers are:

- `open_and_connect`
- `read_typed`
- `write_typed`
- `write_bit_in_word`
- `read_named`
- `poll`
- `read_words`
- `read_dwords`

## Sync / Async Rules

Python maintains both sync and async low-level clients.

- The async method name stays identical to the sync method name.
- The async method returns the same logical result shape.
- Argument names and ordering stay aligned.
- Missing async parity is backlog.

## Cross-Language Semantic Parity

Semantic parity with `plc-comm-hostlink-dotnet` is the target.
Literal public API identity is not the target.

The following must stay aligned across Python and .NET:

- Host Link frame bodies for equivalent operations
- validation behavior
- helper-layer typed behavior
- live PLC behavior

## Intentional Differences From .NET

The following differences are intentional and are not treated as bugs by themselves:

- Python exposes both sync and async low-level clients.
  .NET is async-native and exposes high-level helpers as extension methods.
- Python low-level reads parse decimal tokens into `int` values and return `int | str | list[int | str]`.
  .NET low-level reads return raw `string[]`.
- Python accepts `transport="tcp"/"udp"` and mode values such as `"RUN"` / `"PROGRAM"` or `0/1`.
  .NET uses `HostLinkTransportMode` and `KvPlcMode`.
- Python returns `ModelInfo.model = None` when the `?K` code is unmapped.
  .NET returns `"Unknown"`.

## dtype Codes

Helper-layer typed access uses these codes:

| Code | Type |
| --- | --- |
| `U` | unsigned 16-bit |
| `S` | signed 16-bit |
| `D` | unsigned 32-bit |
| `L` | signed 32-bit |
| `F` | IEEE 754 float32 |

`F` is helper-layer only.
Low-level Host Link suffix validation remains limited to `.U`, `.S`, `.D`, `.L`, and `.H`.

## Documentation Rules

- README, samples, and user docs must describe the current public names.
- If behavior intentionally differs from .NET, document the difference explicitly.
- Do not describe an intentional design difference as missing parity.
