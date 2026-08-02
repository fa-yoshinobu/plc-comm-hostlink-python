# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Entry labels**

- `Release`: Package/version metadata and publishing preparation.
- `Library`: Runtime behavior, public API, protocol handling, or validation in the distributed library.
- `Docs`: README, user guides, generated API docs, or other documentation-only changes.
- `Samples`: Examples, sample flows, sample scripts, or sample applications.
- `Tests`: Test suites, test fixtures, golden vectors, or verification data.
- `Tooling`: Developer/operator command-line tools and helper utilities.
- `CI`: Release checks, workflow scripts, or automation-only changes.

## [Unreleased]

- Library: Bare direct-bit `MWS` targets remain suffix-free on the wire, while their corresponding `MWR` fields are now validated as packed unsigned 16-bit values using exactly one through five ASCII decimal digits and numeric range `0..65535`. Leading zeros are optional; empty or whitespace-only, signed, non-decimal, over-five-digit, and overflowing fields retire the transport. The existing `list[str]` return representation is unchanged; scalar `RD` and `MBS`/`MBR` remain strict bit operations.
- Tests: Added sync/async live-vector, mixed-registration, invalid-response retirement, and reconnect/stale-monitor-metadata coverage for bare direct-bit `MWS`/`MWR`.
- Library: Timer/counter composite responses keep the structural status as the PLC-semantic integer `0` or `1`; the selected `.U`, `.S`, `.H`, `.D`, or `.L` format applies only to current and preset values. Public signatures and Python return types are unchanged.
- Library: Correct formatted single reads of direct-bit devices to accept the PLC's one packed scalar response token instead of expecting 16 or 32 separate bit tokens. Signed `.S` and `.L` responses accept the PLC's explicit leading `+`; bare bit reads remain strict `0`/`1`/`ON`/`OFF` reads. Public signatures are unchanged.
- Library: TCP response framing now uses a reusable growable accumulator with an incremental scan cursor; synchronous numeric-IPv4 connection establishment uses workerless nonblocking `connect_ex`, while hostname DNS remains isolated from the caller deadline.
- Library: Async request admission now uses an O(1) ordered FIFO for enqueue, cancellation removal, and dequeue.
- Tests: Added maximum-size one-byte-fragment response bounds, FIFO source-contract checks, and deterministic numeric-IPv4 connect/close lifecycle coverage.
- Docs: Documented the TCP request-identifier limitation, the residual pre-send-check race, healthy persistent-connection latency decision, and connection-scoped monitor registration.
- Tests: Added direct sync/async TCP checks proving observable pre-send unowned input sends no request and retires the connection, plus monitor registration/read and reconnect/re-registration coverage.
- Library: Public sync/async raw commands now finish frame validation before FIFO admission; the already-invalid empty command remains a protocol input error and reaches no connection or exchange work.
- Tests: Added explicit sync/async cross-language contract evidence that empty public raw input enters neither admission nor exchange and leaves connection and traffic state unchanged.
- Library: **Breaking:** Reject bracketed IPv4 host input such as `[127.0.0.1]` before DNS or socket work; use `127.0.0.1` instead.
- Library: **Breaking:** Limit every raw ASCII request body to 65,506 bytes so the terminating CR produces a maximum 65,507-byte frame for both TCP and UDP.
- CI: Restored Ruff formatting compliance for all tracked Python source.
- Docs: Changed controlled register and expansion-buffer write examples to save and attempt restoration after confirmed writes and to require explicit reconciliation after an outcome-unknown result.
- Tests: Added getting-started/usage fence compilation and cleanup-contract checks for controlled writes.
- Library: **Breaking:** Float32 parsing, formatting, typed access, named reads, and polling now accept only canonical ordinary `.U` word families (`DM`, `EM`, `FM`, `ZF`, `W`, `TM`, `CM`, `VM`, `D`, `E`, `F`); native 32-bit `Z`, direct-bit, and special-response families such as `R`, `T`, `C`, and `AT` fail before FIFO admission and transport.
- Library: **Breaking:** Semantic `.H` reads now return exactly four uppercase hexadecimal digits, and MWR validates every returned token against the ordered formats registered by MWS.
- Library: UDP now reuses one connected socket and local endpoint across successful requests. Timeout, cancellation, transport/protocol failure, malformed or extra input, and detected pre-send unowned datagrams discard that socket; the next request creates a fresh socket from the cached numeric IPv4 endpoint without repeating DNS.
- Library: TCP accepts exactly one non-empty response per request; an extra response is a protocol error and retires the transport instead of becoming the next command's result.
- Library: Async TCP/UDP connection candidates completed after `close()`, cancellation, or timeout are discarded and closed exactly once before they can publish connected state.
- Library: **Breaking:** Timer/counter composite response status must be exactly `0` or `1`; any other numeric status is an invalid response and retires the connection.
- Library: **Breaking:** Public address parsing, normalization, and formatting now share device/data-type compatibility validation; formatters reject invalid hand-constructed address objects instead of emitting unusable text.
- Library: **Breaking:** Named reads and polling reject semantically duplicate keys after device, address, dtype, bit-index, and scalar-count normalization; spelling variants no longer create two keys, while distinct dtype views, bit indices, and overlapping spans remain valid.
- Library: Reject IPv6 literals before connection work and bound synchronous TCP/UDP connection establishment with one monotonic absolute `connect_timeout` from IPv4 DNS through socket configuration and atomic adoption; late resolver/socket results are discarded and partial sockets are closed.
- Tests: Added deterministic synchronous literal/DNS, TCP/UDP, delayed-resolution, delayed-connect, concurrent-close, TCP-option failure, IPv6 rejection, and overflow-boundary coverage for the connection deadline.
- Docs: Clarified the separate complete connection and request deadlines, explicit-only lifecycle, IPv4-only resolver policy, late-result handling, and synchronous TCP socket options.
- Release: Aligned artifact roles so the registry package contains consumer runtime, native API metadata, license, README, and ecosystem-native examples where applicable while excluding repository tests and maintainer tooling; the GitHub source archive retains tracked non-hardware validation and maintainer inputs.
- Docs: README documentation links now include the shared Performance and Choosing a Language pages, and package registry metadata was expanded for discoverability. No functional change.

