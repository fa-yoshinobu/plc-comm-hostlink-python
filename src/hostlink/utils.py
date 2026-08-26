"""High-level helper API for user-facing Host Link workflows.

These helpers wrap :class:`hostlink.client.AsyncHostLinkClient` with typed
operations that are easier to consume than the token-oriented low-level API.
They are the intended source for generated user-facing Python API
documentation.
"""

from __future__ import annotations

import asyncio
import math
import re
import struct
import warnings
from collections.abc import AsyncIterator, Sequence
from dataclasses import KW_ONLY, dataclass
from ipaddress import ip_address
from typing import TYPE_CHECKING, cast

from .device import (
    BIT_BANK_DEVICE_TYPES,
    DEFAULT_FORMAT_BY_DEVICE_TYPE,
    NATIVE_32BIT_DEVICE_TYPES,
    RDC_DEVICE_TYPES,
    DeviceAddress,
    bit_bank_logical_number,
    bit_bank_number_from_logical,
    is_float32_eligible_device_type,
    normalize_suffix,
    parse_device,
    parse_device_text,
    validate_device_count,
    validate_device_span,
)
from .errors import HostLinkProtocolError
from .protocol import HostLinkCommentEncoding, require_comment_encoding

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
    it keeps endpoint and timeout options together in one explicit
    object.

    Attributes:
        host: PLC hostname or IP address.
        plc_profile: Canonical KEYENCE KV PLC profile for the session.
        port: Host Link port number.
        transport: Transport name such as ``"tcp"`` or ``"udp"``.
        timeout: Absolute per-request transaction deadline in seconds.
        connect_timeout: Separate connection-establishment deadline in seconds.
    """

    host: str
    _: KW_ONLY
    plc_profile: str
    port: int
    transport: str
    timeout: float = 3.0
    connect_timeout: float = 3.0

    def __post_init__(self) -> None:
        from .plc_profiles import normalize_plc_profile

        if self.plc_profile is None:
            raise ValueError(
                "plc_profile is required. Use an explicit canonical PLC profile such as 'keyence:kv-8000'."
            )

        object.__setattr__(self, "plc_profile", normalize_plc_profile(self.plc_profile))
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host is required and must be a non-empty string")
        normalized_host = self.host.strip()
        if normalized_host.startswith("[") and normalized_host.endswith("]"):
            try:
                bracketed_literal = ip_address(normalized_host[1:-1])
            except ValueError:
                pass
            else:
                if bracketed_literal.version == 4:
                    raise ValueError("host must not use brackets around an IPv4 address")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port is required and must be an integer in the range 1..65535")
        if not isinstance(self.transport, str) or self.transport.strip().lower() not in {"tcp", "udp"}:
            raise ValueError("transport must be 'tcp' or 'udp'")
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(self.timeout)
            or self.timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number")
        if (
            isinstance(self.connect_timeout, bool)
            or not isinstance(self.connect_timeout, (int, float))
            or not math.isfinite(self.connect_timeout)
            or self.connect_timeout <= 0
        ):
            raise ValueError("connect_timeout must be a positive finite number")
        object.__setattr__(self, "host", normalized_host)
        object.__setattr__(self, "transport", self.transport.strip().lower())


@dataclass(frozen=True)
class HostLinkAddress:
    """Parsed public Host Link address helper result.

    Attributes:
        text: Canonical address text, preserving logical helper notation such
            as ``"DM100:F"`` or ``"DM100.A"``.
        base_device: Canonical base device token used by low-level Host Link
            commands.
        dtype: Logical data type code such as ``"U"``, ``"D"``, ``"F"``,
            ``"COMMENT"``, or ``"BIT_IN_WORD"``.
        bit_index: Bit index for ``"BIT_IN_WORD"`` addresses, otherwise
            ``None``.
    """

    text: str
    base_device: str
    dtype: str
    bit_index: int | None = None

    @property
    def is_bit_in_word(self) -> bool:
        """Whether this address targets one bit inside a word device."""

        return self.dtype == "BIT_IN_WORD"


@dataclass(frozen=True)
class TimerCounterValue:
    """Composite timer/counter read result.

    Host Link ``RD Tn.D`` and ``RD Cn.D`` replies contain the contact/status,
    current value, and preset value in that order.
    """

    status: int
    current: int
    preset: int


def parse_address(address: str) -> HostLinkAddress:
    """Parse a public Host Link helper address.

    This is the public companion to :func:`normalize_address`. It keeps UI and
    adapter code from duplicating private parser details while preserving the
    logical helper forms accepted by :func:`read_named`.

    Args:
        address: User-facing address such as ``"dm100:u"``, ``"dm100:f"``, or
            ``"dm100.a"``. Bare base-device addresses are rejected because the
            data type must be explicit.

    Returns:
        A :class:`HostLinkAddress` with canonical text and parsed metadata.

    Examples:
        Parse a bit-in-word address::

            parsed = parse_address("dm100.a")
            assert parsed.text == "DM100.A"
            assert parsed.bit_index == 10
    """

    base_raw, dtype, bit_index = _parse_address(address)
    base_device = parse_device_text(base_raw)
    _validate_address_semantics(address, parse_device(base_device), dtype)
    if dtype == "BIT_IN_WORD":
        bit_index = _require_bit_in_word_index(address, bit_index)
        canonical = f"{base_device}.{format(bit_index, 'X')}"
    elif dtype:
        canonical = f"{base_device}:{dtype}"
    else:
        raise ValueError(f"Address {address!r} requires an explicit data type such as ':U', ':D', or ':BIT'.")
    return HostLinkAddress(canonical, base_device, dtype, bit_index)


def try_parse_address(address: str) -> HostLinkAddress | None:
    """Try to parse a public Host Link helper address.

    Args:
        address: User-facing address text.

    Returns:
        A parsed :class:`HostLinkAddress`, or ``None`` if validation fails.
    """

    try:
        return parse_address(address)
    except (HostLinkProtocolError, ValueError):
        return None


def format_address(address: HostLinkAddress | str) -> str:
    """Return canonical Host Link helper address text.

    Parsed objects are formatted from their semantic fields and validated by
    the same device/data-type rules as :func:`parse_address`. The ``text``
    field is not trusted as an alternate representation.

    Args:
        address: A parsed :class:`HostLinkAddress` or raw address string.

    Returns:
        Canonical address text.
    """

    if isinstance(address, HostLinkAddress):
        base_device = parse_device_text(address.base_device)
        dtype = _normalize_helper_dtype(address.dtype)
        if dtype == "BIT_IN_WORD":
            bit_index = _require_bit_in_word_index(address.text, address.bit_index)
            candidate = f"{base_device}.{format(bit_index, 'X')}"
        else:
            if address.bit_index is not None:
                raise ValueError("bit_index is only valid when dtype is BIT_IN_WORD")
            candidate = f"{base_device}:{dtype}"
        return parse_address(candidate).text
    return normalize_address(address)


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
    - ``"H"``: hexadecimal 16-bit word text

    The ``"F"`` helper is implemented by reading two consecutive ``.U`` words
    and converting them into a Python ``float``.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base device address such as ``"DM100"``.
        dtype: High-level data type code.

    Returns:
        The converted value. Integer formats return ``int``, ``"F"`` returns
        ``float``, and ``"H"`` returns uppercase hexadecimal ``str``.

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
        raise ValueError("dtype is required; specify 'U', 'S', 'D', 'L', 'F', 'H', or 'BIT'.")

    if key == "BIT":
        raw = await client.read(device, data_format=None)
        values = raw if isinstance(raw, list) else [raw]
        if not values:
            raise HostLinkProtocolError(f"No value returned for {device!r}")
        return _parse_bool_token(values[0])

    addr = parse_device(device)
    if key == "F":
        if not is_float32_eligible_device_type(addr.device_type):
            raise HostLinkProtocolError(
                f"Float32 reads require an ordinary word-device family; {addr.device_type!r} is not eligible."
            )
        lo_word, hi_word = await read_words_single_request(client, device, 2)
        return _words_to_float32(lo_word, hi_word)

    fmt = f".{key}"
    result = await client.read(device, data_format=fmt)
    values = result if isinstance(result, list) else [result]
    if not values:
        raise HostLinkProtocolError(f"No value returned for {device!r}")
    if addr.device_type in {"T", "C"} and key in {"U", "S", "D", "L", "H"}:
        raw = values[-1]
        if key == "H":
            return str(raw).strip().upper()
        return int(raw) if isinstance(raw, str) else raw
    raw = values[0]
    if key == "H":
        return str(raw).strip().upper()
    return int(raw) if isinstance(raw, str) else raw


async def read_timer_counter(client: AsyncHostLinkClient, device: str) -> TimerCounterValue:
    """Read a timer/counter composite value as status, current, and preset.

    The response status must be exactly ``0`` or ``1``.

    Existing :func:`read_typed` and :func:`read_named` keep their compatibility
    behavior of returning the preset value for ``T``/``C`` devices. Use this
    helper when the contact/status or current value is required too.
    """

    addr = parse_device(device)
    if addr.device_type not in {"T", "C"}:
        raise HostLinkProtocolError("read_timer_counter requires a T or C device.")

    target = DeviceAddress(addr.device_type, addr.number, "").to_text()
    result = await client.read(target, data_format=".D")
    values = result if isinstance(result, list) else [result]
    if len(values) < 3:
        raise HostLinkProtocolError(f"Timer/counter response for {target!r} did not contain status/current/preset.")
    return TimerCounterValue(
        status=int(values[0]),
        current=int(values[1]),
        preset=int(values[2]),
    )


async def read_timer(client: AsyncHostLinkClient, device: str) -> TimerCounterValue:
    """Read a timer composite value."""

    if parse_device(device).device_type != "T":
        raise HostLinkProtocolError("read_timer requires a T device.")
    return await read_timer_counter(client, device)


async def read_counter(client: AsyncHostLinkClient, device: str) -> TimerCounterValue:
    """Read a counter composite value."""

    if parse_device(device).device_type != "C":
        raise HostLinkProtocolError("read_counter requires a C device.")
    return await read_timer_counter(client, device)


async def read_comments(
    client: AsyncHostLinkClient,
    device: str,
    encoding: HostLinkCommentEncoding,
) -> str:
    """Read one PLC comment string using exactly the selected codec.

    Args:
        client: Connected asynchronous Host Link client.
        device: Base device address such as ``"DM100"``.
        encoding: Explicit UTF-8 or CP932/Windows-31J selection.

    Returns:
        The PLC comment text for ``device``.
    """

    return await client.read_comments(device, require_comment_encoding(encoding))


async def read_comment_bytes(
    client: AsyncHostLinkClient,
    device: str,
) -> bytes:
    """Read exact PLC comment payload bytes without CR/LF framing."""

    return await client.read_comment_bytes(device)


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
        raise ValueError("dtype is required; specify 'U', 'S', 'D', 'L', 'F', 'H', or 'BIT'.")

    if key == "F":
        addr = parse_device(device)
        if not is_float32_eligible_device_type(addr.device_type):
            raise ValueError(
                f"Float32 writes require an ordinary word-device family; {addr.device_type!r} is not eligible."
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Float value must be finite, got {value!r}.")
        lo_word, hi_word = _float32_to_words(float(value))
        await client.write_consecutive(device, [lo_word, hi_word], data_format=".U")
        return
    if key == "BIT":
        await client.write(device, _parse_bit_write_value(value), data_format=None)
        return
    fmt = f".{key}"
    if key == "H" and isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[0-9A-Fa-f]{1,4}", text):
            raise ValueError(f"Invalid H value {value!r}; use 1..4 hexadecimal digits.")
        write_val: int | str = int(text, 16)
    elif type(value) is int:
        write_val = value
    else:
        raise ValueError(f"{key} value must be an integer, got {value!r}.")
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


def _parse_bit_write_value(value: int | float | bool | str) -> bool:
    if type(value) is bool:
        return value
    raise HostLinkProtocolError(f"Invalid BIT write value: {value!r}. Use bool.")


async def write_bit_in_word(
    client: AsyncHostLinkClient,
    device: str,
    bit_index: int,
    value: bool,
) -> None:
    """Set or clear one bit through an explicit 16-bit read-modify-write.

    The complete plan is validated before FIFO admission. One local FIFO turn
    and one absolute deadline then cover exactly one read and one write, even
    when the requested state is unchanged. This operation is not PLC-atomic:
    PLC logic or a different connection can update the word between requests,
    and that update can be lost. It performs no fallback, retry, or readback.
    """

    await client.write_bit_in_word(device, bit_index, value)


async def read_named(
    client: AsyncHostLinkClient,
    addresses: list[str],
    *,
    comment_encoding: HostLinkCommentEncoding | None = None,
) -> dict[str, int | float | bool | str]:
    """Read multiple named values and return a snapshot dictionary.

    Each input string describes both the base device and the desired
    interpretation. The returned dictionary preserves the original address
    strings as keys.

    Address format examples:

    - ``"DM100:U"`` -- unsigned 16-bit int
    - ``"DM100:F"`` -- float
    - ``"DM100:S"`` -- signed 16-bit int
    - ``"DM100:D"`` -- unsigned 32-bit int
    - ``"DM100:L"`` -- signed 32-bit int
    - ``"CR000:BIT"`` -- direct bit device (bool)
    - ``"DM100.3"`` -- bit 3 within word (bool)
    - ``"DM100.A"`` -- bit 10 within word (bool); bits 10-15 use hex digits A-F
    - ``"DM100:COMMENT"`` -- PLC comment text (str)

    Bit-in-word indices use hexadecimal notation (0-F), matching the KEYENCE address
    format. Bits 0-9 can be written as decimal digits; bits 10-15 must be written as
    ``A``-``F``. For example, bit 12 is ``"DM100.C"``, not ``"DM100.12"``.

    The entire input is validated before admission. Wire reads are grouped by
    device type in first-occurrence order, sorted by address within each group,
    and compatible contiguous or overlapping spans are merged up to request
    limits without splitting an individual entry. All requests run during one
    FIFO turn. Public keys remain in caller order. A multi-request result is not
    one atomic PLC-time observation, and an error returns no partial dictionary.

    Keys must be semantically unique after device family, numeric address,
    dtype, bit index, and scalar count are normalized. Spelling variants are
    rejected, while distinct dtype views, bit indices, and overlapping spans
    remain valid. Returned keys retain their original input spelling.

    Args:
        client: Connected asynchronous Host Link client.
        addresses: Address strings to read as one logical collection result.
        comment_encoding: Required explicit codec when any address uses
            ``:COMMENT``; omit it for collections without comments.

    Returns:
        Dictionary mapping each original address string to its decoded value.

    Examples:
        Read mixed integer, float, and bit-in-word values::

            read_result = await read_named(client, ["DM10:U", "DM20:F", "DM30.A"])
    """
    if not addresses:
        raise ValueError("read_named addresses must not be empty")

    plan = _compile_read_named_plan(addresses)
    selected_comment_encoding = _resolve_plan_comment_encoding(plan, comment_encoding)
    _preflight_read_named_plan(client, plan)
    return await _execute_read_named_plan(client, plan, selected_comment_encoding)


async def poll(
    client: AsyncHostLinkClient,
    addresses: list[str],
    interval: float,
    *,
    comment_encoding: HostLinkCommentEncoding | None = None,
) -> AsyncIterator[dict[str, int | float | bool | str]]:
    """Continuously yield read results for the specified addresses.

    Address parsing and return values follow the same rules as
    :func:`read_named`. The optimized read plan is compiled once and reused on
    every iteration. Each complete cycle owns one FIFO turn; yielding the sample
    and waiting for the post-cycle interval occur after releasing that turn.

    Args:
        client: Connected asynchronous Host Link client.
        addresses: Address strings in :func:`read_named` format.
        interval: Delay in seconds between read results.
        comment_encoding: Required explicit codec when any address uses
            ``:COMMENT``; omit it for collections without comments.

    Yields:
        A dictionary for each polling cycle, keyed by the original address
        strings.

    Usage::

        async for read_result in poll(client, ["DM100:U", "DM200:F"], interval=0.5):
            print(read_result)
    """
    if not addresses:
        raise ValueError("poll addresses must not be empty")
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(interval)
        or interval <= 0
    ):
        raise ValueError(f"interval must be a positive finite number, got {interval!r}")
    plan = _compile_read_named_plan(addresses)
    selected_comment_encoding = _resolve_plan_comment_encoding(plan, comment_encoding)
    _preflight_read_named_plan(client, plan)
    while True:
        yield await _execute_read_named_plan(client, plan, selected_comment_encoding)
        await asyncio.sleep(interval)


def _parse_address(address: str) -> tuple[str, str, int | None]:
    """Parse extended address notation.

    Returns (base_device, dtype, bit_index).
    Bit indices are interpreted as hexadecimal (0-F). Bits 10-15 must be
    written as A-F (e.g. ``"DM100.A"`` = bit 10, ``"DM100.F"`` = bit 15).
    """
    if ":" in address:
        base, dtype = address.split(":", 1)
        return base.strip(), _normalize_helper_dtype(dtype), None
    if "." in address:
        base, bit_str = address.split(".", 1)
        bit_text = bit_str.strip()
        if len(bit_text) == 1 and bit_text.upper() in "0123456789ABCDEF":
            return base.strip(), "BIT_IN_WORD", int(bit_text, 16)
        raise ValueError(f"Invalid bit-in-word index {bit_str!r}; use one hex digit 0-F or ':' for dtype.")
    parsed = parse_device(address)
    if parsed.suffix:
        return address.strip(), parsed.suffix.lstrip(".").upper(), None
    raise ValueError(f"Address {address!r} requires an explicit data type such as ':U', ':D', or ':BIT'.")


def _normalize_helper_dtype(dtype: str) -> str:
    key = dtype.strip().upper().lstrip(".")
    if key == "":
        raise ValueError("address data type is required; use ':U', ':D', ':F', ':BIT', or ':COMMENT'.")
    if key in {"BIT", "BIT_IN_WORD", "COMMENT", "F"}:
        return key
    return normalize_suffix(key).lstrip(".")


def _require_bit_in_word_index(address: str, bit_index: int | None) -> int:
    if bit_index is None:
        raise ValueError(f"bit-in-word address requires explicit bit index 0-F: {address!r}")
    if not 0 <= bit_index <= 15:
        raise ValueError(f"bit-in-word index must be 0-F: {address!r}")
    return bit_index


def _validate_address_semantics(address: str, device: DeviceAddress, dtype: str) -> None:
    """Validate device/data-type compatibility for every public address path."""

    if dtype == "BIT" and device.device_type not in _DIRECT_BIT_DEVICE_TYPES:
        raise ValueError(f"BIT is only valid for direct-bit devices: {address!r}")
    if dtype == "F" and not is_float32_eligible_device_type(device.device_type):
        raise ValueError(
            f"Float32 is valid only for ordinary word-device families, not {device.device_type!r}: {address!r}"
        )
    if dtype == "COMMENT" and device.device_type not in RDC_DEVICE_TYPES:
        raise ValueError(f"COMMENT is not valid for device family {device.device_type!r}: {address!r}")


def _compile_read_named_plan(addresses: list[str]) -> _CompiledReadNamedPlan:
    requests_in_input_order: list[_ReadPlanRequest] = []
    requests_by_device_type: dict[str, list[_ReadPlanRequest]] = {}
    semantic_keys: set[tuple[str, int, str, int | None, int]] = set()
    for index, address in enumerate(addresses):
        request = _parse_read_named_request(address, index)
        semantic_kind = request.kind.removeprefix("SINGLE_")
        if semantic_kind == "DIRECT_BIT":
            semantic_kind = "BIT"
        semantic_bit_index = request.bit_index if semantic_kind == "BIT_IN_WORD" else None
        semantic_key = (
            request.base_address.device_type,
            request.base_address.number,
            semantic_kind,
            semantic_bit_index,
            1,
        )
        if semantic_key in semantic_keys:
            raise ValueError(f"Named read address {address!r} is semantically duplicated.")
        semantic_keys.add(semantic_key)
        requests_in_input_order.append(request)
        requests_by_device_type.setdefault(request.base_address.device_type, []).append(request)

    segments: list[_ReadPlanSegment] = []
    for bucket in requests_by_device_type.values():
        sorted_requests = sorted(
            bucket,
            key=lambda request: (
                _read_plan_number(request),
                -_get_word_width(request.kind),
                request.index,
            ),
        )
        pending: list[_ReadPlanRequest] = []
        current_start: DeviceAddress | None = None
        current_start_number = 0
        current_end_exclusive = 0
        current_mode = ""

        def flush() -> None:
            nonlocal pending, current_start, current_start_number, current_end_exclusive, current_mode
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
            pending = []
            current_start = None
            current_start_number = 0
            current_end_exclusive = 0
            current_mode = ""

        for request in sorted_requests:
            request_mode = _read_plan_mode(request)
            request_start = _read_plan_number(request)
            request_end_exclusive = request_start + _get_word_width(request.kind)
            mergeable = request_mode in {"WORDS", "DIRECT_BITS"}
            segment_limit = _read_plan_segment_limit(request.base_address.device_type, request_mode)
            can_append = (
                mergeable
                and current_start is not None
                and current_mode == request_mode
                and current_start_number <= request_start <= current_end_exclusive
                and request_end_exclusive - current_start_number <= segment_limit
            )
            if not can_append:
                flush()
                current_start = DeviceAddress(request.base_address.device_type, request.base_address.number, "")
                current_start_number = request_start
                current_end_exclusive = request_end_exclusive
                current_mode = request_mode
            elif request_end_exclusive > current_end_exclusive:
                current_end_exclusive = request_end_exclusive
            pending.append(request)
            if not mergeable:
                flush()
        flush()

    return _CompiledReadNamedPlan(
        requests_in_input_order=tuple(requests_in_input_order),
        segments=tuple(segments),
    )


def _parse_read_named_request(address: str, index: int) -> _ReadPlanRequest:
    base_addr, dtype, bit_idx = _parse_address(address)
    parsed = parse_device(base_addr)
    _validate_address_semantics(address, parsed, dtype)

    if dtype == "BIT" and parsed.device_type in _DIRECT_BIT_DEVICE_TYPES:
        return _ReadPlanRequest(
            index=index,
            address=address,
            base_address=parsed,
            kind="DIRECT_BIT",
        )
    if dtype == "BIT_IN_WORD":
        bit_index = _require_bit_in_word_index(address, bit_idx)
        kind = "BIT_IN_WORD" if parsed.device_type in _OPTIMIZABLE_READ_NAMED_DEVICE_TYPES else "SINGLE_BIT_IN_WORD"
        return _ReadPlanRequest(
            index=index,
            address=address,
            base_address=parsed,
            kind=kind,
            bit_index=bit_index,
        )

    if dtype == "COMMENT":
        return _ReadPlanRequest(index=index, address=address, base_address=parsed, kind="COMMENT")
    if dtype not in {"U", "S", "D", "L", "F", "H", "BIT"}:
        raise ValueError(f"Unsupported read_named data type {dtype!r} for {address!r}")
    if (
        parsed.device_type not in _OPTIMIZABLE_READ_NAMED_DEVICE_TYPES
        or dtype in {"H", "BIT"}
        or (parsed.device_type in NATIVE_32BIT_DEVICE_TYPES and dtype in {"D", "L"})
    ):
        return _ReadPlanRequest(index=index, address=address, base_address=parsed, kind=f"SINGLE_{dtype}")

    return _ReadPlanRequest(
        index=index,
        address=address,
        base_address=parsed,
        kind=dtype,
    )


def _read_plan_mode(request: _ReadPlanRequest) -> str:
    if request.kind == "DIRECT_BIT":
        return "DIRECT_BITS"
    if request.kind.startswith("SINGLE_"):
        return "SINGLE"
    if request.kind == "COMMENT":
        return "COMMENT"
    return "WORDS"


def _preflight_read_named_plan(client: AsyncHostLinkClient, plan: _CompiledReadNamedPlan) -> None:
    """Build every planned command before admitting the aggregate to the FIFO."""

    for segment in plan.segments:
        request = segment.requests[0]
        base = request.base_address.to_text()
        if segment.mode == "WORDS":
            if len(segment.requests) == 1:
                if request.kind == "BIT_IN_WORD":
                    client._build_read_consecutive_command("RDS", base, 1, ".U")
                elif request.kind == "F":
                    client._build_read_consecutive_command("RDS", base, 2, ".U")
                else:
                    client._build_read_command(base, f".{request.kind}")
            else:
                client._build_read_consecutive_command("RDS", segment.start_address.to_text(), segment.count, ".U")
        elif segment.mode == "DIRECT_BITS":
            if len(segment.requests) == 1:
                client._build_read_command(base, None)
            else:
                client._build_read_consecutive_command("RDS", segment.start_address.to_text(), segment.count, None)
        elif segment.mode == "COMMENT":
            client._build_read_comments_command(base)
        elif request.kind == "SINGLE_BIT_IN_WORD":
            client._build_read_command(base, ".U")
        else:
            dtype = request.kind.removeprefix("SINGLE_")
            if dtype == "F":
                if not is_float32_eligible_device_type(request.base_address.device_type):
                    raise HostLinkProtocolError("Float32 reads require an ordinary word-device family.")
                client._build_read_consecutive_command("RDS", base, 2, ".U")
            elif dtype == "BIT":
                client._build_read_command(base, None)
            else:
                client._build_read_command(base, f".{dtype}")


def _resolve_plan_comment_encoding(
    plan: _CompiledReadNamedPlan,
    encoding: HostLinkCommentEncoding | None,
) -> HostLinkCommentEncoding | None:
    has_comment = any(request.kind == "COMMENT" for request in plan.requests_in_input_order)
    if not has_comment:
        if encoding is not None:
            raise ValueError("comment_encoding requires at least one :COMMENT address")
        return None
    if encoding is None:
        raise ValueError("comment_encoding is required when read_named or poll contains :COMMENT")
    return require_comment_encoding(encoding)


async def _execute_read_named_plan(
    client: AsyncHostLinkClient,
    plan: _CompiledReadNamedPlan,
    comment_encoding: HostLinkCommentEncoding | None,
) -> dict[str, int | float | bool | str]:
    resolved: list[int | float | bool | str | None] = [None] * len(plan.requests_in_input_order)

    async with client._exclusive_turn():
        for segment in plan.segments:
            if segment.mode == "DIRECT_BITS":
                if len(segment.requests) == 1:
                    request = segment.requests[0]
                    resolved[request.index] = await read_typed(client, request.base_address.to_text(), "BIT")
                else:
                    tokens = await client.read_consecutive(
                        segment.start_address.to_text(), segment.count, data_format=None
                    )
                    for request in segment.requests:
                        offset = _read_plan_number(request) - segment.start_number
                        resolved[request.index] = _resolve_direct_bit_value(tokens, offset)
            elif segment.mode == "WORDS":
                if len(segment.requests) == 1:
                    request = segment.requests[0]
                    base = request.base_address.to_text()
                    if request.kind == "BIT_IN_WORD":
                        values = await client.read_consecutive(base, 1, data_format=".U")
                        resolved[request.index] = bool((int(values[0]) >> request.bit_index) & 1)
                    else:
                        resolved[request.index] = await read_typed(client, base, request.kind)
                else:
                    words = await read_words_single_request(client, segment.start_address.to_text(), segment.count)
                    for request in segment.requests:
                        offset = _read_plan_number(request) - segment.start_number
                        resolved[request.index] = _resolve_planned_value(words, offset, request.kind, request.bit_index)
            else:
                request = segment.requests[0]
                base = request.base_address.to_text()
                if segment.mode == "COMMENT":
                    if comment_encoding is None:
                        raise HostLinkProtocolError("Compiled COMMENT plan is missing its explicit encoding")
                    resolved[request.index] = await read_comments(client, base, comment_encoding)
                elif request.kind == "SINGLE_BIT_IN_WORD":
                    bit_index = _require_bit_in_word_index(request.address, request.bit_index)
                    raw = await client.read(base, data_format=".U")
                    values = raw if isinstance(raw, list) else [raw]
                    word = int(values[0])
                    resolved[request.index] = bool((word >> bit_index) & 1)
                else:
                    dtype = request.kind.removeprefix("SINGLE_")
                    resolved[request.index] = await read_typed(client, base, dtype)

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


def _read_plan_segment_limit(device_type: str, mode: str) -> int:
    if mode == "DIRECT_BITS":
        return 1000
    if device_type == "TM":
        return 512
    if device_type == "Z":
        return 12
    return 1000


def _get_word_width(kind: str) -> int:
    if kind.startswith("SINGLE_") or kind == "COMMENT":
        return 1
    width = _READ_PLAN_WORD_WIDTH.get(kind)
    if width is None:
        raise HostLinkProtocolError(f"Unsupported read plan value kind: {kind}")
    return width


def _read_plan_number(request: _ReadPlanRequest) -> int:
    if request.kind == "DIRECT_BIT" and request.base_address.device_type in BIT_BANK_DEVICE_TYPES:
        return bit_bank_logical_number(request.base_address.number)
    return request.base_address.number


def _offset_device(start: DeviceAddress, word_offset: int) -> str:
    number = (
        bit_bank_number_from_logical(bit_bank_logical_number(start.number) + word_offset)
        if start.device_type in BIT_BANK_DEVICE_TYPES
        else start.number + word_offset
    )
    return DeviceAddress(start.device_type, number, "").to_text()


def _words_to_float32(lo_word: int, hi_word: int) -> float:
    bits = (lo_word & 0xFFFF) | ((hi_word & 0xFFFF) << 16)
    return cast(float, struct.unpack("<f", struct.pack("<I", bits))[0])


def _float32_to_words(value: float) -> tuple[int, int]:
    if not math.isfinite(value):
        raise ValueError(f"Float value must be finite, got {value!r}.")
    try:
        packed = struct.pack("<f", value)
    except OverflowError as exc:
        raise ValueError(f"Float value is outside the finite float32 range: {value!r}.") from exc
    if not math.isfinite(struct.unpack("<f", packed)[0]):
        raise ValueError(f"Float value is outside the finite float32 range: {value!r}.")
    bits = struct.unpack("<I", packed)[0]
    return bits & 0xFFFF, (bits >> 16) & 0xFFFF


def normalize_address(address: str) -> str:
    """Return the canonical Host Link device string.

    The helper normalizes device-family spelling, trims whitespace, and keeps
    explicit dtype or bit-in-word intent when present.

    Args:
        address: User-facing address such as ``"dm100:u"``, ``"dm100:f"``, or
            ``"DM100.a"``.

    Returns:
        Canonical uppercase address text.
    """

    return parse_address(address).text


async def read_bits_single_request(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[bool]:
    """Read contiguous direct-bit devices using exactly one PLC request."""

    address = parse_device(device)
    if address.suffix:
        raise HostLinkProtocolError("device must be a base direct-bit address without a data-format suffix")
    if address.device_type not in _DIRECT_BIT_DEVICE_TYPES:
        raise HostLinkProtocolError("bit reads require a direct bit device")
    normalized_count = _require_exact_integer(count, 1, 1000, "bit count")
    validate_device_count(address.device_type, "", normalized_count)
    validate_device_span(address.device_type, address.number, "", normalized_count)
    values = await client.read_consecutive(device, normalized_count, data_format=None)
    return [_parse_bool_token(value) for value in values]


async def write_bits_single_request(
    client: AsyncHostLinkClient,
    device: str,
    values: list[bool],
) -> None:
    """Write contiguous direct-bit devices using exactly one PLC request."""

    address = parse_device(device)
    if address.suffix:
        raise HostLinkProtocolError("device must be a base direct-bit address without a data-format suffix")
    if address.device_type not in _DIRECT_BIT_DEVICE_TYPES:
        raise HostLinkProtocolError("bit writes require a direct bit device")
    snapshot = [_parse_bit_write_value(value) for value in values]
    _require_exact_integer(len(snapshot), 1, 1000, "bit count")
    validate_device_count(address.device_type, "", len(snapshot))
    validate_device_span(address.device_type, address.number, "", len(snapshot))
    await client.write_consecutive(device, snapshot, data_format=None)


async def read_words_single_request(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous unsigned words using one PLC request.

    The helper never splits or combines multiple PLC requests.
    """

    values = await client.read_consecutive(device, count, data_format=".U")
    return [int(v) for v in values]


