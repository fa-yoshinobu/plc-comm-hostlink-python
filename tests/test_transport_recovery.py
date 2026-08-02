from __future__ import annotations

import asyncio
import socket
import threading
import time
from typing import Any

import pytest

from hostlink import AsyncHostLinkClient, HostLinkClient
from hostlink.errors import (
    HostLinkCancelledError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkFailureReason,
    HostLinkOutcomeUnknownError,
    HostLinkProtocolError,
)


@pytest.mark.parametrize("split_lf", [False, True])
def test_sync_tcp_traffic_stats_are_independent_of_crlf_segmentation(split_lf: bool) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    server_error: list[BaseException] = []

    def receive_request(connection: socket.socket) -> bytes:
        request = bytearray()
        while not request.endswith(b"\r"):
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("client closed before request terminator")
            request.extend(chunk)
        return bytes(request)

    def serve() -> None:
        try:
            connection, _ = server.accept()
            with connection:
                assert receive_request(connection) == b"FIRST\r"
                connection.sendall(b"FIRST\r" if split_lf else b"FIRST\r\n")
                assert receive_request(connection) == b"SECOND\r"
                connection.sendall((b"\n" if split_lf else b"") + b"SECOND\n\r")
        except BaseException as exc:  # pragma: no cover - surfaced below
            server_error.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        client.connect()
        assert client.send_raw("FIRST") == b"FIRST"
        assert client.send_raw("SECOND") == b"SECOND"
        assert client.traffic_stats().rx_bytes == len(b"FIRST\r") + len(b"SECOND\n")
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()
    assert not thread.is_alive()
    assert server_error == []


@pytest.mark.asyncio
@pytest.mark.parametrize("split_lf", [False, True])
async def test_async_tcp_traffic_stats_are_independent_of_crlf_segmentation(split_lf: bool) -> None:
    completed = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            assert await reader.readuntil(b"\r") == b"FIRST\r"
            writer.write(b"FIRST\r" if split_lf else b"FIRST\r\n")
            await writer.drain()
            assert await reader.readuntil(b"\r") == b"SECOND\r"
            writer.write((b"\n" if split_lf else b"") + b"SECOND\n\r")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            completed.set()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        await client.connect()
        assert await client.send_raw("FIRST") == b"FIRST"
        assert await client.send_raw("SECOND") == b"SECOND"
        assert client.traffic_stats().rx_bytes == len(b"FIRST\r") + len(b"SECOND\n")
        await asyncio.wait_for(completed.wait(), timeout=1.0)
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


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
        transport="tcp",
        timeout=1.0,
    )
    try:
        client.connect()
        with pytest.raises(HostLinkConnectionError, match="before the response terminator"):
            client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
        assert client._sock is None
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_tcp_timeout_does_not_count_partial_response() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            time.sleep(0.2)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=0.05,
    )
    try:
        client.connect()
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_tcp_timeout_is_one_deadline_for_a_trickled_response() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            try:
                for _ in range(5):
                    time.sleep(0.03)
                    connection.sendall(b"A")
            except OSError:
                pass

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=0.08,
    )
    try:
        client.connect()
        started = time.monotonic()
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            client.send_raw("RD DM0.U")
        elapsed = time.monotonic() - started
        assert elapsed < 0.2
        assert client._sock is None
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_complete_plc_error_line_is_counted_before_semantic_failure() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(b"E1\r")

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        client.connect()
        with pytest.raises(HostLinkError, match="E1"):
            client.clear_error()
        assert client.traffic_stats().rx_bytes == 3
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_tcp_oversize_partial_response_does_not_count_receive_bytes() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(b"A" * 65_537)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        client.connect()
        with pytest.raises(HostLinkProtocolError, match="exceeds"):
            client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
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
    )
    try:
        client.connect()
        first_socket = client._sock
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            client.send_raw("RD DM0.U")
        assert client._sock is None
        assert client.traffic_stats().request_count == 1
        assert client.traffic_stats().tx_bytes == len(b"RD DM0.U\r")
        assert client.traffic_stats().rx_bytes == 0

        client.timeout = 1.0
        assert client.send_raw("RD DM1.U") == b"SECOND"
        assert client._sock is not first_socket
        assert client.traffic_stats().request_count == 2
        assert client.traffic_stats().rx_bytes == len(b"SECOND\r")
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()
    assert not thread.is_alive()
    assert server_error == []


def test_sync_udp_successful_requests_reuse_one_local_endpoint() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    port = server.getsockname()[1]
    addresses: list[tuple[str, int]] = []
    server_error: list[BaseException] = []

    def serve() -> None:
        try:
            _, first_address = server.recvfrom(4096)
            addresses.append(first_address)
            server.sendto(b"FIRST\r", first_address)
            _, second_address = server.recvfrom(4096)
            addresses.append(second_address)
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
        timeout=1.0,
    )
    try:
        client.connect()
        assert client.send_raw("FIRST") == b"FIRST"
        assert client.send_raw("SECOND") == b"SECOND"
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()
    assert addresses[0] == addresses[1]
    assert server_error == []


