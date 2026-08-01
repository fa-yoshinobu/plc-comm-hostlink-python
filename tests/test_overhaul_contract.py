from __future__ import annotations

import asyncio
import inspect
import math
from unittest.mock import patch

import pytest

import hostlink
from hostlink import (
    AsyncHostLinkClient,
    HostLinkAddress,
    HostLinkCancelledError,
    HostLinkClient,
    HostLinkClosedError,
    HostLinkCommentEncoding,
    HostLinkConnectionOptions,
    HostLinkError,
    format_address,
    normalize_address,
    poll,
    read_dwords_single_request,
    read_named,
    read_typed,
    read_words_single_request,
    write_dwords_single_request,
    write_typed,
    write_words_single_request,
)
from hostlink.client import ABSOLUTE_RESPONSE_CAP, HostLinkTraceFrame
from hostlink.errors import HostLinkConnectionError, HostLinkProtocolError, HostLinkTransportError
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
        self.retired = False

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.frames.append(payload)
        return self.responses.pop(0) if self.responses else b"OK\r"

    def _close_unlocked(self) -> None:
        self.retired = True
        super()._close_unlocked()


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
        self.retired = False

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.frames.append(payload)
        return self.responses.pop(0) if self.responses else b"OK\r"

    async def _close_unlocked(self) -> None:
        self.retired = True
        await super()._close_unlocked()


class _RejectAdmission:
    async def __aenter__(self) -> None:
        raise AssertionError("invalid Float32 request reached FIFO admission")

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


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


class _FakeAsyncWriter:
    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1

    async def wait_closed(self) -> None:
        return None


class _FakeDatagramTransport:
    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1

    def get_extra_info(self, name: str) -> object:
        if name == "peername":
            return ("127.0.0.1", 8501)
        if name == "sockname":
            return ("127.0.0.1", 40000)
        return None


class _FakeUdpProtocolOwner:
    def __init__(self) -> None:
        self.cancel_count = 0

    def cancel_pending_response(self) -> None:
        self.cancel_count += 1


class _FailingUdpSocket:
    def __init__(self) -> None:
        self.close_count = 0

    def settimeout(self, _timeout: float) -> None:
        return None

    def connect(self, _endpoint: tuple[str, int]) -> None:
        raise OSError("synthetic bind/connect failure")

    def close(self) -> None:
        self.close_count += 1


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


@pytest.mark.asyncio
async def test_async_close_invalidates_and_disposes_late_tcp_connection_candidate() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    writer = _FakeAsyncWriter()

    async def blocked_open_connection(
        *_args: object, **_kwargs: object
    ) -> tuple[asyncio.StreamReader, _FakeAsyncWriter]:
        started.set()
        await release.wait()
        return asyncio.StreamReader(), writer

    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    with patch("hostlink.client.asyncio.open_connection", blocked_open_connection):
        pending = asyncio.create_task(client.connect())
        await started.wait()
        await client.close()
        release.set()
        with pytest.raises(HostLinkClosedError):
            await pending

    assert writer.close_count == 1
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_async_close_invalidates_and_disposes_late_udp_connection_candidate() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    transport = _FakeDatagramTransport()
    loop = asyncio.get_running_loop()

    async def blocked_create_datagram_endpoint(
        *_args: object, **_kwargs: object
    ) -> tuple[_FakeDatagramTransport, object]:
        started.set()
        await release.wait()
        return transport, object()

    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="udp",
        plc_profile="keyence:kv-8000",
    )
    with patch.object(loop, "create_datagram_endpoint", blocked_create_datagram_endpoint):
        pending = asyncio.create_task(client.connect())
        await started.wait()
        await client.close()
        release.set()
        with pytest.raises(HostLinkClosedError):
            await pending

    assert transport.close_count == 1
    assert client._udp_transport is None
    assert client._udp_protocol is None


