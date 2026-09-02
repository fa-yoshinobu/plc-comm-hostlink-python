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
| `read_named` | Read a mixed named collection by address strings. |
| `write_named` | Write one compatible named collection in exactly one PLC request. |
| `poll` | Read repeated named results on a fixed interval. |
| `read_bits_single_request` | Read contiguous direct bits in one PLC request. |
| `write_bits_single_request` | Write contiguous direct bits in one PLC request. |
| `read_words_single_request` | Read contiguous 16-bit words in one PLC request. |
| `read_dwords_single_request` | Read contiguous 32-bit values in one PLC request. |
| `write_words_single_request` | Write contiguous 16-bit words in one PLC request. |
| `write_dwords_single_request` | Write contiguous 32-bit values in one PLC request. |
| `read_timer_counter` | Read timer or counter status, current value, and preset. |
| `read_timer` | Read a timer as status, current value, and preset. |
| `read_counter` | Read a counter as status, current value, and preset. |
| `HostLinkCommentEncoding` | Select the exact codec for a device-comment text read. |
| `read_comment` | Read and explicitly decode one PLC device comment label. |
| `read_comment_bytes` | Read undecoded PLC device-comment payload bytes. |
| `read_expansion_unit_buffer` | Read expansion unit buffer memory. |
| `write_expansion_unit_buffer` | Write expansion unit buffer memory. |

The `single_request` helpers either send exactly one PLC request or reject the
complete input before sending. Bit helpers accept only direct bit device
families and Boolean values, with 1 through 1,000 points subject to the device
range. `read_words` is a deprecated compatibility alias; migrate to
`read_words_single_request`.

### API name migration

Use the canonical names below in new code. The former names remain deprecated
direct-forwarding aliases for this compatibility release and are removed in
the next major release. Inputs, results, exceptions, and Host Link commands are
unchanged.

| Former name | Canonical name |
| --- | --- |
| `read_dwords` | `read_dwords_single_request` |
| `read_comments` | `read_comment` |
| `HostLinkClient.check_error_no` | `HostLinkClient.read_error_number` |
| `AsyncHostLinkClient.check_error_no` | `AsyncHostLinkClient.read_error_number` |
| `write_set_value` | `write_timer_counter_preset` |
| `write_set_value_consecutive` | `write_timer_counter_preset_consecutive` |

## API reference summary

The user-facing API is the high-level helper surface imported from `hostlink`.
It intentionally excludes raw protocol methods and low-level client operations.

```python
from hostlink import (
    HostLinkConnectionOptions,
    HostLinkCommentEncoding,
    TimerCounterValue,
    available_plc_profiles,
    device_range_catalog_for_plc_profile,
    open_and_connect,
    parse_address,
    try_parse_address,
    format_address,
    normalize_address,
    read_typed,
    write_typed,
    read_comment_bytes,
    read_comment,
    read_named,
    write_named,
    poll,
)
from hostlink.errors import (
    HostLinkBaseError,
    HostLinkCancelledError,
    HostLinkClosedError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkNotConnectedError,
    HostLinkOutcomeUnknownError,
    HostLinkProtocolError,
    HostLinkTimeoutError,
    HostLinkTransportError,
)
```

| Exception | Meaning |
| --- | --- |
| `HostLinkBaseError` | Base type for library exceptions. |
| `HostLinkError` | PLC returned an error response such as `E0`, `E1`, or `E6`. |
| `HostLinkProtocolError` | Invalid address, invalid dtype, malformed response, or local validation failure. |
| `HostLinkTimeoutError` | The connect deadline or one absolute transaction deadline expired. |
| `HostLinkCancelledError` | An async operation was cancelled. |
| `HostLinkClosedError` | `close()` rejected active or queued work. |
| `HostLinkNotConnectedError` | A command was attempted without a connected transport. |
| `HostLinkTransportError` | A non-timeout transport failure occurred. |
| `HostLinkOutcomeUnknownError` | A state-changing request may have reached the PLC; inspect `reason` and `detail`. |

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
        connect_timeout=3.0,
    )
    async with await open_and_connect(options) as client:
        print("Connected")


if __name__ == "__main__":
    asyncio.run(main())
