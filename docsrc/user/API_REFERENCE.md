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

Both clients are IPv4-only. `connect_timeout` governs connection establishment;
`timeout` is one absolute deadline from immediately before first send/write
through transmission, receive, and decoding. Normal operations use arrival
FIFO admission. Waiting cancellation sends nothing, and `close()` immediately
rejects active and queued work. No request is retried or resent automatically.
For a state-changing request that may have been sent, timeout, cancellation,
close, transport failure, or malformed confirmation raises
`HostLinkOutcomeUnknownError` with a machine-readable `HostLinkFailureReason`.

## Device Operations

| Operation | Public API |
| --- | --- |
| Single device read/write | `read`, `write` |
| Consecutive device read/write | `read_consecutive`, `write_consecutive` |
| Legacy consecutive read/write | `read_consecutive_legacy`, `write_consecutive_legacy` |
| Forced bit/device control | `forced_set`, `forced_reset`, `forced_set_consecutive`, `forced_reset_consecutive` |
| Timer/counter set-value writes | `write_set_value`, `write_set_value_consecutive` |
| Monitor registration/cycle | `register_monitor_bits`, `register_monitor_words`, `read_monitor_bits`, `read_monitor_words` |
| Comment reads | `read_comments` |
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
count. Direct-bit responses accept only `0`, `1`, `OFF`, or `ON`. UDP responses require a
CR/LF terminator; missing framing is a protocol error and discards the
transport. Datetime clock values must be in years 2000 through 2099.
For direct-bit devices, numeric single reads require the corresponding 16- or
32-point response. Any malformed semantic response shape invalidates the
session before another request.

## High-Level Helpers

| Operation | Public API |
| --- | --- |
| Address parsing and formatting | `HostLinkAddress`, `parse_address`, `try_parse_address`, `format_address`, `normalize_address` |
| Typed values | `read_typed`, `write_typed` |
| Timer/counter composite reads | `TimerCounterValue`, `read_timer_counter`, `read_timer`, `read_counter` |
| Named read collections and polling | `read_named`, `poll` |
| Word/dword reads | `read_words`, `read_dwords` |
| Single-request reads/writes | `read_words_single_request`, `read_dwords_single_request`, `write_words_single_request`, `write_dwords_single_request` |

`read_named` and `poll` require at least one address. They validate the complete
input before send, preserve caller request order, keep each entry indivisible,
and may split only necessary read-only work during one FIFO turn. Such a result
is a logical dictionary, not an atomic PLC-time snapshot; failure returns no
partial dictionary. Poll intervals must be positive finite numbers and cannot
be booleans. The removed `write_bit_in_word` RMW API has no alias.

Float32 reads and writes are defined only for word devices. An `F` write to a
direct bit device such as `Y0` or `R0` raises `ValueError` before any command is
sent.

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
`HostLinkConnectionError`, `HostLinkConnectionOptions`, `HostLinkError`,
`HostLinkFailureReason`, `HostLinkNotConnectedError`, `HostLinkOutcomeUnknownError`,
`HostLinkProtocolError`, `HostLinkTimeoutError`, `HostLinkTransportError`,
`KvDeviceRangeCatalog`, `KvDeviceRangeCategory`,
`KvDeviceRangeEntry`, `KvDeviceRangeNotation`, `KvDeviceRangeSegment`,
`KvHostLinkPlcProfile`, `KvHostLinkPlcProfileDescriptor`, `ModelInfo`, `TimerCounterValue`,
`available_plc_profiles`, `decode_error_code`,
`device_range_catalog_for_plc_profile`, `display_name`, `format_address`,
`normalize_address`, `normalize_plc_profile`, `open_and_connect`,
`parse_address`, `poll`, `plc_profile_descriptors`, `profile_from_name`, `read_comments`,
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
