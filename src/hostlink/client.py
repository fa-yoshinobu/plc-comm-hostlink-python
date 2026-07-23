"""High-level Host Link client (TCP/UDP) with full command coverage."""

from __future__ import annotations

import asyncio
import math
import socket
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar, cast

from .device import (
    DIRECT_BIT_DEVICE_TYPES,
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

ABSOLUTE_RESPONSE_CAP = 65_536
UDP_RECEIVE_BUFFER_SIZE = ABSOLUTE_RESPONSE_CAP + 2


def _remaining_timeout(deadline: float, *, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError
    return remaining


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


@dataclass(frozen=True)
class HostLinkTrafficStats:
    """Immutable lifetime traffic counters for one client.

    TCP receive bytes include the response body and its first CR/LF terminator;
    extra separator bytes are consumed but excluded. UDP receive bytes include
    the complete datagram.
    """

    request_count: int
    tx_bytes: int
    rx_bytes: int


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
        port: int,
        transport: str,
        *,
        plc_profile: str,
    ) -> None:
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host is required and must be a non-empty string")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port is required and must be an integer in the range 1..65535")
        if not isinstance(transport, str) or transport.strip().lower() not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.host = host.strip()
        self.port = port
        self.transport = transport.strip().lower()
        self._maintainer_trace_hook: Callable[[HostLinkTraceFrame], None] | None = None
        self.plc_profile = _normalize_connection_plc_profile(plc_profile)
        self._monitor_bit_count = 0
        self._monitor_word_count = 0

    def _fire_trace(self, direction: HostLinkTraceDirection, data: bytes) -> None:
        if self._maintainer_trace_hook:
            try:
                self._maintainer_trace_hook(HostLinkTraceFrame(direction, data, datetime.now(timezone.utc)))
            except Exception:
                # Maintainer diagnostics must not change command success, ordering, or retry behavior.
                pass

    # --- Internal helpers ----------------------------------------------

    def _build_command(self, body: str) -> bytes:
        return build_frame(body)

    def _process_response(self, response: bytes, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        return ensure_success(decoder(response))

    @staticmethod
    def _validate_response_cap(response: bytes) -> bytes:
        body = response.rstrip(b"\r\n")
        if len(body) > ABSOLUTE_RESPONSE_CAP:
            raise HostLinkProtocolError(f"Response line exceeds {ABSOLUTE_RESPONSE_CAP} bytes")
        return response

    def _device_token(self, device: str, *, drop_suffix: bool = False) -> str:
        addr = parse_device(device)
        if drop_suffix and addr.suffix:
            raise HostLinkProtocolError(f"Device {device!r} must not contain a data-format suffix for this command")
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
        if data_format == "":
            if isinstance(value, bool):
                return "1" if value else "0"
            if type(value) is int and value in {0, 1}:
                return str(value)
            raise HostLinkProtocolError(f"BIT value must be bool or integer 0/1, got {value!r}")
        limits = {
            ".U": (0, 0xFFFF),
            ".S": (-0x8000, 0x7FFF),
            ".D": (0, 0xFFFFFFFF),
            ".L": (-0x80000000, 0x7FFFFFFF),
            ".H": (0, 0xFFFF),
        }.get(data_format)
        if limits is None or type(value) is not int or not limits[0] <= value <= limits[1]:
            raise HostLinkProtocolError(f"value {value!r} is outside the range for data_format {data_format!r}")
        return format(value, "X") if data_format == ".H" else str(value)

    def _build_read_command(self, device: str, data_format: str | None = None) -> tuple[str, str]:
        token, suffix = self._device_with_format(device, data_format)
        return f"RD {token}", suffix

    @staticmethod
    def _decode_read_response(response: str, data_format: str, expected_count: int = 1) -> int | str | list[int | str]:
        values = parse_data_tokens(split_data_tokens(response), data_format=data_format)
        if len(values) != expected_count:
            raise HostLinkProtocolError(
                f"Read response token count mismatch: expected {expected_count}, received {len(values)}"
            )
        return values[0] if expected_count == 1 else values

    @staticmethod
    def _read_response_token_count(device: str, data_format: str) -> int:
        device_type = parse_device(device).device_type
        if device_type in {"T", "C"}:
            return 3
        if device_type in DIRECT_BIT_DEVICE_TYPES:
            if data_format in {".U", ".S", ".H"}:
                return 16
            if data_format in {".D", ".L"}:
                return 32
        return 1

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
    def _decode_data_response(
        response: str, data_format: str = "", expected_count: int | None = None
    ) -> list[int | str]:
        values = parse_data_tokens(split_data_tokens(response), data_format=data_format)
        if expected_count is not None and len(values) != expected_count:
            raise HostLinkProtocolError(
                f"Read response token count mismatch: expected {expected_count}, received {len(values)}"
            )
        return values

    def _build_read_comments_command(self, device: str) -> str:
        addr = parse_device(device)
        validate_device_type("RDC", addr.device_type, RDC_DEVICE_TYPES)
        token = self._device_token(device, drop_suffix=True)
        return f"RDC {token}"

    @staticmethod
    def _decode_read_comments_response(response: str) -> str:
        return response

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
        entries: Sequence[str | tuple[str, str]],
    ) -> str:
        targets = list(entries)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        for entry in targets:
            if isinstance(entry, str):
                device = entry
                data_format: str | None = None
            elif isinstance(entry, tuple) and len(entry) == 2 and all(isinstance(value, str) for value in entry):
                device, data_format = entry
            else:
                raise HostLinkProtocolError(
                    "register_monitor_words entries must be a device string or (device, data_format) tuple"
                )
            addr = parse_device(device)
            validate_device_type("MWS", addr.device_type, MWS_DEVICE_TYPES)
            tok, _ = self._device_with_format(device, data_format)
            tokens.append(tok)
        return "MWS " + " ".join(tokens)

    def _decode_monitor_bits_response(self, response: str) -> list[int | str]:
        return self._decode_data_response(response, expected_count=self._monitor_bit_count)

    def _decode_monitor_words_response(self, response: str) -> list[str]:
        values = split_data_tokens(response)
        if len(values) != self._monitor_word_count:
            raise HostLinkProtocolError(
                f"Monitor response token count mismatch: expected {self._monitor_word_count}, received {len(values)}"
            )
        return values

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
        value: datetime | tuple[int, int, int, int, int, int, int],
    ) -> str:
        if isinstance(value, datetime):
            if not 2000 <= value.year <= 2099:
                raise HostLinkProtocolError("datetime year must be in range 2000..2099")
            year = value.year - 2000
            month = value.month
            day = value.day
            hour = value.hour
            minute = value.minute
            second = value.second
            week = (value.weekday() + 1) % 7
        else:
            if not isinstance(value, tuple) or len(value) != 7 or any(type(field) is not int for field in value):
                raise HostLinkProtocolError(
                    "time value must contain integer year, month, day, hour, minute, second, and week fields"
                )
            year, month, day, hour, minute, second, week = value

        validate_range("year(YY)", year, 0, 99)
        validate_range("month", month, 1, 12)
        validate_range("day", day, 1, 31)
        validate_range("hour", hour, 0, 23)
        validate_range("minute", minute, 0, 59)
        validate_range("second", second, 0, 59)
        validate_range("week", week, 0, 6)
        if not isinstance(value, datetime):
            try:
                calendar = datetime(2000 + year, month, day, hour, minute, second)
            except ValueError as exc:
                raise HostLinkProtocolError("time value contains a nonexistent calendar date") from exc
            expected_week = (calendar.weekday() + 1) % 7
            if week != expected_week:
                raise HostLinkProtocolError(f"week {week} does not match the calendar date (expected {expected_week})")

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
        data_format: str,
    ) -> tuple[str, str]:
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = self._require_expansion_data_format(data_format)
        validate_expansion_buffer_count(suffix, count)
        validate_expansion_buffer_span(address, suffix, count)
        effective_suffix = suffix
        parts = ["URD", f"{unit_no:02d}", f"{address}{effective_suffix}"]
        parts.append(str(count))
        return " ".join(parts), suffix

    def _decode_expansion_unit_buffer_response(
        self, response: str, data_format: str, expected_count: int
    ) -> list[int | str]:
        return self._decode_data_response(response, data_format=data_format, expected_count=expected_count)

    def _build_write_expansion_unit_buffer_command(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        data_format: str,
    ) -> str:
        if not values:
            raise HostLinkProtocolError("values must not be empty")
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        suffix = self._require_expansion_data_format(data_format)
        validate_expansion_buffer_count(suffix, len(values))
        validate_expansion_buffer_span(address, suffix, len(values))
        payload = " ".join(self._format_value(v, suffix) for v in values)
        effective_suffix = suffix
        parts = ["UWR", f"{unit_no:02d}", f"{address}{effective_suffix}"]
        parts.append(str(len(values)))
        parts.append(payload)
        return " ".join(parts)

    @staticmethod
    def _require_expansion_data_format(data_format: str) -> str:
        if not isinstance(data_format, str) or not data_format.strip():
            raise HostLinkProtocolError("data_format is required for expansion unit buffer access")
        suffix = normalize_suffix(data_format)
        if suffix not in {".U", ".S", ".D", ".L", ".H"}:
            raise HostLinkProtocolError(f"Unsupported expansion unit buffer data_format {data_format!r}")
        return suffix