```

`host`, `port`, `transport`, and `plc_profile` are required.
`connect_timeout` is one separate absolute connection-establishment deadline.
It begins before IPv4 hostname resolution and includes endpoint selection,
socket creation/connect, required TCP configuration, and final adoption. A
literal IPv4 address bypasses DNS. If sync or async resolution/connection finishes
after the deadline or after `close()`, its result is discarded, its candidate
transport is closed, and it cannot connect the client. `timeout` is one absolute request deadline from
immediately before the first send/write through send/drain, receive, and
decoding. Both default to 3 seconds. A synchronous `connect_timeout` value too
large for the platform wait APIs is rejected before connection work. The
clients are IPv4-only; IPv6 literals and bracketed IPv4 such as `[127.0.0.1]`
are not supported. Use `127.0.0.1` without brackets. Frames always end in CR.
Commands never connect lazily: call `connect()`, enter the
client context, or use `open_and_connect` first.

The maintainer-only `send_raw` command body is limited to 65,506 ASCII bytes;
with its terminating CR, the complete TCP or UDP request is at most 65,507
bytes. Oversized input is rejected before connection-state and socket work.

## Performance notes

For stable local networks, UDP usually has the lowest latency. TCP is the safer
default for remote or less predictable networks because the OS handles
retransmission. The synchronous TCP transport enables `TCP_NODELAY` and
socket keepalive before publishing the connected state. `TCP_NODELAY` keeps
small Host Link command frames from waiting behind Nagle buffering; keepalive
probe timing remains an operating-system setting.

Reuse one connected client for repeated reads and writes. Prefer
`read_words_single_request`, `read_dwords_single_request`, or `read_named` over
many individual `read_typed` calls when one application snapshot can be read as
one request.

UDP keeps this logical connection state and reuses one connected socket and
source port across successful operations. Timeout, cancellation, transport or
protocol failure, malformed or extra input, and a detected pre-send unowned
datagram discard that socket. The next admitted request creates a fresh socket
from the cached numeric IPv4 endpoint without repeating DNS. Network rules must
allow the PLC to reply to the current source port.

## Connection reuse and concurrent requests

Keep one connected `AsyncHostLinkClient` open for repeated reads, writes, and
polling. Normal sync and async clients admit operations in arrival FIFO order.
An async operation cancelled while waiting sends nothing. `close()` immediately
retires active and already queued work without waiting behind a command. A
failed or cancelled exchange closes the transport, and the library never
reconnects, retries, or resends automatically.

TCP owns exactly one non-empty response line per request. Additional CR/LF
separators are ignored, but a second non-empty line is a protocol error and
retires the transport; it can never satisfy a later operation.

Host Link response lines do not contain a request identifier. Before sending,
the client rejects already observable TCP input without transmitting the new
request and retires that connection. Input that arrives after this check but
before the actual send is a residual race: the library cannot prove whether the
next response belongs to the current request. A healthy TCP connection is not
closed and reopened for every request because doing so would add a TCP
handshake to normal operations, break connection-scoped monitor registration,
and still would not add a protocol request identifier. The library instead
serializes requests, reuses healthy connections for normal latency, and retires
the connection as soon as unowned, malformed, extra, timed-out, or cancelled
input is observed.

`MBS`/`MWS` monitor registration and the corresponding `MBR`/`MWR` read must use
the same live TCP connection. Closing, losing, or replacing that connection
clears the client's registration metadata. Register the monitor devices again
after every reconnect before reading monitor values.

Use `close()` and `connect()` for an intentional reconnect. After a persistent
connection failure, create a new client with the same `HostLinkConnectionOptions`.

## Read a single value

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
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
| `H` | Hexadecimal 16-bit word text | `str` |

## Write a single value

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed, write_typed


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        address = "DM100"
        original = await read_typed(client, address, "U")
        write_confirmed = False
        try:
            await write_typed(client, address, "U", 42)
            write_confirmed = True
            readback = await read_typed(client, address, "U")
            print(f"{address} readback = {readback}")
        finally:
            if write_confirmed:
                await write_typed(client, address, "U", original)


if __name__ == "__main__":
    asyncio.run(main())
```

This is a matched read/write/readback pattern. Keep it on a test address until
you know the register is safe for your machine. The example restores only a
confirmed write. If the write result is outcome-unknown, reopen the client,
inspect the register, and reconcile it explicitly instead of retrying or
restoring blindly. If restoration fails, inspect and reconcile the register
manually; do not assume that the saved value was restored.

## Named read collection

```python
import asyncio
from hostlink import HostLinkCommentEncoding, HostLinkConnectionOptions, open_and_connect, read_named


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        addresses = ["DM0:U", "DM1:S", "DM2:D", "DM4:F", "DM10.A", "DM0:COMMENT"]
        read_result = await read_named(
            client,
            addresses,
            comment_encoding=HostLinkCommentEncoding.UTF8,
        )
        for address, value in read_result.items():
            print(f"{address} = {value}")


if __name__ == "__main__":
    asyncio.run(main())
```

