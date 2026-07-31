from __future__ import annotations

import inspect
import math
from unittest.mock import patch

import pytest

import hostlink
from hostlink import (
    AsyncHostLinkClient,
    HostLinkClient,
    HostLinkConnectionOptions,
    poll,
    read_dwords_single_request,
    read_words_single_request,
    write_dwords_single_request,
    write_typed,
    write_words_single_request,
)
from hostlink.client import ABSOLUTE_RESPONSE_CAP, HostLinkTraceFrame
from hostlink.errors import HostLinkConnectionError, HostLinkProtocolError
from hostlink.protocol import parse_scalar_token


class _RecordingClient(HostLinkClient):
    def __init__(self, responses: list[bytes] | None = None) -> None:
        super().__init__(
            "127.0.0.1",
            port=8501,
            transport="tcp",
            plc_profile="keyence:kv-8000",
        )
        self.frames: list[bytes] = []
        self.responses = list(responses or [])

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.frames.append(payload)
        return self.responses.pop(0) if self.responses else b"OK\r"


class _AsyncRecordingClient(AsyncHostLinkClient):
    def __init__(self, responses: list[bytes] | None = None) -> None:
        super().__init__(
            "127.0.0.1",
            port=8501,
            transport="tcp",
            plc_profile="keyence:kv-8000",
        )
        self.frames: list[bytes] = []
        self.responses = list(responses or [])

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.frames.append(payload)
        return self.responses.pop(0) if self.responses else b"OK\r"


class _FakeSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    def recv(self, _size: int) -> bytes:
        return self.chunks.pop(0)

    def sendall(self, _payload: bytes) -> None:
        return None

    def settimeout(self, _timeout: float) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _client_parameters(client_type: type[object]) -> set[str]:
    return set(inspect.signature(client_type).parameters)


def test_endpoint_fields_are_required_and_invalid_values_are_rejected() -> None:
    with pytest.raises(TypeError):
        HostLinkClient("127.0.0.1", plc_profile="keyence:kv-8000")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        HostLinkConnectionOptions("127.0.0.1", plc_profile="keyence:kv-8000")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="plc_profile is required"):
        HostLinkClient(
            "127.0.0.1",
            port=8501,
            transport="tcp",
            plc_profile=None,  # type: ignore[arg-type]
        )

    invalid = (
        {"host": "", "port": 8501, "transport": "tcp", "timeout": 3.0},
        {"host": "127.0.0.1", "port": 0, "transport": "tcp", "timeout": 3.0},
        {"host": "127.0.0.1", "port": 65536, "transport": "tcp", "timeout": 3.0},
        {"host": "127.0.0.1", "port": 8501, "transport": "", "timeout": 3.0},
        {"host": "127.0.0.1", "port": 8501, "transport": None, "timeout": 3.0},
        {"host": "127.0.0.1", "port": 8501, "transport": "serial", "timeout": 3.0},
        {"host": "127.0.0.1", "port": 8501, "transport": "tcp", "timeout": 0.0},
        {"host": "127.0.0.1", "port": 8501, "transport": "tcp", "timeout": float("inf")},
    )
    for values in invalid:
        with pytest.raises(ValueError):
            HostLinkClient(**values, plc_profile="keyence:kv-8000")  # type: ignore[arg-type]


def test_timeout_defaults_to_three_seconds_and_preserves_valid_explicit_value() -> None:
    common = {
        "host": "127.0.0.1",
        "port": 8501,
        "transport": "tcp",
        "plc_profile": "keyence:kv-8000",
    }
    assert HostLinkClient(**common).timeout == 3.0  # type: ignore[arg-type]
    assert AsyncHostLinkClient(**common).timeout == 3.0  # type: ignore[arg-type]
    assert HostLinkConnectionOptions(**common).timeout == 3.0  # type: ignore[arg-type]
    assert HostLinkClient(**common).connect_timeout == 3.0  # type: ignore[arg-type]
    assert AsyncHostLinkClient(**common).connect_timeout == 3.0  # type: ignore[arg-type]
    assert HostLinkConnectionOptions(**common).connect_timeout == 3.0  # type: ignore[arg-type]
    assert HostLinkClient(**common, timeout=1.25).timeout == 1.25  # type: ignore[arg-type]
    assert HostLinkClient(**common, connect_timeout=1.5).connect_timeout == 1.5  # type: ignore[arg-type]
    for invalid in (True, 0, -1, float("inf"), float("nan"), "1"):
        with pytest.raises(ValueError, match="connect_timeout"):
            HostLinkConnectionOptions(**common, connect_timeout=invalid)  # type: ignore[arg-type]


