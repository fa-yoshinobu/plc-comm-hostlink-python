[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-hostlink-python/)
[![PyPI](https://img.shields.io/pypi/v/kv-hostlink.svg)](https://pypi.org/project/kv-hostlink/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

# KV Host Link Protocol for Python

![Illustration](https://raw.githubusercontent.com/fa-yoshinobu/plc-comm-hostlink-python/main/docsrc/assets/kv.png)

High-performance Python library for KEYENCE KV series PLCs using the Host Link (Upper Link) protocol.

This README intentionally covers the recommended high-level helper API only:

- `HostLinkConnectionOptions`
- `open_and_connect`
- `normalize_address`
- `read_typed`
- `write_typed`
- `read_comments`
- `write_bit_in_word`
- `read_named`
- `poll`
- `read_words_single_request`
- `read_dwords_single_request`
- `read_words_chunked`
- `read_dwords_chunked`

## Installation

```bash
pip install kv-hostlink
```

Published metadata lives at <https://pypi.org/project/kv-hostlink/>, where wheel and tarball downloads are also available.

## Quick Start

```python
import asyncio

from hostlink import HostLinkConnectionOptions, open_and_connect, read_named, read_typed, write_typed


async def main() -> None:
    options = HostLinkConnectionOptions(
        host="192.168.250.100",
        port=8501,
        transport="tcp",
        timeout=3.0,
    )
    async with await open_and_connect(options) as client:
        dm0 = await read_typed(client, "DM0", "U")
        await write_typed(client, "DM10", "U", dm0)

        snapshot = await read_named(
            client,
            ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.0", "DM20:COMMENT"],
        )
        print(snapshot)


if __name__ == "__main__":
    asyncio.run(main())
```

## Supported PLC Registers

Start with these public high-level families first:

- word devices: `DM`, `EM`, `FM`, `W`, `ZF`, `TM`, `Z`
- bit devices: `R`, `MR`, `LR`, `CR`, `X`, `Y`, `M`, `L`
- typed forms: `DM100:S`, `DM100:D`, `DM100:L`, `DM100:F`
- comment form: `DM100:COMMENT`
- bit-in-word forms: `DM100.3`, `DM100.A`
- timer/counter scalar forms: `T10:D`, `C10:D`

See the full public table in [Supported PLC Registers](docsrc/user/SUPPORTED_REGISTERS.md).

## Public Documentation

- [Getting Started](docsrc/user/GETTING_STARTED.md)
- [Supported PLC Registers](docsrc/user/SUPPORTED_REGISTERS.md)
- [Latest Communication Verification](docsrc/user/LATEST_COMMUNICATION_VERIFICATION.md)
- [User Guide](docsrc/user/USER_GUIDE.md)
- [API Reference](docsrc/user/API_REFERENCE.md)
- [Troubleshooting](docsrc/user/TROUBLESHOOTING.md)
- [Performance Guide](docsrc/user/PERFORMANCE_GUIDE.md)
- [Samples](samples/README.md)

Maintainer-only notes and retained evidence live under `internal_docs/`.

## Common Workflows

Address normalization:

```python
from hostlink import normalize_address

print(normalize_address("dm100"))    # DM100
print(normalize_address("dm100.a"))  # DM100.A
```

Typed block reads:

```python
words = await read_words_single_request(client, "DM100", 10)
dwords = await read_dwords_single_request(client, "DM200", 4)
```

Bit-in-word update:

```python
await write_bit_in_word(client, "DM50", bit_index=3, value=True)
```

Comment read:

```python
comment = await read_comments(client, "DM100")
```

XYM aliases are also accepted for comment reads, for example `D10`, `E20`, `F30`, `M100`, `L200`, `X100`, and `Y100`.

## Verified Hardware

- CPU: `KV-7500`
- Ethernet: built-in Ethernet port and `KV-XLE02`
- Transport: `TCP` and `UDP`

## Development and Release Checks

```bash
run_ci.bat
release_check.bat
```

## License

Distributed under the MIT License.