Use `read_named` when one application result groups unsigned words, signed
words, double words, floats, comments, and bit-in-word values. Mixed,
non-contiguous, or oversized sets can require multiple sequential read-only PLC
requests, so the returned dictionary is not one instant in PLC time. Every
entry is validated before the first send, individual entries are never split,
and the aggregate holds one FIFO turn. On the wire, reads are grouped by device
type in first-occurrence order, sorted by address within each group, and merged
when compatible contiguous or overlapping spans fit the protocol limit. The
returned dictionary still retains caller declaration order. Failure returns no
partial dictionary. This automatic splitting applies
only to `read_named`/`poll`; state-changing multi-request work is not synthesized.
When the collection contains `:COMMENT`, `comment_encoding` is required and is
validated before any request is sent.

Named keys must be semantically unique by device family, numeric address,
dtype, bit index, and scalar count. Case and leading zeros do not make a second
key distinct. Different dtype views of the same word, different bit indices,
and overlapping multiword spans are valid. Result keys preserve the original
input strings.

## Named write collection

```python
from hostlink import write_named

await write_named(client, {"DM100:U": 123, "DM101:U": 456})
await write_named(client, {"R115:BIT": True, "R200:BIT": False})
await write_named(client, {"T10:D": 1000, "T11:D": 2000})
```

`write_named` snapshots and validates the complete mapping before sending. It
accepts the update only when it fits one compatible contiguous `WR`, `WRS`, or
`WSS` request. It never splits state-changing work and never returns partial
success. Mixed device families or dtypes, gaps, reverse order, semantic
duplicates, range/count-limit violations, and bit-in-word read-modify-write
targets are rejected before communication. Use `",count"` with a sequence for
one explicit range, for example `{"DM300:U,3": [1, 2, 3]}`.

## Block reads

```python
import asyncio
from hostlink import (
    HostLinkConnectionOptions,
    open_and_connect,
    read_dwords_single_request,
    read_words_single_request,
)


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        words = await read_words_single_request(client, "DM200", 8)
        dwords = await read_dwords_single_request(client, "DM300", 4)
        print(f"Words: {len(words)}, DWords: {len(dwords)}")


if __name__ == "__main__":
    asyncio.run(main())
```

Single-request methods send exactly one PLC command. The library does not expose
an automatic chunking helper: if a larger logical read is required, the
application must divide it explicitly and account for the fact that each
request observes the PLC at a different time.

## Bit in word

The `.n` notation used by `read_named` reads hexadecimal bit indexes from `0`
through `F`; `.A` means bit 10. Use the explicit client method when a
client-side read-modify-write is the intended policy:

```python
client.write_bit_in_word("DM50", 10, True)
await async_client.write_bit_in_word("DM50", 10, True)
```

The helper form `await write_bit_in_word(async_client, "DM50", 10, True)` has
the same contract. The value must be an actual `bool`, the index is `0..15`,
and the target must be an ordinary 16-bit word device. Invalid plans fail
before FIFO admission. After activation, one absolute transaction deadline
covers exactly one word read followed by one word write in one FIFO turn; queue
wait is outside that deadline. The write is sent even when the bit is already
in the requested state. There is no fallback, resend, success readback, or
implicit named-write behavior.

This operation is not PLC-atomic. PLC logic or another connection can change
the word between requests and that change can be lost. Use PLC-side logic, a
handshake, or exclusive ownership of the complete word when that matters.
Async cancellation before the write starts sends no write. Failure after write
transmission may have started is outcome-unknown: do not retry automatically;
reopen and reconcile PLC state. A complete PLC error is definitive and does
not by itself retire a healthy connection.

Expansion-unit buffer memory uses its own explicit route-specific method:

```python
client.write_bit_in_expansion_unit_buffer(1, 100, 3, True)
await async_client.write_bit_in_expansion_unit_buffer(1, 100, 3, True)
```

The async helper form
`await write_bit_in_expansion_unit_buffer(async_client, 1, 100, 3, True)`
has the same contract. Both requests remain on the selected unit/address and
one `.U` word: exactly one `URD` point followed by one `UWR` point. The ordinary
device and expansion-unit routes never fall back to one another. The same
shared-deadline, cancellation, outcome-unknown, no-readback, and
non-PLC-atomic rules apply.

## Polling

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, poll


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        count = 0
        async for snapshot in poll(client, ["DM0:U", "DM1:S", "DM4:F"], interval=1.0):
            print(f"DM0:U={snapshot['DM0:U']}, DM1:S={snapshot['DM1:S']}, DM4:F={snapshot['DM4:F']}")
            count += 1
            if count >= 3:
                break


if __name__ == "__main__":
    asyncio.run(main())
