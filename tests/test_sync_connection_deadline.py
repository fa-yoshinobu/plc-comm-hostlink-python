from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable

import pytest

from hostlink import (
    AsyncHostLinkClient,
    HostLinkClient,
    HostLinkClosedError,
    HostLinkTimeoutError,
    HostLinkTransportError,
)

_FLOAT_TIMEOUT_TOLERANCE = 1e-9


def _is_within_timeout_upper_bound(value: float, upper_bound: float) -> bool:
    """Allow only binary floating-point representation noise at the deadline."""

    return 0 < value <= upper_bound + _FLOAT_TIMEOUT_TOLERANCE


class _FakeSocket:
    def __init__(
        self,
        *,
        connect_action: Callable[[], None] | None = None,
        keepalive_error: OSError | None = None,
    ) -> None:
        self.connect_action = connect_action
        self.keepalive_error = keepalive_error
        self.timeouts: list[float] = []
        self.options: list[tuple[int, int, int]] = []
        self.connected_to: tuple[str, int] | None = None
        self.closed = False
        self.closed_event = threading.Event()

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def connect(self, endpoint: tuple[str, int]) -> None:
        self.connected_to = endpoint
        if self.connect_action is not None:
            self.connect_action()

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if option == socket.SO_KEEPALIVE and self.keepalive_error is not None:
            raise self.keepalive_error
        self.options.append((level, option, value))

    def shutdown(self, _how: int) -> None:
        return None

    def close(self) -> None:
        self.closed = True
        self.closed_event.set()


def _client(host: str, *, transport: str, connect_timeout: float = 0.2) -> HostLinkClient:
    return HostLinkClient(
        host,
        port=8501,
        transport=transport,
        connect_timeout=connect_timeout,
        plc_profile="keyence:kv-8000",
    )


def test_connect_timeout_rejects_values_larger_than_platform_waits() -> None:
    client = _client(
        "127.0.0.1",
        transport="tcp",
        connect_timeout=threading.TIMEOUT_MAX * 2,
    )
    with pytest.raises(ValueError, match="connect_timeout"):
        client.connect()
    assert client._sock is None


