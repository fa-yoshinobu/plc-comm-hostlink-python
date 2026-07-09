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
    FORCE_CONSECUTIVE_DEVICE_TYPES,
    FORCE_SINGLE_DEVICE_TYPES,
    MBS_DEVICE_TYPES,
    MWS_DEVICE_TYPES,
    RDC_DEVICE_TYPES,
    WR_DEVICE_TYPES,
    WS_DEVICE_TYPES,
    DeviceAddress,
    normalize_suffix,
    parse_device,
    require_explicit_format,
    resolve_effective_format,
    validate_device_count,
    validate_device_span,
    validate_device_type,
    validate_expansion_buffer_count,
    validate_expansion_buffer_span,
    validate_range,
)
from .errors import HostLinkConnectionError, HostLinkProtocolError
from .protocol import (
    build_frame,
    decode_comment_response,
    decode_response,
    ensure_success,
    parse_data_tokens,
    split_data_tokens,
)

UDP_RECEIVE_BUFFER_SIZE = 65_535


class HostLinkTraceDirection(Enum):
    """Direction for a traced Host Link frame."""

    SEND = "send"
    RECEIVE = "receive"


@dataclass(frozen=True)
class HostLinkTraceFrame:
    """One raw Host Link frame observed by a trace hook."""

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
    """PLC model response returned by ``query_model``."""

    code: str
    model: str | None


T = TypeVar("T")


def _normalize_connection_plc_profile(plc_profile: str | None) -> str:
    if plc_profile is None:
        raise ValueError("plc_profile is required. Use an explicit canonical PLC profile such as 'keyence:kv-8000'.")

    from .plc_profiles import normalize_plc_profile

    return normalize_plc_profile(plc_profile)


