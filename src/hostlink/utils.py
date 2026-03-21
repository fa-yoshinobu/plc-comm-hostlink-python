"""High-level utility helpers for the Host Link client."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator

from .errors import HostLinkProtocolError

if TYPE_CHECKING:
    from .client import AsyncHostLinkClient


async def read_typed(
    client: "AsyncHostLinkClient",
    device: str,
    dtype: str,
) -> int | float | str:
    """
    Read a single device value and convert it to the appropriate Python type.

    Args:
        client: Connected AsyncHostLinkClient.
        device: Device address string, e.g. "DM100".
        dtype: Data type code — "U" unsigned 16-bit int, "S" signed 16-bit int,
               "D" unsigned 32-bit int, "L" signed 32-bit int,
               "H" hex string, "F" float.

    Returns:
        Converted value as int, float, or str.
    """
    fmt = f".{dtype.lstrip('.')}"
    result = await client.read(device, data_format=fmt)
    values = result if isinstance(result, list) else [result]
    if not values:
        raise HostLinkProtocolError(f"No value returned for {device!r}")
    raw = values[0]
    key = dtype.upper().lstrip(".")
    if key == "F":
        return float(raw) if isinstance(raw, str) else float(raw)
    return int(raw) if isinstance(raw, str) else raw


async def write_typed(
    client: "AsyncHostLinkClient",
    device: str,
    dtype: str,
    value: int | float | str,
) -> None:
    """
    Write a value using the specified data type format.

    Args:
        client: Connected AsyncHostLinkClient.
        device: Device address string, e.g. "DM100".
        dtype: Data type code — same as read_typed.
        value: Value to write.
    """
    fmt = f".{dtype.lstrip('.')}"
    await client.write(device, value, data_format=fmt)


async def poll(
    client: "AsyncHostLinkClient",
    devices: list[str],
    interval: float,
    *,
    data_format: str | None = None,
) -> AsyncIterator[dict[str, int | str | list]]:
    """
    Yield a snapshot of all devices every *interval* seconds.

    Args:
        client: Connected AsyncHostLinkClient.
        devices: List of device address strings.
        interval: Poll interval in seconds.
        data_format: Optional data format suffix applied to all devices.

    Usage::

        async for snapshot in poll(client, ["DM100", "MR0"], interval=0.5):
            print(snapshot)
    """
    while True:
        snapshot: dict[str, int | str | list] = {}
        for device in devices:
            snapshot[device] = await client.read(device, data_format=data_format)
        yield snapshot
        await asyncio.sleep(interval)


async def open_and_connect(
    host: str,
    port: int = 8501,
    transport: str = "tcp",
    timeout: float = 3.0,
) -> "AsyncHostLinkClient":
    """
    Return a connected AsyncHostLinkClient.

    Equivalent to creating a client with ``auto_connect=False`` and then
    calling ``await client.connect()``.

    Usage::

        client = await open_and_connect("192.168.1.10")
        async with client:
            values = await client.read_consecutive("DM100", 10)
    """
    from .client import AsyncHostLinkClient

    client = AsyncHostLinkClient(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        auto_connect=False,
    )
    await client.connect()
    return client
