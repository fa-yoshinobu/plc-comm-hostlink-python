"""Device parser and validation utilities for Host Link."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import HostLinkProtocolError


SUPPORTED_FORMATS = {"", ".U", ".S", ".D", ".L", ".H"}

# KEYENCE expression + XYM expression
DEVICE_RANGES = {
    "R": (0, 199915, 10),
    "B": (0, 0x7FFF, 16),
    "MR": (0, 399915, 10),
    "LR": (0, 99915, 10),
    "CR": (0, 7915, 10),
    "VB": (0, 0xF9FF, 16),
    "DM": (0, 65534, 10),
    "EM": (0, 65534, 10),
    "FM": (0, 32767, 10),
    "ZF": (0, 524287, 10),
    "W": (0, 0x7FFF, 16),
    "TM": (0, 511, 10),
    "Z": (1, 12, 10),
    "T": (0, 3999, 10),
    "TC": (0, 3999, 10),
    "TS": (0, 3999, 10),
    "C": (0, 3999, 10),
    "CC": (0, 3999, 10),
    "CS": (0, 3999, 10),
    "AT": (0, 7, 10),
    "CM": (0, 7599, 10),
    "VM": (0, 589823, 10),
    "X": (0, 0x1999F, 16),
    "Y": (0, 0x63999F, 16),
    "M": (0, 15999, 10),
    "L": (0, 15999, 10),
    "D": (0, 65534, 10),
    "E": (0, 65534, 10),
    "F": (0, 32767, 10),
}

TYPE_PATTERN = "|".join(sorted(DEVICE_RANGES.keys(), key=len, reverse=True))
DEVICE_RE = re.compile(rf"^(?P<type>{TYPE_PATTERN})?(?P<number>[0-9A-F]+)(?P<suffix>\.[USDLH])?$")


@dataclass(frozen=True)
class DeviceAddress:
    device_type: str
    number: int
    suffix: str = ""

    def to_text(self) -> str:
        _, _, base = DEVICE_RANGES[self.device_type]
        if base == 16:
            number = format(self.number, "X")
        else:
            number = str(self.number)
        return f"{self.device_type}{number}{self.suffix}"


def normalize_suffix(suffix: str | None) -> str:
    if not suffix:
        return ""
    s = suffix.upper()
    if not s.startswith("."):
        s = f".{s}"
    if s not in SUPPORTED_FORMATS:
        raise HostLinkProtocolError(f"Unsupported data format suffix: {suffix!r}")
    return s


def parse_device(text: str, *, allow_omitted_type: bool = True) -> DeviceAddress:
    raw = text.strip().upper()
    match = DEVICE_RE.match(raw)
    if not match:
        if allow_omitted_type and raw.isdigit():
            return parse_device(f"R{raw}", allow_omitted_type=False)
        raise HostLinkProtocolError(f"Invalid device expression: {text!r}")

    device_type = match.group("type") or "R"
    number_text = match.group("number")
    suffix = normalize_suffix(match.group("suffix"))

    lo, hi, base = DEVICE_RANGES[device_type]
    number = int(number_text, base)
    if number < lo or number > hi:
        raise HostLinkProtocolError(
            f"Device number out of range: {device_type}{number_text} (allowed: {lo}..{hi})"
        )
    return DeviceAddress(device_type=device_type, number=number, suffix=suffix)


def parse_device_text(text: str, *, default_suffix: str = "") -> str:
    """Parse/validate device text and return normalized command token."""
    addr = parse_device(text)
    suffix = normalize_suffix(default_suffix) if default_suffix else addr.suffix
    if suffix != addr.suffix:
        addr = DeviceAddress(addr.device_type, addr.number, suffix)
    return addr.to_text()


def validate_range(name: str, value: int, lo: int, hi: int) -> None:
    if value < lo or value > hi:
        raise HostLinkProtocolError(f"{name} out of range: {value} (allowed: {lo}..{hi})")