```

`poll` requires a non-empty address list and yields one logical dictionary on
each interval until cancellation or until your loop exits. It compiles the same
optimized, potentially multi-request plan as `read_named` once before the first
cycle and reuses it for every cycle. Each cycle owns one FIFO turn, stages the
complete result, releases the turn, then yields and waits for the interval. The
result remains non-atomic across multiple PLC requests. The interval must be a
positive finite number; zero, negative values, infinities,
NaN, booleans, and strings are rejected before the first read result or PLC
request.

## Operational recipes

The samples directory includes two read-only operational recipes:

- `samples/multi_plc_monitor.py` reads one or more PLCs in one loop and writes CSV rows as `timestamp,plc,tag,value`.
- `samples/config_polling.py` runs the same polling workflow from a JSON or YAML configuration file.

JSON configuration needs no extra package. YAML configuration requires
PyYAML: `python -m pip install PyYAML`.

Both recipes use the same reconnect states as `polling_reconnect.py`: `connected`, `lost`, `reconnecting`, and `recovered`. The default reconnect backoff starts at 1 second and caps at 30 seconds.

Validate a monitor setup without opening a PLC connection:

```bash
python samples/multi_plc_monitor.py --plc line-a=192.168.250.100,keyence:kv-8000,8501,tcp --tag dm100=DM100:U --cycles 1 --dry-run
```

Validate a configuration file without opening a PLC connection:

```bash
python samples/config_polling.py --config samples/config_polling.example.json --dry-run
```

## Address reference table

| Form | Example | Meaning |
|---|---|---|
| `:U` | `DM100:U` | Unsigned 16-bit view. |
| `:S` | `DM100:S` | Signed 16-bit view. |
| `:D` | `DM100:D` | Unsigned 32-bit view. |
| `:L` | `DM100:L` | Signed 32-bit view. |
| `:F` | `DM100:F` | IEEE 754 32-bit float view. |
| `:BIT` | `CR000:BIT` | Direct bit device view. |
| `:COMMENT` | `DM100:COMMENT` | PLC device comment text; `read_named`/`poll` require `comment_encoding`. |
| `.n` | `DM100.A` | One bit inside a word; `n` is hexadecimal `0` to `F`. |

Float32 is available only for the ordinary `.U` word families `DM`, `EM`,
`FM`, `ZF`, `W`, `TM`, `CM`, `VM`, `D`, `E`, and `F`. Native 32-bit `Z`,
direct-bit, and special-response families such as `R`, `T`, `C`, and `AT`
reject `:F` before FIFO admission and communication. Use Z through its
supported integer representation, or move Float32 storage to an ordinary word
family.

Semantic `.H` reads return exactly four uppercase digits from `0000` through
`FFFF`; shorter valid PLC tokens are padded after validation. Raw response APIs
remain unchanged. MWS retains the ordered format of every registered word, and
MWR validates each returned position against its matching `.U`, `.S`, `.H`,
`.D`, or `.L` format before returning data.

Only `MWS`/`MWR` gives a bare direct-bit target packed-word meaning. This mixed
registration keeps its field order and sends the relay target without a suffix:

```python
await client.register_monitor_words([("DM120", ".U"), "R5000", ("DM121", ".S")])
values = await client.read_monitor_words()
```

The wire registration is `MWS DM120.U R5000 DM121.S`. The `R5000` MWR field is
the unsigned 16-bit packed value beginning at that bit. Its exact grammar is
one through five ASCII decimal digits with optional leading zeros, and its
numeric value must be `0..65535`. Empty or whitespace-only, signed,
non-decimal, over-five-digit, and overflowing fields are protocol errors that
retire the transport. The method keeps its existing `list[str]` result, so wire
value `00013` remains string `"00013"`. This does not change bare scalar `RD`,
which still reads one strict bit, or `MBS`/`MBR`, which still returns one strict
bit per registered device. Monitor registration is connection-scoped;
re-register after reconnect before calling MWR.

For `read_named` and `poll`, do not omit the type suffix. Use `DM100:U` instead of relying on `DM100` to mean an unsigned word.
Pass `comment_encoding` only when the collection contains `:COMMENT`; an
unused comment codec is rejected before communication.

`parse_address`, `normalize_address`, and `format_address` share the same
device/data-type compatibility checks. A hand-constructed `HostLinkAddress`
with an invalid combination is rejected by the formatter; accepted formatted
text can always be parsed again with the same semantics.

## Timer/counter helpers

```python
import asyncio
from hostlink import HostLinkConnectionOptions, open_and_connect, read_counter, read_timer, read_timer_counter


async def main() -> None:
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
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

