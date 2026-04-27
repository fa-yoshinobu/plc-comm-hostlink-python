"""High-level Host Link client (TCP/UDP) with full command coverage."""

from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar, cast

from .device import (
    FORCE_DEVICE_TYPES,
    MBS_DEVICE_TYPES,
    MWS_DEVICE_TYPES,
    RDC_DEVICE_TYPES,
    WS_DEVICE_TYPES,
    DeviceAddress,
    normalize_suffix,
    parse_device,
    parse_device_text,
    resolve_effective_format,
    validate_device_count,
    validate_device_span,
    validate_device_type,
    validate_expansion_buffer_count,
    validate_expansion_buffer_span,
    validate_range,
)
from .device_ranges import KvDeviceRangeCatalog, device_range_catalog_for_query_model
from .errors import HostLinkConnectionError, HostLinkProtocolError
from .protocol import (
    build_frame,
    decode_comment_response,
    decode_response,
    ensure_success,
    parse_data_tokens,
    split_data_tokens,
)


class HostLinkTraceDirection(Enum):
    SEND = "send"
    RECEIVE = "receive"


@dataclass(frozen=True)
class HostLinkTraceFrame:
    direction: HostLinkTraceDirection
    data: bytes
    timestamp: datetime


MODEL_CODES = {
    "134": "KV-N24nn",
    "133": "KV-N40nn",
    "132": "KV-N60nn",
    "128": "KV-NC32T",
    "63": "KV-X550",
    "61": "KV-X530",
    "60": "KV-X520",
    "62": "KV-X500",
    "59": "KV-X310",
    "58": "KV-8000A",
    "57": "KV-8000",
    "55": "KV-7500",
    "54": "KV-7300",
    "53": "KV-5500",
    "52": "KV-5000",
    "51": "KV-3000",
    "50": "KV-1000",
    "49": "KV-700 (With expansion memory)",
    "48": "KV-700 (No expansion memory)",
}


@dataclass
class ModelInfo:
    code: str
    model: str | None


T = TypeVar("T")


