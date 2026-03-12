# HostLink Python API Reference

This reference describes the public API of `hostlink.HostLinkClient`.

## Imports

```python
from hostlink import HostLinkClient
from hostlink.errors import HostLinkError, HostLinkProtocolError, HostLinkConnectionError
```

## Exceptions

- `HostLinkError`: PLC returned an error response such as `E0`, `E1`, `E2`, `E4`, `E5`, or `E6`.
- `HostLinkProtocolError`: local validation/parsing failure (invalid device, invalid format, malformed frame, etc.).
- `HostLinkConnectionError`: socket/timeout/connect/disconnect failure.

## Data Models

### `ModelInfo`

- `code: str`: raw model code returned by `?K` (for example `63`).
- `model: str | None`: mapped model name when known (for example `KV-X550`).

## Class: `HostLinkClient`

### Constructor

```python
HostLinkClient(
    host: str,
    *,
    port: int = 8501,
    transport: str = "tcp",
    timeout: float = 3.0,
    buffer_size: int = 8192,
    append_lf_on_send: bool = False,
    auto_connect: bool = True,
)
```

- `host`: PLC IP or hostname.
- `port`: Host Link port (default `8501`).
- `transport`: `"tcp"` or `"udp"`.
- `timeout`: socket timeout in seconds.
- `buffer_size`: receive buffer size.
- `append_lf_on_send`: if `True`, command terminator is `CRLF`; otherwise `CR`.
- `auto_connect`: connect during initialization.

### Connection and Raw Access

#### `connect() -> None`

Open socket connection to PLC.

#### `close() -> None`

Close socket connection.

#### `send_raw(body: str) -> str`

Send raw Host Link command body (without CR/LF) and return decoded response text.

- Raises: `HostLinkError`, `HostLinkProtocolError`, `HostLinkConnectionError`

### Basic PLC Commands

#### `change_mode(mode: int | str) -> None`

Switch PLC mode.

- Supported values: `0`, `1`, `"PROGRAM"`, `"RUN"`

#### `clear_error() -> None`

Send `ER`.

#### `check_error_no() -> str`

Send `?E` and return the PLC error number string.

#### `query_model() -> ModelInfo`

Send `?K` and return model code + mapped model name.

#### `confirm_operating_mode() -> int`

Send `?M` and return mode as integer (`0` or `1`).

#### `set_time(value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None`

Send `WRT`.

- `None`: use current local datetime.
- Tuple format: `(yy, mm, dd, hh, mi, ss, w)` where `w` is `0=Sun..6=Sat`.

### Forced Set/Reset

#### `forced_set(device: str) -> None`

Send `ST <device>`.

#### `forced_reset(device: str) -> None`

Send `RS <device>`.

#### `forced_set_consecutive(device: str, count: int) -> None`

Send `STS <device> <count>`.

- `count` range: `1..16`

#### `forced_reset_consecutive(device: str, count: int) -> None`

Send `RSS <device> <count>`.

- `count` range: `1..16`

### Read Commands

#### `read(device: str, *, data_format: str | None = None) -> int | str | list[int | str]`

Send `RD`.

- Returns one scalar when one token is returned, otherwise a list.

#### `read_consecutive(device: str, count: int, *, data_format: str | None = None) -> list[int | str]`

Send `RDS`.

#### `read_consecutive_legacy(device: str, count: int, *, data_format: str | None = None) -> list[int | str]`

Send `RDE` (legacy-compatible).

### Write Commands

#### `write(device: str, value: int | str, *, data_format: str | None = None) -> None`

Send `WR`.

#### `write_consecutive(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WRS`.

#### `write_consecutive_legacy(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WRE` (legacy-compatible).

#### `write_set_value(device: str, value: int | str, *, data_format: str | None = None) -> None`

Send `WS`.

- Allowed device families: `T/TC/TS/C/CC/CS`

#### `write_set_value_consecutive(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WSS`.

- Allowed device families: `T/TC/TS/C/CC/CS`

### Monitor Commands

#### `register_monitor_bits(*devices: str) -> None`

Send `MBS` to register bit monitor table entries.

- Max devices: `120`

#### `register_monitor_words(*devices: str) -> None`

Send `MWS` to register word monitor table entries.

- Max devices: `120`

#### `read_monitor_bits() -> list[int | str]`

Send `MBR`.

#### `read_monitor_words() -> list[str]`

Send `MWR`.

### Comments, Bank, Expansion Unit Buffer

#### `read_comments(device: str, *, strip_padding: bool = True) -> str`

Send `RDC`.

- If `strip_padding=True`, right-side spaces are trimmed.

#### `switch_bank(bank_no: int) -> None`

Send `BE`.

- `bank_no` range: `0..15`

#### `read_expansion_unit_buffer(unit_no: int, address: int, count: int, *, data_format: str = "") -> list[int | str]`

Send `URD`.

- `unit_no` range: `0..48`
- `address` range: `0..59999`

#### `write_expansion_unit_buffer(unit_no: int, address: int, values: Sequence[int | str], *, data_format: str = "") -> None`

Send `UWR`.

- `unit_no` range: `0..48`
- `address` range: `0..59999`

## Supported Data Format Values

- `""` (omitted)
- `.U`
- `.S`
- `.D`
- `.L`
- `.H`

## Minimal Example

```python
from hostlink import HostLinkClient

with HostLinkClient("192.168.0.10", transport="tcp") as plc:
    plc.change_mode("RUN")
    current = plc.read("DM200.S")
    plc.write("DM200.S", 1234)
    values = plc.read_consecutive("R100", 4)
    print(current, values)
```

