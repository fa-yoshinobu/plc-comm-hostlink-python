from __future__ import annotations

import asyncio
import socket
import threading
import time

import pytest

from hostlink import (
    AsyncHostLinkClient,
    HostLinkCancelledError,
    HostLinkClient,
    HostLinkClosedError,
    HostLinkCommentEncoding,
    HostLinkFailureReason,
    HostLinkOutcomeUnknownError,
    HostLinkProtocolError,
    HostLinkTimeoutError,
    read_named,
)
from hostlink.client import ABSOLUTE_REQUEST_BODY_CAP


class _RecordingRawClient(HostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.frames: list[bytes] = []

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.frames.append(payload)
        return b"OK\r"


def test_request_body_capacity_accepts_exact_max_and_rejects_max_plus_one_before_send() -> None:
    client = _RecordingRawClient()
    client.send_raw("R" * ABSOLUTE_REQUEST_BODY_CAP)
    assert client.frames == [b"R" * ABSOLUTE_REQUEST_BODY_CAP + b"\r"]

    with pytest.raises(HostLinkProtocolError, match="exceeds"):
        client.send_raw("R" * (ABSOLUTE_REQUEST_BODY_CAP + 1))
    assert len(client.frames) == 1


class _TimeoutSocket:
    def __init__(self) -> None:
        self.closed = False
        self.sent: list[bytes] = []

    def settimeout(self, _timeout: float) -> None:
        return None

    def sendall(self, payload: bytes) -> None:
        self.sent.append(payload)

    def recv(self, _size: int) -> bytes:
        raise TimeoutError("native timeout")

    def shutdown(self, _how: int) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_unknown_raw_command_timeout_has_structured_outcome_and_native_cause() -> None:
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="udp",
    )
    transport = _TimeoutSocket()
    client._sock = transport  # type: ignore[assignment]

    with pytest.raises(HostLinkOutcomeUnknownError) as raised:
        client.send_raw("VENDOR_COMMAND 1")

    assert raised.value.reason is HostLinkFailureReason.TIMEOUT
    assert isinstance(raised.value.detail, HostLinkTimeoutError)
    assert isinstance(raised.value.detail.__cause__, TimeoutError)
    assert transport.sent == [b"VENDOR_COMMAND 1\r"]
    assert transport.closed


class _SyncFifoClient(HostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.commands: list[str] = []
        self.first_started = threading.Event()
        self.release_first = threading.Event()

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        self.commands.append(command)
        if len(self.commands) == 1:
            self.first_started.set()
            assert self.release_first.wait(timeout=1.0)
        return b"1\r"


def test_sync_operations_are_admitted_in_arrival_fifo_order() -> None:
    client = _SyncFifoClient()
    threads = [threading.Thread(target=client.send_raw, args=(f"RD DM{index}.U",)) for index in range(3)]
    threads[0].start()
    assert client.first_started.wait(timeout=1.0)
    threads[1].start()
    deadline = time.monotonic() + 1.0
    while len(client._lock._queue) < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert len(client._lock._queue) == 1
    threads[2].start()
    deadline = time.monotonic() + 1.0
    while len(client._lock._queue) < 2 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert len(client._lock._queue) == 2
    client.release_first.set()
    for thread in threads:
        thread.join(timeout=1.0)
        assert not thread.is_alive()
    assert client.commands == ["RD DM0.U", "RD DM1.U", "RD DM2.U"]


class _DecodeDeadlineSyncClient(_RecordingRawClient):
    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self._last_exchange_deadline = time.monotonic() + 0.001
        return b"OK\r"


def test_sync_absolute_deadline_includes_response_decoding() -> None:
    client = _DecodeDeadlineSyncClient()

    def slow_decoder(_response: bytes) -> str:
        time.sleep(0.05)
        return "OK"

    with pytest.raises(HostLinkTimeoutError, match="decoding"):
        client._send_decoded("RD DM0.U", slow_decoder)


def test_sync_close_immediately_rejects_active_write_and_queued_read() -> None:
    client_socket, peer_socket = socket.socketpair()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="tcp",
    )
    client._sock = client_socket
    errors: dict[str, BaseException] = {}

    def active_write() -> None:
        try:
            client.write("DM0", 1, data_format=".U")
        except BaseException as exc:
            errors["active"] = exc

    def queued_read() -> None:
        try:
            client.read("DM1", data_format=".U")
        except BaseException as exc:
            errors["queued"] = exc

    active = threading.Thread(target=active_write)
    active.start()
    assert peer_socket.recv(1024) == b"WR DM0.U 1\r"
    queued = threading.Thread(target=queued_read)
    queued.start()
    time.sleep(0.02)

    started = time.monotonic()
    client.close()
    assert time.monotonic() - started < 0.2
    active.join(timeout=1.0)
    queued.join(timeout=1.0)
    peer_socket.close()

    assert not active.is_alive()
    assert not queued.is_alive()
    assert isinstance(errors["queued"], HostLinkClosedError)
    assert isinstance(errors["active"], HostLinkOutcomeUnknownError)
    assert errors["active"].reason is HostLinkFailureReason.CLOSED  # type: ignore[union-attr]


