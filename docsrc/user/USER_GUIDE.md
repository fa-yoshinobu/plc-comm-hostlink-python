# User Guide: KEYENCE Host Link Python

Asynchronous Python client for KEYENCE KV series PLCs using the Host Link (Upper Link) protocol.

## Installation

```bash
pip install .
```

---

## Quick Start

### Synchronous client

```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.250.100", 8501) as plc:
    # Read DM100
    val = plc.read("DM100")
    print(f"DM100 = {val}")

    # Write 1234 to DM100
    plc.write("DM100", 1234)
```

### Async client

```python
import asyncio
from hostlink import open_and_connect

async def main():
    async with await open_and_connect("192.168.250.100") as plc:
        val = await plc.read("DM100")
        print(f"DM100 = {val}")

asyncio.run(main())
```

---

## Device Addressing

### Device Types

| Category | Devices |
|----------|---------|
| Bit devices | `R`, `MR`, `LR`, `CR`, `B` |
| Word devices | `DM`, `EM`, `FM`, `W`, `TM`, `CM`, `Z`, `AT` |
| Timer/Counter coil | `T`, `C` |

### Data Format Suffixes

```python
plc.read("DM100")         # raw value (unsigned 16-bit)
plc.read("DM100", ".S")   # signed 16-bit
plc.read("DM100", ".D")   # unsigned 32-bit (2 words)
plc.read("DM100", ".L")   # signed 32-bit (2 words)
plc.read("DM100", ".F")   # float32 (2 words)
plc.read("DM100", ".H")   # hex string
```

### Consecutive Read

```python
# Read 10 consecutive words from DM0
values = await plc.read_consecutive("DM0", 10)
```

---

## Typed Read / Write

Utility functions handle type conversion automatically:

| dtype | Type | Size |
|-------|------|------|
| `"U"` | unsigned 16-bit int | 1 word |
| `"S"` | signed 16-bit int | 1 word |
| `"D"` | unsigned 32-bit int | 2 words |
| `"L"` | signed 32-bit int | 2 words |
| `"F"` | float32 | 2 words |

```python
import asyncio
from hostlink import open_and_connect
from hostlink import read_typed, write_typed

async def main():
    async with await open_and_connect("192.168.250.100") as plc:
        f = await read_typed(plc, "DM100", "F")     # float32
        v = await read_typed(plc, "DM200", "L")     # signed 32-bit
        await write_typed(plc, "DM100", "F", 3.14)
        await write_typed(plc, "DM200", "S", -100)

asyncio.run(main())
```

### Contiguous Array Read

```python
from hostlink import read_words, read_dwords

# Read 10 words from DM0 ↁElist[int]
words = await read_words(plc, "DM0", 10)

# Read 4 DWords (32-bit pairs) from DM0 ↁElist[int]
dwords = await read_dwords(plc, "DM0", 4)
```

### Bit-in-Word Write

```python
from hostlink import write_bit_in_word

# Set bit 3 of DM100 (read-modify-write)
await write_bit_in_word(plc, "DM100", bit_index=3, value=True)
```

---

## Named-Device Read

Read multiple devices in one call using address strings with optional type suffixes.

Address notation:

| Format | Meaning |
|--------|---------|
| `"DM100"` | DM100 as unsigned 16-bit |
| `"DM100:F"` | DM100 as float32 |
| `"DM100:S"` | DM100 as signed 16-bit |
| `"DM100:D"` | DM100-DM101 as unsigned 32-bit |
| `"DM100:L"` | DM100-DM101 as signed 32-bit |
| `"DM100.3"` | Bit 3 of DM100 (bool) |
| `"DM100.A"` | Bit 10 of DM100 (bool) -- bits 10-15 use hex digits A-F |

```python
from hostlink import read_named

result = await read_named(plc, ["DM100", "DM101:F", "DM102:S", "DM0.3"])
# result == {"DM100": 42, "DM101:F": 3.14, "DM102:S": -1, "DM0.3": True}
```

---

## Polling

`poll` yields device snapshots at a fixed interval until the loop is broken.

```python
import asyncio
from hostlink import open_and_connect, poll

async def main():
    async with await open_and_connect("192.168.250.100") as plc:
        async for snapshot in poll(plc, ["DM100", "DM101:F", "DM0.3"], interval=1.0):
            print(snapshot)
            # {"DM100": 42, "DM101:F": 3.14, "DM0.3": True}

asyncio.run(main())
```

Press `Ctrl+C` to stop.

---

## Error Handling

| Exception | Condition |
|-----------|-----------|
| `HostLinkBaseError` | Base class for all host link errors |
| `HostLinkError` | PLC returned an error code (e.g. `!E1`, `!E0`) |
| `HostLinkProtocolError` | Unexpected or malformed response |
| `HostLinkConnectionError` | TCP connection failure |

```python
from hostlink import HostLinkConnectionError, HostLinkError, HostLinkProtocolError

try:
    val = await plc.read("DM100")
except HostLinkProtocolError as e:
    print(f"Protocol error: {e}")
except HostLinkConnectionError as e:
    print(f"Connection error: {e}")
except HostLinkError as e:
    print(f"PLC error: code={e.code}  response={e.response}")
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `HostLinkConnectionError` | Wrong IP or port | Default port is 8501; confirm in KV Studio Ethernet settings |
| `HostLinkProtocolError` | Invalid device name | Check device type and address range for your KV model |
| `TimeoutError` | PLC not responding | Verify network and that the KV Ethernet unit is enabled |
