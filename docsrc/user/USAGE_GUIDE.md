# Usage guide

## Recommended entry points

| Name | Use it for |
|---|---|
| `HostLinkConnectionOptions` | Keep connection settings in one explicit object. |
| `open_and_connect` | Create and open the recommended async client. |
| `available_plc_profiles` | List the exact canonical profile strings accepted by the range catalog. |
| `device_range_catalog_for_plc_profile` | Select the profile-specific device range catalog. |
| `parse_address` | Parse helper-layer address text into metadata. |
| `try_parse_address` | Parse address text without raising on invalid input. |
| `format_address` | Return canonical text from a parsed address or raw string. |
| `normalize_address` | Normalize helper-layer address text. |
| `read_typed` | Read one typed value. |
| `write_typed` | Write one typed value. |
| `read_named` | Read a mixed snapshot by address strings. |
| `poll` | Read repeated snapshots on a fixed interval. |
| `read_words_single_request` | Read contiguous 16-bit words in one PLC request. |
| `read_dwords_single_request` | Read contiguous 32-bit values in one PLC request. |
| `read_words_chunked` | Read a large 16-bit word block by explicit chunks. |
| `read_dwords_chunked` | Read a large 32-bit value block by explicit chunks. |
| `write_bit_in_word` | Set or clear one bit inside a word device. |
| `read_timer_counter` | Read timer or counter status, current value, and preset. |
| `read_timer` | Read a timer as status, current value, and preset. |
| `read_counter` | Read a counter as status, current value, and preset. |
| `read_comments` | Read a PLC device comment label. |
| `read_expansion_unit_buffer` | Read expansion unit buffer memory. |
| `write_expansion_unit_buffer` | Write expansion unit buffer memory. |

## Connection

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect


async def main() -> None:
    options = HostLinkConnectionOptions(
        host="192.168.250.100",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="tcp",
        timeout=3.0,
        append_lf_on_send=False,
    )
    async with await open_and_connect(options) as client:
        print("Connected")


if __name__ == "__main__":
    asyncio.run(main())
```

`HostLinkConnectionOptions` defaults to TCP, port `8501`, a 3-second timeout, and no LF appended after CR.

## Performance notes

For stable local networks, UDP usually has the lowest latency. TCP is the safer
default for remote or less predictable networks because the OS handles
retransmission. The TCP transport enables `TCP_NODELAY`, which keeps small Host
Link command frames from waiting behind Nagle buffering.

Reuse one connected client for repeated reads and writes. Prefer
`read_words_single_request`, `read_dwords_single_request`, or `read_named` over
many individual `read_typed` calls when one application snapshot can be read as
one request.

## Read a single value

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        unsigned_word = await read_typed(client, "DM0", "U")
        signed_word = await read_typed(client, "DM1", "S")
        unsigned_dword = await read_typed(client, "DM2", "D")
        signed_dword = await read_typed(client, "DM4", "L")
        float_value = await read_typed(client, "DM6", "F")
        print(f"{unsigned_word}, {signed_word}, {unsigned_dword}, {signed_dword}, {float_value}")


if __name__ == "__main__":
    asyncio.run(main())
```

| Suffix | Meaning | Returned Python type |
|---|---|---|
| `U` | Unsigned 16-bit word | `int` |
| `S` | Signed 16-bit word | `int` |
| `D` | Unsigned 32-bit double word | `int` |
| `L` | Signed 32-bit double word | `int` |
| `F` | IEEE 754 32-bit floating point | `float` |

## Write a single value

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed, write_typed


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        address = "DM100"
        original = await read_typed(client, address, "U")
        try:
            await write_typed(client, address, "U", 42)
            readback = await read_typed(client, address, "U")
            print(f"{address} readback = {readback}")
        finally:
            await write_typed(client, address, "U", original)


if __name__ == "__main__":
    asyncio.run(main())
```

This is a matched read/write/readback pattern. Keep it on a test address until you know the register is safe for your machine.

## Named snapshot

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        addresses = ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.A", "DM0:COMMENT"]
        snapshot = await read_named(client, addresses)
        for address, value in snapshot.items():
            print(f"{address} = {value}")


if __name__ == "__main__":
    asyncio.run(main())
```

Use `read_named` when one application snapshot mixes unsigned words, signed words, double words, floats, comments, and bit-in-word values.

## Block reads