def test_sync_udp_pre_send_unowned_datagram_discards_socket_and_uses_a_fresh_socket() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    port = server.getsockname()[1]

    def serve() -> None:
        _, first_address = server.recvfrom(4096)
        server.sendto(b"FIRST\r", first_address)
        time.sleep(0.02)
        server.sendto(b"UNOWNED\r", first_address)
        _, second_address = server.recvfrom(4096)
        server.sendto(b"SECOND\r", second_address)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        client.connect()
        assert client.send_raw("FIRST") == b"FIRST"
        first_socket = client._sock
        time.sleep(0.05)
        with pytest.raises(HostLinkProtocolError, match="unowned UDP"):
            client.send_raw("SECOND")
        assert client.send_raw("SECOND") == b"SECOND"
        assert client._sock is not first_socket
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


def test_sync_udp_connected_generation_filters_wrong_source_endpoint() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    rogue = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = server.getsockname()[1]
    server_error: list[BaseException] = []

    def serve() -> None:
        try:
            _, address = server.recvfrom(4096)
            rogue.sendto(b"ROGUE\r", address)
            time.sleep(0.02)
            server.sendto(b"EXPECTED\r", address)
        except BaseException as exc:  # pragma: no cover - surfaced below
            server_error.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        client.connect()
        assert client.send_raw("RD DM0.U") == b"EXPECTED"
    finally:
        client.close()
        thread.join(timeout=3.0)
        rogue.close()
        server.close()
    assert server_error == []


def test_sync_udp_active_close_reports_state_changing_outcome_unknown() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(2.0)
    port = server.getsockname()[1]
    request_seen = threading.Event()
    outcome: list[BaseException] = []

    def serve() -> None:
        server.recvfrom(4096)
        request_seen.set()

    def write() -> None:
        try:
            client.send_raw("WR DM0.U 1")
        except BaseException as exc:
            outcome.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    client.connect()
    operation = threading.Thread(target=write)
    operation.start()
    assert request_seen.wait(timeout=1.0)
    client.close()
    operation.join(timeout=2.0)
    thread.join(timeout=2.0)
    server.close()

    assert not operation.is_alive()
    assert len(outcome) == 1
    assert isinstance(outcome[0], HostLinkOutcomeUnknownError)
    assert outcome[0].reason is HostLinkFailureReason.CLOSED  # type: ignore[union-attr]
    assert client._sock is None
    assert not client._udp_logically_connected


def test_sync_udp_missing_terminator_invalidates_transport() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def serve() -> None:
        _, address = server.recvfrom(4096)
        server.sendto(b"UNTERMINATED", address)

    thread = threading.Thread(target=serve)
    thread.start()
    client = HostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        client.connect()
        with pytest.raises(HostLinkProtocolError, match="terminator"):
            client.send_raw("RD DM0.U")
        assert client._sock is None
        assert client.traffic_stats().request_count == 1
        assert client.traffic_stats().rx_bytes == 0
    finally:
        client.close()
        thread.join(timeout=3.0)
        server.close()


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


class _UnterminatedUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        assert self.transport is not None
        self.transport.sendto(b"UNTERMINATED", address)


class _DuplicateUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.addresses: list[tuple[str | Any, int]] = []

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        assert self.transport is not None
        self.addresses.append(address)
        if len(self.addresses) == 1:
            self.transport.sendto(b"FIRST\r", address)
        else:
            self.transport.sendto(b"SECOND\r", address)


class _DelayedDuplicateUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.addresses: list[tuple[str | Any, int]] = []

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        assert self.transport is not None
        self.addresses.append(address)
        if len(self.addresses) == 1:
            self.transport.sendto(b"FIRST\r", address)
            asyncio.get_running_loop().call_later(0.02, self.transport.sendto, b"UNOWNED\r", address)
        else:
            self.transport.sendto(b"SECOND\r", address)


class _SourceFilteringUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        assert self.transport is not None
        rogue = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            rogue.sendto(b"ROGUE\r", address)
        finally:
            rogue.close()
        asyncio.get_running_loop().call_later(0.02, self.transport.sendto, b"EXPECTED\r", address)


