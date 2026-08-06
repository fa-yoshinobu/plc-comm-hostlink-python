from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from hostlink import AsyncHostLinkClient, HostLinkClient, poll, read_named, read_typed, write_typed
from hostlink.errors import HostLinkProtocolError
from hostlink.protocol import build_frame, parse_scalar_token


@pytest.mark.parametrize("body", ["RD DM0\rRD DM1", "RD DM0\nRD DM1", "RD\tDM0", "RD\x00DM0"])
def test_raw_frame_rejects_control_characters(body: str) -> None:
    with pytest.raises(HostLinkProtocolError, match="control"):
        build_frame(body)


def test_direct_bit_response_accepts_only_documented_tokens() -> None:
    assert parse_scalar_token("0") == 0
    assert parse_scalar_token("1") == 1
    assert parse_scalar_token("OFF") == 0
    assert parse_scalar_token("ON") == 1
    for token in ("TRUE", "FALSE", "2", "-1", "GARBAGE"):
        with pytest.raises(HostLinkProtocolError, match="direct bit"):
            parse_scalar_token(token)


def test_read_response_token_counts_are_exact() -> None:
    with pytest.raises(HostLinkProtocolError, match="expected 1, received 2"):
        HostLinkClient._decode_read_response("1 2", ".U")
    with pytest.raises(HostLinkProtocolError, match="expected 3, received 2"):
        HostLinkClient._decode_data_response("1 2", ".U", 3)
    with pytest.raises(HostLinkProtocolError, match="expected 2, received 3"):
        HostLinkClient._decode_data_response("1 2 3", ".U", 2)


def test_datetime_year_requires_host_link_century() -> None:
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="tcp",
    )
    assert client._build_set_time_command(datetime(2000, 1, 1)) == "WRT 00 01 01 00 00 00 6"
    assert client._build_set_time_command(datetime(2099, 12, 31)) == "WRT 99 12 31 00 00 00 4"
    for year in (1999, 2100):
        with pytest.raises(HostLinkProtocolError, match="2000..2099"):
            client._build_set_time_command(datetime(year, 1, 1))


class _NoSendAsyncClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.exchange_count = 0

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.exchange_count += 1
        raise AssertionError(f"unexpected send: {payload!r}")


class _ChunkingAsyncClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.commands: list[str] = []

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        self.commands.append(command)
        parts = command.split()
        if parts[0] == "RD":
            return b"7\r"
        assert parts[0] == "RDS"
        return (" ".join("7" for _ in range(int(parts[2]))) + "\r").encode("ascii")


class _DirectBitAsyncClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.commands: list[str] = []

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        self.commands.append(command)
        if command == "RD R000.U":
            return b"32777\r"
        if command in {"WR R000.U 32777", "WR R000.U 32769"}:
            return b"OK\r"
        raise AssertionError(f"unexpected command: {command}")


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _MalformedSyncClient(HostLinkClient):
    def __init__(self, response: bytes = b"1 2\r") -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.fake_socket = _FakeSocket()
        self._sock = self.fake_socket  # type: ignore[assignment]
        self.response = response

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        return self.response


class _MalformedAsyncClient(AsyncHostLinkClient):
    def __init__(self, response: bytes = b"1 2\r") -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self._reader = object()  # type: ignore[assignment]
        self.response = response

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        return self.response