```python
import asyncio
from hostlink import (
    HostLinkConnectionOptions,
    open_and_connect,
    read_dwords_chunked,
    read_dwords_single_request,
    read_words_chunked,
    read_words_single_request,
)


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        words = await read_words_single_request(client, "DM200", 8)
        dwords = await read_dwords_single_request(client, "DM300", 4)
        large_words = await read_words_chunked(client, "DM1000", 128, max_per_request=64)
        large_dwords = await read_dwords_chunked(client, "DM2000", 64, max_dwords_per_request=32)
        print(f"Words: {len(words)}, DWords: {len(dwords)}")
        print(f"Chunked words: {len(large_words)}, chunked DWords: {len(large_dwords)}")


if __name__ == "__main__":
    asyncio.run(main())
```

Single-request methods send one PLC command. Chunked methods split only where you explicitly choose a chunk size.

## Bit in word

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_named, write_bit_in_word


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        await write_bit_in_word(client, "DM50", bit_index=10, value=True)
        snapshot = await read_named(client, ["DM50.A"])
        print(f"DM50.A = {snapshot['DM50.A']}")


if __name__ == "__main__":
    asyncio.run(main())
```

The `.n` notation uses hexadecimal bit indexes from `0` through `F`; `.A` means bit 10.

## Polling

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, poll


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        count = 0
        async for snapshot in poll(client, ["DM0", "DM1:S", "DM4:F"], interval=1.0):
            print(f"DM0={snapshot['DM0']}, DM1:S={snapshot['DM1:S']}, DM4:F={snapshot['DM4:F']}")
            count += 1
            if count >= 3:
                break


if __name__ == "__main__":
    asyncio.run(main())
```

`poll` yields a dictionary snapshot on each interval until cancellation or until your loop exits.

## Address reference table

| Form | Example | Meaning |
|---|---|---|
| Plain | `DM100` | Default type for the device family, usually unsigned word for word devices. |
| `:U` | `DM100:U` | Unsigned 16-bit view. |
| `:S` | `DM100:S` | Signed 16-bit view. |
| `:D` | `DM100:D` | Unsigned 32-bit view. |
| `:L` | `DM100:L` | Signed 32-bit view. |
| `:F` | `DM100:F` | IEEE 754 32-bit float view. |
| `:COMMENT` | `DM100:COMMENT` | PLC device comment text. |
| `.n` | `DM100.A` | One bit inside a word; `n` is hexadecimal `0` to `F`. |

## Timer/counter helpers

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_counter, read_timer, read_timer_counter


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        timer = await read_timer(client, "T0")
        counter = await read_counter(client, "C0")
        generic = await read_timer_counter(client, "T0")
        print(f"T0 status={timer.status}, current={timer.current}, preset={timer.preset}")
        print(f"C0 status={counter.status}, current={counter.current}, preset={counter.preset}")
        print(f"Generic T0 preset={generic.preset}")


if __name__ == "__main__":
    asyncio.run(main())
```

`read_timer_counter` returns `status`, `current`, and `preset`. `read_timer` accepts timer devices, and `read_counter` accepts counter devices.

> **Caution:** Timer/Counter preset writes (`WS`/`WSS`) only supported on KV-8000/7000-series. Other models return error `E1`.

## Device comments

Use `label = await read_comments(client, "DM0")` after connecting to read the PLC device comment label for `DM0`.

## Expansion unit buffer

```python
import asyncio
from hostlink import (
    HostLinkConnectionOptions,
    open_and_connect,
    read_expansion_unit_buffer,
    write_expansion_unit_buffer,
)


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501)
    async with await open_and_connect(options) as client:
        buffer_words = await read_expansion_unit_buffer(
            client,
            unit_no=0,
            address=0,
            count=4,
            data_format="U",
        )
        await write_expansion_unit_buffer(
            client,
            unit_no=0,
            address=10,
            values=[1, 2, 3, 4],
            data_format="U",
        )
        print(f"Read {len(buffer_words)} expansion buffer values.")


if __name__ == "__main__":
    asyncio.run(main())
```

Expansion unit buffer methods access module buffer memory by unit number, buffer address, count, and data format.

## Runnable samples

The `samples/` directory contains ready-to-run scripts for the most common high-level workflows.
Each script accepts `--host` and `--port` arguments.

| Script | What it demonstrates |
|---|---|
| `samples/high_level_async.py` | Async typed reads/writes, block reads, bit-in-word, named snapshots, and polling. |
| `samples/high_level_sync.py` | Synchronous CLI wrapper that runs the async workflow with `asyncio.run`. |
| `samples/basic_high_level_rw.py` | Compact typed read/write for unsigned, signed, double-word, and float values. |
| `samples/named_snapshot.py` | Mixed snapshot with `read_named`. |
| `samples/polling_monitor.py` | Repeated snapshot loop with `poll`. |