### BREAKING

- Library: Device-comment text reads now require an explicit `HostLinkCommentEncoding.UTF8` or `.CP932` selection. Removed UTF-8-first/Shift_JIS-fallback decoding; named reads containing `:COMMENT` also require `comment_encoding`.
- Library: Integer-only public arguments now require an exact Python `int`; booleans, floats, numeric strings, implicit conversions, and out-of-range values raise `ValueError` before communication.
- Library: Removed the public sync/async/helper `write_bit_in_word` read-modify-write API without an alias because it could lose updates made by the PLC or another connection.
- Library: Replaced generic connection failures with machine-readable timeout, cancellation, closed, not-connected, transport, and state-changing outcome-unknown errors; callers that match exact exception types must migrate.

### Migration

- Remove brackets from IPv4 host input. Reduce raw request bodies longer than 65,506 ASCII bytes or use command-specific operations whose protocol contract permits multiple requests.
- Pass `HostLinkCommentEncoding.UTF8` or `.CP932` to `read_comments`; pass `comment_encoding` when `read_named` or `poll` contains `:COMMENT`. Use `read_comment_bytes` when the application cannot assert the payload encoding.
- Pass actual integers to bank, count, unit, address, mode, and bit-index parameters. Keep `PROGRAM` and `RUN` only where the mode API explicitly documents those string forms.
- Replace `write_bit_in_word` with a PLC-side atomic bit operation or an application/PLC ownership design for the complete word.
- Catch the specific Host Link error type needed by the application. For `HostLinkOutcomeUnknownError`, inspect `reason`, reconcile PLC state explicitly, and do not blindly retry.
- Move Float32 data from `Z:F` to an ordinary word family or access Z through its supported integer representation. Expect semantic hexadecimal reads such as `A` to be returned as `000A`. Allow the UDP source port to change only after an exchange invalidates the reused socket.

### Fixed