class _HoldingUdpServer(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.request_seen = asyncio.Event()

    def datagram_received(self, data: bytes, address: tuple[str | Any, int]) -> None:
        self.request_seen.set()


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
    )
    try:
        await client.connect()
        first_transport = client._udp_transport
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            await client.send_raw("RD DM0.U")
        assert client._udp_transport is None

        client.timeout = 1.0
        assert await client.send_raw("RD DM1.U") == b"SECOND"
        assert protocol.count == 2
        assert client._udp_transport is not first_transport
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_udp_successful_requests_reuse_one_local_endpoint() -> None:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _DuplicateUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        await client.connect()
        assert await client.send_raw("FIRST") == b"FIRST"
        assert await client.send_raw("SECOND") == b"SECOND"
        assert protocol.addresses[0] == protocol.addresses[1]
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_udp_pre_send_unowned_datagram_discards_endpoint_and_recreates() -> None:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _DelayedDuplicateUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        await client.connect()
        assert await client.send_raw("FIRST") == b"FIRST"
        first_transport = client._udp_transport
        await asyncio.sleep(0.05)
        with pytest.raises(HostLinkProtocolError, match="unowned UDP"):
            await client.send_raw("SECOND")
        assert await client.send_raw("SECOND") == b"SECOND"
        assert client._udp_transport is not first_transport
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_udp_connected_generation_filters_wrong_source_endpoint() -> None:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        _SourceFilteringUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        await client.connect()
        assert await client.send_raw("RD DM0.U") == b"EXPECTED"
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_udp_active_close_reports_state_changing_outcome_unknown() -> None:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _HoldingUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        await client.connect()
        operation = asyncio.create_task(client.send_raw("WR DM0.U 1"))
        await asyncio.wait_for(protocol.request_seen.wait(), timeout=1.0)
        await client.close()
        with pytest.raises(HostLinkOutcomeUnknownError) as raised:
            await operation
        assert raised.value.reason is HostLinkFailureReason.CLOSED
        assert client._udp_transport is None
        assert not client._udp_logically_connected
    finally:
        await client.close()
        transport.close()


@pytest.mark.asyncio
async def test_async_udp_missing_terminator_invalidates_transport() -> None:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        _UnterminatedUdpServer,
        local_addr=("127.0.0.1", 0),
    )
    port = transport.get_extra_info("sockname")[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="udp",
        timeout=1.0,
    )
    try:
        await client.connect()
        with pytest.raises(HostLinkProtocolError, match="terminator"):
            await client.send_raw("RD DM0.U")
        assert client._udp_transport is None
        assert client._udp_protocol is None
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
        transport="tcp",
        timeout=1.0,
    )
    try:
        await client.connect()
        first_request = asyncio.create_task(client.send_raw("RD DM0.U"))
        await asyncio.wait_for(first_seen.wait(), timeout=1.0)
        first_request.cancel()
        with pytest.raises(HostLinkCancelledError):
            await first_request
        assert client._writer is None

        release_first.set()
        await client.connect()
        assert await client.send_raw("RD DM1.U") == b"SECOND"
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
        transport="tcp",
        timeout=1.0,
    )
    try:
        await client.connect()
        with pytest.raises(HostLinkConnectionError, match="before the response terminator"):
            await client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
        assert client._writer is None
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_async_tcp_timeout_does_not_count_partial_response() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r")
        await asyncio.sleep(0.2)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=0.05,
    )
    try:
        await client.connect()
        with pytest.raises(HostLinkConnectionError, match="Timeout"):
            await client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_async_tcp_timeout_includes_writer_drain() -> None:
    class SlowWriter:
        def write(self, _payload: bytes) -> None:
            return None

        async def drain(self) -> None:
            await asyncio.sleep(0.04)

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    class SlowReader:
        def __init__(self) -> None:
            self.responses = iter((b"O", b"\r"))

        async def read(self, _count: int) -> bytes:
            await asyncio.sleep(0.02)
            return next(self.responses)

    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=8501,
        transport="tcp",
        timeout=0.05,
    )
    client._reader = SlowReader()  # type: ignore[assignment]
    client._writer = SlowWriter()  # type: ignore[assignment]

    started = asyncio.get_running_loop().time()
    with pytest.raises(HostLinkConnectionError, match="Timeout"):
        await client.send_raw("RD DM0.U")
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed < 0.12
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_async_complete_plc_error_line_is_counted_before_semantic_failure() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r")
        writer.write(b"E1\r")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        await client.connect()
        with pytest.raises(HostLinkError, match="E1"):
            await client.clear_error()
        assert client.traffic_stats().rx_bytes == 3
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_async_tcp_oversize_partial_response_does_not_count_receive_bytes() -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r")
        writer.write(b"A" * 65_537)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = AsyncHostLinkClient(
        "127.0.0.1",
        plc_profile="keyence:kv-8000",
        port=port,
        transport="tcp",
        timeout=1.0,
    )
    try:
        await client.connect()
        with pytest.raises(HostLinkProtocolError, match="exceeds"):
            await client.send_raw("RD DM0.U")
        assert client.traffic_stats().rx_bytes == 0
    finally:
        await client.close()
        server.close()
        await server.wait_closed()
