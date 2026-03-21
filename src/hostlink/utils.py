"""High-level utility helpers for the Host Link client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .errors import HostLinkProtocolError

if TYPE_CHECKING:
    from .client import AsyncHostLinkClient


async def read_typed(
    client: AsyncHostLinkClient,
    device: str,
    dtype: str,
) -> int | float:
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
    client: AsyncHostLinkClient,
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
    write_val: int | str = str(value) if isinstance(value, float) else value
    await client.write(device, write_val, data_format=fmt)


async def write_bit_in_word(
    client: AsyncHostLinkClient,
    device: str,
    bit_index: int,
    value: bool,
) -> None:
    """Set or clear a single bit within a word device (read-modify-write).

    Args:
        client: Connected AsyncHostLinkClient.
        device: Word device address string, e.g. "DM100".
        bit_index: Bit position within the word (0–15).
        value: New bit state.
    """
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit_index must be 0-15, got {bit_index}")
    result = await client.read(device, data_format=".U")
    values = result if isinstance(result, list) else [result]
    current = int(values[0]) if isinstance(values[0], str) else int(values[0])
    if value:
        current |= 1 << bit_index
    else:
        current &= ~(1 << bit_index)
    await client.write(device, current & 0xFFFF, data_format=".U")


async def read_named(
    client: AsyncHostLinkClient,
    addresses: list[str],
) -> dict[str, int | float | bool | str]:
    """Read multiple devices by address string and return results as a dict.

    Address format examples:

    - ``"DM100"`` — unsigned 16-bit int
    - ``"DM100:F"`` — float
    - ``"DM100:S"`` — signed 16-bit int
    - ``"DM100:D"`` — unsigned 32-bit int
    - ``"DM100:L"`` — signed 32-bit int
    - ``"DM100.3"`` — bit 3 within word (bool)

    Args:
        client: Connected AsyncHostLinkClient.
        addresses: List of address strings.

    Returns:
        Dictionary mapping each address string to its value.
    """
    result: dict[str, int | float | bool | str] = {}
    for address in addresses:
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            raw = await client.read(base, data_format=".U")
            values = raw if isinstance(raw, list) else [raw]
            w = int(values[0]) if isinstance(values[0], str) else int(values[0])
            result[address] = bool((w >> (bit_idx or 0)) & 1)
        else:
            result[address] = await read_typed(client, base, dtype)
    return result


async def poll(
    client: AsyncHostLinkClient,
    addresses: list[str],
    interval: float,
) -> AsyncIterator[dict[str, int | float | bool | str]]:
    """Yield a snapshot of all devices every *interval* seconds.

    Args:
        client: Connected AsyncHostLinkClient.
        addresses: Address strings (same format as :func:`read_named`).
        interval: Poll interval in seconds.

    Usage::

        async for snapshot in poll(client, ["DM100", "DM200:F"], interval=0.5):
            print(snapshot)
    """
    while True:
        yield await read_named(client, addresses)
        await asyncio.sleep(interval)


def _parse_address(address: str) -> tuple[str, str, int | None]:
    """Parse extended address notation.

    Returns (base_device, dtype, bit_index).
    """
    if ":" in address:
        base, dtype = address.split(":", 1)
        return base.strip(), dtype.strip().upper(), None
    if "." in address:
        base, bit_str = address.split(".", 1)
        try:
            return base.strip(), "BIT_IN_WORD", int(bit_str, 16)
        except ValueError:
            pass
    return address.strip(), "U", None


async def read_words(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read *count* contiguous word values starting at *device*.

    Args:
        client: Connected AsyncHostLinkClient.
        device: Starting device address string, e.g. ``"DM100"``.
        count: Number of words to read.

    Returns:
        List of unsigned 16-bit integers.
    """
    values = await client.read_consecutive(device, count, data_format=".U")
    return [int(v) & 0xFFFF for v in values]


async def read_dwords(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read *count* contiguous DWord (32-bit unsigned) values starting at *device*.

    Reads ``count * 2`` words and combines adjacent word pairs (lo, hi).

    Args:
        client: Connected AsyncHostLinkClient.
        device: Starting device address string (must be a word device).
        count: Number of DWords to read.

    Returns:
        List of unsigned 32-bit integers.
    """
    words = await read_words(client, device, count * 2)
    return [(words[i] | (words[i + 1] << 16)) for i in range(0, count * 2, 2)]


async def open_and_connect(
    host: str,
    port: int = 8501,
    transport: str = "tcp",
    timeout: float = 3.0,
) -> AsyncHostLinkClient:
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
