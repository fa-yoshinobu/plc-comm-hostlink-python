# Project Architecture and Design Goals

This document outlines the core design philosophy and technical structure of the KEYENCE KV Host Link Python library.

## 1. Project Background

The library provides a Python interface to KEYENCE KV series PLCs over the Host Link ASCII protocol. It is designed for industrial monitoring and automation tasks requiring reliable device access via TCP or UDP.

## 2. Core Design Principles

- **Sync and Async Parity**: All public operations are available in both synchronous (`KvHostLinkClient`) and asynchronous (`AsyncKvHostLinkClient`) forms with identical signatures.
- **Protocol Fidelity**: Low-level access mirrors the raw ASCII command structure so advanced users can inspect and debug frame-level behavior.
- **High-Level Abstraction**: `KvHostLinkDeviceClient` accepts human-readable device strings (e.g., `"R0"`, `"DM100"`) and handles address validation automatically.

## 3. Layer Structure

```
AsyncKvHostLinkDeviceClient / KvHostLinkDeviceClient   <- high-level string-address API
        |
AsyncKvHostLinkClient / KvHostLinkClient               <- low-level numeric-address API
        |
Protocol helpers (frame builders / parsers)
        |
Transport (TCP/UDP socket)
```

### Low-Level Client (`KvHostLinkClient`)

- Accepts device type + numeric address directly.
- Exposes all supported command groups: device read/write, extended commands, clock, CPU status.
- `send_raw` allows arbitrary frame injection for protocol investigation.

### High-Level Client (`KvHostLinkDeviceClient`)

- Accepts device strings such as `"R0"`, `"DM100"`, `"B1F"`.
- Resolves device strings via `parse_address`.
- Wraps `KvHostLinkClient` internally.

### Protocol Layer

- Stateless frame builder and parser functions.
- Encodes commands as ASCII with CR terminator.
- Decodes responses including `OK`, data values, and `E*` error codes.

## 4. Async Support

`AsyncKvHostLinkClient` and `AsyncKvHostLinkDeviceClient` wrap the synchronous client via `asyncio.get_event_loop().run_in_executor`, providing non-blocking I/O for concurrent monitoring scenarios.

## 5. Extension Utilities (`utils.py`)

- `open_and_connect` — factory that opens and connects in one call
- `read_typed` / `write_typed` — dtype-based access (U/S/D/L/F)
- `write_bit_in_word` — single-bit write within a word device
- `read_named` / `poll` — address-string-based read and polling helpers

## 6. Error Handling

All protocol errors raise `KvHostLinkError`.
The response parser recognizes `E1`, `E2`, `E3` error codes and maps them to descriptive messages.
