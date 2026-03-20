# User Guide: KEYENCE Host Link Python

High-performance Python client for KEYENCE KV series PLCs using the Host Link protocol.

## 1. Installation
```bash
pip install .
```

## 2. Basic Usage
```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.1.10", 8501) as plc:
    # Read DM100
    val = plc.read("DM100")
    print(f"DM100: {val}")
```

## 3. Device Support
Supports all KV series devices including R, DM, MR, EM, etc.
Use suffixes like `.S`, `.L`, `.H` for different data types.