class HostLinkClient(HostLinkBase):
    """Synchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int,
        transport: str,
        timeout: float = 3.0,
        plc_profile: str,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            plc_profile=plc_profile,
        )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number")
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._rx_buffer = b""
        self._lock = threading.Lock()
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._last_rx_frame_length = 0

    def traffic_stats(self) -> HostLinkTrafficStats:
        """Return an immutable lifetime traffic-counter snapshot."""
        with self._lock:
            return HostLinkTrafficStats(self._request_count, self._tx_bytes, self._rx_bytes)

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
        self._monitor_bit_count = 0
        self._monitor_word_count = 0
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._rx_buffer = b""

    def send_raw(self, body: str) -> bytes:
        """Send one maintainer raw command and return undecoded response body bytes."""

        with self._lock:
            response = self._exchange(self._build_command(body))
            return response.rstrip(b"\r\n")

    def _send_decoded(self, body: str, decoder: Callable[[bytes], str] = decode_response) -> str:
        with self._lock:
            return self._send_decoded_unlocked(body, decoder)

    def _send_decoded_unlocked(self, body: str, decoder: Callable[[bytes], str] = decode_response) -> str:
        response = self._exchange(self._build_command(body))
        try:
            return self._process_response(response, decoder=decoder)
        except HostLinkProtocolError:
            self._close_unlocked()
            raise

    def _send_parsed(self, body: str, parser: Callable[[str], T]) -> T:
        with self._lock:
            response = self._send_decoded_unlocked(body)
            try:
                return parser(response)
            except HostLinkProtocolError:
                self._close_unlocked()
                raise

    def _expect_ok(self, body: str) -> None:
        with self._lock:
            self._expect_ok_unlocked(body)

    def _expect_ok_unlocked(self, body: str) -> None:
        response = self._send_decoded_unlocked(body)
        if response != "OK":
            self._close_unlocked()
            raise HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")

    def _exchange(self, payload: bytes) -> bytes:
        # Note: This is called within self._lock in send_raw
        if self._sock is None:
            raise HostLinkConnectionError("Client is not connected; call connect() before sending a command")

        exchange_complete = False
        deadline = time.monotonic() + self.timeout
        try:
            self._fire_trace(HostLinkTraceDirection.SEND, payload)
            self._sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            self._sock.sendall(payload)
            self._request_count += 1
            self._tx_bytes += len(payload)
            if self.transport == "udp":
                self._sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
                response = self._sock.recv(UDP_RECEIVE_BUFFER_SIZE)
                self._validate_response_cap(response)
                if not response or response[-1] not in (10, 13):
                    raise HostLinkProtocolError("UDP response is missing the required CR/LF terminator")
                self._rx_bytes += len(response)
            else:
                response = self._recv_tcp_line(deadline=deadline)
                self._rx_bytes += self._last_rx_frame_length
            exchange_complete = True
            self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
            return response
        except TimeoutError as exc:
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except HostLinkConnectionError:
            raise
        except OSError as exc:
            raise HostLinkConnectionError("Socket communication failed") from exc
        finally:
            if not exchange_complete:
                # Host Link responses do not carry a transaction ID. Discard
                # the whole transport so a late response cannot satisfy the
                # next request, including when the transport is UDP.
                self._close_unlocked()

    def _recv_tcp_line(self, *, deadline: float | None = None) -> bytes:
        if self._sock is None:
            raise HostLinkConnectionError("Not connected")
        if deadline is None:
            deadline = time.monotonic() + self.timeout
        while True:
            while self._rx_buffer and self._rx_buffer[0] in (10, 13):
                self._rx_buffer = self._rx_buffer[1:]
            idx_cr = self._rx_buffer.find(b"\r")
            idx_lf = self._rx_buffer.find(b"\n")
            idx_list = [idx for idx in (idx_cr, idx_lf) if idx >= 0]
            if idx_list:
                idx = min(idx_list)
                if idx > ABSOLUTE_RESPONSE_CAP:
                    self._close_unlocked()
                    raise HostLinkProtocolError(f"Response line exceeds {ABSOLUTE_RESPONSE_CAP} bytes")
                line = self._rx_buffer[:idx]
                skip = idx
                while skip < len(self._rx_buffer) and self._rx_buffer[skip] in (10, 13):
                    skip += 1
                self._rx_buffer = self._rx_buffer[skip:]
                # A TCP response line ends at the first CR/LF.  Consume any
                # adjacent separator padding, but do not let TCP chunking
                # change the traffic counter.
                self._last_rx_frame_length = idx + 1
                return line

            self._sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            chunk = self._sock.recv(8192)
            if not chunk:
                message = (
                    "Connection closed by PLC before the response terminator"
                    if self._rx_buffer
                    else "Connection closed by PLC"
                )
                raise HostLinkConnectionError(message)
            self._rx_buffer += chunk
            if (
                len(self._rx_buffer) > ABSOLUTE_RESPONSE_CAP
                and b"\r" not in self._rx_buffer
                and b"\n" not in self._rx_buffer
            ):
                self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {ABSOLUTE_RESPONSE_CAP} bytes")

    # --- Commands ---

    def change_mode(self, mode: int | str) -> None:
        """Change the PLC operating mode through the Host Link ``M`` command."""

        self._expect_ok(self._build_change_mode_command(mode))

    def clear_error(self) -> None:
        """Clear the current PLC error through the Host Link ``ER`` command."""

        self._expect_ok(self._build_clear_error_command())

    def check_error_no(self) -> str:
        """Read the current PLC error number as raw response text."""

        return self._send_decoded(self._build_check_error_no_command())

    def query_model(self) -> ModelInfo:
        """Query the PLC model code and mapped model name."""

        return self._send_parsed(self._build_query_model_command(), self._decode_query_model_response)

    def confirm_operating_mode(self) -> int:
        """Return the current PLC operating mode code."""

        return self._send_parsed(
            self._build_confirm_operating_mode_command(), self._decode_confirm_operating_mode_response
        )

    def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int]) -> None:
        """Set the PLC clock from an explicit value."""

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
        return self._send_parsed(
            body,
            lambda response: self._decode_read_response(
                response, suffix, self._read_response_token_count(device, suffix)
            ),
        )

    def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the Host Link ``RDS`` command."""

        body, suffix = self._build_read_consecutive_command("RDS", device, count, data_format)
        return self._send_parsed(body, lambda response: self._decode_data_response(response, suffix, count))

    def read_consecutive_legacy(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the legacy Host Link ``RDE`` command."""

        body, suffix = self._build_read_consecutive_command("RDE", device, count, data_format)
        return self._send_parsed(body, lambda response: self._decode_data_response(response, suffix, count))

    def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one device with the Host Link ``WR`` command."""

        self._expect_ok(self._build_write_command(device, value, data_format))

    def write_bit_in_word(self, device: str, bit_index: int, value: bool) -> None:
        """Set or clear one word bit while holding this client's request lock."""

        if type(bit_index) is not int or not 0 <= bit_index <= 15:
            raise ValueError(f"bit_index must be 0-15, got {bit_index}")
        if not isinstance(value, bool):
            raise TypeError("value must be bool")
        read_body, suffix = self._build_read_command(device, ".U")
        with self._lock:
            response = self._send_decoded_unlocked(read_body)
            try:
                result = self._decode_read_response(response, suffix)
                values = result if isinstance(result, list) else [result]
                if len(values) != 1 or type(values[0]) is not int or not 0 <= values[0] <= 0xFFFF:
                    raise HostLinkProtocolError(f"Bit-in-word read for {device!r} did not return one unsigned word")
            except HostLinkProtocolError:
                self._close_unlocked()
                raise
            current = values[0]
            next_value = current | (1 << bit_index) if value else current & ~(1 << bit_index)
            write_body = self._build_write_command(device, next_value, ".U")
            write_response = self._send_decoded_unlocked(write_body)
            if write_response != "OK":
                self._close_unlocked()
                raise HostLinkProtocolError(f"Expected 'OK' but received {write_response!r} for command {write_body!r}")

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

        body = self._build_register_monitor_bits_command(devices)
        count = len(self._flatten_devices(devices))
        with self._lock:
            self._expect_ok_unlocked(body)
            self._monitor_bit_count = count

    def register_monitor_words(self, entries: Sequence[str | tuple[str, str]]) -> None:
        """Register word devices for later monitor reads."""

        body = self._build_register_monitor_words_command(entries)
        with self._lock:
            self._expect_ok_unlocked(body)
            self._monitor_word_count = len(entries)

    def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        return self._send_parsed("MBR", self._decode_monitor_bits_response)

    def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        return self._send_parsed("MWR", self._decode_monitor_words_response)

    def read_comments(self, device: str) -> str:
        """Read the PLC comment text for one supported device."""

        response = self._send_decoded(self._build_read_comments_command(device), decode_comment_response)
        return self._decode_read_comments_response(response)

    def switch_bank(self, bank_no: int) -> None:
        """Switch the active Host Link bank number."""

        self._expect_ok(self._build_switch_bank_command(bank_no))

    def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str
    ) -> list[int | str]:
        """Read an expansion unit buffer range with ``URD``."""

        body, suffix = self._build_read_expansion_unit_buffer_command(unit_no, address, count, data_format)
        return self._send_parsed(
            body, lambda response: self._decode_expansion_unit_buffer_response(response, suffix, count)
        )

    def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str,
    ) -> None:
        """Write an expansion unit buffer range with ``UWR``."""

        self._expect_ok(self._build_write_expansion_unit_buffer_command(unit_no, address, values, data_format))


