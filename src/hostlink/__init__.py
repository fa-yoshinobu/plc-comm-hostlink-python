"""KEYENCE KV Host Link communication library."""

__version__ = "0.1.2"

from .client import AsyncHostLinkClient, HostLinkClient, HostLinkTraceDirection, HostLinkTraceFrame, ModelInfo
from .errors import (
    HostLinkBaseError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
    decode_error_code,
)
from .utils import (
    open_and_connect,
    poll,
    read_dwords,
    read_named,
    read_typed,
    read_words,
    write_bit_in_word,
    write_typed,
)

__all__ = [
    "HostLinkClient",
    "AsyncHostLinkClient",
    "ModelInfo",
    "HostLinkTraceDirection",
    "HostLinkTraceFrame",
    "HostLinkBaseError",
    "HostLinkConnectionError",
    "HostLinkError",
    "HostLinkProtocolError",
    "decode_error_code",
    "open_and_connect",
    "poll",
    "read_dwords",
    "read_named",
    "read_typed",
    "read_words",
    "write_bit_in_word",
    "write_typed",
]
