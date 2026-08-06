# KV Host Link Python API Reference

This page is a user-facing index of the public Python KV Host Link API surface.
Use the usage guide for examples, and this page when you need to find the
operation name for a specific Host Link workflow.

The sync `HostLinkClient` and async `AsyncHostLinkClient` expose the same
low-level operation names unless noted otherwise. For normal application code,
prefer `open_and_connect` plus the high-level helper functions.

## Connection And PLC Control

| Operation | Public API |
| --- | --- |
| Open a ready-to-use serialized connection | `open_and_connect`, `HostLinkConnectionOptions` |
| Low-level sync/async clients | `HostLinkClient`, `AsyncHostLinkClient` |
| PLC mode and error control | `change_mode`, `clear_error`, `check_error_no`, `confirm_operating_mode` |
| PLC model and clock | `query_model`, `set_time`, `ModelInfo` |
| Connection lifecycle | `connect`, `close` |

Both clients are IPv4-only and reject bracketed IPv4 input such as
`[127.0.0.1]`; use `127.0.0.1` instead. `connect_timeout` is one absolute connection
deadline beginning before IPv4 hostname resolution and ending only after the
transport is fully configured and adopted. A literal IPv4 address bypasses DNS.
The clients reject any resolver or socket result completed after the deadline,
after cancellation, or after `close()`; the late candidate is closed exactly once
before it can publish state. Commands
never connect lazily. `timeout` is a separate absolute request deadline from
immediately before first send/write through transmission, receive, and
decoding. Normal operations use arrival FIFO admission. Waiting cancellation
sends nothing, and `close()` immediately rejects active and queued work. No
request is retried or resent automatically.

Maintainer `send_raw` accepts at most 65,506 ASCII bytes in the command body;
the required terminating CR makes the complete request frame at most 65,507
bytes. Oversized input fails before connection-state or socket work for both
TCP and UDP.
For a state-changing request that may have been sent, timeout, cancellation,
close, transport failure, or malformed confirmation raises
`HostLinkOutcomeUnknownError` with a machine-readable `HostLinkFailureReason`.
UDP reuses one connected socket and local endpoint across successful requests.
Timeout, cancellation, transport or protocol failure, malformed or extra input,
and a detected pre-send unowned datagram discard that socket. The next request
creates a fresh socket from the cached numeric IPv4 endpoint without repeating
DNS. TCP accepts one non-empty response line per request; an extra non-empty
line retires the transport.

## Device Operations

| Operation | Public API |
| --- | --- |
| Single device read/write | `read`, `write` |
| Consecutive device read/write | `read_consecutive`, `write_consecutive` |
| Legacy consecutive read/write | `read_consecutive_legacy`, `write_consecutive_legacy` |
| Forced bit/device control | `forced_set`, `forced_reset`, `forced_set_consecutive`, `forced_reset_consecutive` |
| Timer/counter set-value writes | `write_set_value`, `write_set_value_consecutive` |
| Monitor registration/cycle | `register_monitor_bits`, `register_monitor_words`, `read_monitor_bits`, `read_monitor_words` |
| Comment text reads | `read_comments`, `HostLinkCommentEncoding` |
| Comment raw-byte reads | `read_comment_bytes` |
| Data bank switching | `switch_bank` |
| Expansion unit buffer access | `read_expansion_unit_buffer`, `write_expansion_unit_buffer` |

Numeric low-level operations require a base device and a separate format, for
example `read("DM100", data_format=".D")`. Suffix-bearing low-level input such
as `read("DM100.D")` is rejected. Bare direct-bit devices remain valid because
their bit meaning is determined by the device family and command. `set_time`
requires an explicit datetime/calendar value, and expansion-buffer reads and
writes require an explicit format.

Integer-only arguments require an exact Python `int`; `bool`, floating-point
values such as `1.0`, and numeric strings are rejected with `ValueError` before
frame construction. `confirm_operating_mode` accepts only the exact PLC
response body `0` or `1`; any other body is a protocol error that invalidates
the session.

Semantic read operations validate the exact command-derived response token
count. Bare direct-bit responses accept only `0`, `1`, `OFF`, or `ON`.
Formatted direct-bit single reads return one packed numeric token: `.U`, `.S`,
and `.H` represent 16 bits, while `.D` and `.L` represent 32 bits. Signed `.S`
and `.L` tokens may include an explicit leading `+`. Any malformed semantic
response shape invalidates the session before another request. UDP responses
require a CR/LF terminator; missing framing is a protocol error and discards
the transport. Datetime clock values must be in years 2000 through 2099.
Semantic `.H` results are exactly four uppercase hexadecimal digits. MWS keeps
the ordered registered formats, and MWR validates each returned token against
its corresponding `.U`, `.S`, `.H`, `.D`, or `.L` rule. Raw response bodies are
not normalized.

