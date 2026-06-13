# KV Host Link Protocol for Python

[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/fa-yoshinobu/plc-comm-hostlink-python?label=release)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/kv-hostlink.svg)](https://pypi.org/project/kv-hostlink/)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-hostlink-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

![Illustration](https://raw.githubusercontent.com/fa-yoshinobu/plc-comm-hostlink-python/main/docsrc/assets/kv.png)

High-performance Python library for KEYENCE KV series PLCs using the Host Link (Upper Link) protocol.

This README intentionally covers the recommended high-level helper API only:

- `HostLinkConnectionOptions`
- `open_and_connect`
- `parse_address`
- `try_parse_address`
- `format_address`
- `normalize_address`
- `read_typed`
- `read_timer_counter` / `read_timer` / `read_counter`
- `write_typed`
- `read_comments`
- `write_bit_in_word`
- `read_named`
- `poll`
- `read_words_single_request`
- `read_dwords_single_request`
- `read_words_chunked`
- `read_dwords_chunked`
- `read_expansion_unit_buffer`
- `write_expansion_unit_buffer`

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
- digital trimmer scalar forms on supported PLCs: `AT0:D` / default `AT0`

High-level address syntax is shared across the PLC helper libraries:

- use `:` for data types and special views: `DM100:U`, `DM100:S`, `DM100:D`,
  `DM100:L`, `DM100:F`, `DM100:H`, `DM100:COMMENT`
- use `.` only for bit-in-word access: `DM100.0` through `DM100.F`
- `DM100.D` is bit `0xD` / bit 13, not a 32-bit data type request
- Host Link frames still use the manual suffix form internally, so
  `DM100:D` is sent as `RD DM100.D`

`read_typed(client, "T10", "D")` and `read_named(client, ["T10"])` return the
timer/counter preset value for compatibility. Use
`read_timer_counter(client, "T10")` when the Host Link composite fields are
needed: `status`, `current`, and `preset`.

`AT` is not listed in the WR/WRS device table, so write helpers reject AT before
sending.

`T` / `C` preset writes use Host Link `WS` / `WSS` only on KV-8000/7000-series
CPU units. Manuals state that other CPU units do not support those commands
and return abnormal response `E1` when they are executed.

See the full public table in [Supported PLC Registers](docsrc/user/SUPPORTED_REGISTERS.md).
For model-specific published ranges, call `client.read_device_range_catalog()` or `device_range_catalog_for_plc_profile("keyence:kv-8000")`.

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

## Samples

- [high_level_async.py](samples/high_level_async.py)
- [high_level_sync.py](samples/high_level_sync.py)
- [basic_high_level_rw.py](samples/basic_high_level_rw.py)
- [named_snapshot.py](samples/named_snapshot.py)
- [polling_monitor.py](samples/polling_monitor.py)

## Common Workflows

Address normalization:

```python
from hostlink import format_address, normalize_address, parse_address

print(normalize_address("dm100"))    # DM100
print(normalize_address("dm100.a"))  # DM100.A

parsed = parse_address("dm100.a")
print(parsed.base_device, parsed.bit_index)  # DM100 10
print(format_address(parsed))                # DM100.A
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

Expansion unit buffer access:

```python
from hostlink import read_expansion_unit_buffer, write_expansion_unit_buffer

buffer_words = await read_expansion_unit_buffer(client, 1, 100, 2, data_format="U")
await write_expansion_unit_buffer(client, 1, 200, buffer_words, data_format="U")
```

Comment read:

```python
comment = await read_comments(client, "DM100")
```

XYM aliases are also accepted for comment reads, for example `D10`, `E20`, `F30`, `M100`, `L200`, `X100`, and `Y100`.

## Verified Hardware

- CPU: `KV-7500`
- CPU: `KV-X500`
- Ethernet: built-in Ethernet port and `KV-XLE02`
- Transport: `TCP` and `UDP`

## Development and Release Checks

```bash
run_ci.bat
release_check.bat
```

## License

Distributed under the MIT License.