`read_timer_counter` returns `status`, `current`, and `preset`. The response
status must be exactly `0` or `1`; any other spelling or numeric value is an
invalid response and retires the connection. Status remains the integer `0` or
`1`; the selected numeric format applies only to current and preset. Thus an
`.H` response can be `[0, "270F", "270F"]`, never
`["0000", "270F", "270F"]`. `read_timer` accepts timer devices, and
`read_counter` accepts counter devices.

Use the canonical client methods for preset writes:

```python
await client.write_timer_counter_preset("T100", 1000, data_format=".D")
await client.write_timer_counter_preset_consecutive("C200", [10, 20], data_format=".D")
```

> **Caution:** Timer/Counter preset writes (`WS`/`WSS`) only supported on KV-8000/7000-series. Other models return error `E1`.

## Device comments

The KEYENCE manual does not specify the `RDC` payload character encoding, and
there is no PLC-project character-encoding setting. Do not assume UTF-8.
Select `HostLinkCommentEncoding` explicitly; the library does not guess from
the PLC profile and does not try another codec when the selected decoder fails.

```python
from hostlink import HostLinkCommentEncoding, read_comment, read_comment_bytes

utf8_label = await read_comment(client, "DM0", HostLinkCommentEncoding.UTF8)
cp932_label = await read_comment(client, "DM1", HostLinkCommentEncoding.CP932)
raw_payload = await read_comment_bytes(client, "DM2")
```

`CP932` means Windows-31J and is the compatibility selection for KEYENCE
material that calls the KV string encoding “Shift_JIS”. It includes standard
Shift_JIS characters but is not presented as a separate strict-Shift_JIS
codec. Across supported runtimes, ASCII bytes keep their exact code points,
mapped Windows-31J characters are accepted, and malformed, unmapped, or
vendor-private single bytes `80`, `A0`, and `FD` through `FF` are rejected.
Text reads remove trailing ASCII space padding before strict decoding.
Raw reads perform no codec conversion, remove only CR/LF framing, and preserve
the exact payload, including trailing spaces. Invalid bytes raise
`HostLinkProtocolError`; there is no
replacement, automatic fallback, or `AUTO` selection.

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
    options = HostLinkConnectionOptions(host="192.168.250.100", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
    async with await open_and_connect(options) as client:
        original = await read_expansion_unit_buffer(
            client,
            unit_no=0,
            address=10,
            count=4,
            data_format="U",
        )
        write_confirmed = False
        try:
            await write_expansion_unit_buffer(
                client,
                unit_no=0,
                address=10,
                values=[1, 2, 3, 4],
                data_format="U",
            )
            write_confirmed = True
            readback = await read_expansion_unit_buffer(
                client,
                unit_no=0,
                address=10,
                count=4,
                data_format="U",
            )
            print(f"Read back {len(readback)} expansion buffer values.")
        finally:
            if write_confirmed:
                await write_expansion_unit_buffer(
                    client,
                    unit_no=0,
                    address=10,
                    values=original,
                    data_format="U",
                )


if __name__ == "__main__":
    asyncio.run(main())
```

Expansion unit buffer methods access module buffer memory by unit number, buffer address, count, and data format. Use only a configured unit and buffer range reserved for controlled testing. The example attempts to restore the original values after a confirmed write; a restoration failure requires explicit state reconciliation. If the write outcome is unknown, inspect and reconcile the module state explicitly instead of retrying or restoring blindly.

## Runnable samples

The `samples/` directory contains ready-to-run scripts for the most common high-level workflows.
Each script accepts `--host` and `--port` arguments.

| Script | What it demonstrates |
|---|---|
| `samples/high_level_async.py` | Async typed reads/writes, block reads, bit-in-word, named read collections, and polling. |
| `samples/high_level_sync.py` | Synchronous CLI wrapper that runs the async workflow with `asyncio.run`. |
| `samples/basic_high_level_rw.py` | Compact typed read/write for unsigned, signed, double-word, and float values. |
| `samples/multi_plc_monitor.py` | Read-only multi-PLC polling with reconnect state transitions and long-form CSV output. |
| `samples/config_polling.py` | Read-only polling from a JSON or YAML configuration file, with a `--dry-run` validation mode. |
| `samples/named_read_collection.py` | Mixed named collection with `read_named`. |
| `samples/polling_monitor.py` | Repeated read-result loop with `poll`. |

## Traffic statistics

Call `client.traffic_stats()` for cumulative request, transmitted-byte, and received-byte counts.
For TCP, a received line counts its body plus the first CR/LF terminator; extra CR/LF separators
are consumed but not counted. For UDP, the complete response datagram is counted.