class _AsyncFifoClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.commands: list[str] = []
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        self.commands.append(command)
        if len(self.commands) == 1:
            self.first_started.set()
            await self.release_first.wait()
        return b"1\r"


@pytest.mark.asyncio
async def test_async_fifo_waiter_cancellation_is_typed_and_never_sends() -> None:
    client = _AsyncFifoClient()
    first = asyncio.create_task(client.send_raw("RD DM0.U"))
    await client.first_started.wait()
    cancelled = asyncio.create_task(client.send_raw("RD DM1.U"))
    await asyncio.sleep(0)
    third = asyncio.create_task(client.send_raw("RD DM2.U"))
    await asyncio.sleep(0)

    cancelled.cancel()
    with pytest.raises(HostLinkCancelledError):
        await cancelled
    client.release_first.set()
    assert await first == b"1"
    assert await third == b"1"
    assert client.commands == ["RD DM0.U", "RD DM2.U"]


class _DecodeDeadlineAsyncClient(_AsyncFifoClient):
    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self._last_exchange_deadline = asyncio.get_running_loop().time() + 0.001
        return b"OK\r"


@pytest.mark.asyncio
async def test_async_absolute_deadline_includes_response_decoding() -> None:
    client = _DecodeDeadlineAsyncClient()

    def slow_decoder(_response: bytes) -> str:
        time.sleep(0.05)
        return "OK"

    with pytest.raises(HostLinkTimeoutError, match="decoding"):
        await client._send_decoded("RD DM0.U", slow_decoder)


@pytest.mark.asyncio
async def test_async_close_immediately_rejects_active_write_and_queued_read() -> None:
    request_seen = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.readuntil(b"\r")
            request_seen.set()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
    )
    await client.connect()
    active = asyncio.create_task(client.write("DM0", 1, data_format=".U"))
    await request_seen.wait()
    queued = asyncio.create_task(client.read("DM1", data_format=".U"))
    await asyncio.sleep(0)
    assert len(client._lock._queue) == 1

    started = asyncio.get_running_loop().time()
    await client.close()
    assert asyncio.get_running_loop().time() - started < 0.2
    active_result, queued_result = await asyncio.gather(active, queued, return_exceptions=True)
    server.close()
    await server.wait_closed()

    assert isinstance(queued_result, HostLinkClosedError)
    assert isinstance(active_result, HostLinkOutcomeUnknownError)
    assert active_result.reason is HostLinkFailureReason.CLOSED


class _NamedFifoClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        self.commands: list[str] = []
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        command = payload.rstrip(b"\r").decode("ascii")
        self.commands.append(command)
        if command == "RD DM0.U":
            self.first_started.set()
            await self.release_first.wait()
            return b"10\r"
        if command == "RDC DM2":
            return b"COMMENT\r"
        if command == "RD R000":
            return b"1\r"
        if command == "RD DM9.U":
            return b"9\r"
        raise AssertionError(command)


@pytest.mark.asyncio
async def test_read_named_uses_one_fifo_turn_and_preserves_declared_request_order() -> None:
    client = _NamedFifoClient()
    aggregate = asyncio.create_task(
        read_named(
            client,
            ["DM0:U", "DM2:COMMENT"],
            comment_encoding=HostLinkCommentEncoding.UTF8,
        )
    )
    await client.first_started.wait()
    competing = asyncio.create_task(client.read("DM9", data_format=".U"))
    await asyncio.sleep(0)
    client.release_first.set()

    assert await aggregate == {"DM0:U": 10, "DM2:COMMENT": "COMMENT"}
    assert await competing == 9
    assert client.commands == ["RD DM0.U", "RDC DM2", "RD DM9.U"]


@pytest.mark.asyncio
async def test_read_named_preserves_order_across_device_types() -> None:
    client = _NamedFifoClient()
    client.release_first.set()
    result = await read_named(
        client,
        ["DM0:U", "R0:BIT", "DM2:COMMENT"],
        comment_encoding=HostLinkCommentEncoding.UTF8,
    )
    assert result == {"DM0:U": 10, "R0:BIT": True, "DM2:COMMENT": "COMMENT"}
    assert client.commands == ["RD DM0.U", "RD R000", "RDC DM2"]


@pytest.mark.asyncio
async def test_read_named_comment_requires_explicit_encoding_before_any_send() -> None:
    client = _NamedFifoClient()
    with pytest.raises(ValueError, match="comment_encoding is required"):
        await read_named(client, ["DM0:U", "DM2:COMMENT"])
    assert client.commands == []


@pytest.mark.asyncio
async def test_read_named_rejects_unused_comment_encoding_before_any_send() -> None:
    client = _NamedFifoClient()
    with pytest.raises(ValueError, match="requires at least one :COMMENT"):
        await read_named(
            client,
            ["DM0:U"],
            comment_encoding=HostLinkCommentEncoding.UTF8,
        )
    assert client.commands == []


@pytest.mark.asyncio
async def test_read_named_preflights_every_entry_before_any_send() -> None:
    client = _NamedFifoClient()
    for invalid in ("not-an-address", "R0:F"):
        with pytest.raises((HostLinkProtocolError, ValueError)):
            await read_named(client, ["DM0:U", invalid])
        assert client.commands == []
