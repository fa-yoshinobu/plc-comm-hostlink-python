from __future__ import annotations

import errno
import inspect
import socket
import threading

import pytest

from hostlink import AsyncHostLinkClient, HostLinkClient, HostLinkClosedError
from hostlink.client import ABSOLUTE_RESPONSE_CAP, _AsyncFifoAdmission, _TcpReceiveAccumulator


class _OneByteSocket:
    def __init__(self, body_length: int) -> None:
        self.remaining = body_length

    def settimeout(self, _value: float) -> None:
        return None

    def recv(self, _size: int) -> bytes:
        if self.remaining > 0:
            self.remaining -= 1
            return b"A"
        return b"\r"


class _OneByteReader:
    def __init__(self, body_length: int) -> None:
        self.remaining = body_length

    async def read(self, _size: int) -> bytes:
        if self.remaining > 0:
            self.remaining -= 1
            return b"A"
        return b"\r"


def _sync_client() -> HostLinkClient:
    return HostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )


def _async_client() -> AsyncHostLinkClient:
    return AsyncHostLinkClient(
        "127.0.0.1",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )


def _assert_linear_accumulator_work(accumulator: _TcpReceiveAccumulator) -> None:
    received = ABSOLUTE_RESPONSE_CAP + 1
    assert accumulator.scan_byte_count == received
    assert accumulator.copy_byte_count <= received * 3


def test_sync_tcp_maximum_body_one_byte_fragments_are_scanned_linearly() -> None:
    client = _sync_client()
    body = client._recv_tcp_line(sock=_OneByteSocket(ABSOLUTE_RESPONSE_CAP))

    assert body == b"A" * ABSOLUTE_RESPONSE_CAP
    _assert_linear_accumulator_work(client._rx_buffer)


@pytest.mark.asyncio
async def test_async_tcp_maximum_body_one_byte_fragments_are_scanned_linearly() -> None:
    client = _async_client()
    client._reader = _OneByteReader(ABSOLUTE_RESPONSE_CAP)  # type: ignore[assignment]
    body = await client._recv_tcp_line()

    assert body == b"A" * ABSOLUTE_RESPONSE_CAP
    _assert_linear_accumulator_work(client._rx_buffer)


def test_async_fifo_source_has_constant_time_known_waiter_removal() -> None:
    source = inspect.getsource(_AsyncFifoAdmission)
    assert ".remove(" not in source
    assert ".index(" not in source
    assert "popitem(last=False)" in source
    assert "self._queue.pop(waiter.ticket, None)" in source


def test_numeric_connect_close_wakes_registered_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    waiting = threading.Event()

    class PendingSocket:
        def __init__(self) -> None:
            self.closed = threading.Event()

        def setblocking(self, _value: bool) -> None:
            return None

        def connect_ex(self, _endpoint: tuple[str, int]) -> int:
            return errno.EINPROGRESS

        def shutdown(self, _how: int) -> None:
            return None

        def close(self) -> None:
            self.closed.set()

    candidate = PendingSocket()

    def wait_for_close(*_args: object, **_kwargs: object) -> tuple[list[object], list[object], list[object]]:
        waiting.set()
        assert candidate.closed.wait(timeout=1.0)
        raise OSError("candidate closed")

    monkeypatch.setattr("hostlink.client.socket.socket", lambda *_args, **_kwargs: candidate)
    monkeypatch.setattr("hostlink.client.select.select", wait_for_close)
    client = _sync_client()
    errors: list[BaseException] = []

    def connect() -> None:
        try:
            client.connect()
        except BaseException as error:
            errors.append(error)

    caller = threading.Thread(target=connect)
    caller.start()
    assert waiting.wait(timeout=1.0)
    client.close()
    caller.join(timeout=1.0)

    assert not caller.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], HostLinkClosedError)
    assert client._sock is None
    assert client._connecting_sock is None


def test_numeric_connect_uses_nonblocking_so_error_without_dns_or_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class ReadySocket:
        def setblocking(self, value: bool) -> None:
            calls.append(f"blocking:{value}")

        def connect_ex(self, endpoint: tuple[str, int]) -> int:
            calls.append(f"connect:{endpoint[0]}:{endpoint[1]}")
            return errno.EINPROGRESS

        def getsockopt(self, level: int, option: int) -> int:
            assert (level, option) == (socket.SOL_SOCKET, socket.SO_ERROR)
            calls.append("so-error")
            return 0

        def settimeout(self, _value: float) -> None:
            return None

        def setsockopt(self, _level: int, _option: int, _value: int) -> None:
            return None

        def shutdown(self, _how: int) -> None:
            return None

        def close(self) -> None:
            return None

    ready = ReadySocket()

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("numeric IPv4 must not resolve DNS or create a worker")

    monkeypatch.setattr("hostlink.client.socket.socket", lambda *_args, **_kwargs: ready)
    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", forbidden)
    monkeypatch.setattr("hostlink.client.threading.Thread", forbidden)
    monkeypatch.setattr("hostlink.client.select.select", lambda *_args, **_kwargs: ([], [ready], []))
    client = _sync_client()

    client.connect()
    client.close()

    assert calls == ["blocking:False", "connect:127.0.0.1:8501", "so-error"]


def test_numeric_connect_close_after_readiness_keeps_closed_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checking_socket_error = threading.Event()

    class ClosedBeforeSocketError:
        def __init__(self) -> None:
            self.closed = threading.Event()

        def setblocking(self, _value: bool) -> None:
            return None

        def connect_ex(self, _endpoint: tuple[str, int]) -> int:
            return errno.EINPROGRESS

        def getsockopt(self, _level: int, _option: int) -> int:
            checking_socket_error.set()
            assert self.closed.wait(timeout=1.0)
            raise OSError("candidate closed before SO_ERROR")

        def shutdown(self, _how: int) -> None:
            return None

        def close(self) -> None:
            self.closed.set()

    candidate = ClosedBeforeSocketError()
    monkeypatch.setattr("hostlink.client.socket.socket", lambda *_args, **_kwargs: candidate)
    monkeypatch.setattr(
        "hostlink.client.select.select",
        lambda *_args, **_kwargs: ([], [candidate], []),
    )
    client = _sync_client()
    errors: list[BaseException] = []

    caller = threading.Thread(
        target=lambda: _capture_connect_error(client, errors),
    )
    caller.start()
    assert checking_socket_error.wait(timeout=1.0)
    client.close()
    caller.join(timeout=1.0)

    assert not caller.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], HostLinkClosedError)


def _capture_connect_error(client: HostLinkClient, errors: list[BaseException]) -> None:
    try:
        client.connect()
    except BaseException as error:
        errors.append(error)
