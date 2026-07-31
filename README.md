[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/plc-comm-kv-hostlink.svg)](https://pypi.org/project/plc-comm-kv-hostlink/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/blob/main/LICENSE)

# KEYENCE KV Host Link for Python

Python library for KEYENCE KV Host Link PLC communication.

## PLC Comm Family

This library is part of the plc-comm family. See the [package matrix](https://fa-yoshinobu.github.io/plc-comm-docs-site/package-matrix/) for protocol, language, registry, and install-command mapping.

## Supported PLC profiles

The maintained profile table is in [PLC profiles](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/PROFILES/). Choose one exact canonical PLC profile from that table.

## Supported device types

The shared device and range tables are in the [KV Host Link Device Ranges](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/device-ranges/) page. Use that page for supported device families, address syntax, and profile-specific notes.

## Installation

```bash
pip install plc-comm-kv-hostlink
```

The PyPI wheel and source distribution contain the files needed to install and
use the library; they do not carry the maintained sample tree or documentation
source. Use the GitHub repository for current samples and the shared
documentation site for user guides. GitHub source archives include the test
suite and fixtures so their standard build and test commands are self-contained.

## Quick example

```python
import asyncio
from hostlink import HostLinkConnectionOptions, device_range_catalog_for_plc_profile, open_and_connect, read_typed

async def main() -> None:
    catalog = device_range_catalog_for_plc_profile("keyence:kv-8000")
    options = HostLinkConnectionOptions(
        host="192.168.250.100",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="tcp",
    )
    async with await open_and_connect(options) as client:
        dm0 = await read_typed(client, "DM0", "U")
        print(f"DM0 = {dm0}")

asyncio.run(main())
```

## Documentation

| Page | Use it for |
|---|---|
| [Full documentation site](https://fa-yoshinobu.github.io/plc-comm-docs-site/) | Unified docs for all PLC communication libraries. |
| [Getting started](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/GETTING_STARTED/) | Install the package, connect to your PLC, and run your first read/write. |
| [Usage guide](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/USAGE_GUIDE/) | Use the high-level API and common Host Link workflows. |
| [API reference](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/API_REFERENCE/) | Find public client methods, helpers, profile APIs, and error types. |
| [PLC profiles](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/PROFILES/) | Choose the canonical profile that matches your PLC model and device ranges. |
| [KV Host Link Device Ranges](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/device-ranges/) | Check shared device families, address notation, and range tables. |
| [KV Host Link Troubleshooting & Codes](https://fa-yoshinobu.github.io/plc-comm-docs-site/plc-setup/kv/troubleshooting-codes/) | Troubleshoot common port, profile, address, write-permission, and PLC error-code symptoms. |
| [Gotchas](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/GOTCHAS/) | Check whether this library has any current library-specific caveats. |
| [Performance](https://fa-yoshinobu.github.io/plc-comm-docs-site/performance/) | See measured latency, throughput, and long-run soak results from real PLC hardware. |
| [Choosing a Language](https://fa-yoshinobu.github.io/plc-comm-docs-site/choosing-a-language/) | Compare the .NET, Python, Rust, C++, and Node-RED implementations before you pick one. |
| [Examples](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/blob/main/samples/README.md) | Run maintained Python samples: `samples/high_level_async.py`, `samples/high_level_sync.py`, `samples/basic_high_level_rw.py`, `samples/named_snapshot.py`, `samples/polling_monitor.py`. |

For a zero-code connectivity check, see [PLC Scope](https://github.com/fa-yoshinobu/plc-scope-dotnet) (Windows).

## License and registry

| Item | Value |
| --- | --- |
| License | [MIT](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/blob/main/LICENSE) |
| Registry | [PyPI](https://pypi.org/project/plc-comm-kv-hostlink/) |
| Package | `plc-comm-kv-hostlink` |

## Commercial support

If you plan to embed this library in a paid or commercial product, please consider a separate support agreement or supporting the project as a sponsor.

Contact: <https://fa-labo.com/contact.html>