async def read_dwords_single_request(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Read contiguous unsigned dwords using one PLC request.

    Adjacent word pairs are combined in low-word, high-word order. The helper
    never silently splits the logical request.
    """

    normalized_count = _require_exact_integer(count, 1, 500, "dword count")
    words = await read_words_single_request(client, device, normalized_count * 2)
    return [(words[i] | (words[i + 1] << 16)) for i in range(0, normalized_count * 2, 2)]


async def write_words_single_request(
    client: AsyncHostLinkClient,
    device: str,
    values: list[int],
) -> None:
    """Write contiguous unsigned words using one PLC request.

    The helper rejects the entire operation before send if one value is invalid.
    """

    normalized = [_require_exact_integer(value, 0, 0xFFFF, "word") for value in values]
    await client.write_consecutive(device, normalized, data_format=".U")


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
        normalized = _require_exact_integer(value, 0, 0xFFFFFFFF, "dword")
        words.extend((normalized & 0xFFFF, (normalized >> 16) & 0xFFFF))
    await write_words_single_request(client, device, words)


def _require_exact_integer(value: object, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} value {value!r} must be an integer in the range {minimum}..{maximum}")
    return value


async def read_expansion_unit_buffer(
    client: AsyncHostLinkClient,
    unit_no: int,
    address: int,
    count: int,
    *,
    data_format: str,
) -> list[int | str]:
    """Read buffer memory in an expansion unit.

    This high-level helper exposes the existing Host Link ``URD`` command
    through the same helper namespace as typed and contiguous access. Validation
    and command framing remain owned by the connected client.

    Args:
        client: Connected asynchronous Host Link client.
        unit_no: Expansion unit number, ``0`` to ``48``.
        address: Buffer memory address, ``0`` to ``59999``.
        count: Number of values to read.
        data_format: Required Host Link data suffix such as ``"U"``, ``"S"``,
            ``"D"``, ``"L"``, or ``"H"``.

    Returns:
        Values returned by the PLC after Host Link token parsing.

    Examples:
        Read two unsigned buffer words from unit 1::

            values = await read_expansion_unit_buffer(client, 1, 100, 2, data_format="U")
    """

    return await client.read_expansion_unit_buffer(unit_no, address, count, data_format=data_format)


async def write_expansion_unit_buffer(
    client: AsyncHostLinkClient,
    unit_no: int,
    address: int,
    values: Sequence[int | str],
    *,
    data_format: str,
) -> None:
    """Write buffer memory in an expansion unit.

    This high-level helper exposes the existing Host Link ``UWR`` command
    without adding hidden chunking or fallback behavior.

    Args:
        client: Connected asynchronous Host Link client.
        unit_no: Expansion unit number, ``0`` to ``48``.
        address: Buffer memory address, ``0`` to ``59999``.
        values: Values to write in one request.
        data_format: Required Host Link data suffix such as ``"U"``, ``"S"``,
            ``"D"``, ``"L"``, or ``"H"``.

    Examples:
        Write two signed buffer words to unit 1::

            await write_expansion_unit_buffer(client, 1, 200, [-1, 2], data_format="S")
    """

    await client.write_expansion_unit_buffer(unit_no, address, values, data_format=data_format)


async def write_bit_in_expansion_unit_buffer(
    client: AsyncHostLinkClient,
    unit_no: int,
    address: int,
    bit_index: int,
    value: bool,
) -> None:
    """Set or clear one expansion-buffer bit through explicit URD/UWR.

    The client validates the complete immutable unit/address route before FIFO
    admission and retains one turn and one absolute deadline across exactly
    one unsigned-word read and one write. This operation is not PLC-atomic and
    performs no fallback, retry, or success readback.
    """

    await client.write_bit_in_expansion_unit_buffer(unit_no, address, bit_index, value)


async def read_words(
    client: AsyncHostLinkClient,
    device: str,
    count: int,
) -> list[int]:
    """Deprecated compatibility alias for :func:`read_words_single_request`.

    This helper wraps the low-level consecutive read and converts the PLC reply
    to Python ``int`` values.

    Args:
        client: Connected asynchronous Host Link client.
        device: Starting base device address such as ``"DM100"``.
        count: Number of 16-bit words to read.

    Returns:
        A list of unsigned word values in PLC order.
    """
    warnings.warn(
        "read_words is deprecated; use read_words_single_request",
        DeprecationWarning,
        stacklevel=2,
    )
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


async def open_and_connect(options: HostLinkConnectionOptions) -> AsyncHostLinkClient:
    """
    Create and connect an :class:`AsyncHostLinkClient`.

    This is the recommended entry point for user code and examples because it
    returns a ready-to-use client in one step.

    Args:
        options: Fully specified Host Link endpoint and timeout settings.

    Returns:
        A connected :class:`AsyncHostLinkClient`.

    Usage::

        options = HostLinkConnectionOptions(
            "192.168.250.100",
            port=8501,
            transport="tcp",
            plc_profile="keyence:kv-8000",
        )
        client = await open_and_connect(options)
        async with client:
            values = await read_words_single_request(client, "DM100", 10)
    """
    from .client import AsyncHostLinkClient

    if not isinstance(options, HostLinkConnectionOptions):
        raise TypeError("open_and_connect requires HostLinkConnectionOptions")

    client = AsyncHostLinkClient(
        options.host,
        port=options.port,
        transport=options.transport,
        timeout=options.timeout,
        connect_timeout=options.connect_timeout,
        plc_profile=options.plc_profile,
    )
    await client.connect()
    return client
