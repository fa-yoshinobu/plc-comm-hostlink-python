"""Published KEYENCE KV device range catalog for Host Link."""
# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .device import DEFAULT_FORMAT_BY_DEVICE_TYPE
from .errors import HostLinkProtocolError

RANGE_CSV_DATA = """DeviceType,Base,KV-NANO,KV-NANO(XYM),KV-3000/5000,KV-3000/5000(XYM),KV-7000,KV-7000(XYM),KV-8000,KV-8000(XYM),KV-X500,KV-X500(XYM)
R,10,R00000-R59915,"X0-599F,Y0-599F",R00000-R99915,"X0-999F,Y0-999F",R00000-R199915,"X0-1999F,Y0-1999F",R00000-R199915,"X0-1999F,Y0-1999F",R00000-R199915,"X0-1999F,Y0-1999F"
B,16,B0000-B1FFF,B0000-B1FFF,B0000-B3FFF,B0000-B3FFF,B0000-B7FFF,B0000-B7FFF,B0000-B7FFF,B0000-B7FFF,B0000-B7FFF,B0000-B7FFF
MR,10,MR00000-MR59915,M0-9599,MR00000-MR99915,M0-15999,MR000000-MR399915,M000000-M63999,MR000000-MR399915,M000000-M63999,MR000000-MR399915,M000000-M63999
LR,10,LR00000-LR19915,L0-3199,LR00000-LR99915,L0-15999,LR00000-LR99915,L00000-L15999,LR00000-LR99915,L00000-L15999,LR00000-LR99915,L00000-L15999
CR,10,CR0000-CR8915,CR0000-CR8915,CR0000-CR3915,CR0000-CR3915,CR0000-CR7915,CR0000-CR7915,CR0000-CR7915,CR0000-CR7915,CR0000-CR7915,CR0000-CR7915
CM,10,CM0000-CM8999,CM0000-CM8999,CM0000-CM5999,CM0000-CM5999,CM0000-CM5999,CM0000-CM5999,CM0000-CM7599,CM0000-CM7599,CM0000-CM7599,CM0000-CM7599
T,10,T0000-T0511,T0000-T0511,T0000-T3999,T0000-T3999,T0000-T3999,T0000-T3999,T0000-T3999,T0000-T3999,T0000-T3999,T0000-T3999
C,10,C0000-C0255,C0000-C0255,C0000-C3999,C0000-C3999,C0000-C3999,C0000-C3999,C0000-C3999,C0000-C3999,C0000-C3999,C0000-C3999
DM,10,DM00000-DM32767,D0-32767,DM00000-DM65534,D0-65534,DM00000-DM65534,D00000-D65534,DM00000-DM65534,D00000-D65534,DM00000-DM65534,D00000-D65534
EM,10,-,-,EM00000-EM65534,E0-65534,EM00000-EM65534,E00000-E65534,EM00000-EM65534,E00000-E65534,EM00000-EM65534,E00000-E65534
FM,10,-,-,FM00000-FM32767,F0-32767,FM00000-FM32767,F00000-F32767,FM00000-FM32767,F00000-F32767,FM00000-FM32767,F00000-F32767
ZF,10,-,-,ZF000000-ZF131071,ZF000000-ZF131071,ZF000000-ZF524287,ZF000000-ZF524287,ZF000000-ZF524287,ZF000000-ZF524287,ZF000000-ZF524287,ZF000000-ZF524287
W,16,W0000-W3FFF,W0000-W3FFF,W0000-W3FFF,W0000-W3FFF,W0000-W7FFF,W0000-W7FFF,W0000-W7FFF,W0000-W7FFF,W0000-W7FFF,W0000-W7FFF
TM,10,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511,TM000-TM511
VM,10,VM0-9499,VM0-9499,VM0-49999,VM0-49999,VM0-63999,VM0-63999,VM0-589823,VM0-589823,-,-
VB,16,VB0-1FFF,VB0-1FFF,VB0-3FFF,VB0-3FFF,VB0-F9FF,VB0-F9FF,VB0-F9FF,VB0-F9FF,-,-
Z,10,Z1-12,Z1-12,Z1-12,Z1-12,Z1-12,Z1-12,Z1-12,Z1-12,-,-
CTH,10,CTH0-3,CTH0-3,CTH0-1,CTH0-3,-,-,-,-,-,-
CTC,10,CTC0-7,CTC0-7,CTC0-3,CTC0-3,-,-,-,-,-,-
AT,10,-,-,AT0-7,AT0-7,AT0-7,AT0-7,AT0-7,AT0-7,-,-
"""


class KvDeviceRangeNotation(Enum):
    DECIMAL = "decimal"
    HEXADECIMAL = "hexadecimal"


class KvDeviceRangeCategory(Enum):
    BIT = "bit"
    WORD = "word"
    TIMER_COUNTER = "timer_counter"
    INDEX = "index"
    FILE_REFRESH = "file_refresh"


@dataclass(frozen=True)
class KvDeviceRangeSegment:
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
    model: str
    model_code: str
    has_model_code: bool
    requested_model: str
    resolved_model: str
    entries: tuple[KvDeviceRangeEntry, ...]

    def entry(self, device_type: str) -> KvDeviceRangeEntry | None:
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
    model_headers: tuple[str, ...]
    rows: tuple[_RangeRow, ...]


def available_device_range_models() -> list[str]:
    return list(_range_table().model_headers)


