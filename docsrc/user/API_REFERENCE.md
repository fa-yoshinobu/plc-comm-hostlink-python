# HostLink Python API Reference

This reference covers the recommended high-level helper API.

It intentionally excludes raw protocol methods and low-level client operations.

## Imports

```python
from hostlink import (
    open_and_connect,
    read_typed,
    write_typed,
    write_bit_in_word,
    read_named,
    poll,
    read_words,
    read_dwords,
)
from hostlink.errors import (
    HostLinkBaseError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
)
```

## Exceptions

- `HostLinkBaseError`: base type for library exceptions
- `HostLinkError`: PLC returned an error response such as `E0`, `E1`, or `E6`
- `HostLinkProtocolError`: invalid address, invalid dtype, malformed response, or local validation failure
- `HostLinkConnectionError`: connect, disconnect, socket, or timeout failure

## Connection Helper

### `await open_and_connect(host, port=8501, transport="tcp", timeout=3.0)`

Create and connect a client for use with the helper functions.

Parameters:

- `host`: PLC IP address or hostname
- `port`: Host Link port, default `8501`
- `transport`: `"tcp"` or `"udp"`
- `timeout`: socket timeout in seconds

Returns:

- A connected async client object for use with the helpers below

Example:

```python
async with await open_and_connect("192.168.250.100", 8501) as client:
    ...
```

## Typed Helpers

Supported dtype codes:

| dtype | Meaning | Width |
|---|---|---|
| `U` | unsigned 16-bit | 1 word |
| `S` | signed 16-bit | 1 word |
| `D` | unsigned 32-bit | 2 words |
| `L` | signed 32-bit | 2 words |
| `F` | IEEE 754 float32 | 2 words |

### `await read_typed(client, device, dtype)`

Read one typed value.

Parameters:

- `client`: connected client from `open_and_connect`
- `device`: base word device such as `"DM100"`
- `dtype`: one of `U`, `S`, `D`, `L`, `F`

Returns:

- `int` for `U`, `S`, `D`, `L`
- `float` for `F`

Example:

```python
value = await read_typed(client, "DM100", "F")
```

### `await write_typed(client, device, dtype, value)`

Write one typed value.

Parameters:

- `client`: connected client from `open_and_connect`
- `device`: base word device such as `"DM100"`
- `dtype`: one of `U`, `S`, `D`, `L`, `F`
- `value`: `int` or `float`

Example:

```python
await write_typed(client, "DM100", "D", 123456)
```

## Contiguous Block Helpers

### `await read_words(client, device, count)`

Read contiguous unsigned 16-bit words.

Parameters:

- `device`: start address such as `"DM200"`
- `count`: number of words

Returns:

- `list[int]`

### `await read_dwords(client, device, count)`

Read contiguous unsigned 32-bit values from adjacent words.

Parameters:

- `device`: start address such as `"DM300"`
- `count`: number of 32-bit values

Returns:

- `list[int]`

Example:

```python
words = await read_words(client, "DM200", 8)
dwords = await read_dwords(client, "DM300", 4)
```

## Bit in Word

### `await write_bit_in_word(client, device, bit_index, value)`

Update a single bit inside a word device by read-modify-write.

Parameters:

- `device`: word device such as `"DM500"`
- `bit_index`: `0` to `15`
- `value`: `True` or `False`

Example:

```python
await write_bit_in_word(client, "DM500", 3, True)
```

## Mixed Snapshots

### `await read_named(client, addresses)`

Read mixed values in one call.

Supported address notation:

| Format | Meaning |
|---|---|
| `"DM100"` | unsigned 16-bit |
| `"DM100:S"` | signed 16-bit |
| `"DM100:D"` | unsigned 32-bit |
| `"DM100:L"` | signed 32-bit |
| `"DM100:F"` | float32 |
| `"DM100.3"` | bit 3 inside the word |
| `"DM100.A"` | bit 10 inside the word |

Parameters:

- `addresses`: `list[str]`

Returns:

- `dict[str, int | float | bool]`

Example:

```python
snapshot = await read_named(client, ["DM100", "DM101:S", "DM102:F", "DM200.3"])
```

## Polling

### `poll(client, addresses, interval)`

Async generator that repeatedly yields snapshot dictionaries using the same
address notation as `read_named`.

Parameters:

- `addresses`: `list[str]`
- `interval`: polling interval in seconds

Yields:

- `dict[str, int | float | bool]`

Example:

```python
async for snapshot in poll(client, ["DM100", "DM101:L", "DM200.3"], interval=1.0):
    print(snapshot)
```

## Notes

- User-facing docs intentionally stop at the helper layer.
- Hex/token-oriented reads and raw protocol commands are maintainer topics.
- See `samples/README.md` for runnable example scripts.