@pytest.mark.asyncio
async def test_async_tcp_connect_cancellation_closes_late_candidate_once_across_repeated_close() -> None:
    started = asyncio.Event()
    writer = _FakeAsyncWriter()

    async def cancellation_resistant_open_connection(
        *_args: object, **_kwargs: object
    ) -> tuple[asyncio.StreamReader, _FakeAsyncWriter]:
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return asyncio.StreamReader(), writer

    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    with patch("hostlink.client.asyncio.open_connection", cancellation_resistant_open_connection):
        pending = asyncio.create_task(client.connect())
        await started.wait()
        pending.cancel()
        with pytest.raises(HostLinkCancelledError, match="cancelled"):
            await pending

    await client.close()
    await client.close()
    assert writer.close_count == 1
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_async_udp_connect_cancellation_closes_late_candidate_once_across_repeated_close() -> None:
    started = asyncio.Event()
    transport = _FakeDatagramTransport()
    loop = asyncio.get_running_loop()

    async def cancellation_resistant_create_datagram_endpoint(
        *_args: object, **_kwargs: object
    ) -> tuple[_FakeDatagramTransport, object]:
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return transport, object()

    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="udp",
        plc_profile="keyence:kv-8000",
    )
    with patch.object(loop, "create_datagram_endpoint", cancellation_resistant_create_datagram_endpoint):
        pending = asyncio.create_task(client.connect())
        await started.wait()
        pending.cancel()
        with pytest.raises(HostLinkCancelledError, match="cancelled"):
            await pending

    await client.close()
    await client.close()
    assert transport.close_count == 1
    assert client._udp_transport is None
    assert client._udp_protocol is None


def test_sync_udp_successor_bind_failure_closes_candidate_and_predecessor() -> None:
    client = HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="udp",
        plc_profile="keyence:kv-8000",
    )
    predecessor = _FakeDatagramTransport()
    candidate = _FailingUdpSocket()
    client._udp_logically_connected = True
    client._udp_remote_endpoint = ("127.0.0.1", 8501)
    client._udp_previous_sock = predecessor  # type: ignore[assignment]

    with patch("hostlink.client.socket.socket", return_value=candidate):
        with pytest.raises(HostLinkTransportError, match="communication failed"):
            client.send_raw("RD DM0.U")

    assert candidate.close_count == 1
    assert predecessor.close_count == 1
    assert not client._udp_logically_connected


@pytest.mark.asyncio
async def test_async_udp_successor_bind_failure_closes_predecessor_generation() -> None:
    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="udp",
        plc_profile="keyence:kv-8000",
    )
    predecessor = _FakeDatagramTransport()
    predecessor_protocol = _FakeUdpProtocolOwner()
    client._udp_logically_connected = True
    client._udp_remote_endpoint = ("127.0.0.1", 8501)
    client._udp_previous_transport = predecessor
    client._udp_previous_protocol = predecessor_protocol  # type: ignore[assignment]
    loop = asyncio.get_running_loop()

    async def fail_bind(*_args: object, **_kwargs: object) -> tuple[object, object]:
        raise OSError("synthetic bind failure")

    with patch.object(loop, "create_datagram_endpoint", fail_bind):
        with pytest.raises(HostLinkTransportError, match="communication failed"):
            await client.send_raw("RD DM0.U")

    assert predecessor.close_count == 1
    assert predecessor_protocol.cancel_count == 1
    assert not client._udp_logically_connected


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


@pytest.mark.parametrize(
    ("token", "expected"),
    [("0", "0000"), ("a", "000A"), ("ff", "00FF"), ("FFFF", "FFFF")],
)
def test_semantic_hex_response_is_always_four_uppercase_digits(token: str, expected: str) -> None:
    assert parse_scalar_token(token, data_format=".H") == expected


def test_hex_timer_counter_read_keeps_status_semantic_and_canonicalizes_values() -> None:
    client = _RecordingClient([b"1 a ff\r"])

    assert client.read("T0", data_format=".H") == [1, "000A", "00FF"]
    assert client.frames == [b"RD T0.H\r"]
    assert not client.retired


@pytest.mark.asyncio
async def test_hex_direct_bit_typed_read_packs_status_tokens_before_canonicalizing_value() -> None:
    response = " ".join(["1", "0", "1", "0"] + ["0"] * 12).encode() + b"\r"
    client = _AsyncRecordingClient([response])

    assert await read_typed(client, "R0", "H") == "0005"
    assert client.frames == [b"RD R000.H\r"]
    assert not client.retired


def test_monitor_words_validate_each_registered_format_and_preserve_nonhex_strings() -> None:
    client = _RecordingClient([b"OK\r", b"0001 -2 a 4294967295 -2147483648\r"])
    client.register_monitor_words([("DM0", ".U"), ("DM1", ".S"), ("DM2", ".H"), ("DM3", ".D"), ("DM5", ".L")])

    assert client.read_monitor_words() == ["0001", "-2", "000A", "4294967295", "-2147483648"]
    assert not client.retired


