# Host Link Communication Python

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)

A Python client library for KEYENCE KV series PLCs using the Host Link
Communication protocol.

This published site intentionally focuses on the recommended high-level helper
API:

- `open_and_connect`
- `read_typed`
- `write_typed`
- `read_words`
- `read_dwords`
- `write_bit_in_word`
- `read_named`
- `poll`

Low-level token-oriented client methods are intentionally left out of the
published user site and remain repository-maintainer material.

## Key Features

- High-level typed reads and writes for `U`, `S`, `D`, `L`, and `F`
- Mixed named snapshots with `read_named`
- Repeated snapshot streaming with `poll`
- Contiguous block helpers for words and dwords
- Strict lint, type-check, and test coverage in CI

## Quick Start

### Basic Usage

```python
from hostlink import open_and_connect, read_named, read_typed, write_typed

async def main() -> None:
    client = await open_and_connect("192.168.250.100", 8501)
    async with client:
        dm0 = await read_typed(client, "DM0", "U")
        await write_typed(client, "DM10", "U", dm0)

        snapshot = await read_named(client, ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.0"])
        print(snapshot)
```

## Documentation

- [User Guide](user/USER_GUIDE.md)
- [API Reference](user/API_REFERENCE.md)
- [Performance Guide](user/PERFORMANCE_GUIDE.md)
- [Troubleshooting](user/TROUBLESHOOTING.md)

## Development & CI

This project enforces strict quality standards via `run_ci.bat`.

### Quality Checks
- **Linting & Formatting**: [Ruff](https://ruff.rs/)
- **Type Checking**: [Mypy](http://mypy-lang.org/)
- **Unit Testing**: Python `pytest`

### Local CI Run
```bash
run_ci.bat
```
Validates the code and builds a standalone CLI tool in the `publish/` directory.

## License

Distributed under the MIT License.
