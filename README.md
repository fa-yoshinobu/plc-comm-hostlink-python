# Pr_HOST-LINK-COMMUNICATION-FUNCTION

Python library for KEYENCE KV-XLE02 Host Link communication (TCP/UDP).

## Features

- **Synchronous and Asynchronous clients**: Supports both standard blocking calls and `asyncio`.
- **Full Command Coverage**: Supports basic commands (RD, WR, RDS, WRS), forced set/reset, monitor registration, and more.
- **Protocol Support**: Works over both TCP and UDP.
- **Type Safety**: Automatic parsing and validation of device addresses and data formats.

## Installation

```bash
pip install .
```

## Usage

### Synchronous Client (TCP)

```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.0.10") as plc:
    plc.change_mode("RUN")
    value = plc.read("DM200.S")
    plc.write("DM200.S", 1234)
    values = plc.read_consecutive("R100", 4)
```

### Asynchronous Client (TCP)

```python
import asyncio
from hostlink import AsyncHostLinkClient

async def main():
    async with AsyncHostLinkClient("192.168.0.10") as plc:
        await plc.change_mode("RUN")
        value = await plc.read("DM200.S")
        await plc.write("DM200.S", 1234)
        values = await plc.read_consecutive("R100", 4)

asyncio.run(main())
```

### UDP Support

```python
plc = HostLinkClient("192.168.0.10", transport="udp")
```

## Development & Testing

### Run Tests

```bash
# Install test dependencies
pip install ".[test]"

# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=hostlink tests/
```

### CI/CD

This project uses GitHub Actions for continuous integration. Every push to the `main` branch or pull request triggers the automated test suite across multiple Python versions (3.9 - 3.12).