def test_constructor_and_unconnected_command_do_not_create_a_socket() -> None:
    with patch("hostlink.client.socket.socket") as socket_factory:
        client = HostLinkClient(
            "127.0.0.1",
            port=8501,
            transport="tcp",
            plc_profile="keyence:kv-8000",
        )
        socket_factory.assert_not_called()
        with pytest.raises(HostLinkConnectionError, match="call connect"):
            client.send_raw("?K")
        socket_factory.assert_not_called()


@pytest.mark.asyncio
async def test_async_constructor_and_unconnected_command_do_not_open_transport() -> None:
    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    assert client._writer is None
    assert client._udp_transport is None
    with pytest.raises(HostLinkConnectionError, match="call connect"):
        await client.send_raw("?K")
    assert client._writer is None
    assert client._udp_transport is None


def test_raw_command_preserves_error_and_non_ascii_response_bytes() -> None:
    client = _RecordingClient([b"E1\r", b"\xff\x80\r\n"])
    assert client.send_raw("FIRST") == b"E1"
    assert client.send_raw("SECOND") == b"\xff\x80"


def test_maintainer_trace_is_opt_in_ordered_and_cannot_change_command_result() -> None:
    observed: list[tuple[str, bytes]] = []

    def trace(frame: HostLinkTraceFrame) -> None:
        observed.append((frame.direction.value, frame.data))

    client = HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    client._maintainer_trace_hook = trace
    client._sock = _FakeSocket([b"OK\r"])  # type: ignore[assignment]
    assert client.send_raw("RD DM0.U") == b"OK"
    assert observed == [("send", b"RD DM0.U\r"), ("receive", b"OK")]

    def broken_trace(_frame: object) -> None:
        raise RuntimeError("diagnostic failure")

    client = HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    client._maintainer_trace_hook = broken_trace
    client._sock = _FakeSocket([b"OK\r"])  # type: ignore[assignment]
    assert client.send_raw("RD DM0.U") == b"OK"


def test_low_level_numeric_devices_require_separate_explicit_format() -> None:
    client = _RecordingClient([b"1\r"])
    with pytest.raises(HostLinkProtocolError, match="data_format is required"):
        client.read("DM0")
    with pytest.raises(HostLinkProtocolError, match="must not contain"):
        client.read("DM0.U", data_format=".U")
    assert client.frames == []

    assert client.read("DM0", data_format=".U") == 1
    assert client.frames == [b"RD DM0.U\r"]


@pytest.mark.parametrize(
    ("data_format", "minimum", "maximum"),
    [
        (".U", 0, 0xFFFF),
        (".S", -0x8000, 0x7FFF),
        (".D", 0, 0xFFFFFFFF),
        (".L", -0x80000000, 0x7FFFFFFF),
        (".H", 0, 0xFFFF),
    ],
)
def test_write_formats_accept_boundaries_and_reject_overflow_without_masking(
    data_format: str, minimum: int, maximum: int
) -> None:
    client = _RecordingClient()
    client.write("DM0", minimum, data_format=data_format)
    client.write("DM0", maximum, data_format=data_format)
    sent_before_invalid = list(client.frames)

    for value in (minimum - 1, maximum + 1, True, 1.0, "1"):
        with pytest.raises(HostLinkProtocolError):
            client.write("DM0", value, data_format=data_format)  # type: ignore[arg-type]
    assert client.frames == sent_before_invalid


@pytest.mark.parametrize(
    ("token", "data_format"),
    [
        ("65536", ".U"),
        ("-32769", ".S"),
        ("4294967296", ".D"),
        ("-2147483649", ".L"),
        ("10000", ".H"),
        ("12x", ".U"),
    ],
)
def test_typed_response_overflow_and_malformed_tokens_are_rejected(token: str, data_format: str) -> None:
    with pytest.raises(HostLinkProtocolError):
        parse_scalar_token(token, data_format=data_format)


