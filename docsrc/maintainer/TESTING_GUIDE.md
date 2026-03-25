# Testing Guide

This document describes the test structure and verification approach for `plc-comm-hostlink-python`.

Related documents:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PROTOCOL_SPEC.md](PROTOCOL_SPEC.md)

## Automated Tests

The test suite is under `tests/`.

Run with:

```powershell
python -m unittest discover -s tests -v
```

Or with pytest:

```powershell
python -m pytest tests/ -v
```

Expected result: all tests pass.

## Test Coverage

The test suite covers:

- Frame encoding and decoding for all supported commands
- Device address parsing (`R0`, `DM100`, `B1F`, etc.)
- Error response parsing (`E1`, `E2`, `E3`)
- Multi-device read/write round-trips (mock transport)
- 32-bit value packing (DWord, Float32)
- Extension utilities: `read_typed`, `write_typed`, `write_bit_in_word`, `poll`

## Hardware Verification

Verified hardware targets:

- KEYENCE KV-7500 (TCP and UDP)

For live hardware verification, use the scripts in `scripts/`.

## Cross-Library Parity

The Python library is kept in sync with `plc-comm-hostlink-dotnet`.

When adding or changing a method, verify:

1. The equivalent .NET method exists and has the same semantics.
2. The async wrapper exists in `AsyncKvHostLinkClient` / `AsyncKvHostLinkDeviceClient`.
3. Extension utilities in `utils.py` are updated where applicable.

## Linting and Type Checking

```powershell
python -m ruff check .
python -m mypy src scripts
```

Both must pass with 0 errors before release.