A bare direct-bit entry is a special case only for `MWS`/`MWR`. For example,
`register_monitor_words(["R5000"])` transmits exact `MWS R5000`; it does not
append `.U`. The matching MWR field is the packed unsigned 16-bit word beginning
at `R5000`. Its field grammar is exactly one through five ASCII decimal digits,
with optional leading zeros, and its numeric value must be `0` through `65535`.
Signs, empty or whitespace-only fields, non-decimal characters, more than five
digits, and overflow are protocol errors that retire the transport.
`read_monitor_words` preserves
the existing public string representation, so PLC field `00013` returns
`["00013"]`. Bare scalar `RD` and `MBS`/`MBR` remain strict bit operations and
accept only `0`, `1`, `OFF`, or `ON` per field.

`read_comments(device, encoding)` requires
`HostLinkCommentEncoding.UTF8` or `HostLinkCommentEncoding.CP932`; it never
detects, falls back, or selects a codec from the PLC profile. `CP932` is the
Windows-31J compatibility selection for KEYENCE “Shift_JIS” terminology. Its
portable strict repertoire preserves ASCII code points, accepts mapped
half-width and double-byte Windows-31J characters, and rejects malformed,
unmapped, or vendor-private single bytes `80`, `A0`, and `FD` through `FF`.
`read_comment_bytes(device)` returns the undecoded `RDC` body with CR/LF
framing removed and trailing ASCII padding preserved. A named collection that
contains `:COMMENT` likewise requires its explicit `comment_encoding`.
Passing `comment_encoding` to a collection without `:COMMENT` is rejected as
an unused configuration error before communication.

## High-Level Helpers

| Operation | Public API |
| --- | --- |
| Address parsing and formatting | `HostLinkAddress`, `parse_address`, `try_parse_address`, `format_address`, `normalize_address` |
| Typed values | `read_typed`, `write_typed` |
| Timer/counter composite reads | `TimerCounterValue`, `read_timer_counter`, `read_timer`, `read_counter` |
| Named read collections and polling | `read_named`, `poll` |
| Explicit bit-in-word write | `HostLinkClient.write_bit_in_word`, `AsyncHostLinkClient.write_bit_in_word`, `write_bit_in_word` |
| Expansion-buffer bit write | `HostLinkClient.write_bit_in_expansion_unit_buffer`, `AsyncHostLinkClient.write_bit_in_expansion_unit_buffer`, `write_bit_in_expansion_unit_buffer` |
| Word/dword reads | `read_words`, `read_dwords` |
| Single-request reads/writes | `read_words_single_request`, `read_dwords_single_request`, `write_words_single_request`, `write_dwords_single_request` |

`read_named` and `poll` require at least one address. They validate the complete
input before send and keep each entry indivisible. Wire reads are grouped by
device type in first-occurrence order, sorted by address within each group, and
merged when compatible contiguous or overlapping spans fit the protocol limit.
The complete optimized plan owns one FIFO turn, while returned dictionary keys
remain in caller input order. Such a result is a logical dictionary, not an
atomic PLC-time snapshot; failure returns no partial dictionary. Named keys must
be semantically unique by device family,
numeric address, dtype, bit index, and scalar count. Case and leading-zero
spelling variants are rejected as duplicates, while distinct dtype views, bit
indices, and overlapping spans remain valid; returned keys preserve the input
spelling. `poll` compiles the optimized plan once, reuses it for every cycle,
and releases the FIFO turn before yielding a sample or waiting for the interval.
Poll intervals must be positive finite numbers and cannot be booleans.
`write_bit_in_word` is an explicit Boolean-only, 16-bit word read-modify-write.
It validates the complete plan before FIFO admission, retains one client turn,
and uses one absolute deadline for its one read and one write after activation.
It always sends the write after a successful read, performs no retry or
readback, and is not PLC-atomic against PLC logic or another connection.
`write_bit_in_expansion_unit_buffer` applies the same contract to exactly one
`.U` word on the existing URD/UWR unit/address route. The selected route is
immutable across both requests and never falls back to an ordinary device.

