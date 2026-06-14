[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml) [![Release](https://img.shields.io/github/v/release/fa-yoshinobu/plc-comm-hostlink-python?label=release)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/releases/latest) [![PyPI](https://img.shields.io/pypi/v/kv-hostlink.svg)](https://pypi.org/project/kv-hostlink/) [![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff) [![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

# KV Host Link Protocol for Python

KEYENCE KV series PLC communication library for Python via the Host Link (Upper Link) protocol.

## Supported profiles

| Canonical profile | Hardware | Notes |
|---|---|---|
| `keyence:kv-nano` | KV-NANO | Standard device names. |
| `keyence:kv-nano-xym` | KV-NANO | XYM alias names. |
| `keyence:kv-3000` | KV-3000 | Standard device names with EM, FM, ZF, VM, VB, CTH, CTC, and AT ranges. |
| `keyence:kv-3000-xym` | KV-3000 | XYM alias names. |
| `keyence:kv-5000` | KV-5000 / KV-5500 | Standard device names with EM, FM, ZF, VM, VB, CTH, CTC, and AT ranges. |
| `keyence:kv-5000-xym` | KV-5000 / KV-5500 | XYM alias names. |
| `keyence:kv-7000` | KV-7000 / KV-7300 / KV-7500 | Large R, MR, DM, EM, FM, ZF, VM, VB, and AT ranges. |
| `keyence:kv-7000-xym` | KV-7000 / KV-7300 / KV-7500 | XYM alias names. |
| `keyence:kv-8000` | KV-8000 | Largest VM range in the embedded catalog. |
| `keyence:kv-8000-xym` | KV-8000 | XYM alias names. |
| `keyence:kv-x500` | KV-X500 / KV-X520 / KV-X530 / KV-X550 / KV-X310 | AT, VM, VB, CTH, and CTC are not available. |
| `keyence:kv-x500-xym` | KV-X500 / KV-X520 / KV-X530 / KV-X550 / KV-X310 | XYM alias names; AT, VM, VB, CTH, and CTC are not available. |

## Supported device types

| Device | What you use it for |
|---|---|
| `DM` | General data memory words, usually the safest first read target. |
| `EM` | Extended data memory words on models that provide EM ranges. |
| `FM` | File memory words on models that provide FM ranges. |
| `R` | Relay bit devices using KEYENCE two-digit bit notation. |
| `MR` | Internal relay bit devices using two-digit bit notation. |
| `T` | Timer current, status, and preset values. |
| `C` | Counter current, status, and preset values. |
| `X` / `Y` | Input and output aliases in XYM profiles, using decimal-bank plus hex-bit notation. |

See [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md) for the full table.

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
| [Getting started](docsrc/user/GETTING_STARTED.md) | Install the package, connect to your PLC, and run your first read/write. |
| [Usage guide](docsrc/user/USAGE_GUIDE.md) | Use typed reads, writes, snapshots, blocks, bit-in-word updates, polling, timers, comments, and expansion buffer access. |
| [Supported registers](docsrc/user/SUPPORTED_REGISTERS.md) | Check supported device families and address forms. |
| [PLC profiles](docsrc/user/PROFILES.md) | Choose the canonical profile that matches your PLC model and device ranges. |
| [Gotchas](docsrc/user/GOTCHAS.md) | Check the common Host Link failure modes before troubleshooting wiring or ladder code. |
| [Examples](samples/README.md) | Run sample scripts that exercise the high-level API: `samples/high_level_async.py`, `samples/high_level_sync.py`, `samples/basic_high_level_rw.py`, `samples/named_snapshot.py`, and `samples/polling_monitor.py`. |

## Hardware verified

Physical communication has been verified with `KV-7500` over the built-in Ethernet port and `KV-XLE02` using `TCP` and `UDP`.

## License and registry

Distributed under the MIT License.

PyPI package: https://pypi.org/project/kv-hostlink/
