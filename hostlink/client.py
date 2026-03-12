"""High-level Host Link client (TCP/UDP) with full command coverage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import socket
from typing import Iterable, Sequence

from .device import DeviceAddress, normalize_suffix, parse_device, parse_device_text, validate_range
from .errors import HostLinkConnectionError, HostLinkProtocolError
from .protocol import (
    build_frame,
    decode_response,
    ensure_success,
    parse_data_tokens,
    split_data_tokens,
)


MODEL_CODES = {
    "63": "KV-X550",
    "61": "KV-X530",
    "60": "KV-X520",
    "62": "KV-X500",
    "59": "KV-X310",
    "57": "KV-8000",
    "58": "KV-8000A",
    "54": "KV-7300",
    "55": "KV-7500",
}


@dataclass
class ModelInfo:
    code: str
    model: str | None


class HostLinkClient:
    """Client for KEYENCE KV Host Link protocol."""

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
    ) -> None:
        self.host = host
        self.port = port
        self.transport = transport.lower()
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.append_lf_on_send = append_lf_on_send
        self._sock: socket.socket | None = None
        self._rx_buffer = b""

        if self.transport not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        if auto_connect:
            self.connect()

    def __enter__(self) -> "HostLinkClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock_type = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
        sock = socket.socket(socket.AF_INET, sock_type)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
        except OSError as exc:
            sock.close()
            raise HostLinkConnectionError(f"Failed to connect to {self.host}:{self.port}") from exc
        self._sock = sock
        self._rx_buffer = b""

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._rx_buffer = b""

    def send_raw(self, body: str) -> str:
        response = self._exchange(build_frame(body, append_lf=self.append_lf_on_send))
        return ensure_success(decode_response(response))

    # --- Basic commands -------------------------------------------------

    def change_mode(self, mode: int | str) -> None:
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
        self._expect_ok(f"M{mode_no}")

    def clear_error(self) -> None:
        self._expect_ok("ER")

    def check_error_no(self) -> str:
        return self.send_raw("?E")

    def query_model(self) -> ModelInfo:
        code = self.send_raw("?K")
        return ModelInfo(code=code, model=MODEL_CODES.get(code))

    def confirm_operating_mode(self) -> int:
        return int(self.send_raw("?M"))

    def set_time(self, value: datetime | tuple[int, int, int, int, int, int, int] | None = None) -> None:
        if value is None:
            now = datetime.now()
            year = now.year % 100
            month = now.month
            day = now.day
            hour = now.hour
            minute = now.minute
            second = now.second
            # Python weekday(): Monday=0..Sunday=6 -> Host Link: Sunday=0
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

        self._expect_ok(
            "WRT "
            + " ".join(
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
        )

    # --- Forced set/reset ----------------------------------------------

    def forced_set(self, device: str) -> None:
        self._expect_ok(f"ST {self._device_token(device, drop_suffix=True)}")

    def forced_reset(self, device: str) -> None:
        self._expect_ok(f"RS {self._device_token(device, drop_suffix=True)}")

    def forced_set_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        self._expect_ok(f"STS {self._device_token(device, drop_suffix=True)} {count}")

    def forced_reset_consecutive(self, device: str, count: int) -> None:
        validate_range("count", count, 1, 16)
        self._expect_ok(f"RSS {self._device_token(device, drop_suffix=True)} {count}")

    # --- Read/write -----------------------------------------------------

    def read(self, device: str, *, data_format: str | None = None) -> int | str | list[int | str]:
        token, suffix = self._device_with_format(device, data_format)
        response = self.send_raw(f"RD {token}")
        values = parse_data_tokens(split_data_tokens(response), data_format=suffix)
        if len(values) == 1:
            return values[0]
        return values

    def read_consecutive(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        validate_range("count", count, 1, 1000)
        token, suffix = self._device_with_format(device, data_format)
        response = self.send_raw(f"RDS {token} {count}")
        return parse_data_tokens(split_data_tokens(response), data_format=suffix)

    def read_consecutive_legacy(self, device: str, count: int, *, data_format: str | None = None) -> list[int | str]:
        validate_range("count", count, 1, 1000)
        token, suffix = self._device_with_format(device, data_format)
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
        token, suffix = self._device_with_format(device, data_format)
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
        token, suffix = self._device_with_format(device, data_format)
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
        token = self._ensure_timer_or_counter(device, data_format)
        suffix = parse_device(token).suffix
        payload = " ".join(self._format_value(v, suffix) for v in values)
        self._expect_ok(f"WSS {token} {len(values)} {payload}")

    # --- Monitor --------------------------------------------------------

    def register_monitor_bits(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens = [self._device_token(d, drop_suffix=True) for d in targets]
        self._expect_ok("MBS " + " ".join(tokens))

    def register_monitor_words(self, *devices: str) -> None:
        targets = self._flatten_devices(devices)
        if not targets:
            raise HostLinkProtocolError("At least one device is required")
        if len(targets) > 120:
            raise HostLinkProtocolError("Maximum 120 devices can be registered")
        tokens = [self._device_token(d) for d in targets]
        self._expect_ok("MWS " + " ".join(tokens))

    def read_monitor_bits(self) -> list[int | str]:
        response = self.send_raw("MBR")
        return parse_data_tokens(split_data_tokens(response))

    def read_monitor_words(self) -> list[str]:
        response = self.send_raw("MWR")
        return split_data_tokens(response)

    # --- Others ---------------------------------------------------------

    def read_comments(self, device: str, *, strip_padding: bool = True) -> str:
        token = self._device_token(device, drop_suffix=True)
        response = self.send_raw(f"RDC {token}")
        return response.rstrip(" ") if strip_padding else response

    def switch_bank(self, bank_no: int) -> None:
        validate_range("bank_no", bank_no, 0, 15)
        self._expect_ok(f"BE {bank_no}")

    def read_expansion_unit_buffer(
        self,
        unit_no: int,
        address: int,
        count: int,
        *,
        data_format: str = "",
    ) -> list[int | str]:
        validate_range("unit_no", unit_no, 0, 48)
        validate_range("address", address, 0, 59999)
        validate_range("count", count, 1, 1000)
        suffix = normalize_suffix(data_format)
        parts = ["URD", f"{unit_no:02d}", str(address)]
        if suffix:
            parts.append(suffix)
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
        validate_range("count", len(values), 1, 1000)
        suffix = normalize_suffix(data_format)
        payload = " ".join(self._format_value(v, suffix) for v in values)
        parts = ["UWR", f"{unit_no:02d}", str(address)]
        if suffix:
            parts.append(suffix)
        parts.append(str(len(values)))
        parts.append(payload)
        self._expect_ok(" ".join(parts))

    # --- Internal helpers ----------------------------------------------

    def _expect_ok(self, body: str) -> None:
        response = self.send_raw(body)
        if response != "OK":
            raise HostLinkProtocolError(f"Expected 'OK' but received {response!r} for command {body!r}")

    def _device_token(self, device: str, *, drop_suffix: bool = False) -> str:
        addr = parse_device(device)
        if drop_suffix and addr.suffix:
            addr = DeviceAddress(addr.device_type, addr.number, "")
        return addr.to_text()

    def _device_with_format(self, device: str, data_format: str | None) -> tuple[str, str]:
        addr = parse_device(device)
        suffix = normalize_suffix(data_format) if data_format is not None else addr.suffix
        addr = DeviceAddress(addr.device_type, addr.number, suffix)
        return addr.to_text(), suffix

    def _ensure_timer_or_counter(self, device: str, data_format: str | None) -> str:
        token = parse_device_text(device, default_suffix=data_format or "")
        device_type = parse_device(token).device_type
        if device_type not in {"T", "TC", "TS", "C", "CC", "CS"}:
            raise HostLinkProtocolError("WS/WSS supports timer/counter devices only (T/C family)")
        return token

    @staticmethod
    def _flatten_devices(devices: Iterable[str] | tuple[Iterable[str], ...]) -> list[str]:
        if len(devices) == 1 and isinstance(next(iter(devices)), (list, tuple)):
            return list(next(iter(devices)))
        return list(devices)  # type: ignore[arg-type]

    @staticmethod
    def _format_value(value: int | str, data_format: str) -> str:
        if isinstance(value, int):
            if data_format == ".H":
                return format(value & 0xFFFF, "X")
            return str(value)
        return str(value).strip()

    def _exchange(self, payload: bytes) -> bytes:
        self.connect()
        assert self._sock is not None

        try:
            self._sock.sendall(payload)
            if self.transport == "udp":
                return self._sock.recv(self.buffer_size)
            return self._recv_tcp_line()
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