`parse_address`, `normalize_address`, and `format_address` apply the same
device/data-type compatibility rules. Formatting a `HostLinkAddress` validates
its semantic fields, ignores stale `text`, and produces output that can be
parsed again with the same device, dtype, and bit-index meaning.

Timer/counter composite reads require response status to be exactly `0` or
`1`; any other spelling or numeric status is an invalid response and retires
the session. The status is a structural field and remains the integer `0` or
`1`. The selected `.U`, `.S`, `.H`, `.D`, or `.L` format applies only to the
current and preset fields; for example, `.H` does not turn status `0` into
`"0000"`.

Float32 reads and writes are defined only for ordinary one-word `.U` families
that support two consecutive words: `DM`, `EM`, `FM`, `ZF`, `W`, `TM`, `CM`,
`VM`, `D`, `E`, and `F`. Native 32-bit `Z`, direct-bit, and special-response
families, including `R`, `T`, `C`, and `AT`, reject `:F` during parsing and
before FIFO admission or transport. Typed helpers and named reads use the same
canonical family metadata.

## Address, Profile, And Diagnostics

| Operation | Public API |
| --- | --- |
| Device range catalog | `KvDeviceRangeCatalog`, `KvDeviceRangeEntry`, `KvDeviceRangeSegment`, `KvDeviceRangeCategory`, `KvDeviceRangeNotation` |
| Profile lookup | `KvHostLinkPlcProfile`, `KvHostLinkPlcProfileDescriptor`, `available_plc_profiles`, `plc_profile_descriptors`, `normalize_plc_profile`, `profile_from_name`, `display_name` |
| Device range catalog lookup | `device_range_catalog_for_plc_profile` |
| Error handling | `HostLinkError`, `HostLinkProtocolError`, `HostLinkTimeoutError`, `HostLinkCancelledError`, `HostLinkClosedError`, `HostLinkNotConnectedError`, `HostLinkTransportError`, `HostLinkOutcomeUnknownError`, `HostLinkFailureReason`, `decode_error_code` |

For banked bit families `R`, `MR`, `LR`, and `CR`, numeric catalog bounds and
point counts use `bank * 16 + bit`; `address_range` continues to display PLC
notation. Catalog bounds describe profiles and are not transport-side address
guards.

## Public Symbol Index

The package exports these public names from `hostlink.__all__`:

`AsyncHostLinkClient`, `HostLinkAddress`, `HostLinkBaseError`,
`HostLinkCancelledError`, `HostLinkClient`, `HostLinkClosedError`,
`HostLinkCommentEncoding`, `HostLinkConnectionError`, `HostLinkConnectionOptions`, `HostLinkError`,
`HostLinkFailureReason`, `HostLinkNotConnectedError`, `HostLinkOutcomeUnknownError`,
`HostLinkProtocolError`, `HostLinkTimeoutError`, `HostLinkTransportError`,
`KvDeviceRangeCatalog`, `KvDeviceRangeCategory`,
`KvDeviceRangeEntry`, `KvDeviceRangeNotation`, `KvDeviceRangeSegment`,
`KvHostLinkPlcProfile`, `KvHostLinkPlcProfileDescriptor`, `ModelInfo`, `TimerCounterValue`,
`available_plc_profiles`, `decode_error_code`,
`device_range_catalog_for_plc_profile`, `display_name`, `format_address`,
`normalize_address`, `normalize_plc_profile`, `open_and_connect`,
`parse_address`, `poll`, `plc_profile_descriptors`, `profile_from_name`,
`read_comment_bytes`, `read_comments`,
`read_counter`, `read_dwords`,
`read_dwords_single_request`,
`read_expansion_unit_buffer`, `read_named`, `read_timer`,
`read_timer_counter`, `read_typed`, `read_words`,
`read_words_single_request`, `try_parse_address`,
`write_dwords_single_request`,
`write_expansion_unit_buffer`, `write_typed`,
`write_words_single_request`.

## Generated API Details

The docs site renders the installed package with mkdocstrings so class,
function, dataclass, and enum signatures are searchable from the site API
reference.

## Traffic statistics

`HostLinkClient.traffic_stats()` and `AsyncHostLinkClient.traffic_stats()` return `HostLinkTrafficStats` snapshots.
TCP receive bytes count the body plus the first CR/LF terminator, independent of separator
segmentation; UDP receive bytes count the complete datagram.