@pytest.mark.parametrize(
    ("data_format", "response"),
    [(".U", "-1"), (".S", "100000"), (".H", "NOT_HEX"), (".D", "4294967296"), (".L", "-2147483649")],
)
def test_monitor_word_format_violation_retires_transport(data_format: str, response: str) -> None:
    client = _RecordingClient([b"OK\r", f"{response}\r".encode()])
    client.register_monitor_words([("DM0", data_format)])

    with pytest.raises(HostLinkProtocolError):
        client.read_monitor_words()
    assert client.retired


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
    ("response", "encoding", "expected"),
    [
        (b"COMMENT\r", HostLinkCommentEncoding.UTF8, "COMMENT"),
        (b"A B   \r", HostLinkCommentEncoding.UTF8, "A B"),
        (b"COMMENT\t  \r", HostLinkCommentEncoding.UTF8, "COMMENT\t"),
        ("全角　".encode() + b"  \r", HostLinkCommentEncoding.UTF8, "全角　"),
        ("日本語".encode("cp932") + b"  \r", HostLinkCommentEncoding.CP932, "日本語"),
        (b"   \r", HostLinkCommentEncoding.UTF8, ""),
    ],
)
def test_comment_trims_only_ascii_space_padding(
    response: bytes,
    encoding: HostLinkCommentEncoding,
    expected: str,
) -> None:
    client = _RecordingClient([response])
    assert client.read_comments("DM0", encoding) == expected


def test_comment_encoding_is_explicit_and_never_falls_back() -> None:
    ambiguous = b"\xc2\xa2\r"
    assert _RecordingClient([ambiguous]).read_comments("DM0", HostLinkCommentEncoding.UTF8) == "¢"
    assert _RecordingClient([ambiguous]).read_comments("DM0", HostLinkCommentEncoding.CP932) == "ﾂ｢"

    client = _RecordingClient(["あ".encode("cp932") + b"\r"])
    with pytest.raises(HostLinkProtocolError, match="not valid utf-8"):
        client.read_comments("DM0", HostLinkCommentEncoding.UTF8)


@pytest.mark.parametrize(
    ("payload", "encoding"),
    [
        (b"\xe3\x81", HostLinkCommentEncoding.UTF8),
        (b"\x82", HostLinkCommentEncoding.CP932),
    ],
)
def test_comment_malformed_selected_codec_is_rejected_without_replacement(
    payload: bytes,
    encoding: HostLinkCommentEncoding,
) -> None:
    client = _RecordingClient([payload + b"\r"])
    with pytest.raises(HostLinkProtocolError, match="no fallback codec"):
        client.read_comments("DM0", encoding)


@pytest.mark.parametrize("payload", [b"\x80", b"\xa0", b"\xfd", b"\xfe", b"\xff"])
def test_cp932_rejects_nonportable_vendor_private_single_bytes(payload: bytes) -> None:
    client = _RecordingClient([payload + b"\r"])
    with pytest.raises(HostLinkProtocolError, match="not valid cp932"):
        client.read_comments("DM0", HostLinkCommentEncoding.CP932)


def test_cp932_preserves_ascii_controls_and_accepts_windows_31j_extensions() -> None:
    payload = b"\x1a\x1c\x7f\x87\x90\xed\x40\xfa\x4a"
    expected = "\x1a\x1c\x7f" + b"\x87\x90\xed\x40\xfa\x4a".decode("cp932")
    assert _RecordingClient([payload + b"\r"]).read_comments("DM0", HostLinkCommentEncoding.CP932) == expected


def test_utf8_bom_is_preserved_as_payload_and_is_not_a_cp932_signal() -> None:
    payload = b"\xef\xbb\xbfA"
    assert _RecordingClient([payload + b"\r"]).read_comments("DM0", HostLinkCommentEncoding.UTF8) == "\ufeffA"
    with pytest.raises(HostLinkProtocolError, match="not valid cp932"):
        _RecordingClient([payload + b"\r"]).read_comments("DM0", HostLinkCommentEncoding.CP932)


