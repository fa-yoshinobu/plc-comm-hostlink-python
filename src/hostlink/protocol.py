"""Frame builder and response parser for Host Link ASCII protocol."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .errors import HostLinkError, HostLinkProtocolError

ERROR_RE = re.compile(r"^E[0-9]$")
CR = b"\r"
LF = b"\n"


def build_frame(body: str) -> bytes:
    """Encode a Host Link command body and append the required line ending."""

    payload = body.strip().encode("ascii")
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


def decode_comment_response(raw: bytes) -> str:
    """Decode comment responses which may be UTF-8 or Shift_JIS.

    Normal Host Link responses are ASCII, but PLC comments often contain
    localized text. Host Link comment padding is trailing ASCII space bytes.
    Remove only those bytes before decoding so other whitespace remains.
    """

    if not raw:
        raise HostLinkProtocolError("Empty response")
    payload = raw.rstrip(b"\r\n")
    if not payload:
        raise HostLinkProtocolError(f"Malformed response frame: {raw!r}")
    payload = payload.rstrip(b" ")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        pass

    try:
        return payload.decode("shift_jis")
    except UnicodeDecodeError as exc:
        raise HostLinkProtocolError("Response could not be decoded as UTF-8 or Shift_JIS") from exc


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
        return normalized
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
    try:
        return int(token, 10)
    except ValueError:
        return token


def parse_data_tokens(tokens: Iterable[str], *, data_format: str = "") -> list[int | str]:
    """Convert multiple response tokens according to the selected data format."""

    return [parse_scalar_token(token, data_format=data_format) for token in tokens]
