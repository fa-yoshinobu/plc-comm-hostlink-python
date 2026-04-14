"""KEYENCE KV Host Link communication library.

The user-facing surface of this package is the high-level helper API exported
from :mod:`hostlink.utils`:

- :func:`open_and_connect`
- :class:`HostLinkConnectionOptions`
- :func:`read_typed`
- :func:`write_typed`
- :func:`read_words_single_request`
- :func:`read_dwords_single_request`
- :func:`read_words_chunked`
- :func:`read_dwords_chunked`
- :func:`write_bit_in_word`
- :func:`read_named`
- :func:`poll`

The low-level clients remain part of the package for advanced and maintainer
workflows, but the helpers above are the recommended entry points for normal
application code and generated user documentation.
"""

__version__ = "0.1.6"

from .client import AsyncHostLinkClient, HostLinkClient, HostLinkTraceDirection, HostLinkTraceFrame, ModelInfo
from .errors import (
    HostLinkBaseError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
    decode_error_code,
)
from .utils import (
    HostLinkConnectionOptions,
    normalize_address,
    open_and_connect,
    poll,
    read_dwords,
    read_dwords_chunked,
    read_dwords_single_request,
    read_named,
    read_typed,
    read_words,
    read_words_chunked,
    read_words_single_request,
    write_bit_in_word,
    write_dwords_chunked,
    write_dwords_single_request,
    write_typed,
    write_words_chunked,
    write_words_single_request,
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
    "HostLinkConnectionOptions",
    "normalize_address",
    "open_and_connect",
    "poll",
    "read_dwords",
    "read_dwords_chunked",
    "read_dwords_single_request",
    "read_named",
    "read_typed",
    "read_words",
    "read_words_chunked",
    "read_words_single_request",
    "write_bit_in_word",
    "write_dwords_chunked",
    "write_dwords_single_request",
    "write_typed",
    "write_words_chunked",
    "write_words_single_request",
]