- Library: `RDC` comment decoding no longer guesses a codec. UTF-8 and the portable strict CP932/Windows-31J repertoire decode consistently across runtimes, ambiguous bytes follow only the caller selection, malformed or runtime-private bytes never fall back or use replacement, and raw comment payload bytes are available without losing trailing padding.
- Library: Reject Float32 writes to direct bit devices before transport, require exact `0`/`1` operating-mode responses, reject non-positive or non-finite poll intervals, and calculate `R`/`MR`/`LR`/`CR` catalog bounds through banked-bit logical indexes.
- Library: Normal sync/async clients now use arrival FIFO admission; waiting async cancellation sends nothing, and `close()` immediately rejects active and queued work. One absolute request deadline covers transmit, drain, receive, and decode, while connection establishment has a separate deadline.
- Library: `read_named`/`poll` now preflight the complete input, group wire reads by first-occurring device type, sort each group by address, merge compatible contiguous or overlapping spans up to protocol limits, and hold one FIFO turn. Public result keys remain in caller order; multi-request results remain non-atomic and never return a partial dictionary after failure. Polling compiles this plan once and reuses it for every cycle.
- Library: Enforce the 65,506-byte request-body and 65,536-byte response-body boundaries before transport/acceptance, retain native failure causes, never automatically resend after a possible send, and keep all transports IPv4-only.
- Samples: Correct the dtype-bearing normalization examples, validate every runnable sample, and make `basic_test.py` read-only unless a controlled write-test device is explicitly selected; write tests restore the original value.
- CI: Include tests and fixtures in GitHub source archives and execute the complete non-hardware and package-consumer gates from the extracted archive.
- CI: Package validation now installs the built wheel into a fresh isolated virtual environment and checks public imports, signatures, docstrings, version identity, and installed origin without checkout or `PYTHONPATH` access.
- CI: Worktree source-archive validation now uses one synthetic Git tree containing modifications, untracked files, and deletions instead of archiving `HEAD` with an incomplete overlay.

## [3.2.1] - 2026-07-29

- Release: Bumped package metadata and `hostlink.__version__` to `3.2.1`.
- Release: GitHub Release drafts now prepend this version's changelog section to generated notes and repair a missing section on workflow reruns.

### BREAKING
- Library: Removed the deprecated, ineffective `allow_omitted_type` keyword from the internal device parser. Device tokens must continue to include an explicit device type.

### Migration
- Replace `parse_device(text, allow_omitted_type=...)` with `parse_device(text)`; the removed keyword never enabled omitted device types.

### Fixed
- Library: Parse hexadecimal profile range endpoints such as `VB0-F9FF` without discarding valid leading hexadecimal letters.
- Library: Synchronous and asynchronous TCP/UDP exchanges now use one absolute request deadline across send, drain, and complete response assembly. Repeated partial data can no longer restart the timeout; an incomplete timed-out exchange still invalidates its transport.
- Library: Direct-bit numeric and bit-in-word reads/writes now pack or preserve complete 16-/32-bit values, and ordinary disconnects retain the public connection-error classification.
- Library: Consecutive RDS requests split at command limits, while profile/device catalog upper bounds no longer reject sends; the internal parser table now stores number bases only.

### Tests
- Tests: Added trickle-response and send-delay coverage proving that the configured timeout bounds the complete request rather than each individual I/O wait.

## [3.2.0] - 2026-07-17

- Release: Bumped package metadata and `hostlink.__version__` to `3.2.0`.
- CI: Excluded maintainer-only files, tests, and release tooling from generated source archives while retaining the complete sample set, and added source-archive contract checks to local, CI, and release gates.

- Library: Added immutable client-lifetime traffic snapshots through `traffic_stats()` on synchronous and asynchronous clients.
- Library: Made TCP receive-byte accounting independent of CR/LF segmentation by counting the response body and first terminator only; UDP datagram accounting is unchanged.

## [3.1.0] - 2026-07-13

### Added
- Library: Added `KvHostLinkPlcProfileDescriptor` and `plc_profile_descriptors()` for canonical Host Link profile metadata.

### Changed
- Library: Require explicit `port`, `transport`, and canonical `plc_profile` connection settings while retaining the common 3-second timeout default.
- Library: Constructors now perform local initialization only; commands require an explicit successful `connect()` and never reconnect or retry implicitly after transport failure.
- Library: Fix normal command framing to CR, make PLC clock values and expansion-buffer formats mandatory, and strictly validate typed write values and response tokens without masking or fallback conversion.
- Library: Return undecoded response-body `bytes` from maintainer `send_raw`; semantic operations use private command-specific decoding.
- Library: Normalize comment padding by removing trailing ASCII space bytes only, and serialize sync and async bit-in-word read-modify-write operations as one compound critical section.
- Library: Enforce an internal 65,536-byte response-body cap for TCP and UDP while keeping receive chunk sizing private.
- Docs: Document the explicit connection lifecycle, base-device plus separate-format low-level contract, and single-request timing boundary.
- Samples/Tooling: Require an explicit destination port for every runnable single-PLC, multi-PLC, configuration-driven, and validation entry point. Multi-PLC inputs may inherit only an explicitly supplied common port; no `8501` runtime fallback remains.

- Release: Bumped package metadata and `hostlink.__version__` to `3.1.0`.