def test_set_time_requires_explicit_valid_calendar_and_weekday() -> None:
    client = _RecordingClient()
    with pytest.raises(TypeError):
        client.set_time()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="nonexistent"):
        client.set_time((26, 2, 30, 0, 0, 0, 1))
    with pytest.raises(ValueError, match="does not match"):
        client.set_time((26, 7, 11, 0, 0, 0, 0))
    assert client.frames == []


@pytest.mark.parametrize(
    ("data_format", "minimum", "maximum"),
    [
        (".U", 0, 0xFFFF),
        (".S", -0x8000, 0x7FFF),
        (".D", 0, 0xFFFFFFFF),
        (".L", -0x80000000, 0x7FFFFFFF),
        (".H", 0, 0xFFFF),
    ],
)
def test_expansion_buffer_requires_format_and_validates_all_format_boundaries(
    data_format: str, minimum: int, maximum: int
) -> None:
    client = _RecordingClient()
    client.write_expansion_unit_buffer(1, 0, [minimum, maximum], data_format=data_format)
    frames_before_invalid = list(client.frames)
    with pytest.raises(HostLinkProtocolError):
        client.write_expansion_unit_buffer(1, 0, [minimum - 1], data_format=data_format)
    with pytest.raises(HostLinkProtocolError):
        client.write_expansion_unit_buffer(1, 0, [maximum + 1], data_format=data_format)
    assert client.frames == frames_before_invalid


def test_expansion_buffer_missing_or_empty_format_is_rejected_before_send() -> None:
    client = _RecordingClient()
    with pytest.raises(TypeError):
        client.read_expansion_unit_buffer(1, 0, 1)  # type: ignore[call-arg]
    for data_format in ("", None):
        with pytest.raises(HostLinkProtocolError):
            client.read_expansion_unit_buffer(1, 0, 1, data_format=data_format)  # type: ignore[arg-type]
    assert client.frames == []


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (b"COMMENT\r", "COMMENT"),
        (b"A B   \r", "A B"),
        (b"COMMENT\t  \r", "COMMENT\t"),
        ("全角　".encode() + b"  \r", "全角　"),
        ("日本語".encode("shift_jis") + b"  \r", "日本語"),
        (b"   \r", ""),
    ],
)
def test_comment_trims_only_ascii_space_padding(response: bytes, expected: str) -> None:
    client = _RecordingClient([response])
    assert client.read_comments("DM0") == expected


def test_tcp_response_cap_accepts_boundary_and_rejects_one_byte_more() -> None:
    client = _RecordingClient()
    boundary_socket = _FakeSocket([b"A" * ABSOLUTE_RESPONSE_CAP + b"\r"])
    client._sock = boundary_socket  # type: ignore[assignment]
    assert client._recv_tcp_line() == b"A" * ABSOLUTE_RESPONSE_CAP
    assert not boundary_socket.closed

    overflow_socket = _FakeSocket([b"A" * (ABSOLUTE_RESPONSE_CAP + 1) + b"\r"])
    client._sock = overflow_socket  # type: ignore[assignment]
    with pytest.raises(HostLinkProtocolError, match="exceeds"):
        client._recv_tcp_line()
    assert overflow_socket.closed
    assert client._sock is None


def test_udp_response_cap_rejects_one_byte_more_and_invalidates_socket() -> None:
    client = HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="udp",
        plc_profile="keyence:kv-8000",
    )
    overflow_socket = _FakeSocket([b"A" * (ABSOLUTE_RESPONSE_CAP + 1) + b"\r"])
    client._sock = overflow_socket  # type: ignore[assignment]
    with pytest.raises(HostLinkProtocolError, match="exceeds"):
        client.send_raw("RD DM0.U")
    assert overflow_socket.closed
    assert client._sock is None


def test_removed_public_options_helpers_and_trace_types_are_absent() -> None:
    forbidden_parameters = {
        "append_lf_on_send",
        "auto_connect",
        "buffer_size",
        "trace_hook",
        "_maintainer_trace_hook",
        "_allow_manual_profile",
    }
    assert forbidden_parameters.isdisjoint(_client_parameters(HostLinkClient))
    assert forbidden_parameters.isdisjoint(_client_parameters(AsyncHostLinkClient))

    for name in (
        "read_words_chunked",
        "read_dwords_chunked",
        "write_words_chunked",
        "write_dwords_chunked",
        "HostLinkTraceDirection",
        "HostLinkTraceFrame",
        "write_bit_in_word",
    ):
        assert not hasattr(hostlink, name)