@pytest.mark.parametrize("transport", ["tcp", "udp"])
def test_sync_literal_ipv4_bypasses_dns_and_configures_before_adoption(
    monkeypatch: pytest.MonkeyPatch,
    transport: str,
) -> None:
    fake = _FakeSocket()

    def forbidden_resolver(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("literal IPv4 must not use DNS")

    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", forbidden_resolver)
    monkeypatch.setattr("hostlink.client.socket.socket", lambda family, kind: fake)

    client = _client("127.0.0.1", transport=transport)
    client.connect()

    assert client._sock is fake
    assert fake.connected_to == ("127.0.0.1", 8501)
    assert fake.timeouts and _is_within_timeout_upper_bound(fake.timeouts[0], client.connect_timeout)
    if transport == "tcp":
        assert fake.options == [
            (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        ]
    else:
        assert fake.options == []
    client.close()


def test_connection_timeout_tolerance_rejects_meaningful_overrun() -> None:
    assert _is_within_timeout_upper_bound(0.20000000001164153, 0.2)
    assert not _is_within_timeout_upper_bound(0.201, 0.2)


@pytest.mark.parametrize(
    ("transport", "socket_type"),
    [("tcp", socket.SOCK_STREAM), ("udp", socket.SOCK_DGRAM)],
)
def test_sync_hostname_resolution_is_ipv4_only_and_selects_first_matching_result(
    monkeypatch: pytest.MonkeyPatch,
    transport: str,
    socket_type: int,
) -> None:
    resolver_calls: list[tuple[str, int, int, int]] = []
    fake = _FakeSocket()

    def resolve(host: str, port: int, family: int, kind: int) -> list[tuple[object, ...]]:
        resolver_calls.append((host, port, family, kind))
        return [
            (socket.AF_INET6, kind, 0, "", ("::1", port, 0, 0)),
            (socket.AF_INET, kind, 0, "", ("192.0.2.10", port)),
            (socket.AF_INET, kind, 0, "", ("192.0.2.11", port)),
        ]

    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", resolve)
    monkeypatch.setattr("hostlink.client.socket.socket", lambda family, kind: fake)

    client = _client("plc.example.test", transport=transport)
    client.connect()

    assert resolver_calls == [("plc.example.test", 8501, socket.AF_INET, socket_type)]
    assert fake.connected_to == ("192.0.2.10", 8501)
    assert client._sock is fake
    client.close()


def test_sync_dns_timeout_returns_promptly_and_never_adopts_late_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver_started = threading.Event()
    release_resolver = threading.Event()
    resolver_returned = threading.Event()
    socket_created = threading.Event()

    def delayed_resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        resolver_started.set()
        assert release_resolver.wait(timeout=1.0)
        resolver_returned.set()
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.0.2.20", 8501))]

    def create_socket(_family: int, _kind: int) -> _FakeSocket:
        socket_created.set()
        return _FakeSocket()

    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", delayed_resolver)
    monkeypatch.setattr("hostlink.client.socket.socket", create_socket)
    client = _client("slow-dns.example.test", transport="tcp", connect_timeout=0.03)

    started = time.monotonic()
    try:
        with pytest.raises(HostLinkTimeoutError, match="Connect deadline expired"):
            client.connect()
    finally:
        release_resolver.set()
    elapsed = time.monotonic() - started

    assert elapsed < 0.3
    assert resolver_started.is_set()
    assert resolver_returned.wait(timeout=0.3)
    assert not socket_created.wait(timeout=0.05)
    assert client._sock is None
    assert client.traffic_stats().request_count == 0


def test_sync_connect_timeout_closes_a_late_partial_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_started = threading.Event()
    release_connect = threading.Event()

    def block_connect() -> None:
        connect_started.set()
        assert release_connect.wait(timeout=1.0)

    fake = _FakeSocket(connect_action=block_connect)
    monkeypatch.setattr("hostlink.client.socket.socket", lambda family, kind: fake)
    client = _client("127.0.0.1", transport="tcp", connect_timeout=0.03)

    try:
        with pytest.raises(HostLinkTimeoutError, match="Connect deadline expired"):
            client.connect()
    finally:
        release_connect.set()

    assert connect_started.is_set()
    assert fake.closed_event.wait(timeout=0.3)
    assert client._sock is None
    assert client.traffic_stats().request_count == 0


def test_sync_close_during_dns_is_closed_and_late_resolution_creates_no_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver_started = threading.Event()
    release_resolver = threading.Event()
    socket_created = threading.Event()
    errors: list[BaseException] = []

    def delayed_resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        resolver_started.set()
        assert release_resolver.wait(timeout=1.0)
        return [(socket.AF_INET, socket.SOCK_DGRAM, 0, "", ("192.0.2.30", 8501))]

    def create_socket(_family: int, _kind: int) -> _FakeSocket:
        socket_created.set()
        return _FakeSocket()

    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", delayed_resolver)
    monkeypatch.setattr("hostlink.client.socket.socket", create_socket)
    client = _client("close-dns.example.test", transport="udp", connect_timeout=0.5)

    def connect() -> None:
        try:
            client.connect()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=connect)
    thread.start()
    assert resolver_started.wait(timeout=0.3)
    client.close()
    thread.join(timeout=0.3)
    release_resolver.set()

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], HostLinkClosedError)
    assert not socket_created.wait(timeout=0.05)
    assert client._sock is None


def test_sync_tcp_configuration_failure_closes_candidate_and_preserves_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cause = OSError("keepalive rejected")
    fake = _FakeSocket(keepalive_error=cause)
    monkeypatch.setattr("hostlink.client.socket.socket", lambda family, kind: fake)
    client = _client("127.0.0.1", transport="tcp")

    with pytest.raises(HostLinkTransportError) as raised:
        client.connect()

    assert raised.value.__cause__ is cause
    assert fake.closed
    assert client._sock is None


def test_sync_resolver_failure_before_deadline_is_transport_with_native_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cause = socket.gaierror("name not found")

    def fail_resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        raise cause

    monkeypatch.setattr("hostlink.client.socket.getaddrinfo", fail_resolver)
    client = _client("missing.example.test", transport="udp")

    with pytest.raises(HostLinkTransportError) as raised:
        client.connect()

    assert raised.value.__cause__ is cause
    assert client._sock is None


@pytest.mark.parametrize("client_type", [HostLinkClient, AsyncHostLinkClient])
@pytest.mark.parametrize("host", ["::1", "[::1]"])
def test_ipv6_literal_is_rejected_before_any_connection_work(
    monkeypatch: pytest.MonkeyPatch,
    client_type: type[HostLinkClient] | type[AsyncHostLinkClient],
    host: str,
) -> None:
    socket_created = False

    def create_socket(*_args: object, **_kwargs: object) -> _FakeSocket:
        nonlocal socket_created
        socket_created = True
        return _FakeSocket()

    monkeypatch.setattr("hostlink.client.socket.socket", create_socket)
    with pytest.raises(ValueError, match="IPv4"):
        client_type(
            host,
            port=8501,
            transport="tcp",
            plc_profile="keyence:kv-8000",
        )
    assert not socket_created
