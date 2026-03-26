"""KEYENCE KV Host Link communication library.

The user-facing surface of this package is the high-level helper API exported
from :mod:`hostlink.utils`:

- :func:`open_and_connect`
- :func:`read_typed`
- :func:`write_typed`
- :func:`read_words`
- :func:`read_dwords`
- :func:`write_bit_in_word`
- :func:`read_named`
- :func:`poll`

The low-level clients remain part of the package for advanced and maintainer
workflows, but the helpers above are the recommended entry points for normal
application code and generated user documentation.
"""

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
