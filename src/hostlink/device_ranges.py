"""Published KEYENCE KV device range catalog for Host Link."""
# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .device import DEFAULT_FORMAT_BY_DEVICE_TYPE
from .errors import HostLinkProtocolError
from .plc_profiles import (
    _KvHostLinkPlcProfileDefinition,
    _profile_definition_from_name,
    _profiles,
    normalize_plc_profile,
)


class KvDeviceRangeNotation(Enum):
    """Address number notation used by one device range row."""

    DECIMAL = "decimal"
    HEXADECIMAL = "hexadecimal"


class KvDeviceRangeCategory(Enum):
    """Broad device category used by the maintained KV range catalog."""

    BIT = "bit"
    WORD = "word"
    TIMER_COUNTER = "timer_counter"
    INDEX = "index"
    FILE_REGISTER = "file_register"


@dataclass(frozen=True)
class KvDeviceRangeSegment:
    """One concrete segment from a published KV device range row."""

    device: str
    category: KvDeviceRangeCategory
    is_bit_device: bool
    notation: KvDeviceRangeNotation
    lower_bound: int
    upper_bound: int | None
    point_count: int | None
    address_range: str


@dataclass(frozen=True)
class KvDeviceRangeEntry:
    """Catalog entry for one logical Host Link device family."""

    device: str
    device_type: str
    category: KvDeviceRangeCategory
    is_bit_device: bool
    notation: KvDeviceRangeNotation
    supported: bool
    lower_bound: int
    upper_bound: int | None
    point_count: int | None
    address_range: str | None
    source: str
    notes: str | None
    segments: tuple[KvDeviceRangeSegment, ...]


@dataclass(frozen=True)
class KvDeviceRangeCatalog:
    """Resolved KV device range catalog for one canonical PLC profile."""

    plc_profile: str
    model_code: str
    has_model_code: bool
    requested_plc_profile: str
    resolved_plc_profile: str
    entries: tuple[KvDeviceRangeEntry, ...]

    def entry(self, device_type: str) -> KvDeviceRangeEntry | None:
        """Return the catalog entry matching a device type or segment alias."""

        wanted = device_type.strip().upper()
        for entry in self.entries:
            if entry.device_type.upper() == wanted:
                return entry
        for entry in self.entries:
            if entry.device.upper() == wanted:
                return entry
        for entry in self.entries:
            if any(segment.device.upper() == wanted for segment in entry.segments):
                return entry
        return None


@dataclass(frozen=True)
class _RangeRow:
    device_type: str
    notation: KvDeviceRangeNotation
    ranges: tuple[str, ...]


@dataclass(frozen=True)
class _RangeTable:
    profiles: tuple[_KvHostLinkPlcProfileDefinition, ...]
    rows: tuple[_RangeRow, ...]


def device_range_catalog_for_plc_profile(plc_profile: str) -> KvDeviceRangeCatalog:
    """Resolve and return the device range catalog for a canonical PLC profile."""

    return _build_catalog(plc_profile, None)


def _build_catalog(plc_profile: str, model_code: str | None) -> KvDeviceRangeCatalog:
    requested_plc_profile = normalize_plc_profile(plc_profile)

    table = _range_table()
    resolved_profile = _range_profile_for_plc_profile(table, requested_plc_profile)
    model_index = table.profiles.index(resolved_profile)

    entries = tuple(_build_entry(row, model_index, resolved_profile.source_label) for row in table.rows)
    return KvDeviceRangeCatalog(
        plc_profile=resolved_profile.name,
        model_code=model_code or "",
        has_model_code=model_code is not None,
        requested_plc_profile=requested_plc_profile,
        resolved_plc_profile=resolved_profile.name,
        entries=entries,
    )


def _build_entry(row: _RangeRow, model_index: int, resolved_model: str) -> KvDeviceRangeEntry:
    range_text = row.ranges[model_index].strip()
    supported = bool(range_text) and range_text != "-"
    address_range = range_text if supported else None
    segments = _parse_segments(row, address_range) if address_range is not None else ()
    primary_device = _primary_device_name(row, segments)
    category, is_bit_device = _device_metadata(primary_device)
    notation = _entry_notation(row.notation, segments)
    lower_bound, upper_bound, point_count = _summarize_entry_bounds(segments)

    return KvDeviceRangeEntry(
        device=primary_device,
        device_type=row.device_type,
        category=category,
        is_bit_device=is_bit_device,
        notation=notation,
        supported=supported,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        point_count=point_count,
        address_range=address_range,
        source=f"Embedded device range table ({resolved_model})",
        notes="Published address range expands to multiple alias devices; inspect segments."
        if len(segments) > 1
        else None,
        segments=segments,
    )


