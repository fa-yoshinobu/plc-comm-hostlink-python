# (KEYENCE KV) Host Link Communication Python

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Static Analysis: Ruff](https://img.shields.io/badge/Lint-Ruff-black.svg)](https://github.com/astral-sh/ruff)

A Python client library for KEYENCE KV series PLCs using the **Host Link Communication** protocol. Designed for reliable communication with KV-8000, KV-7500, and other compatible models.

## Key Features

- **Keyence Focused**: Implements the KV series Upper Link protocol (HOST LINK).
- **Modern Python**: Strictly typed and designed for performance and reliability.
- **Zero Mojibake**: English-only documentation and UTF-8 encoding standards.
- **CI-Ready**: Integrated quality checks via `run_ci.bat`.

## Quick Start

### Installation
```bash
# (Coming Soon)
# pip install hostlink-python
```

### Basic Usage
```python
from hostlink.client import HostLinkClient

# Connect to a KEYENCE KV PLC
client = HostLinkClient("192.168.1.10", 8501)

# Read D100 (Word)
val = client.read("D100")
print(f"Value: {val}")
```

## Documentation

Follows the workspace-wide hierarchical documentation policy:

- [**API Reference**](docs/user/API_REFERENCE.md): Detailed method definitions.
- [**QA Reports**](docs/validation/reports/): Formal evidence of communication with Keyence hardware.
- [**Protocol Spec**](docs/maintainer/PROTOCOL_SPEC.md): Internal technical details of the Host Link protocol.

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

Distributed under the [MIT License](LICENSE).

