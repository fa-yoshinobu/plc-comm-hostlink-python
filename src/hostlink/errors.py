"""Error types and error-code decoder for Host Link."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ERROR_CODE_MESSAGES = {
    "E0": "Abnormal device No.",
    "E1": "Abnormal command",
    "E2": "Program not registered",
    "E4": "Write disabled",
    "E5": "Unit error",
    "E6": "No comments",
}


def decode_error_code(code: str) -> str:
    """Return a readable message for a Host Link error code."""
    return ERROR_CODE_MESSAGES.get(code, "Unknown error")


class HostLinkBaseError(Exception):
    """Base class for all Host Link errors."""


@dataclass
class HostLinkError(HostLinkBaseError):
    """Raised when PLC returns an error response (E0/E1/E2/E4/E5/E6)."""

    code: str
    response: str

    def __str__(self) -> str:
        return f"{self.code}: {decode_error_code(self.code)} (response={self.response!r})"


class HostLinkProtocolError(HostLinkBaseError, ValueError):
    """Raised when a frame/response is malformed."""


class HostLinkConnectionError(HostLinkBaseError, ConnectionError):
    """Compatibility base for machine-readable connection failures."""


class HostLinkFailureReason(Enum):
    """Stable reason retained by :class:`HostLinkOutcomeUnknownError`."""

    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CLOSED = "closed"
    TRANSPORT = "transport"
    MALFORMED_RESPONSE = "malformed_response"


class HostLinkTimeoutError(HostLinkConnectionError, TimeoutError):
    """Raised when a configured connect or transaction deadline expires."""


class HostLinkClosedError(HostLinkConnectionError):
    """Raised when local close retires an active or queued transport generation."""


class HostLinkNotConnectedError(HostLinkConnectionError):
    """Raised when an operation is attempted without a connected transport."""


class HostLinkTransportError(HostLinkConnectionError):
    """Raised for non-timeout socket or transport I/O failure."""


class HostLinkCancelledError(HostLinkBaseError):
    """Raised when an asynchronous Host Link operation is cancelled."""


@dataclass
class HostLinkOutcomeUnknownError(HostLinkBaseError):
    """A state-changing request may have reached the PLC without confirmation."""

    reason: HostLinkFailureReason
    detail: HostLinkBaseError | HostLinkCancelledError

    def __str__(self) -> str:
        return f"State-changing Host Link outcome is unknown ({self.reason.value}): {self.detail}"