### Removed
- Library: Breaking: Remove `auto_connect`, `append_lf_on_send`, public receive-buffer sizing, public trace exports/options, comment padding switches, default address suffixes, and public automatic word/dword chunking helpers.
- Library: Breaking: Reject suffix-bearing numeric low-level devices such as `DM0.U`; pass `device="DM0"` and `data_format=".U"` separately.

### Deprecated
- Library: Deprecated the ineffective `allow_omitted_type` parser argument; device types remain explicit.

### Fixed
- Library: Reject missing or contradictory numeric formats before communication, eliminating the conflicting low-level `DM100.D` dword and high-level `DM100.D` bit-13 interpretations.
- Library: Preserve raw PLC error and non-ASCII response bytes, reject invalid calendar/weekday combinations, and discard transports after response overflow or incomplete exchanges.
- Library: Require exact command-derived response token counts, strict documented `0`/`1`/`ON`/`OFF` direct-bit tokens, and CR/LF-terminated UDP datagrams; malformed UDP framing invalidates the transport.
- Library: Derive single-read token counts from device width (including 16/32-point direct-bit numeric reads) and discard the session after malformed semantic response shapes.
- Library: Reject CR/LF and other control characters in maintainer raw command bodies, preventing multi-frame injection and response desynchronization.
- Library: Reject empty named reads/polls and Float32 overflow with the documented `ValueError`; datetime clock values are limited to years 2000 through 2099.
- Tooling: Update the E2E smoke script to require `plc_profile`, remove the deleted LF option, and verify raw `b"E1"` behavior.
- Tests: Remove library-local cross-implementation frame vectors; cross-language verification is maintained as a separate repository and test concern.


- Library: Corrected ten KV device range cells against live PLC hardware and the KEYENCE simulator, and pinned the canonical profile source to `plc-comm-hostlink-profiles` `v1.2.0`. `VM` widens to `VM0-9999` on KV-NANO and `VM0-59999` on KV-3000/KV-5000; `Z` widens to `Z1-23` on KV-8000. `CTH` narrows to `CTH0-1` on the KV-3000 and KV-5000 XYM profiles, matching their base profiles: `CTH2` and `CTH3` were previously accepted there and are now rejected.
- Library: Discard sync and async TCP/UDP transports after timeout, cancellation, partial response, or socket failure.
- Library: Parse BIT writes from explicit boolean tokens and reject ambiguous values before communication.
- Library: Serialize bit-in-word read-modify-write pairs across the full compound operation.
- CI: Require exact-tag checkout and verify tag, manifest, runtime, and distribution versions before a GitHub Release upload.
- Docs: Correct the supported-profile scope, `CTH`/`CTC` parser behavior, optional YAML dependency, and maintainer commands.

## [3.0.0] - 2026-07-10

### Changed
- Release: Bumped package metadata and `hostlink.__version__` to `3.0.0`.
- Docs: Replaced relative README links with absolute URLs so they resolve on package registry pages.
- Docs: Updated PLC profile documentation and API reference entries for the new `hostlink.plc_profiles` module.
- Tests: Updated canonical PLC profile display-name coverage to use the profile API.

### BREAKING
- Library: Breaking: Moved PLC profile lookup APIs into `hostlink.plc_profiles`; imports from `hostlink.device_ranges` are no longer supported.
- Migration: Import `available_plc_profiles`, `normalize_plc_profile`, `profile_from_name`, and `display_name` from the package root or `hostlink.plc_profiles`.

## [2.0.0] - 2026-07-06

### BREAKING
- Release: Renamed the PyPI install package while keeping the Python import name unchanged.

| Old install name | New install name | Import name |
| --- | --- | --- |
| `kv-hostlink` | `plc-comm-kv-hostlink` | `hostlink` |

### Added
- Docs: Added `docsrc/user/API_REFERENCE.md` as the standard user-facing API index and linked it from the README.

### Changed
- Release: Bumped package metadata to `2.0.0`.
- Docs: Added the plc-comm family package matrix link to the README.
- Tests: Added package-rename import-name coverage for `import hostlink`.
- Tooling: Updated release duplicate checks to query `plc-comm-kv-hostlink`.

## [1.3.0] - 2026-07-06

