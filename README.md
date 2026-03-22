
[![CI](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml/badge.svg)](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/workflows/test.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://fa-yoshinobu.github.io/plc-comm-hostlink-python/)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Types-Mypy-blue.svg)](http://mypy-lang.org/)

High-performance Python client library for KEYENCE KV series PLCs using the Host Link (Upper Link) protocol. Designed for mission-critical applications requiring speed, stability, and full specification coverage.

---

## Key Features

- **High Performance**: Achieves 1,000+ operations/sec with TCP/UDP optimizations (TCP_NODELAY enabled).
- **Dual Support**: Provides both Synchronous (HostLinkClient) and Asynchronous (AsyncHostLinkClient) interfaces.
- **Full Spec Coverage**: Supports RD/WR, RDS/WRS, Monitoring (MBS/MWS), Expansion Unit Access (URD/UWR), and more.
- **Hardware Verified**: Formally validated against real KV-7500 hardware.
- **Type Safety**: 100% compliant with mypy for robust development.
- **Industrial Standards**: Built-in support for multiple data formats (.U, .S, .D, .L, .H).

## Installation

```bash
# Clone the repository
git clone https://github.com/fa-yoshinobu/plc-comm-hostlink-python.git
cd plc-comm-hostlink-python

# Install dependencies
pip install -e .
```

## Quick Start

### 1. Synchronous (Simple Scripts)
```python
from hostlink import HostLinkClient

# Connect to KV-7500 via TCP (Default port 8501)
with HostLinkClient("192.168.250.101") as plc:
    # Read Signed 16-bit Word
    val = plc.read("DM0.S")
    print(f"DM0: {val}")

    # Write 32-bit Double Word
    plc.write("DM100.D", 1234567)
```

### 2. Asynchronous (High Concurrency)
```python
import asyncio
from hostlink import AsyncHostLinkClient

async def main():
    async with AsyncHostLinkClient("192.168.250.101", transport="udp") as plc:
        # Batch Read 100 Words
        data = await plc.read_consecutive("DM100", 100)
        print(f"Read {len(data)} words.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Documentation

Detailed guides are available in the docsrc/ directory:

### User Documentation
- [**User Guide**](docsrc/user/USER_GUIDE.md): Getting started and PLC configuration.
- [**API Reference**](docsrc/user/API_REFERENCE.md): Detailed method signatures and classes.
- [**Troubleshooting**](docsrc/user/TROUBLESHOOTING.md): Solutions for connection and protocol errors.
- [**Performance Tuning**](docsrc/user/PERFORMANCE_GUIDE.md): Tips for high-frequency communication.

### Developer & QA Documentation
- [**QA Evidence (KV-7500)**](docsrc/validation/reports/QA_REPORT_20260319_KV7500.md): Formal hardware verification report.
- [**Protocol Specification**](docsrc/maintainer/PROTOCOL_SPEC.md): Technical details of the Host Link protocol.
- [**Specification Coverage**](docsrc/maintainer/SPEC_COVERAGE.md): Implemented vs. Available commands.

---

## Verified Hardware

The following models are formally verified with this library:
- **CPU**: KV-7500, KV-8000, KV-X550 (via ?K model detection)
- **Ethernet Units**: KV-XLE02, Built-in Ethernet Port
- **Protocol**: Host Link (Upper Link), TCP and UDP modes.

## License

Distributed under the MIT License (LICENSE).