def _parse_segments(row: _RangeRow, range_text: str) -> tuple[KvDeviceRangeSegment, ...]:
    segments = []
    for segment_text in range_text.split(","):
        segment = segment_text.strip()
        if not segment:
            continue
        device = _segment_device(segment) or row.device_type
        category, is_bit_device = _device_metadata(device)
        notation = _notation_for_device(row.notation, device)
        lower_bound, upper_bound, point_count = _parse_segment_bounds(segment, notation, device)
        segments.append(
            KvDeviceRangeSegment(
                device=device,
                category=category,
                is_bit_device=is_bit_device,
                notation=notation,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                point_count=point_count,
                address_range=segment,
            )
        )
    return tuple(segments)


def _segment_device(segment: str) -> str:
    chars = []
    for char in segment:
        if not char.isalpha() or not char.isascii():
            break
        chars.append(char)
    return "".join(chars)


def _primary_device_name(row: _RangeRow, segments: tuple[KvDeviceRangeSegment, ...]) -> str:
    unique_devices: list[str] = []
    for segment in segments:
        if segment.device.upper() not in [device.upper() for device in unique_devices]:
            unique_devices.append(segment.device)
    return unique_devices[0] if len(unique_devices) == 1 else row.device_type


def _summarize_entry_bounds(segments: tuple[KvDeviceRangeSegment, ...]) -> tuple[int, int | None, int | None]:
    if not segments:
        return 0, None, None
    first = segments[0]
    all_same = all(
        segment.lower_bound == first.lower_bound
        and segment.upper_bound == first.upper_bound
        and segment.point_count == first.point_count
        for segment in segments[1:]
    )
    return (first.lower_bound, first.upper_bound, first.point_count) if all_same else (first.lower_bound, None, None)


def _entry_notation(
    fallback: KvDeviceRangeNotation,
    segments: tuple[KvDeviceRangeSegment, ...],
) -> KvDeviceRangeNotation:
    if not segments:
        return fallback
    first = segments[0]
    return first.notation if all(segment.notation == first.notation for segment in segments[1:]) else fallback


def _parse_segment_bounds(
    segment: str,
    notation: KvDeviceRangeNotation,
    default_device: str,
) -> tuple[int, int | None, int | None]:
    parts = [part.strip() for part in segment.split("-", 1)]
    if len(parts) != 2:
        raise ValueError(f"Invalid device range segment {segment!r}: missing '-' separator.")

    lower = _parse_segment_number(parts[0], notation, default_device)
    upper = _parse_segment_number(parts[1], notation, default_device)
    if lower is None:
        raise ValueError(f"Invalid device range start {parts[0]!r} in segment {segment!r}.")
    if upper is None:
        raise ValueError(f"Invalid device range end {parts[1]!r} in segment {segment!r}.")
    if upper < lower:
        raise ValueError(f"Invalid device range bounds in segment {segment!r}.")
    return lower, upper, upper - lower + 1


def _parse_segment_number(
    text: str,
    notation: KvDeviceRangeNotation,
    default_device: str,
) -> int | None:
    normalized = text.strip()
    if normalized.startswith(default_device):
        normalized = normalized[len(default_device) :]
    normalized = _trim_leading_ascii_letters(normalized)
    if not normalized:
        return None
    if default_device in {"X", "Y"}:
        return _parse_xym_segment_number(normalized)
    base = 16 if notation == KvDeviceRangeNotation.HEXADECIMAL else 10
    try:
        return int(normalized, base)
    except ValueError:
        return None


def _parse_xym_segment_number(text: str) -> int | None:
    bank_text = "" if len(text) == 1 else text[:-1]
    if any(character < "0" or character > "9" for character in bank_text):
        return None

    try:
        bit = int(text[-1], 16)
    except ValueError:
        return None

    bank = int(bank_text, 10) if bank_text else 0
    return bank * 16 + bit


def _trim_leading_ascii_letters(value: str) -> str:
    index = 0
    while index < len(value) and value[index].isascii() and value[index].isalpha():
        index += 1
    return value[index:]


def _device_metadata(device_type: str) -> tuple[KvDeviceRangeCategory, bool]:
    if device_type == "Z":
        return KvDeviceRangeCategory.INDEX, False
    if device_type == "ZF":
        return KvDeviceRangeCategory.FILE_REGISTER, False
    if device_type in {"T", "C", "AT", "CTH", "CTC"}:
        return KvDeviceRangeCategory.TIMER_COUNTER, False
    if _is_direct_bit_device_type(device_type):
        return KvDeviceRangeCategory.BIT, True
    if DEFAULT_FORMAT_BY_DEVICE_TYPE.get(device_type) == "":
        return KvDeviceRangeCategory.BIT, True
    return KvDeviceRangeCategory.WORD, False