### Added
- Release: Bumped package metadata to `1.3.0` and synced the embedded profile fixture to `plc-comm-hostlink-profiles` `v1.1.0`.
- Library: Added `CTH`/`CTC` (high-speed counter / comparator, codes 04H/05H) device support to the address parser, treated like the counter (`C`) device. Availability is model/unit dependent (governed by the canonical catalog).
- Library: Synced the embedded KV Host Link device-range catalog with the canonical `TC`/`TS`/`CC`/`CS` (timer/counter current and set value) rows and official `device_name` labels.

### Fixed
- Library: Corrected the misspelled `KvDeviceRangeCategory.FILE_REFRESH` member to `FILE_REGISTER` (value `file_refresh` → `file_register`). The category is a descriptive label only; device identification uses `device_type`/device code and bit/word width uses `is_bit_device`.

## [1.2.0] - 2026-07-05

### Changed
- Release: Bumped package metadata to `1.2.0`.
- Tooling: Normalized line-ending handling in the canonical profile JSON update script so `-SourceRoot` runs no longer report false changes.
- Release: Synced `__version__` with the package version.
- Library: Synced the embedded KV Host Link device-range fixture to `plc-comm-hostlink-profiles` `v1.0.1`, including `display_name` labels for KEYENCE model families and XYM variants.
- Library: Added `display_name(plc_profile)` as the public UI-label helper while keeping stored PLC profile values canonical.
- Docs: Documented the profile display-name helper and canonical-ID storage guidance.
- Tests: Added canonical fixture parity coverage for profile `display_name` values.
- Samples: Added read-only `multi_plc_monitor.py` and `config_polling.py` operational recipes with dry-run validation and reconnect backoff.
- Docs: Added public API docstrings for the Host Link Python package and a CI coverage check for public API documentation.
- Docs: Removed the per-library troubleshooting/code page; shared KV Host Link troubleshooting and code guidance now lives in the PLC Setup Guide.
- Docs: Removed the per-library latest communication verification page and links so user docs stay focused on usage, not verification logs.
- Docs: Removed the manual page-navigation block from Getting Started and rely on site navigation instead.
- Docs: Removed the thin per-library Troubleshooting page after moving common KV Host Link troubleshooting to the PLC Setup Guide.
- Docs: Moved shared KV Host Link gotcha and troubleshooting items to the common PLC Setup Guide and standardized the Gotchas page structure with SLMP.
- Docs: Moved shared supported-register and device-range guidance to the common KV Host Link Device Ranges page and folded the Python API reference summary into the Usage Guide.

## [1.1.1] - 2026-06-29

### Changed
- Release: Bumped package metadata to `1.1.1`.
- Docs: Documented explicit Host Link value-format requirements in existing user docs.
- Samples: Updated high-level, snapshot, and polling samples to use explicit value-format suffixes.

## [1.1.0] - 2026-06-29

### Changed
- Release: Bumped package metadata to `1.1.0`.
- Library: Made Host Link device parsing require explicit device areas and value-format suffixes; numeric-only devices no longer default to `R`, and suffixless named addresses no longer infer a default format.
- Docs: Updated Host Link API, supported-register, and usage guidance for explicit device/value-format requirements.
- Tests: Updated parser, high-level helper, sync/async parity, spec-compliance, and shared frame-vector coverage for explicit device/value-format requirements.

### Fixed
- Library: Reject malformed embedded device-range segments while building the KV range catalog instead of silently defaulting invalid lower bounds to `0`.
- Library: Made `BIT_IN_WORD` helper addresses require an explicit bit index such as `DM100.0` through `DM100.F`; `DM100:BIT_IN_WORD` now fails instead of silently reading bit 0.
- Tests: Added coverage for invalid embedded device-range segment parsing.
- Tests: Added coverage for rejecting `BIT_IN_WORD` addresses without an explicit bit index.

## [1.0.1] - 2026-06-25

### Changed
- Release: Bumped Python package metadata to `1.0.1`.
- Library: Removed the `None` default from `HostLinkConnectionOptions.plc_profile` so connection options require an explicit canonical PLC profile.
- Library: Made `open_and_connect()` reject omitted `plc_profile` values instead of relying on a fallback placeholder.
- Docs: Updated Host Link documentation for safer write/restore patterns.
- Samples: Updated Host Link samples to use safer write/restore patterns.

## [1.0.0] - 2026-06-24

### Changed
- Release: Bumped package metadata to `1.0.0` for the first stable release line.
- Tests: Expanded the Host Link frame-vector test runner so the Python suite covers the same command families as the shared vector file.

### Fixed
- Tests: Aligned the Python Host Link frame vectors with the .NET canonical vector set so matching IDs describe the same request shape across libraries.