def test_comment_decode_failure_retires_but_plc_error_keeps_sync_connection() -> None:
    malformed = _RecordingClient([b"\x82\r"])
    with pytest.raises(HostLinkProtocolError):
        malformed.read_comments("DM0", HostLinkCommentEncoding.CP932)
    assert malformed.retired

    plc_error = _RecordingClient([b"E1\r", b"TEXT OK  \r"])
    with pytest.raises(HostLinkError, match="E1"):
        plc_error.read_comment_bytes("DM0")
    assert not plc_error.retired
    assert plc_error.read_comments("DM1", HostLinkCommentEncoding.UTF8) == "TEXT OK"


@pytest.mark.asyncio
async def test_comment_decode_failure_retires_but_plc_error_keeps_async_connection() -> None:
    malformed = _AsyncRecordingClient([b"\x82\r"])
    with pytest.raises(HostLinkProtocolError):
        await malformed.read_comments("DM0", HostLinkCommentEncoding.CP932)
    assert malformed.retired

    plc_error = _AsyncRecordingClient([b"E1\r", b"RAW OK  \r"])
    with pytest.raises(HostLinkError, match="E1"):
        await plc_error.read_comments("DM0", HostLinkCommentEncoding.UTF8)
    assert not plc_error.retired
    assert await plc_error.read_comment_bytes("DM1") == b"RAW OK  "


def test_comment_raw_bytes_preserve_padding_and_encoding() -> None:
    payload = "日本語".encode("cp932") + b"   "
    client = _RecordingClient([payload + b"\r\n"])
    assert client.read_comment_bytes("DM0") == payload


def test_comment_encoding_selection_is_validated_before_send() -> None:
    client = _RecordingClient()
    with pytest.raises(ValueError, match="HostLinkCommentEncoding"):
        client.read_comments("DM0", "utf-8")  # type: ignore[arg-type]
    assert client.frames == []


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


def test_sync_tcp_rejects_two_nonempty_responses_in_one_receive() -> None:
    client = HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    duplicate_socket = _FakeSocket([b"OK\rEXTRA\r"])
    client._sock = duplicate_socket  # type: ignore[assignment]

    with pytest.raises(HostLinkProtocolError, match="more than one"):
        client._recv_tcp_line(sock=duplicate_socket)  # type: ignore[arg-type]
    assert duplicate_socket.closed
    assert client._sock is None


@pytest.mark.asyncio
async def test_async_tcp_rejects_two_nonempty_responses_in_one_receive() -> None:
    client = AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    reader = asyncio.StreamReader()
    reader.feed_data(b"OK\rEXTRA\r")
    client._reader = reader

    with pytest.raises(HostLinkProtocolError, match="more than one"):
        await client._recv_tcp_line()
    assert client._reader is None


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
    with pytest.raises(ValueError, match="Float32 writes.*ordinary word-device"):
        await write_typed(client, device, "F", 1.25)
    assert client.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("device", ["R0", "T0", "C0", "Z0", "AT0"])
async def test_special_family_float32_typed_named_and_poll_reject_before_fifo(device: str) -> None:
    client = _AsyncRecordingClient()
    client._lock = _RejectAdmission()  # type: ignore[assignment]

    with pytest.raises(ValueError, match="ordinary word-device"):
        await read_typed(client, device, "F")
    with pytest.raises(ValueError, match="ordinary word-device"):
        await write_typed(client, device, "F", 1.25)
    with pytest.raises(ValueError, match="ordinary word-device"):
        await read_named(client, [f"{device}:F"])

    stream = poll(client, [f"{device}:F"], interval=0.01)
    with pytest.raises(ValueError, match="ordinary word-device"):
        await anext(stream)

    with pytest.raises(ValueError, match="ordinary word-device"):
        normalize_address(f"{device}:F")
    with pytest.raises(ValueError, match="ordinary word-device"):
        format_address(HostLinkAddress("ignored", device, "F"))
    assert client.frames == []


@pytest.mark.asyncio
async def test_dm_float32_typed_read_and_write_remain_supported() -> None:
    read_client = _AsyncRecordingClient([b"0 16256\r"])
    assert await read_typed(read_client, "DM0", "F") == 1.0
    assert read_client.frames == [b"RDS DM0.U 2\r"]

    write_client = _AsyncRecordingClient([b"OK\r"])
    await write_typed(write_client, "DM0", "F", 1.0)
    assert write_client.frames == [b"WRS DM0.U 2 0 16256\r"]


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
