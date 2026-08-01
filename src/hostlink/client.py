"""High-level Host Link client (TCP/UDP) with full command coverage."""

from __future__ import annotations

import asyncio
import math
import select
import socket
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from ipaddress import ip_address
from typing import Any, NoReturn, TypeVar, cast

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
from .errors import (
    HostLinkBaseError,
    HostLinkCancelledError,
    HostLinkClosedError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkFailureReason,
    HostLinkNotConnectedError,
    HostLinkOutcomeUnknownError,
    HostLinkProtocolError,
    HostLinkTimeoutError,
    HostLinkTransportError,
)
from .protocol import (
    HostLinkCommentEncoding,
    build_frame,
    decode_comment_response,
    decode_response,
    ensure_success,
    extract_comment_payload,
    parse_data_tokens,
    require_comment_encoding,
    split_data_tokens,
)

ABSOLUTE_RESPONSE_CAP = 65_536
UDP_RECEIVE_BUFFER_SIZE = ABSOLUTE_RESPONSE_CAP + 2
ABSOLUTE_REQUEST_BODY_CAP = 65_536
ABSOLUTE_REQUEST_FRAME_CAP = ABSOLUTE_REQUEST_BODY_CAP + 1
_ASYNC_TIMEOUT_ERRORS = (TimeoutError, asyncio.TimeoutError)

_READ_ONLY_COMMANDS = frozenset({"?E", "?K", "?M", "RD", "RDS", "RDE", "RDC", "MBR", "MWR", "URD"})


@dataclass
class _SyncAdmissionWaiter:
    generation: int
    event: threading.Event
    error: HostLinkClosedError | None = None


