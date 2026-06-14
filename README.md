[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml) [![Release](https://img.shields.io/github/v/release/fa-yoshinobu/plc-comm-hostlink-python?label=release)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/releases/latest) [![PyPI](https://img.shields.io/pypi/v/kv-hostlink.svg)](https://pypi.org/project/kv-hostlink/) [![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/GETTING_STARTED/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff) [![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

# KEYENCE KV Host Link for Python

Python library for KEYENCE KV Host Link PLC communication.

## Supported PLC profiles

The maintained profile table is in [PLC profiles](docsrc/user/PROFILES.md). Choose one exact canonical PLC profile from that table.

## Supported device types

The maintained device and range tables are in [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md). Use that page for supported device families, address syntax, and profile-specific notes.

## Installation

```bash
pip install kv-hostlink
```

## Quick example

```python
import asyncio
from hostlink import HostLinkConnectionOptions, device_range_catalog_for_plc_profile, open_and_connect, read_typed

async def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-7000")
    options = HostLinkConnectionOptions(host="192.168.250.100", port=8501)
    async with await open_and_connect(options) as client:
        dm0 = await read_typed(client, "DM0", "U")
        print(f"{catalog.plc_profile} DM0 = {dm0}")

asyncio.run(main())
```

## Documentation

| Page | Use it for |
|---|---|
| [Full documentation site](https://fa-yoshinobu.github.io/plc-comm-docs-site/) | Unified docs for all PLC communication libraries. |
| [Getting started](docsrc/user/GETTING_STARTED.md) | Install the package, connect to your PLC, and run your first read/write. |
| [Usage guide](docsrc/user/USAGE_GUIDE.md) | Use typed reads, writes, snapshots, blocks, bit-in-word updates, polling, timers, comments, and expansion buffer access. |
| [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md) | Check supported device families and address forms. |
| [PLC profiles](docsrc/user/PROFILES.md) | Choose the canonical profile that matches your PLC model and device ranges. |
| [Gotchas](docsrc/user/GOTCHAS.md) | Check the common Host Link failure modes before troubleshooting wiring or ladder code. |
| [Examples](samples/README.md) | Run maintained Python samples. |

## Hardware verified

Live-device verification is maintained in [Latest communication verification](docsrc/user/LATEST_COMMUNICATION_VERIFICATION.md).
See that page for verified PLC models, transports, dates, limitations, and retained validation notes.

## License and registry

| Item | Value |
| --- | --- |
| License | [MIT](LICENSE) |
| Registry | [PyPI](https://pypi.org/project/kv-hostlink/) |
| Package | `kv-hostlink` |
