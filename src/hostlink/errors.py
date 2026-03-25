"""Error types and error-code decoder for Host Link."""

from __future__ import annotations

from dataclasses import dataclass

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
    """Raised when socket communication fails."""