class _SyncFifoAdmission:
    """Fair, reentrant, close-invalidatable admission for one sync client."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._queue: deque[_SyncAdmissionWaiter] = deque()
        self._active = False
        self._generation = 0
        self._local = threading.local()

    def __enter__(self) -> _SyncFifoAdmission:
        depth = getattr(self._local, "depth", 0)
        if depth:
            self._local.depth = depth + 1
            return self
        waiter = _SyncAdmissionWaiter(self._generation, threading.Event())
        with self._guard:
            waiter.generation = self._generation
            if not self._active and not self._queue:
                self._active = True
                waiter.event.set()
            else:
                self._queue.append(waiter)
        waiter.event.wait()
        if waiter.error is not None:
            raise waiter.error
        self._local.depth = 1
        self._local.generation = waiter.generation
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth > 1:
            self._local.depth = depth - 1
            return
        self._local.depth = 0
        with self._guard:
            self._active = False
            if self._queue:
                waiter = self._queue.popleft()
                self._active = True
                waiter.event.set()

    def invalidate(self) -> None:
        """Retire the generation and reject every currently queued waiter."""

        with self._guard:
            self._generation += 1
            while self._queue:
                waiter = self._queue.popleft()
                waiter.error = HostLinkClosedError("Client closed before the queued operation was sent")
                waiter.event.set()

    def active_was_invalidated(self) -> bool:
        generation = getattr(self._local, "generation", self._generation)
        with self._guard:
            return generation != self._generation

    def adopt_if_current(self, action: Callable[[], None]) -> None:
        """Apply one final state adoption atomically with generation validation."""

        generation = getattr(self._local, "generation", self._generation)
        with self._guard:
            if generation != self._generation:
                raise HostLinkClosedError("Client closed before the connection was adopted")
            action()

    def stats(self, request_count: int, tx_bytes: int, rx_bytes: int) -> HostLinkTrafficStats:
        with self._guard:
            return HostLinkTrafficStats(request_count, tx_bytes, rx_bytes)


@dataclass
class _AsyncAdmissionWaiter:
    task: asyncio.Task[object]
    generation: int
    future: asyncio.Future[None]


class _AsyncFifoAdmission:
    """Arrival-ordered, reentrant async admission with waiting cancellation."""

    def __init__(self) -> None:
        self._queue: deque[_AsyncAdmissionWaiter] = deque()
        self._owner: asyncio.Task[object] | None = None
        self._owner_generation = 0
        self._depth = 0
        self._generation = 0

    async def __aenter__(self) -> _AsyncFifoAdmission:
        task = cast(asyncio.Task[object], asyncio.current_task())
        if task is None:
            raise RuntimeError("Host Link operation requires an asyncio task")
        if self._owner is task:
            self._depth += 1
            return self
        loop = asyncio.get_running_loop()
        waiter = _AsyncAdmissionWaiter(task, self._generation, loop.create_future())
        if self._owner is None and not self._queue:
            self._owner = task
            self._owner_generation = self._generation
            self._depth = 1
            waiter.future.set_result(None)
        else:
            self._queue.append(waiter)
        try:
            await asyncio.shield(waiter.future)
        except asyncio.CancelledError as exc:
            if waiter in self._queue:
                self._queue.remove(waiter)
            elif self._owner is task:
                self._release_owner(task)
            raise HostLinkCancelledError("Queued Host Link operation was cancelled before send") from exc
        if self._owner is not task:
            # Generation invalidation completes queued futures with a typed error.
            await waiter.future
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        task = cast(asyncio.Task[object], asyncio.current_task())
        if task is not None:
            self._release_owner(task)

    def _release_owner(self, task: asyncio.Task[object]) -> None:
        if self._owner is not task:
            return
        if self._depth > 1:
            self._depth -= 1
            return
        self._owner = None
        self._depth = 0
        if self._queue:
            waiter = self._queue.popleft()
            self._owner = waiter.task
            self._owner_generation = waiter.generation
            self._depth = 1
            if not waiter.future.done():
                waiter.future.set_result(None)

    def invalidate(self) -> None:
        self._generation += 1
        while self._queue:
            waiter = self._queue.popleft()
            if not waiter.future.done():
                waiter.future.set_exception(HostLinkClosedError("Client closed before the queued operation was sent"))

    def active_was_invalidated(self) -> bool:
        return self._owner is not None and self._owner_generation != self._generation


def _remaining_timeout(deadline: float, *, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _validated_timeout(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def _absolute_deadline(name: str, value: float, *, clock: Callable[[], float]) -> float:
    timeout = _validated_timeout(name, value)
    if timeout > threading.TIMEOUT_MAX:
        raise ValueError(f"{name} cannot be represented by the platform wait APIs")
    deadline = clock() + timeout
    if not math.isfinite(deadline):
        raise ValueError(f"{name} cannot be represented as a monotonic deadline")
    return deadline


def _normalize_ipv4_host(host: object, *, name: str = "host") -> str:
    if not isinstance(host, str):
        raise ValueError(f"{name} must be a string")
    normalized = host.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    literal_text = normalized[1:-1] if normalized.startswith("[") and normalized.endswith("]") else normalized
    try:
        literal = ip_address(literal_text)
    except ValueError:
        return normalized
    if literal.version != 4:
        raise ValueError(f"{name} must be an IPv4 address or a hostname that resolves to IPv4")
    return literal_text


def _resolve_first_ipv4_endpoint(host: str, port: int, socket_type: int) -> tuple[str, int]:
    try:
        literal = ip_address(host)
    except ValueError:
        endpoints = socket.getaddrinfo(host, port, socket.AF_INET, socket_type)
        for family, resolved_type, _protocol, _canonical_name, sockaddr in endpoints:
            if family != socket.AF_INET or resolved_type != socket_type:
                continue
            address, resolved_port = sockaddr[0], sockaddr[1]
            if isinstance(address, str) and isinstance(resolved_port, int):
                return address, resolved_port
        raise socket.gaierror(f"host did not resolve to an IPv4 address: {host}") from None
    if literal.version != 4:
        raise socket.gaierror(f"host did not resolve to an IPv4 address: {host}")
    return str(literal), port


class _SyncConnectState:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.abandoned = False
        self.done = False
        self.completed_at: float | None = None
        self.sock: socket.socket | None = None
        self.error: BaseException | None = None


def _close_socket_quietly(sock: socket.socket) -> None:
    try:
        sock.close()
    except Exception:
        pass


def _open_sync_ipv4_socket_before_deadline(
    *,
    host: str,
    port: int,
    transport: str,
    deadline: float,
    ensure_current: Callable[[], None],
) -> socket.socket:
    """Resolve, create, connect, and configure without adopting a late result."""

    state = _SyncConnectState()
    socket_type = socket.SOCK_STREAM if transport == "tcp" else socket.SOCK_DGRAM

    def worker() -> None:
        candidate: socket.socket | None = None

        def was_abandoned() -> bool:
            with state.condition:
                return state.abandoned

        try:
            endpoint = _resolve_first_ipv4_endpoint(host, port, socket_type)
            if was_abandoned():
                return
            _remaining_timeout(deadline, clock=time.monotonic)
            candidate = socket.socket(socket.AF_INET, socket_type)
            if was_abandoned():
                return
            candidate.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            candidate.connect(endpoint)
            if was_abandoned():
                return
            _remaining_timeout(deadline, clock=time.monotonic)
            if transport == "tcp":
                candidate.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if was_abandoned():
                    return
                _remaining_timeout(deadline, clock=time.monotonic)
                candidate.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if was_abandoned():
                    return
                _remaining_timeout(deadline, clock=time.monotonic)
            completed_at = time.monotonic()
            with state.condition:
                if not state.abandoned:
                    state.sock = candidate
                    state.completed_at = completed_at
                    state.done = True
                    candidate = None
                    state.condition.notify_all()
        except BaseException as exc:
            completed_at = time.monotonic()
            with state.condition:
                if not state.abandoned:
                    state.error = exc
                    state.completed_at = completed_at
                    state.done = True
                    state.condition.notify_all()
        finally:
            if candidate is not None:
                _close_socket_quietly(candidate)

    threading.Thread(target=worker, name="hostlink-ipv4-connect", daemon=True).start()

    with state.condition:
        while not state.done:
            try:
                ensure_current()
            except BaseException:
                state.abandoned = True
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                state.abandoned = True
                raise TimeoutError
            state.condition.wait(timeout=min(remaining, 0.01))

        try:
            ensure_current()
        except BaseException:
            state.abandoned = True
            late_socket = state.sock
            state.sock = None
            if late_socket is not None:
                _close_socket_quietly(late_socket)
            raise

        if state.error is not None:
            if state.completed_at is not None and state.completed_at >= deadline:
                raise TimeoutError from state.error
            raise state.error

        connected = state.sock
        state.sock = None
        if connected is None:
            raise HostLinkTransportError("Connection worker did not produce a socket")
        if time.monotonic() >= deadline:
            _close_socket_quietly(connected)
            raise TimeoutError
        return connected


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
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port is required and must be an integer in the range 1..65535")
        if not isinstance(transport, str) or transport.strip().lower() not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.host = _normalize_ipv4_host(host)
        self.port = port
        self.transport = transport.strip().lower()
        self._maintainer_trace_hook: Callable[[HostLinkTraceFrame], None] | None = None
        self.plc_profile = _normalize_connection_plc_profile(plc_profile)
        self._monitor_bit_count = 0
        self._monitor_word_formats: tuple[str, ...] = ()

    def _fire_trace(self, direction: HostLinkTraceDirection, data: bytes) -> None:
        if self._maintainer_trace_hook:
            try:
                self._maintainer_trace_hook(HostLinkTraceFrame(direction, data, datetime.now(timezone.utc)))
            except Exception:
                # Maintainer diagnostics must not change command success, ordering, or retry behavior.
                pass

    # --- Internal helpers ----------------------------------------------

    def _build_command(self, body: str) -> bytes:
        frame = build_frame(body)
        if len(frame) > ABSOLUTE_REQUEST_FRAME_CAP:
            raise HostLinkProtocolError(f"Request body exceeds {ABSOLUTE_REQUEST_BODY_CAP} bytes")
        return frame

    def _process_response(self, response: bytes, *, decoder: Callable[[bytes], str] = decode_response) -> str:
        return ensure_success(decoder(response))

    @staticmethod
    def _process_comment_payload(response: bytes) -> bytes:
        payload = extract_comment_payload(response)
        if len(payload) == 2 and payload[0] == ord("E") and ord("0") <= payload[1] <= ord("9"):
            ensure_success(payload.decode("ascii"))
        return payload

    @staticmethod
    def _validate_response_cap(
        response: bytes,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
    ) -> bytes:
        if type(maximum_response_body) is not int or not 0 <= maximum_response_body <= ABSOLUTE_RESPONSE_CAP:
            raise HostLinkProtocolError("maximum response body is outside the protocol capacity")
        body = response.rstrip(b"\r\n")
        if len(body) > maximum_response_body:
            raise HostLinkProtocolError(f"Response line exceeds {maximum_response_body} bytes")
        return response

    @staticmethod
    def _raw_command_is_state_changing(payload: bytes) -> bool:
        command = payload[:-1].split(maxsplit=1)[0].decode("ascii", errors="ignore").upper()
        return command not in _READ_ONLY_COMMANDS

    @staticmethod
    def _outcome_reason(error: BaseException) -> HostLinkFailureReason:
        if isinstance(error, HostLinkTimeoutError):
            return HostLinkFailureReason.TIMEOUT
        if isinstance(error, (HostLinkCancelledError, asyncio.CancelledError)):
            return HostLinkFailureReason.CANCELLED
        if isinstance(error, HostLinkClosedError):
            return HostLinkFailureReason.CLOSED
        if isinstance(error, HostLinkProtocolError):
            return HostLinkFailureReason.MALFORMED_RESPONSE
        return HostLinkFailureReason.TRANSPORT

    @staticmethod
    def _raise_outcome_unknown(error: HostLinkBaseError | HostLinkCancelledError) -> NoReturn:
        raise HostLinkOutcomeUnknownError(HostLinkBase._outcome_reason(error), error) from error

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
    def _decode_read_response(
        response: str,
        data_format: str,
        expected_count: int = 1,
        *,
        timer_counter_composite: bool = False,
        direct_bit_response: bool = False,
    ) -> int | str | list[int | str]:
        tokens = split_data_tokens(response)
        if len(tokens) != expected_count:
            raise HostLinkProtocolError(
                f"Read response token count mismatch: expected {expected_count}, received {len(tokens)}"
            )
        if direct_bit_response:
            values = parse_data_tokens(tokens)
        elif timer_counter_composite:
            if tokens[0] not in {"0", "1"}:
                raise HostLinkProtocolError(
                    f"Timer/counter response status {tokens[0]!r} is invalid; expected 0 or 1"
                )
            status = int(tokens[0])
            values = [status, *parse_data_tokens(tokens[1:], data_format=data_format)]
        else:
            values = parse_data_tokens(tokens, data_format=data_format)
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
    ) -> tuple[str, tuple[str, ...]]:
        targets = list(entries)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens: list[str] = []
        formats: list[str] = []
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
            tok, suffix = self._device_with_format(device, data_format)
            tokens.append(tok)
            formats.append(suffix)
        return "MWS " + " ".join(tokens), tuple(formats)

    def _decode_monitor_bits_response(self, response: str) -> list[int | str]:
        return self._decode_data_response(response, expected_count=self._monitor_bit_count)

    def _decode_monitor_words_response(self, response: str) -> list[str]:
        values = split_data_tokens(response)
        if len(values) != len(self._monitor_word_formats):
            raise HostLinkProtocolError(
                "Monitor response token count mismatch: "
                f"expected {len(self._monitor_word_formats)}, received {len(values)}"
            )
        validated: list[str] = []
        for token, data_format in zip(values, self._monitor_word_formats, strict=True):
            parsed = parse_data_tokens([token], data_format=data_format)[0]
            validated.append(parsed if isinstance(parsed, str) else token)
        return validated

    def _build_change_mode_command(self, mode: int | str) -> str:
        if isinstance(mode, str):
            upper = mode.strip().upper()
            if upper == "PROGRAM":
                mode_no = 0
            elif upper == "RUN":
                mode_no = 1
            else:
                raise ValueError(f"Unsupported mode: {mode!r}")
        else:
            if type(mode) is not int:
                raise ValueError("mode must be integer 0/1 or string PROGRAM/RUN")
            mode_no = mode
        if mode_no not in {0, 1}:
            raise ValueError("mode must be 0/1 or PROGRAM/RUN")
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
        if response not in {"0", "1"}:
            raise HostLinkProtocolError(f"Unsupported PLC mode response: {response!r}")
        return 0 if response == "0" else 1

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
                raise ValueError(
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
                raise ValueError("time value contains a nonexistent calendar date") from exc
            expected_week = (calendar.weekday() + 1) % 7
            if week != expected_week:
                raise ValueError(f"week {week} does not match the calendar date (expected {expected_week})")

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
        connect_timeout: float = 3.0,
        plc_profile: str,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            plc_profile=plc_profile,
        )
        self.timeout = _validated_timeout("timeout", timeout)
        self.connect_timeout = _validated_timeout("connect_timeout", connect_timeout)
        self._sock: socket.socket | None = None
        self._udp_previous_sock: socket.socket | None = None
        self._udp_remote_endpoint: tuple[str, int] | None = None
        self._udp_logically_connected = False
        self._rx_buffer = b""
        self._lock = _SyncFifoAdmission()
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._last_rx_frame_length = 0
        self._last_exchange_deadline: float | None = None

    def traffic_stats(self) -> HostLinkTrafficStats:
        """Return an immutable lifetime traffic-counter snapshot."""
        return self._lock.stats(self._request_count, self._tx_bytes, self._rx_bytes)

    def _check_decode_deadline(self, *, state_changing: bool) -> None:
        if self._last_exchange_deadline is None or time.monotonic() <= self._last_exchange_deadline:
            return
        self._close_unlocked()
        error = HostLinkTimeoutError("Timeout: transaction deadline expired during response decoding")
        if state_changing:
            self._raise_outcome_unknown(error)
        raise error

    def __enter__(self) -> HostLinkClient:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def connect(self) -> None:
        """Open the configured TCP or UDP socket if it is not already open."""

        with self._lock:
            if self._sock is not None or (self.transport == "udp" and self._udp_logically_connected):
                return
            deadline = _absolute_deadline("connect_timeout", self.connect_timeout, clock=time.monotonic)

            def ensure_current() -> None:
                if self._lock.active_was_invalidated():
                    raise HostLinkClosedError("Client closed while connecting")

            sock: socket.socket | None = None
            try:
                connected = _open_sync_ipv4_socket_before_deadline(
                    host=self.host,
                    port=self.port,
                    transport=self.transport,
                    deadline=deadline,
                    ensure_current=ensure_current,
                )
                sock = connected

                def adopt() -> None:
                    _remaining_timeout(deadline, clock=time.monotonic)
                    self._sock = connected
                    self._rx_buffer = b""
                    if self.transport == "udp":
                        getpeername = getattr(connected, "getpeername", None)
                        peer = getpeername() if callable(getpeername) else (self.host, self.port)
                        self._udp_remote_endpoint = (str(peer[0]), int(peer[1]))
                        self._udp_logically_connected = True

                self._lock.adopt_if_current(adopt)
            except TimeoutError as exc:
                if sock is not None:
                    _close_socket_quietly(sock)
                raise HostLinkTimeoutError(f"Connect deadline expired for {self.host}:{self.port}") from exc
            except HostLinkClosedError:
                if sock is not None:
                    _close_socket_quietly(sock)
                raise
            except OSError as exc:
                if sock is not None:
                    _close_socket_quietly(sock)
                raise HostLinkTransportError(f"Failed to connect to {self.host}:{self.port}") from exc

    def close(self) -> None:
        """Immediately retire the active generation and reject queued work."""

        self._lock.invalidate()
        self._close_unlocked()

    def _close_unlocked(self) -> None:
        self._monitor_bit_count = 0
        self._monitor_word_formats = ()
        sock = self._sock
        previous_udp_sock = self._udp_previous_sock
        self._sock = None
        self._udp_previous_sock = None
        self._udp_remote_endpoint = None
        self._udp_logically_connected = False
        self._rx_buffer = b""
        for owned_sock in (sock, previous_udp_sock):
            if owned_sock is None:
                continue
            try:
                owned_sock.shutdown(socket.SHUT_RDWR)
            except (AttributeError, OSError):
                pass
            owned_sock.close()

    def _prepare_udp_request_socket(self, *, deadline: float) -> socket.socket:
        if self._sock is not None:
            return self._sock
        if not self._udp_logically_connected or self._udp_remote_endpoint is None:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")

        previous = self._udp_previous_sock
        candidate = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            candidate.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            candidate.connect(self._udp_remote_endpoint)
            if previous is not None and candidate.getsockname() == previous.getsockname():
                raise HostLinkTransportError("UDP request socket reused the predecessor local endpoint")

            def adopt() -> None:
                self._sock = candidate
                self._udp_previous_sock = None

            self._lock.adopt_if_current(adopt)
        except BaseException:
            _close_socket_quietly(candidate)
            raise

        if previous is not None:
            _close_socket_quietly(previous)
        return candidate

    def _retain_successful_udp_socket(self, sock: socket.socket) -> None:
        def retain() -> None:
            self._sock = None
            self._udp_previous_sock = sock

        self._lock.adopt_if_current(retain)

    def _reject_unowned_tcp_input(self, sock: socket.socket) -> None:
        self._rx_buffer = self._rx_buffer.lstrip(b"\r\n")
        if self._rx_buffer:
            self._close_unlocked()
            raise HostLinkProtocolError("Received an extra non-empty TCP response before the next request")
        if not isinstance(sock, socket.socket):
            return
        while True:
            readable, _, _ = select.select([sock], [], [], 0)
            if not readable:
                return
            pending = sock.recv(8192, socket.MSG_PEEK)
            if not pending:
                raise HostLinkTransportError("Connection closed by PLC")
            separator_count = len(pending) - len(pending.lstrip(b"\r\n"))
            if separator_count != len(pending):
                self._close_unlocked()
                raise HostLinkProtocolError("Received an extra non-empty TCP response before the next request")
            sock.recv(separator_count)

    def send_raw(self, body: str) -> bytes:
        """Send one maintainer raw command and return undecoded response body bytes."""

        with self._lock:
            payload = self._build_command(body)
            response = self._exchange(
                payload,
                state_changing=self._raw_command_is_state_changing(payload),
            )
            result = response.rstrip(b"\r\n")
            self._check_decode_deadline(state_changing=self._raw_command_is_state_changing(payload))
            return result

    def _send_decoded(
        self,
        body: str,
        decoder: Callable[[bytes], str] = decode_response,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
    ) -> str:
        with self._lock:
            return self._send_decoded_unlocked(
                body,
                decoder,
                maximum_response_body=maximum_response_body,
            )

    def _send_decoded_unlocked(
        self,
        body: str,
        decoder: Callable[[bytes], str] = decode_response,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
        state_changing: bool = False,
    ) -> str:
        response = self._exchange(
            self._build_command(body),
            maximum_response_body=maximum_response_body,
            state_changing=state_changing,
        )
        try:
            result = self._process_response(response, decoder=decoder)
            self._check_decode_deadline(state_changing=state_changing)
            return result
        except HostLinkProtocolError as exc:
            self._check_decode_deadline(state_changing=state_changing)
            self._close_unlocked()
            if state_changing:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkError:
            self._check_decode_deadline(state_changing=state_changing)
            raise

    def _send_comment_payload(
        self,
        body: str,
        parser: Callable[[bytes], T],
    ) -> T:
        with self._lock:
            response = self._exchange(self._build_command(body), state_changing=False)
            try:
                result = parser(self._process_comment_payload(response))
                self._check_decode_deadline(state_changing=False)
                return result
            except HostLinkProtocolError:
                self._check_decode_deadline(state_changing=False)
                self._close_unlocked()
                raise
            except HostLinkError:
                self._check_decode_deadline(state_changing=False)
                raise

    def _send_parsed(
        self,
        body: str,
        parser: Callable[[str], T],
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
    ) -> T:
        with self._lock:
            response = self._send_decoded_unlocked(body, maximum_response_body=maximum_response_body)
            try:
                result = parser(response)
                self._check_decode_deadline(state_changing=False)
                return result
            except HostLinkProtocolError:
                self._check_decode_deadline(state_changing=False)
                self._close_unlocked()
                raise

    def _expect_ok(self, body: str) -> None:
        with self._lock:
            self._expect_ok_unlocked(body)

    def _expect_ok_unlocked(self, body: str) -> None:
        response = self._send_decoded_unlocked(body, maximum_response_body=2, state_changing=True)
        if response != "OK":
            self._close_unlocked()
            error = HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")
            self._raise_outcome_unknown(error)

    def _exchange(
        self,
        payload: bytes,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
        state_changing: bool,
    ) -> bytes:
        # Note: This is called within self._lock in send_raw
        sock = self._sock
        if self.transport == "udp" and not self._udp_logically_connected and sock is None:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
        if self.transport == "tcp" and sock is None:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
        if not 0 <= maximum_response_body <= ABSOLUTE_RESPONSE_CAP:
            raise HostLinkProtocolError("maximum response body is outside the protocol capacity")

        exchange_complete = False
        may_have_sent = False
        try:
            self._fire_trace(HostLinkTraceDirection.SEND, payload)
            timeout = _validated_timeout("timeout", self.timeout)
            deadline = time.monotonic() + timeout
            self._last_exchange_deadline = deadline
            if self.transport == "udp":
                sock = self._prepare_udp_request_socket(deadline=deadline)
            if sock is None:
                raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
            if self.transport == "tcp":
                self._reject_unowned_tcp_input(sock)
            sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            may_have_sent = True
            sock.sendall(payload)
            self._request_count += 1
            self._tx_bytes += len(payload)
            if self.transport == "udp":
                sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
                response = sock.recv(UDP_RECEIVE_BUFFER_SIZE)
                self._validate_response_cap(response, maximum_response_body)
                if not response or response[-1] not in (10, 13):
                    raise HostLinkProtocolError("UDP response is missing the required CR/LF terminator")
                self._rx_bytes += len(response)
            else:
                response = self._recv_tcp_line(
                    deadline=deadline,
                    maximum_response_body=maximum_response_body,
                    sock=sock,
                )
                self._rx_bytes += self._last_rx_frame_length
            if self._lock.active_was_invalidated():
                raise HostLinkClosedError("Client closed before the response was accepted")
            if self.transport == "udp":
                self._retain_successful_udp_socket(sock)
            exchange_complete = True
            self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
            return response
        except TimeoutError as exc:
            timeout_error = HostLinkTimeoutError("Timeout: transaction deadline expired")
            if state_changing and may_have_sent:
                timeout_error.__cause__ = exc
                self._raise_outcome_unknown(timeout_error)
            raise timeout_error from exc
        except HostLinkProtocolError as exc:
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkClosedError as exc:
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkConnectionError as exc:
            connection_error: HostLinkConnectionError = (
                HostLinkClosedError("Client closed during the active operation")
                if self._lock.active_was_invalidated()
                else exc
            )
            if connection_error is not exc:
                connection_error.__cause__ = exc
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(connection_error)
            if connection_error is exc:
                raise
            raise connection_error from exc
        except OSError as exc:
            transport_error: HostLinkConnectionError = (
                HostLinkClosedError("Client closed during the active operation")
                if self._lock.active_was_invalidated()
                else HostLinkTransportError("Socket communication failed")
            )
            if state_changing and may_have_sent:
                transport_error.__cause__ = exc
                self._raise_outcome_unknown(transport_error)
            raise transport_error from exc
        finally:
            if not exchange_complete:
                # Host Link responses do not carry a transaction ID. Discard
                # the whole transport so a late response cannot satisfy the
                # next request, including when the transport is UDP.
                self._close_unlocked()

    def _recv_tcp_line(
        self,
        *,
        deadline: float | None = None,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
        sock: socket.socket | None = None,
    ) -> bytes:
        sock = self._sock if sock is None else sock
        if sock is None:
            raise HostLinkNotConnectedError("Not connected")
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
                if idx > maximum_response_body:
                    self._close_unlocked()
                    raise HostLinkProtocolError(f"Response line exceeds {maximum_response_body} bytes")
                line = self._rx_buffer[:idx]
                skip = idx
                while skip < len(self._rx_buffer) and self._rx_buffer[skip] in (10, 13):
                    skip += 1
                self._rx_buffer = self._rx_buffer[skip:]
                if self._rx_buffer:
                    self._close_unlocked()
                    raise HostLinkProtocolError("Received more than one non-empty TCP response for one request")
                # A TCP response line ends at the first CR/LF.  Consume any
                # adjacent separator padding, but do not let TCP chunking
                # change the traffic counter.
                self._last_rx_frame_length = idx + 1
                return line

            sock.settimeout(_remaining_timeout(deadline, clock=time.monotonic))
            chunk = sock.recv(8192)
            if not chunk:
                message = (
                    "Connection closed by PLC before the response terminator"
                    if self._rx_buffer
                    else "Connection closed by PLC"
                )
                raise HostLinkTransportError(message)
            self._rx_buffer += chunk
            if (
                len(self._rx_buffer) > maximum_response_body
                and b"\r" not in self._rx_buffer
                and b"\n" not in self._rx_buffer
            ):
                self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {maximum_response_body} bytes")

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
        device_type = parse_device(device).device_type
        return self._send_parsed(
            body,
            lambda response: self._decode_read_response(
                response,
                suffix,
                self._read_response_token_count(device, suffix),
                timer_counter_composite=device_type in {"T", "C"},
                direct_bit_response=device_type in DIRECT_BIT_DEVICE_TYPES,
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

        body, formats = self._build_register_monitor_words_command(entries)
        with self._lock:
            self._expect_ok_unlocked(body)
            self._monitor_word_formats = formats

    def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        return self._send_parsed("MBR", self._decode_monitor_bits_response)

    def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        return self._send_parsed("MWR", self._decode_monitor_words_response)

    def read_comment_bytes(self, device: str) -> bytes:
        """Read exact PLC comment payload bytes without CR/LF framing."""

        return self._send_comment_payload(self._build_read_comments_command(device), lambda payload: payload)

    def read_comments(self, device: str, encoding: HostLinkCommentEncoding) -> str:
        """Read PLC comment text using exactly the selected encoding."""

        selected = require_comment_encoding(encoding)
        return self._send_comment_payload(
            self._build_read_comments_command(device),
            lambda payload: decode_comment_response(payload, selected),
        )

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
        connect_timeout: float = 3.0,
        plc_profile: str,
    ) -> None:
        super().__init__(
            host,
            port,
            transport,
            plc_profile=plc_profile,
        )
        self.timeout = _validated_timeout("timeout", timeout)
        self.connect_timeout = _validated_timeout("connect_timeout", connect_timeout)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._udp_transport: asyncio.DatagramTransport | None = None
        self._udp_protocol: _HostLinkUDPProtocol | None = None
        self._udp_previous_transport: asyncio.DatagramTransport | None = None
        self._udp_previous_protocol: _HostLinkUDPProtocol | None = None
        self._udp_remote_endpoint: tuple[str, int] | None = None
        self._udp_logically_connected = False
        self._rx_buffer = b""
        self._lock = _AsyncFifoAdmission()
        self._request_count = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._last_rx_frame_length = 0
        self._last_exchange_deadline: float | None = None

    def traffic_stats(self) -> HostLinkTrafficStats:
        """Return an immutable lifetime traffic-counter snapshot."""
        return HostLinkTrafficStats(self._request_count, self._tx_bytes, self._rx_bytes)

    def _exclusive_turn(self) -> _AsyncFifoAdmission:
        """Return the reentrant admission used by one logical aggregate read."""

        return self._lock

    async def _check_decode_deadline(self, *, state_changing: bool) -> None:
        if self._last_exchange_deadline is None or asyncio.get_running_loop().time() <= self._last_exchange_deadline:
            return
        await self._close_unlocked()
        error = HostLinkTimeoutError("Timeout: transaction deadline expired during response decoding")
        if state_changing:
            self._raise_outcome_unknown(error)
        raise error

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
        if self._reader is not None or (self.transport == "udp" and self._udp_logically_connected):
            return

        if self.transport == "tcp":
            candidate_writer: asyncio.StreamWriter | None = None
            candidate_disposed = False
            connection_attempt = asyncio.ensure_future(
                asyncio.open_connection(self.host, self.port, family=socket.AF_INET)
            )

            async def dispose_writer(writer: asyncio.StreamWriter) -> None:
                nonlocal candidate_disposed
                if candidate_disposed:
                    return
                candidate_disposed = True
                writer.close()
                wait_closed = getattr(writer, "wait_closed", None)
                if callable(wait_closed):
                    await wait_closed()

            async def dispose_connection_attempt() -> None:
                connection_attempt.cancel()
                try:
                    _, late_writer = await connection_attempt
                except BaseException:
                    return
                await dispose_writer(late_writer)

            try:
                candidate_reader, candidate_writer = await asyncio.wait_for(
                    asyncio.shield(connection_attempt),
                    timeout=self.connect_timeout,
                )
                assert candidate_writer is not None
                if self._lock.active_was_invalidated():
                    await dispose_writer(candidate_writer)
                    raise HostLinkClosedError("Client closed while connecting")
                self._reader = candidate_reader
                self._writer = candidate_writer
                self._rx_buffer = b""
            except asyncio.TimeoutError as exc:
                await dispose_connection_attempt()
                raise HostLinkTimeoutError(f"Connect deadline expired for {self.host}:{self.port}") from exc
            except asyncio.CancelledError as exc:
                await dispose_connection_attempt()
                raise HostLinkCancelledError(f"Connect cancelled for {self.host}:{self.port}") from exc
            except HostLinkClosedError:
                raise
            except OSError as exc:
                raise HostLinkTransportError(f"Failed to connect to {self.host}:{self.port}") from exc
        else:
            loop = asyncio.get_running_loop()
            protocol = _HostLinkUDPProtocol()
            candidate_transport: asyncio.DatagramTransport | None = None
            endpoint_attempt = asyncio.ensure_future(
                loop.create_datagram_endpoint(
                    lambda: protocol,
                    remote_addr=(self.host, self.port),
                    family=socket.AF_INET,
                )
            )

            async def dispose_endpoint_attempt() -> None:
                endpoint_attempt.cancel()
                try:
                    late_transport, _ = await endpoint_attempt
                except BaseException:
                    return
                late_transport.close()

            try:
                candidate_transport, _ = await asyncio.wait_for(
                    asyncio.shield(endpoint_attempt),
                    timeout=self.connect_timeout,
                )
                assert candidate_transport is not None
                if self._lock.active_was_invalidated():
                    candidate_transport.close()
                    raise HostLinkClosedError("Client closed while connecting")
                peer = candidate_transport.get_extra_info("peername")
                if not isinstance(peer, tuple) or len(peer) < 2:
                    candidate_transport.close()
                    raise HostLinkTransportError("UDP endpoint did not expose its connected peer")
                self._udp_transport = candidate_transport
                self._udp_protocol = protocol
                self._udp_remote_endpoint = (str(peer[0]), int(peer[1]))
                self._udp_logically_connected = True
            except asyncio.TimeoutError as exc:
                await dispose_endpoint_attempt()
                raise HostLinkTimeoutError(f"Connect deadline expired for {self.host}:{self.port}") from exc
            except asyncio.CancelledError as exc:
                await dispose_endpoint_attempt()
                raise HostLinkCancelledError(f"Connect cancelled for {self.host}:{self.port}") from exc
            except HostLinkClosedError:
                raise
            except OSError as exc:
                raise HostLinkTransportError(f"Failed to setup UDP endpoint for {self.host}:{self.port}") from exc

    async def close(self) -> None:
        """Immediately retire the active generation and reject queued work."""

        self._lock.invalidate()
        await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        self._monitor_bit_count = 0
        self._monitor_word_formats = ()
        writer = self._writer
        self._writer = None
        self._reader = None
        self._rx_buffer = b""
        udp_transport = self._udp_transport
        udp_protocol = self._udp_protocol
        previous_udp_transport = self._udp_previous_transport
        previous_udp_protocol = self._udp_previous_protocol
        self._udp_transport = None
        self._udp_protocol = None
        self._udp_previous_transport = None
        self._udp_previous_protocol = None
        self._udp_remote_endpoint = None
        self._udp_logically_connected = False

        if udp_protocol is not None:
            udp_protocol.cancel_pending_response()
        if previous_udp_protocol is not None:
            previous_udp_protocol.cancel_pending_response()
        if udp_transport is not None:
            udp_transport.close()
        if previous_udp_transport is not None:
            previous_udp_transport.close()
        if writer is not None:
            writer.close()

    async def _prepare_udp_request_endpoint(
        self, *, deadline: float
    ) -> tuple[asyncio.DatagramTransport, _HostLinkUDPProtocol]:
        if not self._udp_logically_connected or self._udp_remote_endpoint is None:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
        if self._udp_transport is not None and self._udp_protocol is not None:
            return self._udp_transport, self._udp_protocol

        loop = asyncio.get_running_loop()
        protocol = _HostLinkUDPProtocol()
        candidate: asyncio.DatagramTransport | None = None
        try:
            candidate, _ = await asyncio.wait_for(
                loop.create_datagram_endpoint(
                    lambda: protocol,
                    remote_addr=self._udp_remote_endpoint,
                    family=socket.AF_INET,
                ),
                timeout=_remaining_timeout(deadline, clock=loop.time),
            )
            assert candidate is not None
            if self._lock.active_was_invalidated():
                raise HostLinkClosedError("Client closed while preparing the UDP request socket")
            previous_transport = self._udp_previous_transport
            previous_protocol = self._udp_previous_protocol
            if previous_transport is not None and candidate.get_extra_info(
                "sockname"
            ) == previous_transport.get_extra_info("sockname"):
                raise HostLinkTransportError("UDP request socket reused the predecessor local endpoint")
            self._udp_transport = candidate
            self._udp_protocol = protocol
            self._udp_previous_transport = None
            self._udp_previous_protocol = None
        except BaseException:
            if candidate is not None:
                candidate.close()
            raise

        if previous_protocol is not None:
            previous_protocol.cancel_pending_response()
        if previous_transport is not None:
            previous_transport.close()
        return candidate, protocol

    def _retain_successful_udp_endpoint(
        self,
        transport: asyncio.DatagramTransport,
        protocol: _HostLinkUDPProtocol,
    ) -> None:
        if self._lock.active_was_invalidated():
            raise HostLinkClosedError("Client closed before the UDP response was accepted")
        protocol.cancel_pending_response()
        self._udp_transport = None
        self._udp_protocol = None
        self._udp_previous_transport = transport
        self._udp_previous_protocol = protocol

    async def _reject_unowned_tcp_input(self) -> None:
        self._rx_buffer = self._rx_buffer.lstrip(b"\r\n")
        if self._reader is not None:
            internal_buffer = getattr(self._reader, "_buffer", None)
            if isinstance(internal_buffer, bytearray) and internal_buffer:
                self._rx_buffer += bytes(internal_buffer)
                internal_buffer.clear()
                self._rx_buffer = self._rx_buffer.lstrip(b"\r\n")
        if self._rx_buffer:
            await self._close_unlocked()
            raise HostLinkProtocolError("Received an extra non-empty TCP response before the next request")

    async def send_raw(self, body: str) -> bytes:
        """Send one maintainer raw command and return undecoded response body bytes."""

        async with self._lock:
            payload = self._build_command(body)
            response = await self._exchange(
                payload,
                state_changing=self._raw_command_is_state_changing(payload),
            )
            result = response.rstrip(b"\r\n")
            await self._check_decode_deadline(state_changing=self._raw_command_is_state_changing(payload))
            return result

    async def _send_decoded(
        self,
        body: str,
        decoder: Callable[[bytes], str] = decode_response,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
    ) -> str:
        async with self._lock:
            return await self._send_decoded_unlocked(
                body,
                decoder,
                maximum_response_body=maximum_response_body,
            )

    async def _send_decoded_unlocked(
        self,
        body: str,
        decoder: Callable[[bytes], str] = decode_response,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
        state_changing: bool = False,
    ) -> str:
        response = await self._exchange(
            self._build_command(body),
            maximum_response_body=maximum_response_body,
            state_changing=state_changing,
        )
        try:
            result = self._process_response(response, decoder=decoder)
            await self._check_decode_deadline(state_changing=state_changing)
            return result
        except HostLinkProtocolError as exc:
            await self._check_decode_deadline(state_changing=state_changing)
            await self._close_unlocked()
            if state_changing:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkError:
            await self._check_decode_deadline(state_changing=state_changing)
            raise

    async def _send_comment_payload(
        self,
        body: str,
        parser: Callable[[bytes], T],
    ) -> T:
        async with self._lock:
            response = await self._exchange(self._build_command(body), state_changing=False)
            try:
                result = parser(self._process_comment_payload(response))
                await self._check_decode_deadline(state_changing=False)
                return result
            except HostLinkProtocolError:
                await self._check_decode_deadline(state_changing=False)
                await self._close_unlocked()
                raise
            except HostLinkError:
                await self._check_decode_deadline(state_changing=False)
                raise

    async def _send_parsed(
        self,
        body: str,
        parser: Callable[[str], T],
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
    ) -> T:
        async with self._lock:
            response = await self._send_decoded_unlocked(body, maximum_response_body=maximum_response_body)
            try:
                result = parser(response)
                await self._check_decode_deadline(state_changing=False)
                return result
            except HostLinkProtocolError:
                await self._check_decode_deadline(state_changing=False)
                await self._close_unlocked()
                raise

    async def _expect_ok(self, body: str) -> None:
        async with self._lock:
            await self._expect_ok_unlocked(body)

    async def _expect_ok_unlocked(self, body: str) -> None:
        response = await self._send_decoded_unlocked(body, maximum_response_body=2, state_changing=True)
        if response != "OK":
            await self._close_unlocked()
            error = HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")
            self._raise_outcome_unknown(error)

    async def _exchange(
        self,
        payload: bytes,
        *,
        maximum_response_body: int = ABSOLUTE_RESPONSE_CAP,
        state_changing: bool,
    ) -> bytes:
        # Note: This is called within self._lock in send_raw
        if self.transport == "tcp" and self._reader is None:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
        if self.transport == "udp" and not self._udp_logically_connected:
            raise HostLinkNotConnectedError("Client is not connected; call connect() before sending a command")
        if not 0 <= maximum_response_body <= ABSOLUTE_RESPONSE_CAP:
            raise HostLinkProtocolError("maximum response body is outside the protocol capacity")

        exchange_complete = False
        loop = asyncio.get_running_loop()
        may_have_sent = False
        try:
            if self.transport == "tcp":
                if self._writer is None:
                    raise HostLinkNotConnectedError("Not connected")
                if self._reader is None:
                    raise HostLinkNotConnectedError("Not connected")
                await self._reject_unowned_tcp_input()
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                timeout = _validated_timeout("timeout", self.timeout)
                deadline = loop.time() + timeout
                self._last_exchange_deadline = deadline
                may_have_sent = True
                self._writer.write(payload)
                remaining = _remaining_timeout(deadline, clock=loop.time)
                await asyncio.wait_for(self._writer.drain(), timeout=remaining)
                self._request_count += 1
                self._tx_bytes += len(payload)
                remaining = _remaining_timeout(deadline, clock=loop.time)
                response = await asyncio.wait_for(
                    self._recv_tcp_line(maximum_response_body=maximum_response_body), timeout=remaining
                )
                self._rx_bytes += self._last_rx_frame_length
                if self._lock.active_was_invalidated():
                    raise HostLinkClosedError("Client closed before the response was accepted")
                exchange_complete = True
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
            else:
                timeout = _validated_timeout("timeout", self.timeout)
                deadline = loop.time() + timeout
                self._last_exchange_deadline = deadline
                udp_transport, udp_protocol = await self._prepare_udp_request_endpoint(deadline=deadline)
                self._fire_trace(HostLinkTraceDirection.SEND, payload)
                udp_protocol.prepare_response()
                may_have_sent = True
                udp_transport.sendto(payload)
                self._request_count += 1
                self._tx_bytes += len(payload)
                remaining = _remaining_timeout(deadline, clock=loop.time)
                response = await asyncio.wait_for(udp_protocol.wait_response(), timeout=remaining)
                self._validate_response_cap(response, maximum_response_body)
                if not response or response[-1] not in (10, 13):
                    raise HostLinkProtocolError("UDP response is missing the required CR/LF terminator")
                self._rx_bytes += len(response)
                if self._lock.active_was_invalidated():
                    raise HostLinkClosedError("Client closed before the response was accepted")
                self._retain_successful_udp_endpoint(udp_transport, udp_protocol)
                exchange_complete = True
                self._fire_trace(HostLinkTraceDirection.RECEIVE, response)
                return response
        except _ASYNC_TIMEOUT_ERRORS as exc:
            timeout_error = HostLinkTimeoutError("Timeout: transaction deadline expired")
            if state_changing and may_have_sent:
                timeout_error.__cause__ = exc
                self._raise_outcome_unknown(timeout_error)
            raise timeout_error from exc
        except asyncio.CancelledError as exc:
            cancelled_error: HostLinkConnectionError | HostLinkCancelledError
            cancelled_error = (
                HostLinkClosedError("Client closed during the active operation")
                if self._lock.active_was_invalidated()
                else HostLinkCancelledError("Active Host Link operation was cancelled")
            )
            if state_changing and may_have_sent:
                cancelled_error.__cause__ = exc
                self._raise_outcome_unknown(cancelled_error)
            raise cancelled_error from exc
        except HostLinkProtocolError as exc:
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkClosedError as exc:
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(exc)
            raise
        except HostLinkConnectionError as exc:
            connection_error: HostLinkConnectionError = (
                HostLinkClosedError("Client closed during the active operation")
                if self._lock.active_was_invalidated()
                else exc
            )
            if connection_error is not exc:
                connection_error.__cause__ = exc
            if state_changing and may_have_sent:
                self._raise_outcome_unknown(connection_error)
            if connection_error is exc:
                raise
            raise connection_error from exc
        except OSError as exc:
            transport_error: HostLinkConnectionError = (
                HostLinkClosedError("Client closed during the active operation")
                if self._lock.active_was_invalidated()
                else HostLinkTransportError("Socket communication failed")
            )
            if state_changing and may_have_sent:
                transport_error.__cause__ = exc
                self._raise_outcome_unknown(transport_error)
            raise transport_error from exc
        finally:
            if not exchange_complete:
                # This also runs for CancelledError, which intentionally is
                # not translated into a library exception.
                await self._close_unlocked()

    async def _recv_tcp_line(self, *, maximum_response_body: int = ABSOLUTE_RESPONSE_CAP) -> bytes:
        if self._reader is None:
            raise HostLinkNotConnectedError("Not connected")
        while True:
            self._rx_buffer = self._rx_buffer.lstrip(b"\r\n")
            idx_cr = self._rx_buffer.find(b"\r")
            idx_lf = self._rx_buffer.find(b"\n")
            indexes = [index for index in (idx_cr, idx_lf) if index >= 0]
            if indexes:
                index = min(indexes)
                if index > maximum_response_body:
                    await self._close_unlocked()
                    raise HostLinkProtocolError(f"Response line exceeds {maximum_response_body} bytes")
                line = self._rx_buffer[:index]
                skip = index
                while skip < len(self._rx_buffer) and self._rx_buffer[skip] in (10, 13):
                    skip += 1
                self._rx_buffer = self._rx_buffer[skip:]
                if self._rx_buffer:
                    await self._close_unlocked()
                    raise HostLinkProtocolError("Received more than one non-empty TCP response for one request")
                self._last_rx_frame_length = len(line) + 1
                return line

            chunk = await self._reader.read(8192)
            if not chunk:
                message = (
                    "Connection closed by PLC before the response terminator"
                    if self._rx_buffer
                    else "Connection closed by PLC"
                )
                raise HostLinkTransportError(message)
            self._rx_buffer += chunk
            if (
                len(self._rx_buffer) > maximum_response_body
                and b"\r" not in self._rx_buffer
                and b"\n" not in self._rx_buffer
            ):
                await self._close_unlocked()
                raise HostLinkProtocolError(f"Response line exceeds {maximum_response_body} bytes")

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
        device_type = parse_device(device).device_type
        return await self._send_parsed(
            body,
            lambda response: self._decode_read_response(
                response,
                suffix,
                self._read_response_token_count(device, suffix),
                timer_counter_composite=device_type in {"T", "C"},
                direct_bit_response=device_type in DIRECT_BIT_DEVICE_TYPES,
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

        body, formats = self._build_register_monitor_words_command(entries)
        async with self._lock:
            await self._expect_ok_unlocked(body)
            self._monitor_word_formats = formats

    async def read_monitor_bits(self) -> list[int | str]:
        """Read the currently registered bit monitor values."""

        return await self._send_parsed("MBR", self._decode_monitor_bits_response)

    async def read_monitor_words(self) -> list[str]:
        """Read the currently registered word monitor values."""

        return await self._send_parsed("MWR", self._decode_monitor_words_response)

    async def read_comment_bytes(self, device: str) -> bytes:
        """Read exact PLC comment payload bytes without CR/LF framing."""

        return await self._send_comment_payload(self._build_read_comments_command(device), lambda payload: payload)

    async def read_comments(self, device: str, encoding: HostLinkCommentEncoding) -> str:
        """Read PLC comment text using exactly the selected encoding."""

        selected = require_comment_encoding(encoding)
        return await self._send_comment_payload(
            self._build_read_comments_command(device),
            lambda payload: decode_comment_response(payload, selected),
        )

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
            raise HostLinkNotConnectedError("UDP endpoint is not connected or has no pending request")
        return await self._future

    def cancel_pending_response(self) -> None:
        """Cancel and forget any response waiter owned by this endpoint."""

        if self._future is not None and not self._future.done():
            self._future.cancel()
        self._future = None
