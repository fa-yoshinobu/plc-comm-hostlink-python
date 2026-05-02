"""KEYENCE KV Host Link communication library.

The user-facing surface of this package is the high-level helper API exported
from :mod:`hostlink.utils`:

- :func:`open_and_connect`
- :class:`HostLinkConnectionOptions`
- :class:`HostLinkAddress`
- :func:`parse_address`
- :func:`try_parse_address`
- :func:`format_address`
- :func:`normalize_address`
- :func:`read_typed`
- :func:`write_typed`
- :func:`read_comments`
- :func:`read_words_single_request`
- :func:`read_dwords_single_request`
- :func:`read_words_chunked`
- :func:`read_dwords_chunked`
- :func:`read_expansion_unit_buffer`
- :func:`write_expansion_unit_buffer`
- :func:`write_bit_in_word`
- :func:`read_named`
- :func:`poll`

The low-level clients remain part of the package for advanced and maintainer
workflows, but the helpers above are the recommended entry points for normal
application code and generated user documentation.
"""

__version__ = "0.1.9"

from .client import AsyncHostLinkClient, HostLinkClient, HostLinkTraceDirection, HostLinkTraceFrame, ModelInfo
from .device_ranges import (
    KvDeviceRangeCatalog,
    KvDeviceRangeCategory,
    KvDeviceRangeEntry,
    KvDeviceRangeNotation,
    KvDeviceRangeSegment,
    available_device_range_models,
    device_range_catalog_for_model,
)
from .errors import (
    HostLinkBaseError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
    decode_error_code,
)
from .utils import (
    HostLinkAddress,
    HostLinkConnectionOptions,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    poll,
    read_comments,
    read_dwords,
    read_dwords_chunked,
    read_dwords_single_request,
    read_expansion_unit_buffer,
    read_named,
    read_typed,
    read_words,
    read_words_chunked,
    read_words_single_request,
    try_parse_address,
    write_bit_in_word,
    write_dwords_chunked,
    write_dwords_single_request,
    write_expansion_unit_buffer,
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
    "KvDeviceRangeCatalog",
    "KvDeviceRangeCategory",
    "KvDeviceRangeEntry",
    "KvDeviceRangeNotation",
    "KvDeviceRangeSegment",
    "available_device_range_models",
    "device_range_catalog_for_model",
    "HostLinkAddress",
    "HostLinkConnectionOptions",
    "format_address",
    "normalize_address",
    "open_and_connect",
    "parse_address",
    "poll",
    "read_comments",
    "read_dwords",
    "read_dwords_chunked",
    "read_dwords_single_request",
    "read_named",
    "read_typed",
    "read_words",
    "read_words_chunked",
    "read_words_single_request",
    "read_expansion_unit_buffer",
    "try_parse_address",
    "write_bit_in_word",
    "write_dwords_chunked",
    "write_dwords_single_request",
    "write_expansion_unit_buffer",
    "write_typed",
    "write_words_chunked",
    "write_words_single_request",
]
