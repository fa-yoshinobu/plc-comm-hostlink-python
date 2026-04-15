"""High-level helper API for user-facing Host Link workflows.

These helpers wrap :class:`hostlink.client.AsyncHostLinkClient` with typed
operations that are easier to consume than the token-oriented low-level API.
They are the intended source for generated user-facing Python API
documentation.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .device import DEFAULT_FORMAT_BY_DEVICE_TYPE, DeviceAddress, parse_device, parse_device_text
from .errors import HostLinkProtocolError

if TYPE_CHECKING:
    from .client import AsyncHostLinkClient


_OPTIMIZABLE_READ_NAMED_DEVICE_TYPES = frozenset(
    device_type for device_type, default_format in DEFAULT_FORMAT_BY_DEVICE_TYPE.items() if default_format == ".U"
)
_DIRECT_BIT_DEVICE_TYPES = frozenset(
    device_type for device_type, default_format in DEFAULT_FORMAT_BY_DEVICE_TYPE.items() if default_format == ""
)

_READ_PLAN_WORD_WIDTH = {
    "U": 1,
    "S": 1,
    "D": 2,
    "L": 2,
    "F": 2,
    "BIT_IN_WORD": 1,
    "DIRECT_BIT": 1,
}


@dataclass(frozen=True)
class _ReadPlanRequest:
    index: int
    address: str
    base_address: DeviceAddress
    kind: str
    bit_index: int = 0


@dataclass(frozen=True)
class _ReadPlanSegment:
    start_address: DeviceAddress
    start_number: int
    count: int
    mode: str
    requests: tuple[_ReadPlanRequest, ...]


@dataclass(frozen=True)
class _CompiledReadNamedPlan:
    requests_in_input_order: tuple[_ReadPlanRequest, ...]
    segments: tuple[_ReadPlanSegment, ...]


@dataclass(frozen=True)
class HostLinkConnectionOptions:
    """Stable connection settings for one Host Link session.

    The dataclass is the preferred input for :func:`open_and_connect` because
    it keeps transport, timeout, and framing options together in one explicit
    object.

    Attributes:
        host: PLC hostname or IP address.
        port: Host Link port number.
        transport: Transport name such as ``"tcp"`` or ``"udp"``.
        timeout: Socket timeout in seconds.
        append_lf_on_send: Whether an LF byte is appended after the trailing
            CR on transmitted commands.
    """

    host: str
    port: int = 8501
    transport: str = "tcp"
    timeout: float = 3.0
    append_lf_on_send: bool = False


async def read_typed(
    client: AsyncHostLinkClient,
    device: str,
    dtype: str,
) -> int | float | bool | str:
    """
    Read a single device value through the high-level helper API.

    The base device address is supplied separately from the data type code.
    For example, use ``device="DM100"`` and ``dtype="D"`` rather than the
    low-level style ``"DM100.D"``.

    Supported data type codes are:

    - ``"U"``: unsigned 16-bit integer
    - ``"S"``: signed 16-bit integer
    - ``"D"``: unsigned 32-bit integer
    - ``"L"``: signed 32-bit integer
    - ``"F"``: IEEE 754 float32

    The ``"F"`` helper is implemented by reading two consecutive ``.U`` words
    and converting them into a Python ``float``.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base device address such as ``"DM100"``.
        dtype: High-level data type code.

    Returns:
        The converted value. Integer formats return ``int`` and ``"F"``
        returns ``float``.

    Raises:
        HostLinkProtocolError: If the PLC reply does not contain a value.

    Examples:
        Read an unsigned word::

            value = await read_typed(client, "DM100", "U")

        Read a float32 from two words::

            temperature = await read_typed(client, "DM200", "F")
    """
    key = dtype.upper().lstrip(".").strip()
    if key == "":
        addr = parse_device(device)
        suffix = DEFAULT_FORMAT_BY_DEVICE_TYPE.get(addr.device_type, "")
        key = suffix.lstrip(".") if suffix else "BIT"

    if key == "BIT":
        raw = await client.read(device, data_format=None)
        values = raw if isinstance(raw, list) else [raw]
        if not values:
            raise HostLinkProtocolError(f"No value returned for {device!r}")
        return _parse_bool_token(values[0])

    if key == "F":
        lo_word, hi_word = await read_words(client, device, 2)
        return _words_to_float32(lo_word, hi_word)
    fmt = f".{key}"
    result = await client.read(device, data_format=fmt)
    values = result if isinstance(result, list) else [result]
    if not values:
        raise HostLinkProtocolError(f"No value returned for {device!r}")
    raw = values[0]
    return int(raw) if isinstance(raw, str) else raw


async def read_comments(
    client: AsyncHostLinkClient,
    device: str,
    *,
    strip_padding: bool = True,
) -> str:
    """Read one PLC comment string through the high-level helper API.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base device address such as ``"DM100"``.
        strip_padding: Whether to trim trailing spaces from the fixed-width
            Host Link ``RDC`` response.

    Returns:
        The PLC comment text for ``device``.
    """

    return await client.read_comments(device, strip_padding=strip_padding)


async def write_typed(
    client: AsyncHostLinkClient,
    device: str,
    dtype: str,
    value: int | float | bool | str,
) -> None:
    """
    Write a single device value through the high-level helper API.

    Supported data type codes are the same as :func:`read_typed`. For
    ``dtype="F"``, the helper converts the Python value to IEEE 754 float32
    and writes two consecutive ``.U`` words.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base device address such as ``"DM100"``.
        dtype: High-level data type code.
        value: Value to write. ``float`` is supported only with ``dtype="F"``.

    Examples:
        Write a signed 16-bit value::

            await write_typed(client, "DM10", "S", -123)

        Write a float32 value::

            await write_typed(client, "DM200", "F", 12.5)
    """
    key = dtype.upper().lstrip(".").strip()
    if key == "":
        addr = parse_device(device)
        suffix = DEFAULT_FORMAT_BY_DEVICE_TYPE.get(addr.device_type, "")
        key = suffix.lstrip(".") if suffix else "BIT"

    if key == "F":
        lo_word, hi_word = _float32_to_words(float(value))
        await client.write_consecutive(device, [lo_word, hi_word], data_format=".U")
        return
    if key == "BIT":
        await client.write(device, 1 if bool(value) else 0, data_format=None)
        return
    fmt = f".{key}"
    write_val: int | str = str(value) if isinstance(value, float) else value  # type: ignore[assignment]
    await client.write(device, write_val, data_format=fmt)


def _parse_bool_token(token: int | str) -> bool:
    if isinstance(token, int):
        return token != 0
    text = token.strip().upper()
    if text in {"1", "ON", "TRUE"}:
        return True
    if text in {"0", "OFF", "FALSE"}:
        return False
    raise HostLinkProtocolError(f"Invalid direct bit response token: {token!r}")


async def write_bit_in_word(
    client: AsyncHostLinkClient,
    device: str,
    bit_index: int,
    value: bool,
) -> None:
    """Set or clear a single bit inside a word device.

    This helper performs a read-modify-write cycle against a word-oriented
    device such as ``DM``, rather than issuing a force-set or force-reset
    command against a bit device family.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base word device address such as ``"DM100"``.
        bit_index: Bit position within the word, in the range ``0`` to ``15``.
        value: New bit state.

    Raises:
        ValueError: If ``bit_index`` is outside ``0`` to ``15``.

    Examples:
        Set bit 3 in ``DM100``::

            await write_bit_in_word(client, "DM100", 3, True)
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
    """Read multiple named values and return a snapshot dictionary.

    Each input string describes both the base device and the desired
    interpretation. The returned dictionary preserves the original address
    strings as keys.

    Address format examples:

    - ``"DM100"`` -- unsigned 16-bit int
    - ``"DM100:F"`` -- float
    - ``"DM100:S"`` -- signed 16-bit int
    - ``"DM100:D"`` -- unsigned 32-bit int
    - ``"DM100:L"`` -- signed 32-bit int
    - ``"DM100.3"`` -- bit 3 within word (bool)
    - ``"DM100.A"`` -- bit 10 within word (bool); bits 10-15 use hex digits A-F
    - ``"DM100:COMMENT"`` -- PLC comment text (str)

    Bit-in-word indices use hexadecimal notation (0-F), matching the KEYENCE address
    format. Bits 0-9 can be written as decimal digits; bits 10-15 must be written as
    ``A``-``F``. For example, bit 12 is ``"DM100.C"``, not ``"DM100.12"``.

    When all requested addresses are compatible with helper-layer batching, this
    function automatically merges contiguous reads into one or more ``RDS``
    requests. Mixed or non-optimizable address sets fall back to sequential
    helper reads with the same return shape.

    Args:
        client: Connected asynchronous Host Link client.
        addresses: Address strings to read in one logical snapshot.

    Returns:
        Dictionary mapping each original address string to its decoded value.

    Examples:
        Read mixed integer, float, and bit-in-word values::

            snapshot = await read_named(client, ["DM10", "DM20:F", "DM30.A"])
    """
    if not addresses:
        return {}

    plan = _try_compile_read_named_plan(addresses)
    if plan is not None:
        return await _execute_read_named_plan(client, plan)

    return await _read_named_sequential(client, addresses)