class _ScriptedSyncClient(HostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self._sock = _FakeSocket()  # type: ignore[assignment]

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        counts = {"RD R000.U": 1, "RD R000.D": 1, "RD DM0.U": 1}
        return (" ".join("0" for _ in range(counts[command])) + "\r").encode("ascii")


def test_sync_response_shape_mismatch_invalidates_session() -> None:
    client = _MalformedSyncClient(b"0000 0000\r")
    with pytest.raises(HostLinkProtocolError, match="expected 1, received 2"):
        client.read("R0", data_format=".H")
    assert client._sock is None
    assert client.fake_socket.closed


@pytest.mark.asyncio
async def test_async_response_shape_mismatch_invalidates_session() -> None:
    client = _MalformedAsyncClient(b"0000 0000\r")
    with pytest.raises(HostLinkProtocolError, match="expected 1, received 2"):
        await client.read("R0", data_format=".H")
    assert client._reader is None


@pytest.mark.parametrize(
    ("data_format", "response", "expected"),
    [
        (".U", "0 0 65535", [0, 0, 65535]),
        (".S", "1 -32768 32767", [1, -32768, 32767]),
        (".H", "0 a FFFF", [0, "000A", "FFFF"]),
        (".D", "1 0 4294967295", [1, 0, 4294967295]),
        (".L", "0 -2147483648 2147483647", [0, -2147483648, 2147483647]),
    ],
)
def test_timer_counter_status_is_raw_and_format_applies_only_to_values(
    data_format: str,
    response: str,
    expected: list[int | str],
) -> None:
    assert (
        HostLinkClient._decode_read_response(
            response,
            data_format,
            3,
            timer_counter_composite=True,
        )
        == expected
    )


def test_timer_counter_status_must_be_exactly_zero_or_one() -> None:
    for response in ("2 10 20", "-1 10 20", "0000 10 20", "ON 10 20"):
        with pytest.raises(HostLinkProtocolError):
            HostLinkClient._decode_read_response(response, ".L", 3, timer_counter_composite=True)

    client = _MalformedSyncClient(b"2 10 20\r")
    with pytest.raises(HostLinkProtocolError, match="status"):
        client.read("T0", data_format=".D")
    assert client._sock is None
    assert client.fake_socket.closed


@pytest.mark.parametrize(
    ("data_format", "response"),
    [
        (".H", b"0 1\r"),
        (".H", b"0 1 2 3\r"),
        (".U", b"0 -1 0\r"),
        (".U", b"0 0 65536\r"),
        (".S", b"0 -32769 0\r"),
        (".S", b"0 0 32768\r"),
        (".H", b"0 G 2\r"),
        (".H", b"0 1 G\r"),
        (".H", b"0 10000 0000\r"),
        (".D", b"0 4294967296 0\r"),
        (".D", b"0 0 -1\r"),
        (".L", b"0 -2147483649 0\r"),
        (".L", b"0 0 2147483648\r"),
    ],
)
def test_sync_invalid_timer_counter_shape_or_value_invalidates_session(
    data_format: str,
    response: bytes,
) -> None:
    client = _MalformedSyncClient(response)
    with pytest.raises(HostLinkProtocolError):
        client.read("T0", data_format=data_format)
    assert client._sock is None
    assert client.fake_socket.closed


@pytest.mark.asyncio
async def test_async_invalid_timer_counter_status_invalidates_session() -> None:
    client = _MalformedAsyncClient(b"2 10 20\r")
    with pytest.raises(HostLinkProtocolError, match="status"):
        await client.read("C0", data_format=".D")
    assert client._reader is None


def test_single_read_token_count_follows_device_and_format() -> None:
    client = _ScriptedSyncClient()
    assert client.read("R0", data_format=".U") == 0
    assert client.read("R0", data_format=".D") == 0
    assert client.read("DM0", data_format=".U") == 0


@pytest.mark.asyncio
async def test_float32_overflow_is_value_error_before_send() -> None:
    client = _NoSendAsyncClient()
    for value in (1e39, -1e39):
        with pytest.raises(ValueError, match="float32 range"):
            await write_typed(client, "DM0", "F", value)
    assert client.exchange_count == 0


@pytest.mark.asyncio
async def test_named_operations_reject_empty_work() -> None:
    client = _NoSendAsyncClient()
    with pytest.raises(ValueError, match="must not be empty"):
        await read_named(client, [])
    stream = poll(client, [], interval=0.1)
    with pytest.raises(ValueError, match="must not be empty"):
        await anext(stream)
    assert client.exchange_count == 0


@pytest.mark.asyncio
async def test_read_named_splits_merged_ranges_at_command_limit() -> None:
    client = _ChunkingAsyncClient()
    addresses = [f"DM{index}:U" for index in range(2001)]
    result = await read_named(client, addresses)
    assert result == dict.fromkeys(addresses, 7)
    assert client.commands == ["RDS DM0.U 1000", "RDS DM1000.U 1000", "RD DM2000.U"]


@pytest.mark.asyncio
async def test_direct_bit_word_helpers_accept_one_packed_scalar_token() -> None:
    client = _DirectBitAsyncClient()
    assert await read_typed(client, "R0", "U") == 0x8009
    assert await read_named(client, ["R0.0", "R0.3", "R0.F"]) == {
        "R0.0": True,
        "R0.3": True,
        "R0.F": True,
    }
    assert hasattr(client, "write_bit_in_word")


def test_e2e_smoke_uses_current_public_constructor_and_raw_contract() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "e2e_smoke_test.py").read_text(encoding="utf-8")
    assert "append_lf_on_send" not in source
    assert "--append-lf" not in source
    assert "plc_profile=args.plc_profile" in source
    assert 'response = plc.send_raw("INVALID")' in source
    assert 'response == b"E1"' in source
