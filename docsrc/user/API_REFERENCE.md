# HostLink Python API Reference

This reference describes the public API of `hostlink.HostLinkClient`.

## Imports

```python
from hostlink import HostLinkClient, AsyncHostLinkClient
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

- `count` is validated by device family and format.

#### `read_consecutive_legacy(device: str, count: int, *, data_format: str | None = None) -> list[int | str]`

Send `RDE` (legacy-compatible).

- `count` is validated by device family and format.

### Write Commands

#### `write(device: str, value: int | str, *, data_format: str | None = None) -> None`

Send `WR`.

#### `write_consecutive(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WRS`.

- Number of values is validated by device family and format.

#### `write_consecutive_legacy(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WRE` (legacy-compatible).

- Number of values is validated by device family and format.

#### `write_set_value(device: str, value: int | str, *, data_format: str | None = None) -> None`

Send `WS`.

- Allowed device families: `T` or `C`

#### `write_set_value_consecutive(device: str, values: Sequence[int | str], *, data_format: str | None = None) -> None`

Send `WSS`.

- Allowed device families: `T` or `C`

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
- `count` range:
  - `1..1000` for `\"\"/.U/.S/.H`
  - `1..500` for `.D/.L`

#### `write_expansion_unit_buffer(unit_no: int, address: int, values: Sequence[int | str], *, data_format: str = "") -> None`

Send `UWR`.

- `unit_no` range: `0..48`
- `address` range: `0..59999`
- Number of values range:
  - `1..1000` for `""/.U/.S/.H`
  - `1..500` for `.D/.L`

  ## Class: `AsyncHostLinkClient`

  The `AsyncHostLinkClient` provides an asynchronous interface for use with `asyncio`. It supports the same protocol features as `HostLinkClient` but uses `async`/`await` for all network and PLC-interacting methods.

  ### Constructor

  ```python
  AsyncHostLinkClient(
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

  ### Async Usage Example

  ```python
  import asyncio
  from hostlink import AsyncHostLinkClient

  async def main():
  async with AsyncHostLinkClient("192.168.0.10") as plc:
      val = await plc.read("DM0.S")
      print(f"DM0: {val}")
      await plc.write("DM0.S", val + 1)

  if __name__ == "__main__":
  asyncio.run(main())
  ```

  ### Methods

  All methods corresponding to those in `HostLinkClient` (except for class-internal sync helpers) are implemented as `async def` and must be awaited.

  - `await connect() -> None`
  - `await close() -> None`
  - `await send_raw(body: str) -> str`
  - `await change_mode(mode: int | str) -> None`
  - `await clear_error() -> None`
  - `await check_error_no() -> str`
  - `await query_model() -> ModelInfo`
  - `await confirm_operating_mode() -> int`
  - `await set_time(...) -> None`
  - `await forced_set(device: str) -> None`
  - `await forced_reset(device: str) -> None`
  - `await forced_set_consecutive(device: str, count: int) -> None`
  - `await forced_reset_consecutive(device: str, count: int) -> None`
  - `await read(device: str, *, data_format: str | None = None) -> ...`
  - `await read_consecutive(...) -> ...`
  - `await read_consecutive_legacy(...) -> ...`
  - `await write(...) -> None`
  - `await write_consecutive(...) -> None`
  - `await write_consecutive_legacy(...) -> None`
  - `await write_set_value(...) -> None`
  - `await write_set_value_consecutive(...) -> None`
  - `await register_monitor_bits(...) -> None`
  - `await register_monitor_words(...) -> None`
  - `await read_monitor_bits() -> list[int | str]`
  - `await read_monitor_words() -> list[str]`
  - `await read_comments(...) -> str`
  - `await switch_bank(bank_no: int) -> None`
  - `await read_expansion_unit_buffer(...) -> list[int | str]`
  - `await write_expansion_unit_buffer(...) -> None`

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