class HostLinkBase:
    """Base logic for KEYENCE KV Host Link protocol common to sync and async clients."""

    def __init__(
        self,
        host: str,
        port: int = 8501,
        transport: str = "tcp",
        append_lf_on_send: bool = False,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.transport = transport.lower()
        self.append_lf_on_send = append_lf_on_send
        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.trace_hook = trace_hook

    def _fire_trace(self, direction: HostLinkTraceDirection, data: bytes) -> None:
        if self.trace_hook:
            self.trace_hook(HostLinkTraceFrame(direction, data, datetime.now(timezone.utc)))

    # --- Internal helpers ----------------------------------------------

    def _build_command(self, body: str) -> bytes:
        return build_frame(body, append_lf=self.append_lf_on_send)

    def _process_response(self, response: bytes, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        return ensure_success(decoder(response))

    def _get_change_mode_cmd(self, mode: int | str) -> str:
        if isinstance(mode, str):
            upper = mode.strip().upper()
            if upper == "PROGRAM":
                mode_no = 0
            elif upper == "RUN":
                mode_no = 1
            else:
                raise HostLinkProtocolError(f"Unsupported mode: {mode!r}")
        else:
            mode_no = mode
        if mode_no not in {0, 1}:
            raise HostLinkProtocolError("mode must be 0/1 or PROGRAM/RUN")
        return f"M{mode_no}"

    def _get_set_time_cmd(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> str:
        if value is None:
            now = datetime.now()
            year = now.year % 100
            month = now.month
            day = now.day
            hour = now.hour
            minute = now.minute
            second = now.second
            week = (now.weekday() + 1) % 7
        elif isinstance(value, datetime):
            year = value.year % 100
            month = value.month
            day = value.day
            hour = value.hour
            minute = value.minute
            second = value.second
            week = (value.weekday() + 1) % 7
        else:
            year, month, day, hour, minute, second, week = value

        validate_range("year(YY)", year, 0, 99)
        validate_range("month", month, 1, 12)
        validate_range("day", day, 1, 31)
        validate_range("hour", hour, 0, 23)
        validate_range("minute", minute, 0, 59)
        validate_range("second", second, 0, 59)
        validate_range("week", week, 0, 6)

        return "WRT " + " ".join(
            [
                f"{year:02d}",
                f"{month:02d}",
                f"{day:02d}",
                f"{hour:02d}",
                f"{minute:02d}",
                f"{second:02d}",
                str(week),
            ]
        )

    def _device_token(self, device: str, *, drop_suffix: bool = False) -> str:
        addr = parse_device(device)
        if drop_suffix and addr.suffix:
            addr = DeviceAddress(addr.device_type, addr.number, "")
        return addr.to_text()

    def _device_with_format(self, device: str, data_format: str | None, count: int = 1) -> tuple[str, str]:
        addr = parse_device(device)
        suffix = normalize_suffix(data_format) if data_format is not None else addr.suffix
        # If still no suffix, resolve effective default for the device type
        if not suffix:
            suffix = resolve_effective_format(addr.device_type, "")
        validate_device_span(addr.device_type, addr.number, suffix, count)
        addr = DeviceAddress(addr.device_type, addr.number, suffix)
        return addr.to_text(), suffix

    def _ensure_timer_or_counter(self, device: str, data_format: str | None, count: int = 1) -> str:
        token = parse_device_text(device, default_suffix=data_format or "")
        addr = parse_device(token)
        validate_device_type("WS/WSS", addr.device_type, WS_DEVICE_TYPES)
        # Ensure suffix if missing (WS/WSS often needs .D)
        if not addr.suffix:
            suffix = resolve_effective_format(addr.device_type, "")
            addr = DeviceAddress(addr.device_type, addr.number, suffix)
        validate_device_span(addr.device_type, addr.number, addr.suffix, count)
        return addr.to_text()

    @staticmethod
    def _flatten_devices(
        devices: Sequence[str] | tuple[Sequence[str], ...],
    ) -> list[str]:
        if len(devices) == 1 and isinstance(devices[0], (list, tuple)):
            return list(devices[0])
        return list(devices)  # type: ignore[arg-type]

    @staticmethod
    def _format_value(value: int | str, data_format: str) -> str:
        if isinstance(value, int):
            if data_format == ".H":
                return format(value & 0xFFFF, "X")
            return str(value)
        return str(value).strip()


class HostLinkClient(HostLinkBase):
    """Synchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 8501,
        transport: str = "tcp",
        timeout: float = 3.0,
        buffer_size: int = 8192,
        append_lf_on_send: bool = False,
        auto_connect: bool = True,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
    ) -> None:
        super().__init__(host, port, transport, append_lf_on_send, trace_hook)
        self.timeout = timeout
        self.buffer_size = buffer_size
        self._sock: socket.socket | None = None
        self._rx_buffer = b""
        self._lock = threading.Lock()

        if auto_connect:
            self.connect()

    def __enter__(self) -> HostLinkClient:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def connect(self) -> None:
        with self._lock:
            if self._sock is not None:
                return
            sock_type = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
            sock = socket.socket(socket.AF_INET, sock_type)
            sock.settimeout(self.timeout)
            if self.transport == "tcp":
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                sock.connect((self.host, self.port))
            except OSError as exc:
                sock.close()
                raise HostLinkConnectionError(f"Failed to connect to {self.host}:{self.port}") from exc
            self._sock = sock
            self._rx_buffer = b""

    def close(self) -> None:
        with self._lock:
            if self._sock is None:
                return
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._rx_buffer = b""

    def send_raw(self, body: str, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        with self._lock:
            response = self._exchange(self._build_command(body))
            return self._process_response(response, decoder=decoder)

    def _expect_ok(self, body: str) -> None:
        response = self.send_raw(body)
        if response != "OK":
            raise HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")

    def _exchange(self, payload: bytes) -> bytes:
        # Note: This is called within self._lock in send_raw
        if self._sock is None:
            sock_type = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
            self._sock = socket.socket(socket.AF_INET, sock_type)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))

        try:
            self._fire_trace(HostLinkTraceDirection.SEND, payload)
            self._sock.sendall(payload)
            if self.transport == "udp":
                response = self._sock.recv(self.buffer_size)
            else:
                response = self._recv_tcp_line()
            self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
            return response
        except TimeoutError as exc:
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except OSError as exc:
            raise HostLinkConnectionError("Socket communication failed") from exc

    def _recv_tcp_line(self) -> bytes:
        assert self._sock is not None
        while True:
            idx_cr = self._rx_buffer.find(b"\r")
            idx_lf = self._rx_buffer.find(b"\n")
            idx_list = [idx for idx in (idx_cr, idx_lf) if idx >= 0]
            if idx_list:
                idx = min(idx_list)
                line = self._rx_buffer[:idx]
                skip = idx
                while skip < len(self._rx_buffer) and self._rx_buffer[skip] in (10, 13):
                    skip += 1
                self._rx_buffer = self._rx_buffer[skip:]
                return line

            chunk = self._sock.recv(self.buffer_size)
            if not chunk:
                if self._rx_buffer:
                    line = self._rx_buffer
                    self._rx_buffer = b""
                    return line
                raise HostLinkConnectionError("Connection closed by PLC")
            self._rx_buffer += chunk

    # --- Commands ---

    def change_mode(self, mode: int | str) -> None:
        self._expect_ok(self._get_change_mode_cmd(mode))

    def clear_error(self) -> None:
        self._expect_ok("ER")

    def check_error_no(self) -> str:
        return self.send_raw("?E")

    def query_model(self) -> ModelInfo:
        code = self.send_raw("?K")
        return ModelInfo(code=code, model=MODEL_CODES.get(code))

    def read_device_range_catalog(self) -> KvDeviceRangeCatalog:
        return device_range_catalog_for_query_model(self.query_model())

    def confirm_operating_mode(self) -> int:
        return int(self.send_raw("?M"))

    def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None:
        self._expect_ok(self._get_set_time_cmd(value))

    def forced_set(self, device: str) -> None:
        addr = parse_device(device)
        validate_device_type("ST", addr.device_type, FORCE_DEVICE_TYPES)
        self._expect_ok(f"ST {self._device_token(device, drop_suffix=True)}")

    def forced_reset(self, device: str) -> None:
        addr = parse_device(device)
        validate_device_type("RS", addr.device_type, FORCE_DEVICE_TYPES)
        self._expect_ok(f"RS {self._device_token(device, drop_suffix=True)}")

    def forced_set_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        addr = parse_device(device)
        validate_device_type("STS", addr.device_type, FORCE_DEVICE_TYPES)
        self._expect_ok(f"STS {self._device_token(device, drop_suffix=True)} {count}")

    def forced_reset_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        addr = parse_device(device)
        validate_device_type("RSS", addr.device_type, FORCE_DEVICE_TYPES)
        self._expect_ok(f"RSS {self._device_token(device, drop_suffix=True)} {count}")

    def read(self, device: str, *, data_format: str | None = None) -> int | str | list[int | str]:
        token, suffix = self._device_with_format(device, data_format)
        response = self.send_raw(f"RD {token}")
        values = parse_data_tokens(split_data_tokens(response), data_format=suffix)
        if len(values) == 1:
            return values[0]
        return values

    def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        token, suffix = self._device_with_format(device, data_format, count)
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, count)
        response = self.send_raw(f"RDS {token} {count}")
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    def read_consecutive_legacy(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        token, suffix = self._device_with_format(device, data_format, count)
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, count)
        response = self.send_raw(f"RDE {token} {count}")
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        token, suffix = self._device_with_format(device, data_format)
        payload = self._format_value(value, suffix)
        self._expect_ok(f"WR {token} {payload}")

    def write_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token, suffix = self._device_with_format(device, data_format, len(values))
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        self._expect_ok(f"WRS {token} {len(values)} {payload}")

    def write_consecutive_legacy(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token, suffix = self._device_with_format(device, data_format, len(values))
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        self._expect_ok(f"WRE {token} {len(values)} {payload}")

    def write_set_value(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        token = self._ensure_timer_or_counter(device, data_format)
        suffix = parse_device(token).suffix
        payload = self._format_value(value, suffix)
        self._expect_ok(f"WS {token} {payload}")

    def write_set_value_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token = self._ensure_timer_or_counter(device, data_format, len(values))
        suffix = parse_device(token).suffix
        payload = " ".join(self._format_value(v, suffix) for v in values)
        self._expect_ok(f"WSS {token} {len(values)} {payload}")

    def register_monitor_bits(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        for device in targets:
            addr = parse_device(device)
            validate_device_type("MBS", addr.device_type, MBS_DEVICE_TYPES)
            tokens.append(self._device_token(device, drop_suffix=True))
        self._expect_ok("MBS " + " ".join(tokens))

    def register_monitor_words(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        for device in targets:
            addr = parse_device(device)
            validate_device_type("MWS", addr.device_type, MWS_DEVICE_TYPES)
            tok, _ = self._device_with_format(device, None)
            tokens.append(tok)
        self._expect_ok("MWS " + " ".join(tokens))

    def read_monitor_bits(self) -> list[int | str]:
        response = self.send_raw("MBR")
        return parse_data_tokens(split_data_tokens(response))

    def read_monitor_words(self) -> list[str]:
        response = self.send_raw("MWR")
        return split_data_tokens(response)

    def read_comments(self, device: str, *, strip_padding: bool = True) -> str:
        addr = parse_device(device)
        validate_device_type("RDC", addr.device_type, RDC_DEVICE_TYPES)
        token = self._device_token(device, drop_suffix=True)
        response = self.send_raw(f"RDC {token}", decoder=decode_comment_response)
        return response.rstrip(" ") if strip_padding else response

    def switch_bank(self, bank_no: int) -> None:
        validate_range("bank_no", bank_no, 0, 15)
        self._expect_ok(f"BE {bank_no}")

    def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str = ""
    ) -> list[int | str]:
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", count)
        validate_expansion_buffer_span(address, suffix or ".U", count)
        parts = ["URD", f"{unit_no:02d}", str(address)]
        effective_suffix = suffix or ".U"
        parts.append(effective_suffix)
        parts.append(str(count))
        response = self.send_raw(" ".join(parts))
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str = "",
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", len(values))
        validate_expansion_buffer_span(address, suffix or ".U", len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        parts = ["UWR", f"{unit_no:02d}", str(address)]
        effective_suffix = suffix or ".U"
        parts.append(effective_suffix)
        parts.append(str(len(values)))
        parts.append(payload)
        self._expect_ok(" ".join(parts))


class AsyncHostLinkClient(HostLinkBase):
    """Asynchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 8501,
        transport: str = "tcp",
        timeout: float = 3.0,
        buffer_size: int = 8192,
        append_lf_on_send: bool = False,
        auto_connect: bool = True,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
    ) -> None:
        super().__init__(host, port, transport, append_lf_on_send, trace_hook)
        self.timeout = timeout
        self.buffer_size = buffer_size
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._udp_protocol: _HostLinkUDPProtocol | None = None
        self._auto_connect = auto_connect
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> AsyncHostLinkClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def connect(self) -> None:
        async with self._lock:
            await self._connect_unlocked()

    async def _connect_unlocked(self) -> None:
        if self._reader is not None or self._udp_transport is not None:
            return

        if self.transport == "tcp":
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.timeout,
                )
            except (asyncio.TimeoutError, OSError) as exc:
                raise HostLinkConnectionError(f"Failed to connect to {self.host}:{self.port}") from exc
        else:
            loop = asyncio.get_running_loop()
            protocol = _HostLinkUDPProtocol()
            try:
                self._udp_transport, _ = await asyncio.wait_for(
                    loop.create_datagram_endpoint(
                        lambda: protocol,
                        remote_addr=(self.host, self.port),
                    ),
                    timeout=self.timeout,
                )
                self._udp_protocol = protocol
            except (asyncio.TimeoutError, OSError) as exc:
                raise HostLinkConnectionError(f"Failed to setup UDP endpoint for {self.host}:{self.port}") from exc

    async def close(self) -> None:
        async with self._lock:
            if self._writer is not None:
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass
                self._writer = None
                self._reader = None
            if self._udp_transport is not None:
                self._udp_transport.close()
                self._udp_transport = None
                self._udp_protocol = None

    async def send_raw(self, body: str, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        async with self._lock:
            response = await self._exchange(self._build_command(body))
            return self._process_response(response, decoder=decoder)

    async def _expect_ok(self, body: str) -> None:
        response = await self.send_raw(body)
        if response != "OK":
            raise HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")

    async def _exchange(self, payload: bytes) -> bytes:
        # Note: This is called within self._lock in send_raw
        if self._reader is None and self._udp_transport is None:
            await self._connect_unlocked()

        try:
            if self.transport == "tcp":
                assert self._writer is not None
                assert self._reader is not None
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                self._writer.write(payload)
                await self._writer.drain()
                response = await asyncio.wait_for(self._recv_tcp_line(), timeout=self.timeout)
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
            else:
                assert self._udp_transport is not None
                assert self._udp_protocol is not None
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                self._udp_protocol.prepare_response()
                self._udp_transport.sendto(payload)
                response = await asyncio.wait_for(self._udp_protocol.wait_response(), timeout=self.timeout)
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
        except asyncio.TimeoutError as exc:
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except OSError as exc:
            raise HostLinkConnectionError("Socket communication failed") from exc

    async def _recv_tcp_line(self) -> bytes:
        assert self._reader is not None
        # Responses typically end in \r\n. readuntil(\r) gets everything including \r.
        # Leading \n from previous frames are trimmed without affecting padding spaces.
        line = await self._reader.readuntil(b"\r")
        return line.strip(b"\r\n")

    # --- Async Commands ---

    async def change_mode(self, mode: int | str) -> None:
        await self._expect_ok(self._get_change_mode_cmd(mode))

    async def clear_error(self) -> None:
        await self._expect_ok("ER")

    async def check_error_no(self) -> str:
        return await self.send_raw("?E")

    async def query_model(self) -> ModelInfo:
        code = await self.send_raw("?K")
        return ModelInfo(code=code, model=MODEL_CODES.get(code))

    async def read_device_range_catalog(self) -> KvDeviceRangeCatalog:
        return device_range_catalog_for_query_model(await self.query_model())

    async def confirm_operating_mode(self) -> int:
        return int(await self.send_raw("?M"))

    async def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None:
        await self._expect_ok(self._get_set_time_cmd(value))

    async def forced_set(self, device: str) -> None:
        addr = parse_device(device)
        validate_device_type("ST", addr.device_type, FORCE_DEVICE_TYPES)
        await self._expect_ok(f"ST {self._device_token(device, drop_suffix=True)}")

    async def forced_reset(self, device: str) -> None:
        addr = parse_device(device)
        validate_device_type("RS", addr.device_type, FORCE_DEVICE_TYPES)
        await self._expect_ok(f"RS {self._device_token(device, drop_suffix=True)}")

    async def forced_set_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        addr = parse_device(device)
        validate_device_type("STS", addr.device_type, FORCE_DEVICE_TYPES)
        await self._expect_ok(f"STS {self._device_token(device, drop_suffix=True)} {count}")

    async def forced_reset_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        addr = parse_device(device)
        validate_device_type("RSS", addr.device_type, FORCE_DEVICE_TYPES)
        await self._expect_ok(f"RSS {self._device_token(device, drop_suffix=True)} {count}")

    async def read(self, device: str, *, data_format: str | None = None) -> int | str | list[int | str]:
        token, suffix = self._device_with_format(device, data_format)
        response = await self.send_raw(f"RD {token}")
        values = parse_data_tokens(split_data_tokens(response), data_format=suffix)
        if len(values) == 1:
            return values[0]
        return values

    async def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        token, suffix = self._device_with_format(device, data_format, count)
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, count)
        response = await self.send_raw(f"RDS {token} {count}")
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    async def read_consecutive_legacy(
        self, device: str, count: int, *, data_format: str | None = None
    ) -> list[int | str]:
        token, suffix = self._device_with_format(device, data_format, count)
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, count)
        response = await self.send_raw(f"RDE {token} {count}")
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    async def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        token, suffix = self._device_with_format(device, data_format)
        payload = self._format_value(value, suffix)
        await self._expect_ok(f"WR {token} {payload}")

    async def write_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token, suffix = self._device_with_format(device, data_format, len(values))
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        await self._expect_ok(f"WRS {token} {len(values)} {payload}")

    async def write_consecutive_legacy(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token, suffix = self._device_with_format(device, data_format, len(values))
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        await self._expect_ok(f"WRE {token} {len(values)} {payload}")

    async def write_set_value(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        token = self._ensure_timer_or_counter(device, data_format)
        suffix = parse_device(token).suffix
        payload = self._format_value(value, suffix)
        await self._expect_ok(f"WS {token} {payload}")

    async def write_set_value_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token = self._ensure_timer_or_counter(device, data_format, len(values))
        suffix = parse_device(token).suffix
        payload = " ".join(self._format_value(v, suffix) for v in values)
        await self._expect_ok(f"WSS {token} {len(values)} {payload}")

    async def register_monitor_bits(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        for device in targets:
            addr = parse_device(device)
            validate_device_type("MBS", addr.device_type, MBS_DEVICE_TYPES)
            tokens.append(self._device_token(device, drop_suffix=True))
        await self._expect_ok("MBS " + " ".join(tokens))

    async def register_monitor_words(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        for device in targets:
            addr = parse_device(device)
            validate_device_type("MWS", addr.device_type, MWS_DEVICE_TYPES)
            tok, _ = self._device_with_format(device, None)
            tokens.append(tok)
        await self._expect_ok("MWS " + " ".join(tokens))

    async def read_monitor_bits(self) -> list[int | str]:
        response = await self.send_raw("MBR")
        return parse_data_tokens(split_data_tokens(response))

    async def read_monitor_words(self) -> list[str]:
        response = await self.send_raw("MWR")
        return split_data_tokens(response)

    async def read_comments(self, device: str, *, strip_padding: bool = True) -> str:
        addr = parse_device(device)
        validate_device_type("RDC", addr.device_type, RDC_DEVICE_TYPES)
        token = self._device_token(device, drop_suffix=True)
        response = await self.send_raw(f"RDC {token}", decoder=decode_comment_response)
        return response.rstrip(" ") if strip_padding else response

    async def switch_bank(self, bank_no: int) -> None:
        validate_range("bank_no", bank_no, 0, 15)
        await self._expect_ok(f"BE {bank_no}")

    async def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str = ""
    ) -> list[int | str]:
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", count)
        validate_expansion_buffer_span(address, suffix or ".U", count)
        parts = ["URD", f"{unit_no:02d}", str(address)]
        effective_suffix = suffix or ".U"
        parts.append(effective_suffix)
        parts.append(str(count))
        response = await self.send_raw(" ".join(parts))
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    async def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str = "",
    ) -> None:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", len(values))
        validate_expansion_buffer_span(address, suffix or ".U", len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        parts = ["UWR", f"{unit_no:02d}", str(address)]
        effective_suffix = suffix or ".U"
        parts.append(effective_suffix)
        parts.append(str(len(values)))
        parts.append(payload)
        await self._expect_ok(" ".join(parts))


class _HostLinkUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self._future: asyncio.Future[bytes] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        if self._future and not self._future.done():
            self._future.set_result(data.strip())

    def error_received(self, exc: Exception) -> None:
        if self._future and not self._future.done():
            self._future.set_exception(exc)

    def prepare_response(self) -> None:
        self._future = asyncio.get_running_loop().create_future()

    async def wait_response(self) -> bytes:
        assert self._future is not None
        return await self._future