class HostLinkBase:
    """Base logic for KEYENCE KV Host Link protocol common to sync and async clients."""

    def __init__(
        self,
        host: str,
        port: int = 8501,
        transport: str = "tcp",
        append_lf_on_send: bool = False,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
        *,
        plc_profile: str | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.transport = transport.lower()
        self.append_lf_on_send = append_lf_on_send
        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.trace_hook = trace_hook
        if plc_profile is None and not _allow_manual_profile:
            raise ValueError(
                "plc_profile is required for the standard HostLinkClient route "
                "unless you explicitly opt into a low-level raw Host Link path."
            )
        self.plc_profile = _normalize_connection_plc_profile(plc_profile) if plc_profile is not None else None

    def _fire_trace(self, direction: HostLinkTraceDirection, data: bytes) -> None:
        if self.trace_hook:
            self.trace_hook(HostLinkTraceFrame(direction, data, datetime.now(timezone.utc)))

    # --- Internal helpers ----------------------------------------------

    def _build_command(self, body: str) -> bytes:
        return build_frame(body, append_lf=self.append_lf_on_send)

    def _process_response(self, response: bytes, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        return ensure_success(decoder(response))

    def _device_token(self, device: str, *, drop_suffix: bool = False) -> str:
        addr = parse_device(device)
        if drop_suffix and addr.suffix:
            addr = DeviceAddress(addr.device_type, addr.number, "")
        return addr.to_text()

    def _device_with_format(self, device: str, data_format: str | None, count: int = 1) -> tuple[str, str]:
        addr = parse_device(device)
        suffix = require_explicit_format(addr, data_format)
        validate_device_span(addr.device_type, addr.number, suffix, count)
        addr = DeviceAddress(addr.device_type, addr.number, suffix)
        return addr.to_text(), suffix

    def _ensure_timer_or_counter(self, device: str, data_format: str | None, count: int = 1) -> str:
        addr = parse_device(device)
        validate_device_type("WS/WSS", addr.device_type, WS_DEVICE_TYPES)
        suffix = require_explicit_format(addr, data_format)
        addr = DeviceAddress(addr.device_type, addr.number, suffix)
        validate_device_span(addr.device_type, addr.number, addr.suffix, count)
        validate_device_count(addr.device_type, addr.suffix, count)
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

    def _build_read_command(self, device: str, data_format: str | None = None) -> tuple[str, str]:
        token, suffix = self._device_with_format(device, data_format)
        return f"RD {token}", suffix

    @staticmethod
    def _decode_read_response(response: str, data_format: str) -> int | str | list[int | str]:
        values = parse_data_tokens(split_data_tokens(response), data_format=data_format)
        if len(values) == 1:
            return values[0]
        return values

    def _build_read_consecutive_command(
        self,
        command: str,
        device: str,
        count: int,
        data_format: str | None = None,
    ) -> tuple[str, str]:
        token, suffix = self._device_with_format(device, data_format, count)
        addr = parse_device(token)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, count)
        return f"{command} {token} {count}", suffix

    @staticmethod
    def _decode_data_response(response: str, data_format: str = "") -> list[int | str]:
        return parse_data_tokens(split_data_tokens(response), data_format=data_format)

    def _build_read_comments_command(self, device: str) -> str:
        addr = parse_device(device)
        validate_device_type("RDC", addr.device_type, RDC_DEVICE_TYPES)
        token = self._device_token(device, drop_suffix=True)
        return f"RDC {token}"

    @staticmethod
    def _decode_read_comments_response(response: str, *, strip_padding: bool = True) -> str:
        return response.rstrip(" ") if strip_padding else response

    def _build_write_command(self, device: str, value: int | str, data_format: str | None = None) -> str:
        token, suffix = self._device_with_format(device, data_format)
        addr = parse_device(token)
        validate_device_type("WR", addr.device_type, WR_DEVICE_TYPES)
        payload = self._format_value(value, suffix)
        return f"WR {token} {payload}"

    def _build_write_consecutive_command(
        self,
        command: str,
        device: str,
        values: Sequence[int | str],
        data_format: str | None = None,
    ) -> str:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token, suffix = self._device_with_format(device, data_format, len(values))
        addr = parse_device(token)
        validate_device_type(command, addr.device_type, WR_DEVICE_TYPES)
        effective_format = resolve_effective_format(addr.device_type, suffix)
        validate_device_count(addr.device_type, effective_format, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        return f"{command} {token} {len(values)} {payload}"

    def _build_write_set_value_command(self, device: str, value: int | str, data_format: str | None = None) -> str:
        token = self._ensure_timer_or_counter(device, data_format)
        suffix = parse_device(token).suffix
        payload = self._format_value(value, suffix)
        return f"WS {token} {payload}"

    def _build_write_set_value_consecutive_command(
        self,
        device: str,
        values: Sequence[int | str],
        data_format: str | None = None,
    ) -> str:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        token = self._ensure_timer_or_counter(device, data_format, len(values))
        suffix = parse_device(token).suffix
        payload = " ".join(self._format_value(v, suffix) for v in values)
        return f"WSS {token} {len(values)} {payload}"

    def _build_register_monitor_bits_command(
        self,
        devices: Sequence[str] | tuple[Sequence[str], ...],
    ) -> str:
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
        return "MBS " + " ".join(tokens)

    def _build_register_monitor_words_command(
        self,
        devices: Sequence[str] | tuple[Sequence[str], ...],
    ) -> str:
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
        return "MWS " + " ".join(tokens)

    def _decode_monitor_bits_response(self, response: str) -> list[int | str]:
        return self._decode_data_response(response)

    @staticmethod
    def _decode_monitor_words_response(response: str) -> list[str]:
        return split_data_tokens(response)

    def _build_change_mode_command(self, mode: int | str) -> str:
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

    @staticmethod
    def _build_clear_error_command() -> str:
        return "ER"

    @staticmethod
    def _build_check_error_no_command() -> str:
        return "?E"

    @staticmethod
    def _build_query_model_command() -> str:
        return "?K"

    @staticmethod
    def _decode_query_model_response(response: str) -> ModelInfo:
        return ModelInfo(code=response, model=MODEL_CODES.get(response))

    @staticmethod
    def _build_confirm_operating_mode_command() -> str:
        return "?M"

    @staticmethod
    def _decode_confirm_operating_mode_response(response: str) -> int:
        return int(response)

    def _build_set_time_command(
        self,
        value: datetime | tuple[int, int, int, int, int, int, int] | None = None,
    ) -> str:
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

    def _build_forced_command(self, command: str, device: str) -> str:
        addr = parse_device(device)
        validate_device_type(command, addr.device_type, FORCE_SINGLE_DEVICE_TYPES)
        return f"{command} {self._device_token(device, drop_suffix=True)}"

    def _build_forced_consecutive_command(self, command: str, device: str, count: int) -> str:
        validate_range("count", count, 1, 16)
        addr = parse_device(device)
        validate_device_type(command, addr.device_type, FORCE_CONSECUTIVE_DEVICE_TYPES)
        return f"{command} {self._device_token(device, drop_suffix=True)} {count}"

    @staticmethod
    def _build_switch_bank_command(bank_no: int) -> str:
        validate_range("bank_no", bank_no, 0, 15)
        return f"BE {bank_no}"

    def _build_read_expansion_unit_buffer_command(
        self,
        unit_no: int,
        address: int,
        count: int,
        data_format: str = "",
    ) -> tuple[str, str]:
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", count)
        validate_expansion_buffer_span(address, suffix or ".U", count)
        effective_suffix = suffix or ".U"
        parts = ["URD", f"{unit_no:02d}", f"{address}{effective_suffix}"]
        parts.append(str(count))
        return " ".join(parts), suffix

    def _decode_expansion_unit_buffer_response(self, response: str, data_format: str) -> list[int | str]:
        return self._decode_data_response(response, data_format=data_format)

    def _build_write_expansion_unit_buffer_command(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        data_format: str = "",
    ) -> str:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = normalize_suffix(data_format)
        validate_expansion_buffer_count(suffix or ".U", len(values))
        validate_expansion_buffer_span(address, suffix or ".U", len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        effective_suffix = suffix or ".U"
        parts = ["UWR", f"{unit_no:02d}", f"{address}{effective_suffix}"]
        parts.append(str(len(values)))
        parts.append(payload)
        return " ".join(parts)


class HostLinkClient(HostLinkBase):
    """Synchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 8501,
        transport: str = "tcp",
        timeout: float = 3.0,
        plc_profile: str | None = None,
        buffer_size: int = 8192,
        append_lf_on_send: bool = False,
        auto_connect: bool = True,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            append_lf_on_send,
            trace_hook,
            plc_profile=plc_profile,
            _allow_manual_profile=_allow_manual_profile,
        )
        self.timeout = timeout
        if buffer_size <= 0:
            raise ValueError("buffer_size must be positive")
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
        """Open the configured TCP or UDP socket if it is not already open."""

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
        """Close the current socket and clear buffered receive data."""

        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._rx_buffer = b""

    def send_raw(self, body: str, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        """Send one raw Host Link command body and return the decoded response text."""

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

        try:
            self._fire_trace(HostLinkTraceDirection.SEND, payload)
            self._sock.sendall(payload)
            if self.transport == "udp":
                response = self._sock.recv(UDP_RECEIVE_BUFFER_SIZE)
            else:
                response = self._recv_tcp_line()
            self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
            return response
        except TimeoutError as exc:
            if self.transport == "tcp":
                self._close_unlocked()
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except OSError as exc:
            if self.transport == "tcp":
                self._close_unlocked()
            raise HostLinkConnectionError("Socket communication failed") from exc

    def _recv_tcp_line(self) -> bytes:
        if self._sock is None:
            raise HostLinkConnectionError("Not connected")
        while True:
            while self._rx_buffer and self._rx_buffer[0] in (10, 13):
                self._rx_buffer = self._rx_buffer[1:]
            idx_cr = self._rx_buffer.find(b"\r")
            idx_lf = self._rx_buffer.find(b"\n")
            idx_list = [idx for idx in (idx_cr, idx_lf) if idx >= 0]
            if idx_list:
                idx = min(idx_list)
                if idx > self.buffer_size:
                    self._close_unlocked()
                    raise HostLinkProtocolError(f"Response line exceeds {self.buffer_size} bytes")
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
            if (
                len(self._rx_buffer) > self.buffer_size
                and b"\r" not in self._rx_buffer
                and b"\n" not in self._rx_buffer
            ):
                self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {self.buffer_size} bytes")

    # --- Commands ---

    def change_mode(self, mode: int | str) -> None:
        """Change the PLC operating mode through the Host Link ``M`` command."""

        self._expect_ok(self._build_change_mode_command(mode))

    def clear_error(self) -> None:
        """Clear the current PLC error through the Host Link ``ER`` command."""

        self._expect_ok(self._build_clear_error_command())

    def check_error_no(self) -> str:
        """Read the current PLC error number as raw response text."""

        return self.send_raw(self._build_check_error_no_command())

    def query_model(self) -> ModelInfo:
        """Query the PLC model code and mapped model name."""

        response = self.send_raw(self._build_query_model_command())
        return self._decode_query_model_response(response)

    def confirm_operating_mode(self) -> int:
        """Return the current PLC operating mode code."""

        response = self.send_raw(self._build_confirm_operating_mode_command())
        return self._decode_confirm_operating_mode_response(response)

    def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None:
        """Set the PLC clock from ``value`` or from the current system time."""

        self._expect_ok(self._build_set_time_command(value))

    def forced_set(self, device: str) -> None:
        """Force one bit device ON."""

        self._expect_ok(self._build_forced_command("ST", device))

    def forced_reset(self, device: str) -> None:
        """Force one bit device OFF."""

        self._expect_ok(self._build_forced_command("RS", device))

    def forced_set_consecutive(self, device: str, count: int) -> None:
        """Force a consecutive bit-device range ON."""

        self._expect_ok(self._build_forced_consecutive_command("STS", device, count))

    def forced_reset_consecutive(self, device: str, count: int) -> None:
        """Force a consecutive bit-device range OFF."""

        self._expect_ok(self._build_forced_consecutive_command("RSS", device, count))

    def read(self, device: str, *, data_format: str | None = None) -> int | str | list[int | str]:
        """Read one device with the Host Link ``RD`` command."""

        body, suffix = self._build_read_command(device, data_format)
        response = self.send_raw(body)
        return self._decode_read_response(response, suffix)

    def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the Host Link ``RDS`` command."""

        body, suffix = self._build_read_consecutive_command("RDS", device, count, data_format)
        response = self.send_raw(body)
        return self._decode_data_response(response, suffix)

    def read_consecutive_legacy(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the legacy Host Link ``RDE`` command."""

        body, suffix = self._build_read_consecutive_command("RDE", device, count, data_format)
        response = self.send_raw(body)
        return self._decode_data_response(response, suffix)

    def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one device with the Host Link ``WR`` command."""

        self._expect_ok(self._build_write_command(device, value, data_format))

    def write_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive devices with the Host Link ``WRS`` command."""

        self._expect_ok(self._build_write_consecutive_command("WRS", device, values, data_format))

    def write_consecutive_legacy(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive devices with the legacy Host Link ``WRE`` command."""

        self._expect_ok(self._build_write_consecutive_command("WRE", device, values, data_format))

    def write_set_value(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one timer or counter preset/current value with ``WS``."""

        self._expect_ok(self._build_write_set_value_command(device, value, data_format))

    def write_set_value_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive timer or counter values with ``WSS``."""

        self._expect_ok(self._build_write_set_value_consecutive_command(device, values, data_format))

    def register_monitor_bits(self, *devices: str) -> None:
        """Register bit devices for later monitor reads."""

        self._expect_ok(self._build_register_monitor_bits_command(devices))

    def register_monitor_words(self, *devices: str) -> None:
        """Register word devices for later monitor reads."""

        self._expect_ok(self._build_register_monitor_words_command(devices))

    def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        response = self.send_raw("MBR")
        return self._decode_monitor_bits_response(response)

    def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        response = self.send_raw("MWR")
        return self._decode_monitor_words_response(response)

    def read_comments(self, device: str, *, strip_padding: bool = True) -> str:
        """Read the PLC comment text for one supported device."""

        response = self.send_raw(self._build_read_comments_command(device), decoder=decode_comment_response)
        return self._decode_read_comments_response(response, strip_padding=strip_padding)

    def switch_bank(self, bank_no: int) -> None:
        """Switch the active Host Link bank number."""

        self._expect_ok(self._build_switch_bank_command(bank_no))

    def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str = ""
    ) -> list[int | str]:
        """Read an expansion unit buffer range with ``URD``."""

        body, suffix = self._build_read_expansion_unit_buffer_command(unit_no, address, count, data_format)
        response = self.send_raw(body)
        return self._decode_expansion_unit_buffer_response(response, suffix)

    def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str = "",
    ) -> None:
        """Write an expansion unit buffer range with ``UWR``."""

        self._expect_ok(self._build_write_expansion_unit_buffer_command(unit_no, address, values, data_format))


class AsyncHostLinkClient(HostLinkBase):
    """Asynchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 8501,
        transport: str = "tcp",
        timeout: float = 3.0,
        plc_profile: str | None = None,
        buffer_size: int = 8192,
        append_lf_on_send: bool = False,
        auto_connect: bool = True,
        trace_hook: Callable[[HostLinkTraceFrame], None] | None = None,
        _allow_manual_profile: bool = False,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            append_lf_on_send,
            trace_hook,
            plc_profile=plc_profile,
            _allow_manual_profile=_allow_manual_profile,
        )
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
        """Open the configured TCP or UDP transport if it is not already open."""

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
        """Close the current async transport and clear connection state."""

        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
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
        """Send one raw Host Link command body and return the decoded response text."""

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
                if self._writer is None:
                    raise HostLinkConnectionError("Not connected")
                if self._reader is None:
                    raise HostLinkConnectionError("Not connected")
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                self._writer.write(payload)
                await self._writer.drain()
                response = await asyncio.wait_for(self._recv_tcp_line(), timeout=self.timeout)
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
            else:
                if self._udp_transport is None:
                    raise HostLinkConnectionError("Not connected")
                if self._udp_protocol is None:
                    raise HostLinkConnectionError("Not connected")
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                self._udp_protocol.prepare_response()
                self._udp_transport.sendto(payload)
                response = await asyncio.wait_for(self._udp_protocol.wait_response(), timeout=self.timeout)
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
        except asyncio.TimeoutError as exc:
            if self.transport == "tcp":
                await self._close_unlocked()
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except OSError as exc:
            if self.transport == "tcp":
                await self._close_unlocked()
            raise HostLinkConnectionError("Socket communication failed") from exc

    async def _recv_tcp_line(self) -> bytes:
        if self._reader is None:
            raise HostLinkConnectionError("Not connected")
        line = bytearray()
        while True:
            byte = await self._reader.read(1)
            if not byte:
                if line:
                    return bytes(line)
                raise HostLinkConnectionError("Connection closed by PLC")
            if byte[0] in (10, 13):
                if line:
                    return bytes(line)
                # Discard CR/LF left by the previous response, including a
                # terminator split across TCP reads.
                continue
            line.extend(byte)
            if len(line) > self.buffer_size:
                await self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {self.buffer_size} bytes")

    # --- Async Commands ---

    async def change_mode(self, mode: int | str) -> None:
        """Change the PLC operating mode through the Host Link ``M`` command."""

        await self._expect_ok(self._build_change_mode_command(mode))

    async def clear_error(self) -> None:
        """Clear the current PLC error through the Host Link ``ER`` command."""

        await self._expect_ok(self._build_clear_error_command())

    async def check_error_no(self) -> str:
        """Read the current PLC error number as raw response text."""

        return await self.send_raw(self._build_check_error_no_command())

    async def query_model(self) -> ModelInfo:
        """Query the PLC model code and mapped model name."""

        response = await self.send_raw(self._build_query_model_command())
        return self._decode_query_model_response(response)

    async def confirm_operating_mode(self) -> int:
        """Return the current PLC operating mode code."""

        response = await self.send_raw(self._build_confirm_operating_mode_command())
        return self._decode_confirm_operating_mode_response(response)

    async def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None:
        """Set the PLC clock from ``value`` or from the current system time."""

        await self._expect_ok(self._build_set_time_command(value))

    async def forced_set(self, device: str) -> None:
        """Force one bit device ON."""

        await self._expect_ok(self._build_forced_command("ST", device))

    async def forced_reset(self, device: str) -> None:
        """Force one bit device OFF."""

        await self._expect_ok(self._build_forced_command("RS", device))

    async def forced_set_consecutive(self, device: str, count: int) -> None:
        """Force a consecutive bit-device range ON."""

        await self._expect_ok(self._build_forced_consecutive_command("STS", device, count))

    async def forced_reset_consecutive(self, device: str, count: int) -> None:
        """Force a consecutive bit-device range OFF."""

        await self._expect_ok(self._build_forced_consecutive_command("RSS", device, count))

    async def read(self, device: str, *, data_format: str | None = None) -> int | str | list[int | str]:
        """Read one device with the Host Link ``RD`` command."""

        body, suffix = self._build_read_command(device, data_format)
        response = await self.send_raw(body)
        return self._decode_read_response(response, suffix)

    async def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the Host Link ``RDS`` command."""

        body, suffix = self._build_read_consecutive_command("RDS", device, count, data_format)
        response = await self.send_raw(body)
        return self._decode_data_response(response, suffix)

    async def read_consecutive_legacy(
        self, device: str, count: int, *, data_format: str | None = None
    ) -> list[int | str]:
        """Read consecutive devices with the legacy Host Link ``RDE`` command."""

        body, suffix = self._build_read_consecutive_command("RDE", device, count, data_format)
        response = await self.send_raw(body)
        return self._decode_data_response(response, suffix)

    async def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one device with the Host Link ``WR`` command."""

        await self._expect_ok(self._build_write_command(device, value, data_format))

    async def write_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive devices with the Host Link ``WRS`` command."""

        await self._expect_ok(self._build_write_consecutive_command("WRS", device, values, data_format))

    async def write_consecutive_legacy(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive devices with the legacy Host Link ``WRE`` command."""

        await self._expect_ok(self._build_write_consecutive_command("WRE", device, values, data_format))

    async def write_set_value(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one timer or counter preset/current value with ``WS``."""

        await self._expect_ok(self._build_write_set_value_command(device, value, data_format))

    async def write_set_value_consecutive(
        self,
        device: str,
        values: Sequence[int | str],
        *,
        data_format: str | None = None,
    ) -> None:
        """Write consecutive timer or counter values with ``WSS``."""

        await self._expect_ok(self._build_write_set_value_consecutive_command(device, values, data_format))

    async def register_monitor_bits(self, *devices: str) -> None:
        """Register bit devices for later monitor reads."""

        await self._expect_ok(self._build_register_monitor_bits_command(devices))

    async def register_monitor_words(self, *devices: str) -> None:
        """Register word devices for later monitor reads."""

        await self._expect_ok(self._build_register_monitor_words_command(devices))

    async def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        response = await self.send_raw("MBR")
        return self._decode_monitor_bits_response(response)

    async def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        response = await self.send_raw("MWR")
        return self._decode_monitor_words_response(response)

    async def read_comments(self, device: str, *, strip_padding: bool = True) -> str:
        """Read the PLC comment text for one supported device."""

        response = await self.send_raw(self._build_read_comments_command(device), decoder=decode_comment_response)
        return self._decode_read_comments_response(response, strip_padding=strip_padding)

    async def switch_bank(self, bank_no: int) -> None:
        """Switch the active Host Link bank number."""

        await self._expect_ok(self._build_switch_bank_command(bank_no))

    async def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str = ""
    ) -> list[int | str]:
        """Read an expansion unit buffer range with ``URD``."""

        body, suffix = self._build_read_expansion_unit_buffer_command(unit_no, address, count, data_format)
        response = await self.send_raw(body)
        return self._decode_expansion_unit_buffer_response(response, suffix)

    async def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str = "",
    ) -> None:
        """Write an expansion unit buffer range with ``UWR``."""

        await self._expect_ok(self._build_write_expansion_unit_buffer_command(unit_no, address, values, data_format))


class _HostLinkUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self._future: asyncio.Future[bytes] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = cast(asyncio.DatagramTransport, transport)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        if self._future and not self._future.done():
            self._future.set_result(data.rstrip(b"\r\n"))

    def error_received(self, exc: Exception) -> None:
        if self._future and not self._future.done():
            self._future.set_exception(exc)

    def prepare_response(self) -> None:
        self._future = asyncio.get_running_loop().create_future()

    async def wait_response(self) -> bytes:
        if self._future is None:
            raise HostLinkConnectionError("Not connected")
        return await self._future
