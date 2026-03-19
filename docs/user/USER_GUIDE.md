# KEYENCE KV Host Link Python User Guide

This guide describes how to set up and use the `hostlink` library to communicate with KEYENCE KV series PLCs.

## 1. Prerequisites

- **Python**: 3.11 or later.
- **PLC Hardware**: KEYENCE KV-8000, KV-7500, KV-5500, KV-3000, KV-1000, or KV-N series.
- **Ethernet Unit**: KV-XLE02, KV-LE21V, or built-in Ethernet port.

## 2. PLC Configuration

To use Host Link communication, you must enable the "Upper Link" or "Host Link" protocol on your PLC's Ethernet port.

### Settings in KV Studio:
1. Open **Unit Configuration**.
2. Select your Ethernet unit (or CPU built-in port).
3. Set the **IP Address** (e.g., `192.168.0.10`).
4. Enable **Host Link (Upper Link) Communication**.
5. Set the **Port Number** (default is `8501`).
6. Select **TCP** or **UDP** as the transport.

## 3. Basic Usage

### Synchronous Client

Ideal for simple scripts or standalone tools.

```python
from hostlink import HostLinkClient

# Connect to PLC
with HostLinkClient("192.168.0.10", port=8501) as plc:
    # Read a single word from DM0 (signed 16-bit)
    val = plc.read("DM0.S")
    print(f"Current value: {val}")

    # Write a value to DM0
    plc.write("DM0.S", val + 1)

    # Read multiple relays (R0 to R9)
    relays = plc.read_consecutive("R0", 10)
    print(f"Relays: {relays}")
```

### Asynchronous Client

Ideal for high-performance applications or GUI integration.

```python
import asyncio
from hostlink import AsyncHostLinkClient

async def run_plc_task():
    async with AsyncHostLinkClient("192.168.0.10") as plc:
        # Read a 32-bit unsigned value from DM100
        val = await plc.read("DM100.D")
        print(f"32-bit value: {val}")

asyncio.run(run_plc_task())
```

## 4. Device Addressing

The library supports standard KEYENCE device addresses. You can optionally append a data format suffix.

### Examples:
- `R0`: Relay 0 (bit)
- `DM100`: Data Memory 100 (defaults to unsigned 16-bit)
- `DM100.S`: Data Memory 100 (signed 16-bit)
- `DM200.D`: Data Memory 200 (unsigned 32-bit, uses DM200 and DM201)
- `EM0.H`: Extended Memory 0 (Hexadecimal)

### Supported Suffixes:
- `.U`: Unsigned 16-bit (Default for words)
- `.S`: Signed 16-bit
- `.D`: Unsigned 32-bit
- `.L`: Signed 32-bit
- `.H`: Hexadecimal (16-bit)

## 5. Troubleshooting

### Common Errors:
- `HostLinkConnectionError`: Check your IP address, port number, and network cables. Ensure KV Studio "Upper Link" is enabled.
- `HostLinkError (E0)`: Invalid device address. Check if the address exists on your PLC model.
- `HostLinkError (E4)`: Write disabled. Check if the PLC is in a state that allows writing (e.g., check CPU lock or memory protection).

### Debugging:
You can use `send_raw()` to test custom commands directly:
```python
response = plc.send_raw("?K")
print(f"Model Code: {response}")
```
