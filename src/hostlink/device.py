"""Device parser and validation utilities for Host Link."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import HostLinkProtocolError

SUPPORTED_FORMATS = {"", ".U", ".S", ".D", ".L", ".H"}
BIT_BANK_DEVICE_TYPES = {"R", "MR", "LR", "CR"}
XYM_BIT_DEVICE_TYPES = {"X", "Y"}
DIRECT_BIT_DEVICE_TYPES = {"R", "B", "MR", "LR", "CR", "VB", "X", "Y", "M", "L"}
NATIVE_32BIT_DEVICE_TYPES = {"T", "TC", "TS", "C", "CC", "CS", "CTH", "CTC", "Z", "AT"}

# Syntax-level number bases only. PLC/profile address ranges belong to the public
# device-range catalog and must never be reused as transport send guards.
DEVICE_NUMBER_BASES = {
    "R": 10,
    "B": 16,
    "MR": 10,
    "LR": 10,
    "CR": 10,
    "VB": 16,
    "DM": 10,
    "EM": 10,
    "FM": 10,
    "ZF": 10,
    "W": 16,
    "TM": 10,
    "Z": 10,
    "T": 10,
    "TC": 10,
    "TS": 10,
    "C": 10,
    "CC": 10,
    "CS": 10,
    "CTH": 10,
    "CTC": 10,
    "AT": 10,
    "CM": 10,
    "VM": 10,
    "X": 10,
    "Y": 10,
    "M": 10,
    "L": 10,
    "D": 10,
    "E": 10,
    "F": 10,
}

FORCE_SINGLE_DEVICE_TYPES = {"R", "B", "MR", "LR", "CR", "T", "C", "CTH", "CTC", "VB", "X", "Y", "M", "L"}
FORCE_CONSECUTIVE_DEVICE_TYPES = {"R", "B", "MR", "LR", "CR", "VB", "X", "Y", "M", "L"}
MBS_DEVICE_TYPES = {"R", "B", "MR", "LR", "CR", "T", "C", "CTH", "CTC", "VB", "X", "Y", "M", "L"}
MWS_DEVICE_TYPES = {
    "R",
    "B",
    "MR",
    "LR",
    "CR",
    "VB",
    "X",
    "Y",
    "DM",
    "EM",
    "FM",
    "D",
    "E",
    "F",
    "W",
    "TM",
    "Z",
    "TC",
    "TS",
    "CC",
    "CS",
    "CM",
    "VM",
}
RDC_DEVICE_TYPES = {
    "R",
    "B",
    "MR",
    "LR",
    "CR",
    "DM",
    "EM",
    "FM",
    "ZF",
    "W",
    "TM",
    "Z",
    "T",
    "C",
    "CTH",
    "CTC",
    "CM",
    "X",
    "Y",
    "M",
    "L",
    "D",
    "E",
    "F",
}
WS_DEVICE_TYPES = {"T", "C", "CTH", "CTC"}
WR_DEVICE_TYPES = set(DEVICE_NUMBER_BASES) - {"AT"}

DEFAULT_FORMAT_BY_DEVICE_TYPE = {
    "R": "",
    "B": "",
    "MR": "",
    "LR": "",
    "CR": "",
    "VB": "",
    "DM": ".U",
    "EM": ".U",
    "FM": ".U",
    "ZF": ".U",
    "W": ".U",
    "TM": ".U",
    "Z": ".U",
    "AT": ".D",
    "CM": ".U",
    "VM": ".U",
    "T": ".D",
    "TC": ".D",
    "TS": ".D",
    "C": ".D",
    "CC": ".D",
    "CS": ".D",
    "CTH": ".D",
    "CTC": ".D",
    # XYM aliases
    "X": "",
    "Y": "",
    "M": "",
    "L": "",
    "D": ".U",
    "E": ".U",
    "F": ".U",
}

# Float32 helpers always transfer two consecutive ordinary unsigned words.
# Derive the eligible family set from the canonical Host Link family metadata
# instead of maintaining a second, potentially divergent allow-list.
FLOAT32_ELIGIBLE_DEVICE_TYPES = frozenset(
    device_type for device_type, default_format in DEFAULT_FORMAT_BY_DEVICE_TYPE.items() if default_format == ".U"
)


def is_float32_eligible_device_type(device_type: str) -> bool:
    """Return whether *device_type* has the ordinary two-word Float32 shape."""

    return device_type in FLOAT32_ELIGIBLE_DEVICE_TYPES


_COUNT_CATEGORY_BY_DEVICE_TYPE = {
    # up to 1000 for 16-bit/bit, up to 500 for 32-bit
    "R": "up_to_1000",
    "B": "up_to_1000",
    "MR": "up_to_1000",
    "LR": "up_to_1000",
    "CR": "up_to_1000",
    "VB": "up_to_1000",
    "DM": "up_to_1000",
    "EM": "up_to_1000",
    "FM": "up_to_1000",
    "ZF": "up_to_1000",
    "W": "up_to_1000",
    "CM": "up_to_1000",
    "VM": "up_to_1000",
    "X": "up_to_1000",
    "Y": "up_to_1000",
    "M": "up_to_1000",
    "L": "up_to_1000",
    "D": "up_to_1000",
    "E": "up_to_1000",
    "F": "up_to_1000",
    # up to 512 for 16-bit, up to 256 for 32-bit
    "TM": "tm",
    # up to 12
    "Z": "z",
    # up to 8
    "AT": "at",
    # up to 120
    "T": "t_c",
    "TC": "t_c",
    "TS": "t_c",
    "C": "t_c",
    "CC": "t_c",
    "CS": "t_c",
    "CTH": "t_c",
    "CTC": "t_c",
}

TYPE_PATTERN = "|".join(sorted(DEVICE_NUMBER_BASES.keys(), key=len, reverse=True))
DEVICE_RE = re.compile(rf"^(?P<type>{TYPE_PATTERN})?(?P<number>[0-9A-F]+)(?P<suffix>\.[USDLH])?$")


@dataclass(frozen=True)
class DeviceAddress:
    """Parsed Host Link device token and optional data-format suffix."""

    device_type: str
    number: int
    suffix: str = ""

    def to_text(self) -> str:
        """Return the canonical Host Link device token text."""

        base = DEVICE_NUMBER_BASES[self.device_type]
        if self.device_type in BIT_BANK_DEVICE_TYPES:
            number = _format_bit_bank_number(self.number)
        elif self.device_type in XYM_BIT_DEVICE_TYPES:
            number = _format_xym_bit_number(self.number)
        elif base == 16:
            number = format(self.number, "X")
        else:
            number = str(self.number)
        return f"{self.device_type}{number}{self.suffix}"


def normalize_suffix(suffix: str | None) -> str:
    """Normalize an optional data-format suffix to ``.U``/``.S`` style text."""

    if not suffix:
        return ""
    s = suffix.upper()
    if not s.startswith("."):
        s = f".{s}"
    if s not in SUPPORTED_FORMATS:
        raise HostLinkProtocolError(f"Unsupported data format suffix: {suffix!r}")
    return s


def parse_device(text: str) -> DeviceAddress:
    """Parse and validate one Host Link device token."""

    raw = text.strip().upper()
    match = DEVICE_RE.match(raw)
    if not match:
        valid_types = ", ".join(sorted(DEVICE_NUMBER_BASES.keys()))
        raise HostLinkProtocolError(f"Invalid device string {text!r}. Valid device types: {valid_types}")

    device_type = match.group("type")
    if not device_type:
        valid_types = ", ".join(sorted(DEVICE_NUMBER_BASES.keys()))
        raise HostLinkProtocolError(
            f"Device string {text!r} requires an explicit device type. Valid device types: {valid_types}"
        )
    number_text = match.group("number")
    suffix = normalize_suffix(match.group("suffix"))

    base = DEVICE_NUMBER_BASES[device_type]
    try:
        number = (
            _parse_xym_bit_number(device_type, number_text)
            if device_type in XYM_BIT_DEVICE_TYPES
            else int(number_text, base)
        )
    except HostLinkProtocolError:
        raise
    except ValueError as exc:
        raise HostLinkProtocolError(f"Invalid device number for {device_type}: {number_text!r}") from exc
    # PROFILE_RANGE_NOT_A_TRANSPORT_GUARD: catalog/profile upper bounds belong to
    # application policy. The transport validates syntax, family, non-negative
    # addresses, and the selected wire/text representation, but does not block sends by catalog range.
    if number < 0:
        raise HostLinkProtocolError(f"Device number must not be negative: {device_type}{number_text}")
    if device_type in BIT_BANK_DEVICE_TYPES and number % 100 > 15:
        raise HostLinkProtocolError(
            f"Invalid bit-bank device number: {device_type}{number_text} (lower two digits must be 00..15)"
        )
    return DeviceAddress(device_type=device_type, number=number, suffix=suffix)


def parse_device_text(text: str) -> str:
    """Parse/validate device text and return normalized command token."""
    return parse_device(text).to_text()


def _format_bit_bank_number(number: int) -> str:
    bank = number // 100
    bit = number % 100
    return f"{bank}{bit:02d}"


def bit_bank_logical_number(number: int) -> int:
    """Convert KEYENCE decimal-bank bit notation to a zero-based logical bit number."""

    return (number // 100) * 16 + (number % 100)


def bit_bank_number_from_logical(number: int) -> int:
    """Convert a zero-based logical bit number to KEYENCE decimal-bank notation."""

    return (number // 16) * 100 + (number % 16)


def _format_xym_bit_number(number: int) -> str:
    bank = number // 16
    bit = number % 16
    return f"{bank}{bit:X}"


def _format_device_number(device_type: str, number: int) -> str:
    if device_type in BIT_BANK_DEVICE_TYPES:
        return _format_bit_bank_number(number)
    if device_type in XYM_BIT_DEVICE_TYPES:
        return _format_xym_bit_number(number)

    base = DEVICE_NUMBER_BASES[device_type]
    return format(number, "X") if base == 16 else str(number)


def _parse_xym_bit_number(device_type: str, number_text: str) -> int:
    bank_text = "0" if len(number_text) == 1 else number_text[:-1]
    if not bank_text.isdigit():
        raise HostLinkProtocolError(
            f"Invalid X/Y device number: {device_type}{number_text} "
            "(bank digits must be decimal and bit digit must be 0..F)"
        )

    bank = int(bank_text, 10)
    bit = int(number_text[-1], 16)
    return bank * 16 + bit


def resolve_effective_format(device_type: str, suffix: str) -> str:
    """Return the command data format after applying the device default."""

    return suffix if suffix else DEFAULT_FORMAT_BY_DEVICE_TYPE.get(device_type, "")


def require_explicit_format(addr: DeviceAddress, data_format: str | None = None) -> str:
    """Return a usable data-format suffix or reject ambiguous word access."""

    if addr.suffix:
        raise HostLinkProtocolError(
            f"Low-level device {addr.to_text()!r} must not contain a data-format suffix; "
            "pass the base device and data_format separately."
        )
    if data_format is None or (isinstance(data_format, str) and not data_format.strip()):
        if addr.device_type in DIRECT_BIT_DEVICE_TYPES:
            return ""
        expected = resolve_effective_format(addr.device_type, "") or ".U"
        raise HostLinkProtocolError(
            f"data_format is required for numeric device {addr.to_text()!r}; "
            f"specify {expected!r} or another supported numeric format."
        )
    suffix = normalize_suffix(data_format)
    if suffix:
        return suffix
    raise HostLinkProtocolError(f"data_format is required for numeric device {addr.to_text()!r}.")


def validate_device_type(command: str, device_type: str, allowed_types: set[str]) -> None:
    """Raise if ``device_type`` is not valid for a Host Link command."""

    if device_type not in allowed_types:
        supported = ", ".join(sorted(allowed_types))
        raise HostLinkProtocolError(
            f"Command '{command}' does not support device type '{device_type}'. Supported types: {supported}"
        )


def validate_device_count(device_type: str, effective_format: str, count: int) -> None:
    """Validate a consecutive device count against Host Link command limits."""

    category = _COUNT_CATEGORY_BY_DEVICE_TYPE.get(device_type)
    if category is None:
        raise HostLinkProtocolError(f"No count constraint metadata for device type: {device_type}")

    is_32bit = effective_format in {".D", ".L"}
    if category == "up_to_1000":
        lo, hi = (1, 500) if is_32bit else (1, 1000)
    elif category == "tm":
        lo, hi = (1, 256) if is_32bit else (1, 512)
    elif category == "z":
        lo, hi = (1, 12)
    elif category == "at":
        lo, hi = (1, 8)
    elif category == "t_c":
        lo, hi = (1, 120)
    else:
        raise HostLinkProtocolError(f"Unsupported count category: {category}")

    validate_range("count", count, lo, hi)


def validate_device_span(device_type: str, start_number: int, effective_format: str, count: int = 1) -> None:
    """Validate span arithmetic without enforcing catalog/profile address bounds."""

    if device_type not in DEVICE_NUMBER_BASES:
        raise HostLinkProtocolError(f"Unsupported device type: {device_type}")
    if type(count) is not int or count < 1:
        raise ValueError(f"count must be an integer in the range 1.., got {count!r}")
    if start_number < 0:
        raise HostLinkProtocolError(f"Device number must not be negative: {device_type}{start_number}")

    device_width = _device_span_width(device_type, effective_format)
    start_span_number = bit_bank_logical_number(start_number) if device_type in BIT_BANK_DEVICE_TYPES else start_number
    _ = start_span_number + (count * device_width) - 1


def pack_direct_bit_tokens(tokens: list[int | str], expected_count: int, context: str) -> int:
    """Pack direct-bit response tokens with the first token as bit zero."""

    if len(tokens) != expected_count:
        raise HostLinkProtocolError(
            f"Direct-bit word response for {context!r} contained {len(tokens)} tokens; expected {expected_count}"
        )
    result = 0
    for bit, token in enumerate(tokens):
        if isinstance(token, str):
            normalized = token.strip().upper()
            if normalized in {"1", "ON"}:
                enabled = True
            elif normalized in {"0", "OFF"}:
                enabled = False
            else:
                raise HostLinkProtocolError(f"Invalid direct bit response token: {token!r}")
        elif type(token) is int and token in {0, 1}:
            enabled = token == 1
        else:
            raise HostLinkProtocolError(f"Invalid direct bit response token: {token!r}")
        if enabled:
            result |= 1 << bit
    return result


def _device_span_width(device_type: str, effective_format: str) -> int:
    if device_type in DIRECT_BIT_DEVICE_TYPES:
        if effective_format in {".U", ".S", ".H"}:
            return 16
        if effective_format in {".D", ".L"}:
            return 32
        return 1

    if effective_format in {".D", ".L"} and device_type not in NATIVE_32BIT_DEVICE_TYPES:
        return 2
    return 1


def validate_expansion_buffer_count(effective_format: str, count: int) -> None:
    """Validate an expansion-buffer transfer count for the selected data width."""

    lo, hi = (1, 500) if effective_format in {".D", ".L"} else (1, 1000)
    validate_range("count", count, lo, hi)


def validate_expansion_buffer_span(address: int, effective_format: str, count: int) -> None:
    """Validate that an expansion-buffer span stays inside the supported address range."""

    if type(address) is not int:
        raise ValueError(f"address must be an integer, got {address!r}")
    if type(count) is not int or count < 1:
        raise ValueError(f"count must be an integer in the range 1.., got {count!r}")

    word_width = 2 if effective_format in {".D", ".L"} else 1
    end_address = address + (count * word_width) - 1
    if address < 0 or address > 59999 or end_address > 59999:
        raise HostLinkProtocolError(
            f"Expansion buffer span out of range: {address}..{end_address} with format '{effective_format}'"
        )


def validate_range(name: str, value: int, lo: int, hi: int) -> None:
    """Raise ``ValueError`` unless ``value`` is an exact ``int`` in range."""

    if type(value) is not int or value < lo or value > hi:
        raise ValueError(f"{name} must be an integer in the range {lo}..{hi}, got {value!r}")
