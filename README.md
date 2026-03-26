[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-hostlink-python/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

# KV Host Link Protocol for Python

![Illustration](docsrc/assets/kv.png)

High-performance Python library for KEYENCE KV series PLCs using the Host Link
(Upper Link) protocol.

This README intentionally covers the recommended high-level helper API only:
`open_and_connect`, `read_typed`, `write_typed`, `write_bit_in_word`,
`read_named`, `poll`, `read_words`, and `read_dwords`.

Low-level client methods and protocol-level details are kept in maintainer
documentation.

## Key Features

- High-level helper API for typed reads, writes, snapshots, and polling
- Typed helpers for `U`, `S`, `D`, `L`, and helper-level `F`
- Mixed snapshots with `read_named`
- Batch-friendly polling with `poll`
- Contiguous block helpers with `read_words` and `read_dwords`
- Hardware-verified against KV-7500

## Installation

```bash
git clone https://github.com/fa-yoshinobu/plc-comm-hostlink-python.git
cd plc-comm-hostlink-python
pip install -e .
```

## Quick Start

```python
import asyncio

from hostlink import open_and_connect, read_named, read_typed, write_typed


async def main() -> None:
    async with await open_and_connect("192.168.250.100", 8501) as client:
        dm0 = await read_typed(client, "DM0", "U")
        await write_typed(client, "DM10", "U", dm0)

        snapshot = await read_named(
            client,
            ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.0"],
        )
        print(snapshot)


if __name__ == "__main__":
    asyncio.run(main())
```

## Common Workflows

Typed block reads:

```python
words = await read_words(client, "DM100", 10)
dwords = await read_dwords(client, "DM200", 4)
```

Bit-in-word update:

```python
await write_bit_in_word(client, "DM50", bit_index=3, value=True)
```

Polling:

```python
async for snapshot in poll(client, ["DM100", "DM101:L", "DM50.3"], interval=1.0):
    print(snapshot)
```

## Sample Programs

User-facing high-level examples:

- `samples/high_level_async.py`
- `samples/high_level_sync.py`
- `samples/basic_high_level_rw.py`
- `samples/named_snapshot.py`
- `samples/polling_monitor.py`

API and workflow to sample mapping:

| API / workflow | Primary sample | Purpose |
|---|---|---|
| `open_and_connect`, `read_typed`, `write_typed`, `read_words`, `read_dwords`, `write_bit_in_word`, `read_named`, `poll` | `samples/high_level_async.py` | End-to-end async walkthrough of the full helper surface |
| Synchronous CLI entrypoint for the same helper surface | `samples/high_level_sync.py` | Shows how to wrap the async helper API behind `asyncio.run` |
| `read_typed`, `write_typed` | `samples/basic_high_level_rw.py` | Focused typed read/write mirror example |
| `read_named` | `samples/named_snapshot.py` | Mixed typed and bit-in-word snapshot example |
| `poll` | `samples/polling_monitor.py` | Repeated snapshot monitoring loop |

Run examples:

```bash
python samples/high_level_async.py --host 192.168.250.100
python samples/high_level_sync.py --host 192.168.250.100
python samples/basic_high_level_rw.py --host 192.168.250.100
python samples/named_snapshot.py --host 192.168.250.100
python samples/polling_monitor.py --host 192.168.250.100 --poll-count 5
```

## Documentation

User documentation:

- [User Guide](docsrc/user/USER_GUIDE.md)
- [API Reference](docsrc/user/API_REFERENCE.md)
- [Troubleshooting](docsrc/user/TROUBLESHOOTING.md)
- [Performance Tuning](docsrc/user/PERFORMANCE_GUIDE.md)
- [Samples](samples/README.md)

Maintainer and QA documentation:

- [QA Evidence (KV-7500)](docsrc/validation/reports/QA_REPORT_20260319_KV7500.md)
- [Protocol Specification](docsrc/maintainer/PROTOCOL_SPEC.md)
- [Specification Coverage](docsrc/maintainer/SPEC_COVERAGE.md)
- [API Unification Policy](docsrc/maintainer/API_UNIFICATION_POLICY.md)

## Verified Hardware

- CPU: KV-7500, KV-8000, KV-X550
- Ethernet: built-in Ethernet port and KV-XLE02
- Transport: TCP and UDP

## Development and Release Checks

```bash
run_ci.bat
release_check.bat
```

`run_ci.bat` runs lint, format, mypy, high-level docs coverage checks,
user-facing sample validation, and tests.

`release_check.bat` runs `run_ci.bat` and then rebuilds the published docs.

## License

Distributed under the MIT License.
