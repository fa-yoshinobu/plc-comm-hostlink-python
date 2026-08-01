"""Frame builder and response parser for Host Link ASCII protocol."""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum

from .errors import HostLinkError, HostLinkProtocolError

ERROR_RE = re.compile(r"^E[0-9]$")
CR = b"\r"
LF = b"\n"


class HostLinkCommentEncoding(str, Enum):
    """Explicit codec choices for Host Link ``RDC`` comment payloads."""

    UTF8 = "utf-8"
    CP932 = "cp932"


def require_comment_encoding(encoding: HostLinkCommentEncoding) -> HostLinkCommentEncoding:
    """Require an explicit public comment codec selection."""

    if not isinstance(encoding, HostLinkCommentEncoding):
        raise ValueError("encoding must be HostLinkCommentEncoding.UTF8 or HostLinkCommentEncoding.CP932")
    return encoding


def build_frame(body: str) -> bytes:
    """Encode a Host Link command body and append the required line ending."""

    if not isinstance(body, str):
        raise HostLinkProtocolError("Host Link command body must be a string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in body):
        raise HostLinkProtocolError("Host Link command body must not contain control characters")
    try:
        payload = body.strip().encode("ascii")
    except UnicodeEncodeError as exc:
        raise HostLinkProtocolError("Host Link command body must contain ASCII characters only") from exc
    if not payload:
        raise HostLinkProtocolError("Host Link command body must not be empty")
    return payload + CR


def build_command(command: str, *params: str) -> bytes:
    """Build one Host Link command frame from a command name and parameters."""

    parts = [command, *[p for p in params if p != ""]]
    return build_frame(" ".join(parts))


def decode_response(raw: bytes) -> str:
    """Decode a normal ASCII Host Link response frame."""

    if not raw:
        raise HostLinkProtocolError("Empty response")
    raw = raw.rstrip(b"\r\n")
    if not raw:
        raise HostLinkProtocolError(f"Malformed response frame: {raw!r}")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise HostLinkProtocolError(f"Response is not ASCII: {raw!r}") from exc

    if not text:
        raise HostLinkProtocolError(f"Malformed response frame: {raw!r}")
    return text


def extract_comment_payload(raw: bytes) -> bytes:
    """Return the exact ``RDC`` response body bytes without CR/LF framing."""

    if not raw:
        raise HostLinkProtocolError("Empty response")
    payload = raw.rstrip(b"\r\n")
    if not payload:
        raise HostLinkProtocolError(f"Malformed response frame: {raw!r}")
    return payload


def decode_comment_response(raw: bytes, encoding: HostLinkCommentEncoding) -> str:
    """Decode one comment response using exactly the caller-selected codec.

    Normal Host Link responses are ASCII, but PLC comments often contain
    localized text. Host Link comment padding is trailing ASCII space bytes.
    Remove only those bytes before decoding so other whitespace remains. No
    codec detection, fallback, or replacement is performed.
    """

    selected = require_comment_encoding(encoding)
    payload = extract_comment_payload(raw).rstrip(b" ")
    try:
        decoded = payload.decode(selected.value, errors="strict")
    except UnicodeDecodeError as exc:
        raise HostLinkProtocolError(
            f"RDC response is not valid {selected.value}; no fallback codec was attempted"
        ) from exc

    if selected is HostLinkCommentEncoding.CP932:
        # Python's CP932 codec accepts five vendor-private single-byte values
        # that the other supported runtimes reject. Exclude those values when
        # they occur as complete code units so the public contract is identical
        # across Python, .NET, Rust, and Node.js. A valid double-byte sequence
        # may still contain 0x80 or 0xA0 as its trail byte.
        index = 0
        while index < len(payload):
            first = payload[index]
            if first <= 0x7F or 0xA1 <= first <= 0xDF:
                index += 1
            elif 0x81 <= first <= 0x9F or 0xE0 <= first <= 0xFC:
                index += 2
            else:
                raise HostLinkProtocolError("RDC response is not valid cp932; no fallback codec was attempted")

    return decoded


def ensure_success(response_text: str) -> str:
    """Return response text or raise ``HostLinkError`` for PLC error codes."""

    if ERROR_RE.match(response_text):
        raise HostLinkError(code=response_text, response=response_text)
    return response_text


def split_data_tokens(response_text: str) -> list[str]:
    """Split a Host Link data response into non-empty scalar tokens."""

    return [token for token in re.split(r"[ ,]+", response_text) if token != ""]


def parse_scalar_token(token: str, *, data_format: str = "") -> int | str:
    """Convert one response token according to the selected Host Link data format."""

    if data_format == ".H":
        normalized = token.upper()
        if not re.fullmatch(r"[0-9A-F]{1,4}", normalized):
            raise HostLinkProtocolError(f"Invalid hexadecimal response token {token!r}")
        return f"{int(normalized, 16):04X}"
    if data_format in {".U", ".S", ".D", ".L"}:
        if not re.fullmatch(r"-?\d+", token):
            raise HostLinkProtocolError(f"Invalid numeric response token {token!r} for format {data_format!r}")
        parsed = int(token, 10)
        limits = {
            ".U": (0, 0xFFFF),
            ".S": (-0x8000, 0x7FFF),
            ".D": (0, 0xFFFFFFFF),
            ".L": (-0x80000000, 0x7FFFFFFF),
        }[data_format]
        if not limits[0] <= parsed <= limits[1]:
            raise HostLinkProtocolError(
                f"Numeric response token {token!r} is outside the range for format {data_format!r}"
            )
        return parsed
    normalized = token.upper()
    if normalized in {"1", "ON"}:
        return 1
    if normalized in {"0", "OFF"}:
        return 0
    raise HostLinkProtocolError(f"Invalid direct bit response token {token!r}; expected 0/1 or OFF/ON")


def parse_data_tokens(tokens: Iterable[str], *, data_format: str = "") -> list[int | str]:
    """Convert multiple response tokens according to the selected data format."""

    return [parse_scalar_token(token, data_format=data_format) for token in tokens]