async def poll(
    client: AsyncHostLinkClient,
    addresses: list[str],
    interval: float,
) -> AsyncIterator[dict[str, int | float | bool | str]]:
    """Continuously yield snapshots for the specified addresses.

    Address parsing and return values follow the same rules as
    :func:`read_named`. If the address set can be batched, the compiled read
    plan is reused on every iteration.

    Args:
        client: Connected asynchronous Host Link client.
        addresses: Address strings in :func:`read_named` format.
        interval: Delay in seconds between snapshots.

    Yields:
        A dictionary for each polling cycle, keyed by the original address
        strings.

    Usage::

        async for snapshot in poll(client, ["DM100", "DM200:F"], interval=0.5):
            print(snapshot)
    """
    plan = _try_compile_read_named_plan(addresses) if addresses else None
    while True:
        if plan is not None:
            yield await _execute_read_named_plan(client, plan)
        else:
            yield await _read_named_sequential(client, addresses)
        await asyncio.sleep(interval)


def _parse_address(address: str) -> tuple[str, str, int | None]:
    """Parse extended address notation.

    Returns (base_device, dtype, bit_index).
    Bit indices are interpreted as hexadecimal (0-F). Bits 10-15 must be
    written as A-F (e.g. ``"DM100.A"`` = bit 10, ``"DM100.F"`` = bit 15).
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
    parsed = parse_device(address)
    if parsed.suffix:
        return address.strip(), parsed.suffix.lstrip(".").upper(), None
    suffix = DEFAULT_FORMAT_BY_DEVICE_TYPE.get(parsed.device_type, "")
    dtype = suffix.lstrip(".") if suffix else ""
    return address.strip(), dtype, None


async def _read_named_sequential(
    client: AsyncHostLinkClient,
    addresses: list[str],
) -> dict[str, int | float | bool | str]:
    result: dict[str, int | float | bool | str] = {}
    for address in addresses:
        base, dtype, bit_idx = _parse_address(address)
        if dtype == "BIT_IN_WORD":
            raw = await client.read(base, data_format=".U")
            values = raw if isinstance(raw, list) else [raw]
            word = int(values[0]) if isinstance(values[0], str) else int(values[0])
            result[address] = bool((word >> (bit_idx or 0)) & 1)
        elif dtype == "COMMENT":
            result[address] = await read_comments(client, base)
        else:
            result[address] = await read_typed(client, base, dtype)
    return result


def _try_compile_read_named_plan(addresses: list[str]) -> _CompiledReadNamedPlan | None:
    requests_in_input_order: list[_ReadPlanRequest] = []
    requests_by_device_type: dict[str, list[_ReadPlanRequest]] = {}

    for index, address in enumerate(addresses):
        request = _try_parse_optimizable_read_named_request(address, index)
        if request is None:
            return None

        requests_in_input_order.append(request)
        requests_by_device_type.setdefault(request.base_address.device_type, []).append(request)

    segments: list[_ReadPlanSegment] = []
    for bucket in requests_by_device_type.values():
        sorted_requests = sorted(
            bucket,
            key=lambda req: (req.base_address.number, -_get_word_width(req.kind)),
        )

        pending: list[_ReadPlanRequest] = []
        current_start: DeviceAddress | None = None
        current_start_number = 0
        current_end_exclusive = 0
        current_mode = "WORDS"

        for request in sorted_requests:
            request_start = request.base_address.number
            request_end_exclusive = request_start + _get_word_width(request.kind)
            request_mode = "DIRECT_BITS" if request.kind == "DIRECT_BIT" else "WORDS"

            if current_start is None or request_start > current_end_exclusive or current_mode != request_mode:
                if current_start is not None:
                    segments.append(
                        _ReadPlanSegment(
                            start_address=current_start,
                            start_number=current_start_number,
                            count=current_end_exclusive - current_start_number,
                            mode=current_mode,
                            requests=tuple(pending),
                        )
                    )
                    pending.clear()

                current_start = DeviceAddress(request.base_address.device_type, request.base_address.number, "")
                current_start_number = request_start
                current_end_exclusive = request_end_exclusive
                current_mode = request_mode
            elif request_end_exclusive > current_end_exclusive:
                current_end_exclusive = request_end_exclusive

            pending.append(request)

        if current_start is not None:
            segments.append(
                _ReadPlanSegment(
                    start_address=current_start,
                    start_number=current_start_number,
                    count=current_end_exclusive - current_start_number,
                    mode=current_mode,
                    requests=tuple(pending),
                )
            )

    return _CompiledReadNamedPlan(
        requests_in_input_order=tuple(requests_in_input_order),
        segments=tuple(segments),
    )


def _try_parse_optimizable_read_named_request(address: str, index: int) -> _ReadPlanRequest | None:
    base_addr, dtype, bit_idx = _parse_address(address)
    parsed = parse_device(base_addr)

    if parsed.suffix:
        return None
    if dtype == "" and parsed.device_type in _DIRECT_BIT_DEVICE_TYPES:
        return _ReadPlanRequest(
            index=index,
            address=address,
            base_address=parsed,
            kind="DIRECT_BIT",
        )
    if parsed.device_type not in _OPTIMIZABLE_READ_NAMED_DEVICE_TYPES:
        return None

    if dtype == "BIT_IN_WORD":
        return _ReadPlanRequest(
            index=index,
            address=address,
            base_address=parsed,
            kind="BIT_IN_WORD",
            bit_index=bit_idx or 0,
        )

    if dtype not in {"U", "S", "D", "L", "F"}:
        return None

    return _ReadPlanRequest(
        index=index,
        address=address,
        base_address=parsed,
        kind=dtype,
    )


async def _execute_read_named_plan(
    client: AsyncHostLinkClient,
    plan: _CompiledReadNamedPlan,
) -> dict[str, int | float | bool | str]:
    resolved: list[int | float | bool | str | None] = [None] * len(plan.requests_in_input_order)

    for segment in plan.segments:
        if segment.mode == "DIRECT_BITS":
            tokens = await client.read_consecutive(segment.start_address.to_text(), segment.count, data_format=None)
            for request in segment.requests:
                offset = request.base_address.number - segment.start_number
                resolved[request.index] = _resolve_direct_bit_value(tokens, offset)
        else:
            words = await read_words(client, segment.start_address.to_text(), segment.count)
            for request in segment.requests:
                offset = request.base_address.number - segment.start_number
                resolved[request.index] = _resolve_planned_value(words, offset, request.kind, request.bit_index)

    result: dict[str, int | float | bool | str] = {}
    for request in plan.requests_in_input_order:
        value = resolved[request.index]
        if value is None:
            raise HostLinkProtocolError(f"No value resolved for {request.address!r}")
        result[request.address] = value
    return result


def _resolve_planned_value(words: list[int], offset: int, kind: str, bit_index: int) -> int | float | bool:
    if kind == "U":
        return words[offset]
    if kind == "S":
        value = words[offset]
        return value if value < 0x8000 else value - 0x10000
    if kind == "D":
        return words[offset] | (words[offset + 1] << 16)
    if kind == "L":
        value = words[offset] | (words[offset + 1] << 16)
        return value if value < 0x80000000 else value - 0x100000000
    if kind == "F":
        return _words_to_float32(words[offset], words[offset + 1])
    if kind == "BIT_IN_WORD":
        return bool((words[offset] >> bit_index) & 1)
    if kind == "DIRECT_BIT":
        raise HostLinkProtocolError("Direct bit values must be resolved from bit tokens.")
    raise HostLinkProtocolError(f"Unsupported read plan value kind: {kind}")


def _resolve_direct_bit_value(tokens: list[int | str], offset: int) -> bool:
    try:
        return _parse_bool_token(tokens[offset])
    except IndexError as exc:
        raise HostLinkProtocolError("Batched direct bit response was too short") from exc


def _get_word_width(kind: str) -> int:
    width = _READ_PLAN_WORD_WIDTH.get(kind)
    if width is None:
        raise HostLinkProtocolError(f"Unsupported read plan value kind: {kind}")
    return width


def _words_to_float32(lo_word: int, hi_word: int) -> float:
    bits = (lo_word & 0xFFFF) | ((hi_word & 0xFFFF) << 16)
    return cast(float, struct.unpack("<f", struct.pack("<I", bits))[0])


def _float32_to_words(value: float) -> tuple[int, int]:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return bits & 0xFFFF, (bits >> 16) & 0xFFFF


def normalize_address(address: str, *, default_suffix: str = "") -> str:
    """Return the canonical Host Link device string.

    The helper normalizes device-family spelling, trims whitespace, and keeps
    explicit dtype or bit-in-word intent when present.

    Args:
        address: User-facing address such as ``"dm100:f"`` or ``"DM100.a"``.
        default_suffix: Optional default format used by :func:`parse_device_text`.

    Returns:
        Canonical uppercase address text.
    """

    base, dtype, bit_index = _parse_address(address)
    base_text = parse_device_text(base, default_suffix=default_suffix)
    if dtype == "BIT_IN_WORD":
        assert bit_index is not None
        return f"{base_text}.{format(bit_index, 'X')}"
    if ":" in address:
        return f"{base_text}:{dtype}"
    return base_text


async def read_words_single_request(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous unsigned words using one PLC request.

    This helper is the explicit atomic path for one consecutive read. If the
    caller wants multiple protocol requests, use :func:`read_words_chunked`
    instead.
    """

    values = await client.read_consecutive(device, count, data_format=".U")
    return [int(v) & 0xFFFF for v in values]