@pytest.mark.asyncio
async def test_single_request_helpers_never_split_at_or_above_protocol_limit() -> None:
    thousand_words = b" ".join([b"0"] * 1000) + b"\r"
    client = _AsyncRecordingClient([thousand_words, thousand_words, b"OK\r", b"OK\r"])

    assert len(await read_words_single_request(client, "DM0", 1000)) == 1000
    sent = len(client.frames)
    with pytest.raises(ValueError):
        await read_words_single_request(client, "DM0", 1001)
    assert len(client.frames) == sent

    assert len(await read_dwords_single_request(client, "DM0", 500)) == 500
    sent = len(client.frames)
    with pytest.raises(ValueError):
        await read_dwords_single_request(client, "DM0", 501)
    assert len(client.frames) == sent

    await write_words_single_request(client, "DM0", [0] * 1000)
    sent = len(client.frames)
    with pytest.raises(ValueError):
        await write_words_single_request(client, "DM0", [0] * 1001)
    assert len(client.frames) == sent

    await write_dwords_single_request(client, "DM0", [0] * 500)
    sent = len(client.frames)
    with pytest.raises(ValueError):
        await write_dwords_single_request(client, "DM0", [0] * 501)
    assert len(client.frames) == sent


@pytest.mark.asyncio
@pytest.mark.parametrize("device", ["Y0", "R0", "B0", "MR0", "LR0", "CR0", "VB0", "X0", "M0", "L0"])
async def test_float_write_rejects_every_direct_bit_family_without_send(device: str) -> None:
    client = _AsyncRecordingClient()
    with pytest.raises(ValueError, match="Float writes.*direct bit"):
        await write_typed(client, device, "F", 1.25)
    assert client.frames == []


@pytest.mark.parametrize("response", [b"2\r", b"01\r", b" 1\r", b"+1\r", b"1x\r", b"\r", b"RUN\r"])
def test_operating_mode_requires_exact_response_and_invalidates_connection(response: bytes) -> None:
    client = _RecordingClient([response])
    socket = _FakeSocket([])
    client._sock = socket  # type: ignore[assignment]

    with pytest.raises(HostLinkProtocolError):
        client.confirm_operating_mode()

    assert client.frames == [b"?M\r"]
    assert socket.closed
    assert client._sock is None


@pytest.mark.parametrize(("response", "expected"), [(b"0\r", 0), (b"1\r", 1)])
def test_operating_mode_accepts_only_exact_defined_values(response: bytes, expected: int) -> None:
    client = _RecordingClient([response])
    assert client.confirm_operating_mode() == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("interval", [0, -1, math.nan, math.inf, -math.inf, True, "1"])
async def test_poll_rejects_invalid_interval_before_snapshot_or_send(interval: object) -> None:
    client = _AsyncRecordingClient()
    stream = poll(client, ["DM0:U"], interval=interval)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive finite"):
        await anext(stream)
    assert client.frames == []


@pytest.mark.parametrize("invalid", [True, 1.0, "1", None])
def test_integer_only_client_arguments_require_exact_int_without_send(invalid: object) -> None:
    client = _RecordingClient()
    operations = (
        lambda: client.change_mode(invalid),
        lambda: client.forced_set_consecutive("R0", invalid),
        lambda: client.switch_bank(invalid),
        lambda: client.read_consecutive("DM0", invalid, data_format=".U"),
        lambda: client.read_expansion_unit_buffer(invalid, 0, 1, data_format=".U"),
        lambda: client.read_expansion_unit_buffer(1, invalid, 1, data_format=".U"),
        lambda: client.read_expansion_unit_buffer(1, 0, invalid, data_format=".U"),
    )
    for operation in operations:
        with pytest.raises(ValueError):
            operation()
    assert client.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [True, 1.0, "1", None])
async def test_dword_helper_count_requires_exact_int_before_multiplication(invalid: object) -> None:
    client = _AsyncRecordingClient()
    with pytest.raises(ValueError):
        await read_dwords_single_request(client, "DM0", invalid)  # type: ignore[arg-type]
    assert client.frames == []
