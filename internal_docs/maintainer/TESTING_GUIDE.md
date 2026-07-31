# Testing Guide

This document describes the test structure and verification approach for `plc-comm-hostlink-python`.

## Automated Tests

The test suite is under `tests/`.

Run with:

```powershell
call run_ci.bat
```

`run_ci.bat` is the canonical local gate. It runs Ruff, formatting, mypy,
documentation/sample validation, and the complete pytest suite.

`scripts/check_source_archive.ps1` verifies the independently distributed
GitHub source archive. It requires the complete tracked `tests/` tree and
fixtures, extracts the archive under `D:\APP`, runs pytest, and builds the
package from that extracted tree. This is separate from wheel/sdist content
validation.

## Test Coverage

The test suite covers:

- Frame encoding and decoding for all supported commands
- Device address parsing (`R0`, `DM100`, `B1F`, etc.)
- Error response parsing (`E1`, `E2`, `E3`)
- Multi-device read/write round-trips (mock transport)
- 32-bit value packing (DWord, Float32)
- Extension utilities: `read_typed`, `write_typed`, `read_named`, `poll`

## Hardware Checks

For live hardware checks, use the scripts in `scripts/`.
Keep current target support in the profile data, not in this maintainer guide.

## Cross-Library Parity

The Python library is kept semantically aligned with `plc-comm-hostlink-dotnet`.

When adding or changing a method, verify:

1. The equivalent .NET operation exists and has the same semantics.
2. `HostLinkClient` and `AsyncHostLinkClient` stay internally aligned.
3. Exported helper utilities in `utils.py` are updated where applicable.
4. Intentional public API differences stay covered by tests and public docs.

## Linting and Type Checking

Use `run_ci.bat` so lint and type-check targets stay aligned with CI.