async def read_dwords_single_request(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous unsigned dwords using one PLC request.

    Adjacent word pairs are combined in low-word, high-word order. The helper
    never silently splits the logical request.
    """

    words = await read_words_single_request(client, device, count * 2)
    return [(words[i] | (words[i + 1] << 16)) for i in range(0, count * 2, 2)]


async def write_words_single_request(
    client: AsyncHostLinkClient,
    device: str,
    values: list[int],
) -> None:
    """Write contiguous unsigned words using one PLC request.

    This helper is intended for ranges that should remain one logical Host
    Link write. Use :func:`write_words_chunked` only when multiple requests are
    acceptable to the caller.
    """

    await client.write_consecutive(device, [int(value) & 0xFFFF for value in values], data_format=".U")


async def write_dwords_single_request(
    client: AsyncHostLinkClient,
    device: str,
    values: list[int],
) -> None:
    """Write contiguous unsigned dwords using one PLC request.

    Each Python ``int`` is encoded as two ``.U`` words in low-word, high-word
    order before the consecutive write is sent.
    """

    words: list[int] = []
    for value in values:
        words.extend((int(value) & 0xFFFF, (int(value) >> 16) & 0xFFFF))
    await write_words_single_request(client, device, words)


async def read_words_chunked(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
    max_per_request: int = 1000,
) -> list[int]:
    """Read contiguous unsigned words across multiple aligned requests.

    Chunking is explicit here. The helper aligns chunk sizes so the related
    dword helper can reuse the same boundary rules safely.
    """

    effective_max = max(1, (max_per_request // 2) * 2)
    start = parse_device(device)
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, effective_max)
        chunk_device = DeviceAddress(start.device_type, start.number + offset, "").to_text()
        result.extend(await read_words_single_request(client, chunk_device, chunk))
        offset += chunk
        remaining -= chunk
    return result


async def read_dwords_chunked(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
    max_dwords_per_request: int = 500,
) -> list[int]:
    """Read contiguous unsigned dwords across multiple aligned requests.

    Chunk boundaries are aligned to full 32-bit values so one dword is never
    torn across requests.
    """

    if max_dwords_per_request <= 0:
        raise ValueError("max_dwords_per_request must be at least 1")
    start = parse_device(device)
    result: list[int] = []
    remaining = count
    offset = 0
    while remaining > 0:
        chunk = min(remaining, max_dwords_per_request)
        chunk_device = DeviceAddress(start.device_type, start.number + (offset * 2), "").to_text()
        result.extend(await read_dwords_single_request(client, chunk_device, chunk))
        offset += chunk
        remaining -= chunk
    return result


async def write_words_chunked(
    client: AsyncHostLinkClient,
    device: str,
    values: list[int],
    max_per_request: int = 1000,
) -> None:
    """Write contiguous unsigned words across multiple aligned requests.

    Use this helper only when multi-request write semantics are acceptable to
    the caller.
    """

    effective_max = max(1, (max_per_request // 2) * 2)
    start = parse_device(device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, effective_max)
        chunk_device = DeviceAddress(start.device_type, start.number + offset, "").to_text()
        await write_words_single_request(client, chunk_device, values[offset : offset + chunk])
        offset += chunk


async def write_dwords_chunked(
    client: AsyncHostLinkClient,
    device: str,
    values: list[int],
    max_dwords_per_request: int = 500,
) -> None:
    """Write contiguous unsigned dwords across multiple aligned requests.

    Each chunk boundary is aligned to full dwords so one 32-bit value remains
    intact inside one request.
    """

    if max_dwords_per_request <= 0:
        raise ValueError("max_dwords_per_request must be at least 1")
    start = parse_device(device)
    offset = 0
    while offset < len(values):
        chunk = min(len(values) - offset, max_dwords_per_request)
        chunk_device = DeviceAddress(start.device_type, start.number + (offset * 2), "").to_text()
        await write_dwords_single_request(client, chunk_device, values[offset : offset + chunk])
        offset += chunk


async def read_words(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous 16-bit unsigned words starting at ``device``.

    This helper wraps the low-level consecutive read and converts the PLC reply
    to Python ``int`` values.

    Args:
        client: Connected asynchronous Host Link client.
        device: Starting base device address such as ``"DM100"``.
        count: Number of 16-bit words to read.

    Returns:
        A list of unsigned word values in PLC order.
    """
    return await read_words_single_request(client, device, count)


async def read_dwords(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous unsigned 32-bit values starting at ``device``.

    Adjacent word pairs are combined in low-word, high-word order, which
    matches the helper-layer interpretation used by :func:`read_typed` for
    ``dtype="D"`` and ``dtype="F"``.

    Args:
        client: Connected asynchronous Host Link client.
        device: Starting base device address such as ``"DM0"``.
        count: Number of 32-bit values to read.

    Returns:
        A list of Python ``int`` values.
    """
    return await read_dwords_single_request(client, device, count)


async def open_and_connect(
    host: str | HostLinkConnectionOptions,
    port: int = 8501,
    transport: str = "tcp",
    timeout: float = 3.0,
    append_lf_on_send: bool = False,
) -> AsyncHostLinkClient:
    """
    Create and connect an :class:`AsyncHostLinkClient`.

    This is the recommended entry point for user code and examples because it
    returns a ready-to-use client in one step. It is equivalent to creating a
    client with ``auto_connect=False`` and then calling ``await client.connect()``.

    Args:
        host: PLC IP address, hostname, or a :class:`HostLinkConnectionOptions`
            instance.
        port: Host Link port. Defaults to ``8501``.
        transport: Transport string such as ``"tcp"`` or ``"udp"``.
        timeout: Socket timeout in seconds.
        append_lf_on_send: Whether an LF byte is appended after the terminating
            CR when sending commands.

    Returns:
        A connected :class:`AsyncHostLinkClient`.

    Usage::

        client = await open_and_connect("192.168.250.100")
        async with client:
            values = await read_words(client, "DM100", 10)
    """
    from .client import AsyncHostLinkClient

    if isinstance(host, HostLinkConnectionOptions):
        options = host
    else:
        options = HostLinkConnectionOptions(
            host,
            port=port,
            transport=transport,
            timeout=timeout,
            append_lf_on_send=append_lf_on_send,
        )

    client = AsyncHostLinkClient(
        options.host,
        port=options.port,
        transport=options.transport,
        timeout=options.timeout,
        append_lf_on_send=options.append_lf_on_send,
        auto_connect=False,
    )
    await client.connect()
    return client