class AsyncHostLinkClient(HostLinkBase):
    """Asynchronous client for KEYENCE KV Host Link protocol."""

    def __init__(
        self,
        host: str,
        *,
        port: int,
        transport: str,
        timeout: float = 3.0,
        plc_profile: str,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            plc_profile=plc_profile,
        )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number")
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._udp_protocol: _HostLinkUDPProtocol | None = None
        self._lock = asyncio.Lock()
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._last_rx_frame_length = 0

    def traffic_stats(self) -> HostLinkTrafficStats:
        """Return an immutable lifetime traffic-counter snapshot."""
        return HostLinkTrafficStats(self._request_count, self._tx_bytes, self._rx_bytes)

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
        self._monitor_bit_count = 0
        self._monitor_word_count = 0
        writer = self._writer
        self._writer = None
        self._reader = None
        udp_transport = self._udp_transport
        udp_protocol = self._udp_protocol
        self._udp_transport = None
        self._udp_protocol = None

        if udp_protocol is not None:
            udp_protocol.cancel_pending_response()
        if udp_transport is not None:
            udp_transport.close()
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def send_raw(self, body: str) -> bytes:
        """Send one maintainer raw command and return undecoded response body bytes."""

        async with self._lock:
            response = await self._exchange(self._build_command(body))
            return response.rstrip(b"\r\n")

    async def _send_decoded(self, body: str, decoder: Callable[[bytes], str] = decode_response) -> str:
        async with self._lock:
            return await self._send_decoded_unlocked(body, decoder)

    async def _send_decoded_unlocked(self, body: str, decoder: Callable[[bytes], str] = decode_response) -> str:
        response = await self._exchange(self._build_command(body))
        try:
            return self._process_response(response, decoder=decoder)
        except HostLinkProtocolError:
            await self._close_unlocked()
            raise

    async def _send_parsed(self, body: str, parser: Callable[[str], T]) -> T:
        async with self._lock:
            response = await self._send_decoded_unlocked(body)
            try:
                return parser(response)
            except HostLinkProtocolError:
                await self._close_unlocked()
                raise

    async def _expect_ok(self, body: str) -> None:
        async with self._lock:
            await self._expect_ok_unlocked(body)

    async def _expect_ok_unlocked(self, body: str) -> None:
        response = await self._send_decoded_unlocked(body)
        if response != "OK":
            await self._close_unlocked()
            raise HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")

    async def _exchange(self, payload: bytes) -> bytes:
        # Note: This is called within self._lock in send_raw
        if self._reader is None and self._udp_transport is None:
            raise HostLinkConnectionError("Client is not connected; call connect() before sending a command")

        exchange_complete = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        try:
            if self.transport == "tcp":
                if self._writer is None:
                    raise HostLinkConnectionError("Not connected")
                if self._reader is None:
                    raise HostLinkConnectionError("Not connected")
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                self._writer.write(payload)
                await asyncio.wait_for(
                    self._writer.drain(),
                    timeout=_remaining_timeout(deadline, clock=loop.time),
                )
                self._request_count += 1
                self._tx_bytes += len(payload)
                response = await asyncio.wait_for(
                    self._recv_tcp_line(),
                    timeout=_remaining_timeout(deadline, clock=loop.time),
                )
                self._rx_bytes += self._last_rx_frame_length
                exchange_complete = True
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
                self._request_count += 1
                self._tx_bytes += len(payload)
                response = await asyncio.wait_for(
                    self._udp_protocol.wait_response(),
                    timeout=_remaining_timeout(deadline, clock=loop.time),
                )
                self._validate_response_cap(response)
                if not response or response[-1] not in (10, 13):
                    raise HostLinkProtocolError("UDP response is missing the required CR/LF terminator")
                self._rx_bytes += len(response)
                exchange_complete = True
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise HostLinkConnectionError("Timeout while waiting response from PLC") from exc
        except HostLinkConnectionError:
            raise
        except OSError as exc:
            raise HostLinkConnectionError("Socket communication failed") from exc
        finally:
            if not exchange_complete:
                # This also runs for CancelledError, which intentionally is
                # not translated into a library exception.
                await self._close_unlocked()

    async def _recv_tcp_line(self) -> bytes:
        if self._reader is None:
            raise HostLinkConnectionError("Not connected")
        line = bytearray()
        while True:
            byte = await self._reader.read(1)
            if not byte:
                message = (
                    "Connection closed by PLC before the response terminator" if line else "Connection closed by PLC"
                )
                raise HostLinkConnectionError(message)
            if byte[0] in (10, 13):
                if line:
                    self._last_rx_frame_length = len(line) + 1
                    return bytes(line)
                # Discard CR/LF left by the previous response, including a
                # terminator split across TCP reads.
                continue
            line.extend(byte)
            if len(line) > ABSOLUTE_RESPONSE_CAP:
                await self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {ABSOLUTE_RESPONSE_CAP} bytes")

    # --- Async Commands ---

    async def change_mode(self, mode: int | str) -> None:
        """Change the PLC operating mode through the Host Link ``M`` command."""

        await self._expect_ok(self._build_change_mode_command(mode))

    async def clear_error(self) -> None:
        """Clear the current PLC error through the Host Link ``ER`` command."""

        await self._expect_ok(self._build_clear_error_command())

    async def check_error_no(self) -> str:
        """Read the current PLC error number as raw response text."""

        return await self._send_decoded(self._build_check_error_no_command())

    async def query_model(self) -> ModelInfo:
        """Query the PLC model code and mapped model name."""

        return await self._send_parsed(self._build_query_model_command(), self._decode_query_model_response)

    async def confirm_operating_mode(self) -> int:
        """Return the current PLC operating mode code."""

        return await self._send_parsed(
            self._build_confirm_operating_mode_command(), self._decode_confirm_operating_mode_response
        )

    async def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int]) -> None:
        """Set the PLC clock from an explicit value."""

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
        return await self._send_parsed(
            body,
            lambda response: self._decode_read_response(
                response, suffix, self._read_response_token_count(device, suffix)
            ),
        )

    async def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        """Read consecutive devices with the Host Link ``RDS`` command."""

        body, suffix = self._build_read_consecutive_command("RDS", device, count, data_format)
        return await self._send_parsed(body, lambda response: self._decode_data_response(response, suffix, count))

    async def read_consecutive_legacy(
        self, device: str, count: int, *, data_format: str | None = None
    ) -> list[int | str]:
        """Read consecutive devices with the legacy Host Link ``RDE`` command."""

        body, suffix = self._build_read_consecutive_command("RDE", device, count, data_format)
        return await self._send_parsed(body, lambda response: self._decode_data_response(response, suffix, count))

    async def write(self, device: str, value: int | str, *, data_format: str | None = None) -> None:
        """Write one device with the Host Link ``WR`` command."""

        await self._expect_ok(self._build_write_command(device, value, data_format))

    async def write_bit_in_word(self, device: str, bit_index: int, value: bool) -> None:
        """Atomically set or clear one bit in a word for this client.

        The client request lock is held across the read-modify-write pair, so
        concurrent calls on the same client cannot overwrite each other's
        updates. The PLC may still be updated by another connection between
        the two Host Link commands.
        """

        if type(bit_index) is not int or not 0 <= bit_index <= 15:
            raise ValueError(f"bit_index must be 0-15, got {bit_index}")
        if not isinstance(value, bool):
            raise TypeError("value must be bool")

        read_body, suffix = self._build_read_command(device, ".U")
        async with self._lock:
            response = await self._send_decoded_unlocked(read_body)
            try:
                result = self._decode_read_response(response, suffix)
                values = result if isinstance(result, list) else [result]
                if len(values) != 1 or type(values[0]) is not int or not 0 <= values[0] <= 0xFFFF:
                    raise HostLinkProtocolError(f"Bit-in-word read for {device!r} did not return one unsigned word")
            except HostLinkProtocolError:
                await self._close_unlocked()
                raise
            current = values[0]
            if value:
                current |= 1 << bit_index
            else:
                current &= ~(1 << bit_index)

            write_body = self._build_write_command(device, current, ".U")
            write_response = await self._send_decoded_unlocked(write_body)
            if write_response != "OK":
                await self._close_unlocked()
                raise HostLinkProtocolError(f"Expected 'OK' but received {write_response!r} for command {write_body!r}")

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

        body = self._build_register_monitor_bits_command(devices)
        count = len(self._flatten_devices(devices))
        async with self._lock:
            await self._expect_ok_unlocked(body)
            self._monitor_bit_count = count

    async def register_monitor_words(self, entries: Sequence[str | tuple[str, str]]) -> None:
        """Register word devices for later monitor reads."""

        body = self._build_register_monitor_words_command(entries)
        async with self._lock:
            await self._expect_ok_unlocked(body)
            self._monitor_word_count = len(entries)

    async def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        return await self._send_parsed("MBR", self._decode_monitor_bits_response)

    async def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        return await self._send_parsed("MWR", self._decode_monitor_words_response)

    async def read_comments(self, device: str) -> str:
        """Read the PLC comment text for one supported device."""

        response = await self._send_decoded(self._build_read_comments_command(device), decode_comment_response)
        return self._decode_read_comments_response(response)

    async def switch_bank(self, bank_no: int) -> None:
        """Switch the active Host Link bank number."""

        await self._expect_ok(self._build_switch_bank_command(bank_no))

    async def read_expansion_unit_buffer(
        self, unit_no: int, address: int, count: int, *, data_format: str
    ) -> list[int | str]:
        """Read an expansion unit buffer range with ``URD``."""

        body, suffix = self._build_read_expansion_unit_buffer_command(unit_no, address, count, data_format)
        return await self._send_parsed(
            body, lambda response: self._decode_expansion_unit_buffer_response(response, suffix, count)
        )

    async def write_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        values: Sequence[int | str],
        *,
        data_format: str,
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
            self._future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if self._future and not self._future.done():
            self._future.set_exception(exc)

    def prepare_response(self) -> None:
        self.cancel_pending_response()
        self._future = asyncio.get_running_loop().create_future()

    async def wait_response(self) -> bytes:
        if self._future is None:
            raise HostLinkConnectionError("Not connected")
        return await self._future

    def cancel_pending_response(self) -> None:
        """Cancel and forget any response waiter owned by this endpoint."""

        if self._future is not None and not self._future.done():
            self._future.cancel()
        self._future = None