def _is_direct_bit_device_type(device_type: str) -> bool:
    return device_type in {"R", "B", "MR", "LR", "CR", "VB", "X", "Y", "M", "L"}


def _notation_for_device(
    fallback: KvDeviceRangeNotation,
    device_type: str,
) -> KvDeviceRangeNotation:
    return KvDeviceRangeNotation.HEXADECIMAL if device_type in {"B", "W", "VB", "X", "Y"} else fallback


def _range_profile_for_plc_profile(
    table: _RangeTable,
    plc_profile: str,
) -> _KvHostLinkPlcProfileDefinition:
    normalized = _profile_definition_from_name(plc_profile).name
    for profile in table.profiles:
        if profile.name == normalized:
            return profile
    supported = ", ".join(profile.name for profile in table.profiles)
    raise HostLinkProtocolError(f"Unsupported PLC profile {plc_profile!r}. Supported PLC profiles: {supported}.")


@lru_cache(maxsize=1)
def _range_table() -> _RangeTable:
    return _RangeTable(
        profiles=_profiles(),
        rows=(
            _row(
                "R",
                KvDeviceRangeNotation.DECIMAL,
                "R00000-R59915",
                "X0-599F,Y0-599F",
                "R00000-R99915",
                "X0-999F,Y0-999F",
                "R00000-R99915",
                "X0-999F,Y0-999F",
                "R00000-R199915",
                "X0-1999F,Y0-1999F",
                "R00000-R199915",
                "X0-1999F,Y0-1999F",
                "R00000-R199915",
                "X0-1999F,Y0-1999F",
            ),
            _row(
                "B",
                KvDeviceRangeNotation.HEXADECIMAL,
                "B0000-B1FFF",
                "B0000-B1FFF",
                "B0000-B3FFF",
                "B0000-B3FFF",
                "B0000-B3FFF",
                "B0000-B3FFF",
                "B0000-B7FFF",
                "B0000-B7FFF",
                "B0000-B7FFF",
                "B0000-B7FFF",
                "B0000-B7FFF",
                "B0000-B7FFF",
            ),
            _row(
                "MR",
                KvDeviceRangeNotation.DECIMAL,
                "MR00000-MR59915",
                "M0-9599",
                "MR00000-MR99915",
                "M0-15999",
                "MR00000-MR99915",
                "M0-15999",
                "MR000000-MR399915",
                "M000000-M63999",
                "MR000000-MR399915",
                "M000000-M63999",
                "MR000000-MR399915",
                "M000000-M63999",
            ),
            _row(
                "LR",
                KvDeviceRangeNotation.DECIMAL,
                "LR00000-LR19915",
                "L0-3199",
                "LR00000-LR99915",
                "L0-15999",
                "LR00000-LR99915",
                "L0-15999",
                "LR00000-LR99915",
                "L00000-L15999",
                "LR00000-LR99915",
                "L00000-L15999",
                "LR00000-LR99915",
                "L00000-L15999",
            ),
            _row(
                "CR",
                KvDeviceRangeNotation.DECIMAL,
                "CR0000-CR8915",
                "CR0000-CR8915",
                "CR0000-CR3915",
                "CR0000-CR3915",
                "CR0000-CR3915",
                "CR0000-CR3915",
                "CR0000-CR7915",
                "CR0000-CR7915",
                "CR0000-CR7915",
                "CR0000-CR7915",
                "CR0000-CR7915",
                "CR0000-CR7915",
            ),
            _row(
                "CM",
                KvDeviceRangeNotation.DECIMAL,
                "CM0000-CM8999",
                "CM0000-CM8999",
                "CM0000-CM5999",
                "CM0000-CM5999",
                "CM0000-CM5999",
                "CM0000-CM5999",
                "CM0000-CM5999",
                "CM0000-CM5999",
                "CM0000-CM7599",
                "CM0000-CM7599",
                "CM0000-CM7599",
                "CM0000-CM7599",
            ),
            _row(
                "T",
                KvDeviceRangeNotation.DECIMAL,
                "T0000-T0511",
                "T0000-T0511",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
                "T0000-T3999",
            ),
            _row(
                "TC",
                KvDeviceRangeNotation.DECIMAL,
                "TC0000-TC0511",
                "TC0000-TC0511",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
                "TC0000-TC3999",
            ),
            _row(
                "TS",
                KvDeviceRangeNotation.DECIMAL,
                "TS0000-TS0511",
                "TS0000-TS0511",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
                "TS0000-TS3999",
            ),
            _row(
                "C",
                KvDeviceRangeNotation.DECIMAL,
                "C0000-C0255",
                "C0000-C0255",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
                "C0000-C3999",
            ),
            _row(
                "CC",
                KvDeviceRangeNotation.DECIMAL,
                "CC0000-CC0255",
                "CC0000-CC0255",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
                "CC0000-CC3999",
            ),
            _row(
                "CS",
                KvDeviceRangeNotation.DECIMAL,
                "CS0000-CS0255",
                "CS0000-CS0255",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
                "CS0000-CS3999",
            ),
            _row(
                "DM",
                KvDeviceRangeNotation.DECIMAL,
                "DM00000-DM32767",
                "D0-32767",
                "DM00000-DM65534",
                "D0-65534",
                "DM00000-DM65534",
                "D0-65534",
                "DM00000-DM65534",
                "D00000-D65534",
                "DM00000-DM65534",
                "D00000-D65534",
                "DM00000-DM65534",
                "D00000-D65534",
            ),
            _row(
                "EM",
                KvDeviceRangeNotation.DECIMAL,
                "-",
                "-",
                "EM00000-EM65534",
                "E0-65534",
                "EM00000-EM65534",
                "E0-65534",
                "EM00000-EM65534",
                "E00000-E65534",
                "EM00000-EM65534",
                "E00000-E65534",
                "EM00000-EM65534",
                "E00000-E65534",
            ),
            _row(
                "FM",
                KvDeviceRangeNotation.DECIMAL,
                "-",
                "-",
                "FM00000-FM32767",
                "F0-32767",
                "FM00000-FM32767",
                "F0-32767",
                "FM00000-FM32767",
                "F00000-F32767",
                "FM00000-FM32767",
                "F00000-F32767",
                "FM00000-FM32767",
                "F00000-F32767",
            ),
            _row(
                "ZF",
                KvDeviceRangeNotation.DECIMAL,
                "-",
                "-",
                "ZF000000-ZF131071",
                "ZF000000-ZF131071",
                "ZF000000-ZF131071",
                "ZF000000-ZF131071",
                "ZF000000-ZF524287",
                "ZF000000-ZF524287",
                "ZF000000-ZF524287",
                "ZF000000-ZF524287",
                "ZF000000-ZF524287",
                "ZF000000-ZF524287",
            ),
            _row(
                "W",
                KvDeviceRangeNotation.HEXADECIMAL,
                "W0000-W3FFF",
                "W0000-W3FFF",
                "W0000-W3FFF",
                "W0000-W3FFF",
                "W0000-W3FFF",
                "W0000-W3FFF",
                "W0000-W7FFF",
                "W0000-W7FFF",
                "W0000-W7FFF",
                "W0000-W7FFF",
                "W0000-W7FFF",
                "W0000-W7FFF",
            ),
            _row(
                "TM",
                KvDeviceRangeNotation.DECIMAL,
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
                "TM000-TM511",
            ),
            _row(
                "VM",
                KvDeviceRangeNotation.DECIMAL,
                "VM0-9499",
                "VM0-9499",
                "VM0-49999",
                "VM0-49999",
                "VM0-49999",
                "VM0-49999",
                "VM0-63999",
                "VM0-63999",
                "VM0-589823",
                "VM0-589823",
                "-",
                "-",
            ),
            _row(
                "VB",
                KvDeviceRangeNotation.HEXADECIMAL,
                "VB0-1FFF",
                "VB0-1FFF",
                "VB0-3FFF",
                "VB0-3FFF",
                "VB0-3FFF",
                "VB0-3FFF",
                "VB0-F9FF",
                "VB0-F9FF",
                "VB0-F9FF",
                "VB0-F9FF",
                "-",
                "-",
            ),
            _row(
                "Z",
                KvDeviceRangeNotation.DECIMAL,
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-12",
                "Z1-10",
                "Z1-10",
            ),
            _row(
                "CTH",
                KvDeviceRangeNotation.DECIMAL,
                "CTH0-3",
                "CTH0-3",
                "CTH0-1",
                "CTH0-3",
                "CTH0-1",
                "CTH0-3",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            ),
            _row(
                "CTC",
                KvDeviceRangeNotation.DECIMAL,
                "CTC0-7",
                "CTC0-7",
                "CTC0-3",
                "CTC0-3",
                "CTC0-3",
                "CTC0-3",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            ),
            _row(
                "AT",
                KvDeviceRangeNotation.DECIMAL,
                "-",
                "-",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "AT0-7",
                "-",
                "-",
            ),
        ),
    )


def _row(device_type: str, notation: KvDeviceRangeNotation, *ranges: str) -> _RangeRow:
    return _RangeRow(device_type=device_type, notation=notation, ranges=ranges)