def device_range_catalog_for_model(model: str) -> KvDeviceRangeCatalog:
    return _build_catalog(model, None)


def device_range_catalog_for_query_model(model_info: object) -> KvDeviceRangeCatalog:
    code = str(getattr(model_info, "code", ""))
    model = getattr(model_info, "model", None)
    if not model:
        raise HostLinkProtocolError(f"Unsupported model code {code!r}; cannot resolve device range catalog.")
    return _build_catalog(str(model), code)


def _build_catalog(model: str, model_code: str | None) -> KvDeviceRangeCatalog:
    requested_model = model.strip()
    if not requested_model:
        raise HostLinkProtocolError("Model name must not be empty.")

    table = _range_table()
    resolved_model = _resolve_model_column(table, requested_model)
    try:
        model_index = table.model_headers.index(resolved_model)
    except ValueError as exc:
        raise HostLinkProtocolError(
            f"Resolved model column {resolved_model!r} was not found in the embedded device range table."
        ) from exc

    entries = tuple(_build_entry(row, model_index, resolved_model) for row in table.rows)
    return KvDeviceRangeCatalog(
        model=resolved_model,
        model_code=model_code or "",
        has_model_code=model_code is not None,
        requested_model=requested_model,
        resolved_model=resolved_model,
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
        return 0, None, None

    lower = _parse_segment_number(parts[0], notation, default_device)
    upper = _parse_segment_number(parts[1], notation, default_device)
    point_count = upper - lower + 1 if lower is not None and upper is not None and upper >= lower else None
    return lower or 0, upper, point_count


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
    base = 16 if notation == KvDeviceRangeNotation.HEXADECIMAL else 10
    return int(normalized, base)


def _trim_leading_ascii_letters(value: str) -> str:
    index = 0
    while index < len(value) and value[index].isascii() and value[index].isalpha():
        index += 1
    return value[index:]


def _device_metadata(device_type: str) -> tuple[KvDeviceRangeCategory, bool]:
    if device_type == "Z":
        return KvDeviceRangeCategory.INDEX, False
    if device_type == "ZF":
        return KvDeviceRangeCategory.FILE_REFRESH, False
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


def _resolve_model_column(table: _RangeTable, requested_model: str) -> str:
    normalized = _normalize_model_key(requested_model)
    direct = _direct_model_match(table, normalized)
    if direct is not None:
        return direct

    xym_suffix = "(XYM)"
    wants_xym = normalized.endswith(xym_suffix)
    base_model = normalized[: -len(xym_suffix)] if wants_xym else normalized

    if base_model.startswith("KV-NANO") or base_model.startswith("KV-N"):
        resolved_family = "KV-NANO"
    elif base_model.startswith("KV-3000") or base_model.startswith("KV-5000") or base_model.startswith("KV-5500"):
        resolved_family = "KV-3000/5000"
    elif base_model.startswith("KV-7000") or base_model.startswith("KV-7300") or base_model.startswith("KV-7500"):
        resolved_family = "KV-7000"
    elif base_model.startswith("KV-8000"):
        resolved_family = "KV-8000"
    elif base_model.startswith("KV-X5") or base_model.startswith("KV-X3"):
        resolved_family = "KV-X500"
    else:
        supported = ", ".join(table.model_headers)
        raise HostLinkProtocolError(f"Unsupported model {requested_model!r}. Supported range models: {supported}.")

    resolved_key = f"{resolved_family}(XYM)" if wants_xym else resolved_family
    direct = _direct_model_match(table, resolved_key)
    if direct is None:
        raise HostLinkProtocolError(
            f"Resolved model {resolved_key!r} was not found in the embedded device range table."
        )
    return direct


def _direct_model_match(table: _RangeTable, normalized: str) -> str | None:
    return next((header for header in table.model_headers if _normalize_model_key(header) == normalized), None)


def _normalize_model_key(text: str) -> str:
    return "".join(char.upper() for char in text.strip().rstrip("\0") if not char.isspace())


@lru_cache(maxsize=1)
def _range_table() -> _RangeTable:
    rows = list(csv.reader(io.StringIO(RANGE_CSV_DATA.strip())))
    if not rows:
        raise HostLinkProtocolError("Embedded device range table is empty.")

    headers = [field.strip() for field in rows[0]]
    if len(headers) < 3:
        raise HostLinkProtocolError(
            "Embedded device range table must contain at least DeviceType, Base, and one model column."
        )

    model_headers = tuple(headers[2:])
    range_rows = []
    for row in rows[1:]:
        if len(row) != len(headers):
            raise HostLinkProtocolError(
                f"Embedded device range row has {len(row)} columns but {len(headers)} were expected: {row}"
            )
        range_rows.append(
            _RangeRow(
                device_type=row[0].strip(),
                notation=_notation_from_base(row[1]),
                ranges=tuple(field.strip() for field in row[2:]),
            )
        )
    return _RangeTable(model_headers=model_headers, rows=tuple(range_rows))


def _notation_from_base(base_text: str) -> KvDeviceRangeNotation:
    normalized = base_text.strip()
    if normalized.startswith("10"):
        return KvDeviceRangeNotation.DECIMAL
    if normalized.startswith("16"):
        return KvDeviceRangeNotation.HEXADECIMAL
    raise HostLinkProtocolError(f"Unsupported base cell {base_text!r} in the embedded device range table.")
