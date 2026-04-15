"""Frame builder and response parser for Host Link ASCII protocol."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .errors import HostLinkError, HostLinkProtocolError

ERROR_RE = re.compile(r"^E[0-9]$")
CR = b"\r"
LF = b"\n"


def build_frame(body: str, *, append_lf: bool = False) -> bytes:
    payload = body.strip().encode("ascii")
    if append_lf:
        return payload + CR + LF
    return payload + CR


def build_command(command: str, *params: str, append_lf: bool = False) -> bytes:
    parts = [command, *[p for p in params if p != ""]]
    return build_frame(" ".join(parts), append_lf=append_lf)


def decode_response(raw: bytes) -> str:
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
    localized text. This decoder preserves trailing spaces so callers can
    decide whether to strip padding.
    """

    if not raw:
        raise HostLinkProtocolError("Empty response")
    payload = raw.rstrip(b"\r\n")
    if not payload:
        raise HostLinkProtocolError(f"Malformed response frame: {raw!r}")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        pass

    try:
        return payload.decode("shift_jis")
    except UnicodeDecodeError as exc:
        raise HostLinkProtocolError("Response could not be decoded as UTF-8 or Shift_JIS") from exc


def ensure_success(response_text: str) -> str:
    if ERROR_RE.match(response_text):
        raise HostLinkError(code=response_text, response=response_text)
    return response_text


def split_data_tokens(response_text: str) -> list[str]:
    return [token for token in response_text.split(" ") if token != ""]


def parse_scalar_token(token: str, *, data_format: str = "") -> int | str:
    if data_format == ".H":
        return token.upper()
    try:
        return int(token, 10)
    except ValueError:
        return token


def parse_data_tokens(tokens: Iterable[str], *, data_format: str = "") -> list[int | str]:
    return [parse_scalar_token(token, data_format=data_format) for token in tokens]
