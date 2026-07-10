from __future__ import annotations

import asyncio
import socket
import threading
import time
from typing import Any

import pytest

from hostlink import AsyncHostLinkClient, HostLinkClient, write_bit_in_word
from hostlink.errors import HostLinkConnectionError


def test_sync_tcp_eof_before_terminator_rejects_partial_response() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(b"PARTIAL")

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        timeout=1.0,
        auto_connect=False,
    )
    try:
        with pytest.raises(HostLinkConnectionError, match="before the response terminator"):
            client.send_raw("READ")
        assert client._sock is None
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_udp_timeout_discards_delayed_response() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    port = server.getsockname()[1]
    server_error: list[BaseException] = []

    def serve() -> None:
        try:
            _, first_address = server.recvfrom(4096)
            time.sleep(0.15)
            server.sendto(b"FIRST\r", first_address)
            _, second_address = server.recvfrom(4096)
            server.sendto(b"SECOND\r", second_address)
        except BaseException as exc:  # pragma: no cover - surfaced below
            server_error.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=0.05,
        auto_connect=False,
    )
    try:
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            client.send_raw("FIRST")
        assert client._sock is None

        client.timeout = 1.0
        assert client.send_raw("SECOND") == "SECOND"
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()
    assert not thread.is_alive()
    assert server_error == []


class _DelayedUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.count = 0

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        self.count += 1
        if self.count == 1:
            asyncio.get_running_loop().call_later(0.15, self._send, b"FIRST\r", address)
        else:
            self._send(b"SECOND\r", address)

    def _send(self, data: bytes, address: tuple[str | Any, int]) -> None:
        if self.transport is not None:
            self.transport.sendto(data, address)


@pytest.mark.asyncio
async def test_async_udp_timeout_discards_delayed_response() -> None:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _DelayedUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=0.05,
        auto_connect=False,
    )
    try:
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            await client.send_raw("FIRST")
        assert client._udp_transport is None

        client.timeout = 1.0
        assert await client.send_raw("SECOND") == "SECOND"
        assert protocol.count == 2
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_tcp_cancellation_discards_delayed_response() -> None:
    first_seen = asyncio.Event()
    release_first = asyncio.Event()
    connection_count = 0
    handlers: set[asyncio.Task[None]] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connection_count
        connection_count += 1
        current = connection_count
        try:
            await reader.readuntil(b"\r")
            if current == 1:
                first_seen.set()
                await release_first.wait()
                writer.write(b"FIRST\r")
            else:
                writer.write(b"SECOND\r")
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def tracked_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        handlers.add(task)
        try:
            await handle(reader, writer)
        finally:
            handlers.discard(task)

    server = await asyncio.start_server(tracked_handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        timeout=1.0,
        auto_connect=False,
    )
    try:
        first_request = asyncio.create_task(client.send_raw("FIRST"))
        await asyncio.wait_for(first_seen.wait(), timeout=1.0)
        first_request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_request
        assert client._writer is None

        release_first.set()
        assert await client.send_raw("SECOND") == "SECOND"
    finally:
        release_first.set()
        await client.close()
        server.close()
        await server.wait_closed()
        if handlers:
            await asyncio.wait(handlers, timeout=1.0)


@pytest.mark.asyncio
async def test_async_tcp_eof_before_terminator_rejects_partial_response() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r")
        writer.write(b"PARTIAL")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        timeout=1.0,
        auto_connect=False,
    )
    try:
        with pytest.raises(HostLinkConnectionError, match="before the response terminator"):
            await client.send_raw("READ")
        assert client._writer is None
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


class _AtomicWordClient(AsyncHostLinkClient):
    def __init__(self) -> None:
        super().__init__(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            auto_connect=False,
        )
        self.word = 0

    async def _exchange(self, payload: bytes) -> bytes:
        command = payload.decode("ascii").strip()
        if command == "RD DM0.U":
            await asyncio.sleep(0.01)
            return f"{self.word}\r".encode("ascii")
        if command.startswith("WR DM0.U "):
            await asyncio.sleep(0)
            self.word = int(command.rsplit(" ", 1)[1])
            return b"OK\r"
        raise AssertionError(f"unexpected command: {command}")


@pytest.mark.asyncio
async def test_write_bit_in_word_holds_lock_across_read_modify_write() -> None:
    client = _AtomicWordClient()
    await asyncio.gather(
        write_bit_in_word(client, "DM0", 0, True),
        write_bit_in_word(client, "DM0", 1, True),
    )
    assert client.word == 3
