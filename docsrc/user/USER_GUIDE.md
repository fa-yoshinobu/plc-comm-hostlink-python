# User Guide: KEYENCE Host Link Python

This guide covers the recommended high-level helper API only.

Use these helpers for normal application code:

- `open_and_connect`
- `read_typed`
- `write_typed`
- `write_bit_in_word`
- `read_named`
- `poll`
- `read_words`
- `read_dwords`

Raw protocol methods and low-level client APIs are intentionally left to the
maintainer documentation.

## Installation

```bash
pip install .
```

## Connect Once

```python
import asyncio

from hostlink import open_and_connect


async def main() -> None:
    async with await open_and_connect("192.168.250.100", 8501) as client:
        print("Connected")


if __name__ == "__main__":
    asyncio.run(main())
```

`open_and_connect` returns a connected async client object that is then used by
the helper functions below.

## Typed Read and Write

Supported dtype codes:

| dtype | Meaning | Width |
|---|---|---|
| `U` | unsigned 16-bit | 1 word |
| `S` | signed 16-bit | 1 word |
| `D` | unsigned 32-bit | 2 words |
| `L` | signed 32-bit | 2 words |
| `F` | IEEE 754 float32 | 2 words |

```python
import asyncio

from hostlink import open_and_connect, read_typed, write_typed


async def main() -> None:
    async with await open_and_connect("192.168.250.100") as client:
        dm0 = await read_typed(client, "DM0", "U")
        signed = await read_typed(client, "DM10", "S")
        counter = await read_typed(client, "DM20", "D")
        temp = await read_typed(client, "DM40", "F")

        await write_typed(client, "DM100", "U", dm0)
        await write_typed(client, "DM110", "S", signed)
        await write_typed(client, "DM120", "D", counter)
        await write_typed(client, "DM140", "F", temp)


if __name__ == "__main__":
    asyncio.run(main())
```

`F` is implemented in the helper layer by converting two `.U` words as
float32.

## Block Reads

Use block helpers when you need contiguous data from a word area.

```python
words = await read_words(client, "DM200", 8)
dwords = await read_dwords(client, "DM300", 4)
```

- `read_words` returns `list[int]`
- `read_dwords` returns `list[int]` assembled from adjacent words

## Bit in Word

Use `write_bit_in_word` for bit updates inside word devices such as `DM`, `EM`,
`FM`, `W`, or `Z`.

```python
await write_bit_in_word(client, "DM500", bit_index=0, value=True)
await write_bit_in_word(client, "DM500", bit_index=3, value=False)
```

This helper performs a read-modify-write so that the other 15 bits remain
unchanged.

## Mixed Snapshots with `read_named`

`read_named` accepts mixed address notations in a single call.

Supported notation:

| Format | Meaning |
|---|---|
| `"DM100"` | unsigned 16-bit |
| `"DM100:S"` | signed 16-bit |
| `"DM100:D"` | unsigned 32-bit |
| `"DM100:L"` | signed 32-bit |
| `"DM100:F"` | float32 |
| `"DM100.3"` | bit 3 inside the word |
| `"DM100.A"` | bit 10 inside the word |

```python
snapshot = await read_named(
    client,
    ["DM100", "DM101:S", "DM102:D", "DM104:F", "DM200.0", "DM200.A"],
)
print(snapshot)
```

Bit indices use hexadecimal notation from `0` to `F`.

## Polling

`poll` repeatedly yields the same kind of snapshot dictionary.

```python
async for snapshot in poll(
    client,
    ["DM100", "DM101:L", "DM200.3"],
    interval=1.0,
):
    print(snapshot)
```

Break out of the loop or cancel the task to stop polling.

## Error Handling

| Exception | Meaning |
|---|---|
| `HostLinkBaseError` | Base class for library errors |
| `HostLinkError` | PLC returned an error code |
| `HostLinkProtocolError` | Local validation or parsing failure |
| `HostLinkConnectionError` | Connect, disconnect, socket, or timeout failure |

```python
from hostlink.errors import (
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
)


try:
    value = await read_typed(client, "DM100", "U")
except HostLinkProtocolError as ex:
    print(f"Protocol error: {ex}")
except HostLinkConnectionError as ex:
    print(f"Connection error: {ex}")
except HostLinkError as ex:
    print(f"PLC error: code={ex.code} response={ex.response}")
```

## Recommended Samples

| API / workflow | Sample | Purpose |
|---|---|---|
| `open_and_connect`, `read_typed`, `write_typed`, `read_words`, `read_dwords`, `write_bit_in_word`, `read_named`, `poll` | `samples/high_level_async.py` | Full async walkthrough of the helper layer |
| Synchronous entrypoint over the helper layer | `samples/high_level_sync.py` | CLI wrapper that uses `asyncio.run` internally |
| `read_typed`, `write_typed` | `samples/basic_high_level_rw.py` | Focused typed read and write example |
| `read_named` | `samples/named_snapshot.py` | Mixed snapshot example |
| `poll` | `samples/polling_monitor.py` | Repeated snapshot monitoring example |
