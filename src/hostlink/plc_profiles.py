"""Canonical KEYENCE KV PLC profiles for Host Link."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import HostLinkProtocolError


@dataclass(frozen=True)
class KvHostLinkPlcProfile:
    """One canonical KEYENCE KV PLC profile."""

    name: str
    display_name: str


@dataclass(frozen=True)
class _KvHostLinkPlcProfileDefinition:
    name: str
    display_name: str
    source_label: str

    def to_public_profile(self) -> KvHostLinkPlcProfile:
        return KvHostLinkPlcProfile(self.name, self.display_name)


_PROFILES = (
    _KvHostLinkPlcProfileDefinition("keyence:kv-nano", "KEYENCE KV-NANO", "KV-NANO"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-nano-xym", "KEYENCE KV-NANO (XYM)", "KV-NANO(XYM)"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-3000", "KEYENCE KV-3000", "KV-3000"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-3000-xym", "KEYENCE KV-3000 (XYM)", "KV-3000(XYM)"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-5000", "KEYENCE KV-5000", "KV-5000"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-5000-xym", "KEYENCE KV-5000 (XYM)", "KV-5000(XYM)"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-7000", "KEYENCE KV-7000", "KV-7000"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-7000-xym", "KEYENCE KV-7000 (XYM)", "KV-7000(XYM)"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-8000", "KEYENCE KV-8000", "KV-8000"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-8000-xym", "KEYENCE KV-8000 (XYM)", "KV-8000(XYM)"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-x500", "KEYENCE KV-X500", "KV-X500"),
    _KvHostLinkPlcProfileDefinition("keyence:kv-x500-xym", "KEYENCE KV-X500 (XYM)", "KV-X500(XYM)"),
)


def available_plc_profiles() -> list[str]:
    """Return canonical PLC profile strings supported by the library."""

    return [profile.name for profile in _PROFILES]


def normalize_plc_profile(plc_profile: str) -> str:
    """Return the canonical PLC profile string for a supported profile."""

    return _profile_definition_from_name(plc_profile).name


def display_name(plc_profile: str) -> str:
    """Return the canonical human-readable display name for a PLC profile."""

    return _profile_definition_from_name(plc_profile).display_name


def profile_from_name(plc_profile: str) -> KvHostLinkPlcProfile:
    """Resolve a canonical PLC profile string."""

    return _profile_definition_from_name(plc_profile).to_public_profile()


def _profile_definition_from_name(plc_profile: str) -> _KvHostLinkPlcProfileDefinition:
    normalized = _normalize_text(plc_profile)
    if not normalized:
        raise HostLinkProtocolError("PLC profile must not be empty.")
    for profile in _PROFILES:
        if profile.name == normalized:
            return profile
    supported = ", ".join(available_plc_profiles())
    raise HostLinkProtocolError(f"Unsupported PLC profile {plc_profile!r}. Supported PLC profiles: {supported}.")


def _profiles() -> tuple[_KvHostLinkPlcProfileDefinition, ...]:
    return _PROFILES


def _normalize_text(text: str) -> str:
    return text.strip().rstrip("\0")
