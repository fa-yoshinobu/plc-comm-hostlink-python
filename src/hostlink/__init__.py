"""KEYENCE KV Host Link communication library.

The user-facing surface of this package is the high-level helper API exported
from :mod:`hostlink.utils`:

- :func:`open_and_connect`
- :class:`HostLinkConnectionOptions`
- :class:`HostLinkAddress`
- :class:`TimerCounterValue`
- :func:`parse_address`
- :func:`try_parse_address`
- :func:`format_address`
- :func:`normalize_address`
- :func:`read_typed`
- :func:`read_timer_counter`
- :func:`read_timer`
- :func:`read_counter`
- :func:`write_typed`
- :func:`read_comments`
- :func:`read_words_single_request`
- :func:`read_dwords_single_request`
- :func:`read_expansion_unit_buffer`
- :func:`write_expansion_unit_buffer`
- :func:`write_bit_in_word`
- :func:`read_named`
- :func:`poll`

The low-level clients remain part of the package for advanced and maintainer
workflows, but the helpers above are the recommended entry points for normal
application code and generated user documentation.
"""

__version__ = "3.1.0"

from .client import AsyncHostLinkClient, HostLinkClient, HostLinkTrafficStats, ModelInfo
from .device_ranges import (
    KvDeviceRangeCatalog,
    KvDeviceRangeCategory,
    KvDeviceRangeEntry,
    KvDeviceRangeNotation,
    KvDeviceRangeSegment,
    device_range_catalog_for_plc_profile,
)
from .errors import (
    HostLinkBaseError,
    HostLinkConnectionError,
    HostLinkError,
    HostLinkProtocolError,
    decode_error_code,
)
from .plc_profiles import (
    KvHostLinkPlcProfile,
    KvHostLinkPlcProfileDescriptor,
    available_plc_profiles,
    display_name,
    normalize_plc_profile,
    plc_profile_descriptors,
    profile_from_name,
)
from .utils import (
    HostLinkAddress,
    HostLinkConnectionOptions,
    TimerCounterValue,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    poll,
    read_comments,
    read_counter,
    read_dwords,
    read_dwords_single_request,
    read_expansion_unit_buffer,
    read_named,
    read_timer,
    read_timer_counter,
    read_typed,
    read_words,
    read_words_single_request,
    try_parse_address,
    write_bit_in_word,
    write_dwords_single_request,
    write_expansion_unit_buffer,
    write_typed,
    write_words_single_request,
)

__all__ = [
    "HostLinkClient",
    "AsyncHostLinkClient",
    "ModelInfo",
    "HostLinkTrafficStats",
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
    "KvHostLinkPlcProfile",
    "KvHostLinkPlcProfileDescriptor",
    "available_plc_profiles",
    "device_range_catalog_for_plc_profile",
    "display_name",
    "normalize_plc_profile",
    "plc_profile_descriptors",
    "profile_from_name",
    "HostLinkAddress",
    "HostLinkConnectionOptions",
    "TimerCounterValue",
    "format_address",
    "normalize_address",
    "open_and_connect",
    "parse_address",
    "poll",
    "read_comments",
    "read_counter",
    "read_dwords",
    "read_dwords_single_request",
    "read_named",
    "read_timer",
    "read_timer_counter",
    "read_typed",
    "read_words",
    "read_words_single_request",
    "read_expansion_unit_buffer",
    "try_parse_address",
    "write_bit_in_word",
    "write_dwords_single_request",
    "write_expansion_unit_buffer",
    "write_typed",
    "write_words_single_request",
]
