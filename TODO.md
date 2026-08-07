# TODO: Host Link Communication Python

Current active TODOs only.

## Current Status

## HL-PY-004 — Unify the single bit-in-word aggregate read command

### Implementation scope

- Python `read_named` and `poll` plans containing one otherwise unmerged
  bit-in-word point on an optimizable ordinary word-device family

### Target contract

Send `RDS <device>.U 1` for that aggregate segment, matching the .NET,
Node.js, and Rust Host Link implementations. Ordinary single-value `read`
continues to use `RD`; the aggregate still performs one request and returns the
same Boolean value.

### Compatibility impact

Only the Python aggregate wire command changes from `RD` to the explicit
counted `RDS ... 1` form. Public API signatures, values, connections, and
round-trip count do not change.

### Acceptance criteria

1. A sole `DM100.A` named read sends exactly `RDS DM100.U 1` and returns the
   selected bit as `bool`.
2. `poll` reuses the same counted request on every cycle.
3. Ordinary `read("DM100", data_format=".U")` still sends `RD DM100.U`.
4. Host Link cross-verification observes the same aggregate frame in Python,
   .NET, Node.js, and Rust.

### Completion checklist

- [x] Python implementation completed.
- [x] Named-read and poll regression tests added.
- [x] Python static checks and full unit suite passed.
- [x] Host Link cross-language verification passed against the corrected Python source.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is not required for this exact mock wire-contract correction.
- [x] Changelog and maintainer migration record agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

The approved overhaul items, including `HL-EVAL-TODO-006` and
`HL-CONTRACT-001` through `HL-CONTRACT-005`, are implemented in the working
tree. Final cross-runtime verification for the comment-decoding contract is
recorded in the `HL-EVAL-TODO-006` checklist below.

### Verification evidence — 2026-08-01

- Current-worktree CI passed 270 pytest cases plus 18 API-reference generator
  subtests, sample checks, formatting/static checks, build, and package checks;
  Python 3.10 independently passed all 270 tests plus 18 subtests.
- A synthetic current-worktree Git tree produced a self-contained source
  archive; its clean extracted test/build gate passed with 270 tests and its
  isolated package consumer verified all 11 required public symbols.
- The distribution-content guard kept the registry package minimal while the
  GitHub source archive retained tests and fixtures.
- Codex reviewed the actual diff, public surface, validation order, error and
  connection behavior, samples, documentation, and cross-language contracts.
- The first final Python 3.10 rerun exposed a timer-resolution-sensitive
  decoder-deadline test. Its artificial delay was widened without changing the
  runtime contract, and both Python 3.10 and current-runtime suites then passed.
- These deterministic validation and packaging corrections do not require
  additional live PLC communication.

## HL-EVAL-001 — Reject Float32 writes to direct bit devices before transport

### Implementation scope

- Python high-level Float32 write planning in synchronous, asynchronous, and queued paths
- Every direct bit device family accepted by the address parser, including `Y`, `R`, `B`, `MR`, `LR`, `CR`, `VB`, `X`, `M`, and `L`

### Target contract

Float32 (`F`) writes are supported only for word devices. A direct bit target is rejected as caller input before frame construction or transport; the implementation must not reinterpret, split, retry, or send the Float32 bit pattern as consecutive bit writes.

### Compatibility impact

Calls that previously could emit unintended multi-bit writes now fail before communication. This is an intentional safety correction; no compatibility alias or fallback is retained.

### Acceptance criteria

1. `Y0:F` and `R0:F` writes fail with the documented Python input-validation error before any transport call.
2. Every supported direct bit family follows the same rejection path, while valid word-device Float32 writes retain their defined two-word encoding.
3. Sync, async, queued, named, and direct public write paths cannot bypass the validation.
4. Regression tests prove zero sends for rejected writes; live PLC writes are not required for this safety guard.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-005 — Normalize banked bit ranges before calculating bounds and point counts

### Implementation scope

- Python profile/device-range metadata for `R`, `MR`, `LR`, and `CR`
- Public lower-bound, upper-bound, point-count, and display-range properties

### Target contract

Banked bit addresses are parsed as a decimal bank plus a final bit field `00..15`, and their logical index is `bank * 16 + bit`. Numeric bounds and point counts use the logical index, while the public display range preserves PLC notation. Profile catalog ranges remain descriptive metadata and are not communication-library pre-send address guards.

### Compatibility impact

Incorrect numeric bounds and point counts change to their logical values. Display addresses remain in PLC notation, and no new transport-side range rejection is introduced.

### Acceptance criteria

1. All catalog rows for `R`, `MR`, `LR`, and `CR` produce logical lower/upper indices and exact point counts from `bank * 16 + bit`.
2. KV-8000 `R00000..R199915` reports 32,000 points and `MR00000..MR399915` reports 64,000 points.
3. Invalid final bit fields outside `00..15` are rejected by catalog parsing/tests.
4. Address-range display text remains unchanged and transport APIs do not enforce profile catalog bounds.
5. Equivalent vectors agree with the Rust and .NET implementations.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-TODO-006 — Determine the Host Link device-comment encoding contract

### User disposition

The target contract was approved by the user on 2026-08-01. An `RDC` comment encoding must not be fixed by the library or PLC profile and must not be guessed by UTF-8-first/Shift_JIS-fallback decoding. Text decoding requires an explicit caller-selected encoding, and exact raw comment payload bytes remain available. The user subsequently authorized implementation in the current Host Link overhaul cycle.

### Implementation scope

- Python `RDC` device-comment decoding and its sync/async helper and client APIs
- Cross-language comparison with the Rust, Node-RED, and .NET Host Link implementations
- Shared Host Link user documentation where the resulting behavior is common

### Target state

An `RDC` response is first treated as an exact byte payload. A caller that requests text explicitly selects the supported encoding used for that decode. The Python implementation performs no heuristic UTF-8-first fallback, PLC-profile selection, write-source inference, or silent replacement of malformed bytes. A public raw-byte path exposes the undecoded comment payload.

The public selections are exactly UTF-8 and CP932/Windows-31J compatibility;
strict Shift_JIS is not a separate selection. UTF-8 preserves an initial BOM as
text and rejects malformed input. CP932 preserves ASCII bytes `00` through
`7F` as the same Unicode code points, accepts mapped half-width and double-byte
Windows-31J characters, and rejects malformed, unmapped, or vendor-private
single bytes `80`, `A0`, and `FD` through `FF`. This shared subset removes
runtime-specific decoder behavior without guessing or fallback.

### Compatibility impact

This is an intentional breaking change. Existing string APIs that silently try UTF-8 and then Shift_JIS must require an explicit encoding selection, while callers that cannot assert an encoding use the raw-byte API. Migration notes must identify the required selection and the removal of heuristic decoding.

### Acceptance criteria

1. Every public `RDC` text-decoding path requires an explicit supported encoding and has no automatic or profile-selected codec.
2. A public raw-byte path returns the undecoded `RDC` comment payload.
3. The exact codec mapping is defined consistently across all four runtimes, including whether Shift_JIS and Windows-31J/CP932 are separate selections.
4. Ambiguous byte sequences valid under multiple codecs decode only according to the caller's selection; malformed sequences fail without fallback or replacement.
5. Decoder failure and connection-state behavior are explicit and consistent with the library's protocol-error contract.
6. User documentation, tests, generated API reference, changelog, and migration notes agree with the approved contract in every affected implementation.

### Evidence and completion checklist

- [x] Evidence sufficient to reject a universal or profile-fixed `RDC` codec is recorded.
- [x] Shift_JIS versus Windows-31J/CP932 mapping resolved for all four language runtimes.
- [x] Ambiguous and malformed byte vectors defined with evidence-backed expected results.
- [x] Further profile-by-profile live verification is not required to select the explicit-codec/raw-byte contract.
- [x] Target contract and compatibility impact explicitly approved by the user.
- [x] Implementation completed in every affected repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Required live-PLC checks passed, or each unavailable check has an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

### Python implementation and review evidence

- The sync, async, and high-level text APIs require the enum; the raw API
  preserves exact terminator-free payload bytes including ASCII-space padding.
- Named reads and polls require an explicit codec exactly when a `:COMMENT`
  entry exists. Missing and unused codec settings fail before FIFO admission or
  transport.
- Shared ambiguity, BOM, ASCII-control, forbidden-singleton, mapped-extension,
  malformed, raw-padding, PLC-error, and connection-retirement vectors are
  executable tests. A valid PLC `E0` through `E9` keeps the connection reusable.
- Codex self-review inspected the actual diff, public API, validation order,
  errors, connection state, deadlines, aggregate behavior, tests, docs,
  packaging, and cross-runtime mapping. Accepted and corrected findings: `4`;
  rejected: `0`; duplicate: `0`; deferred: `0`.
  - Python's codec accepted five nonportable private singleton bytes; explicit
    code-unit validation now rejects them without rejecting a valid `80`/`A0`
    trail byte.
  - An explicit codec on a non-comment aggregate was silently unused; it now
    fails complete preflight with zero sends.
  - Shared ambiguity and UTF-8 BOM vectors were aligned with the other three
    runtimes.
  - Sync and async connection-state tests now prove decoder failure retires the
    connection while a framed PLC error does not.

### Current evidence boundary

Before this implementation cycle, the reviewed implementations tried UTF-8
first and fell back to Shift_JIS. The located KEYENCE material says that
KV-8000 strings use Shift_JIS in a specific EtherNet/IP connection-guide
context, but it does not define the Host Link `RDC` response encoding:
<https://www.keyence.co.jp/support/user/controls/plc/connection_guide/kv_iv4/>.

The deterministic cross-runtime vectors include `C2 A2` as UTF-8 `U+00A2`
and CP932 `U+FF82 U+FF62`; UTF-8 `EF BB BF 41` as retained `U+FEFF A` and an
invalid CP932 sequence; exact CP932 ASCII controls `1A`, `1C`, and `7F`;
Windows extension mappings `87 90` → `U+2252`, `ED 40` → `U+7E8A`, and
`FA 4A` → `U+2160`; malformed UTF-8 `E3 81`; forbidden CP932 singletons
`80`, `A0`, and `FD` through `FF`; and incomplete, malformed, or unassigned
CP932 pairs. Every invalid vector raises `HostLinkProtocolError`, performs no
fallback or replacement, and retires the connection that received it.

On 2026-08-01, after the user's explicit `OK`, a read-only live check used KEYENCE KV-X500 / `keyence:kv-x500` at `192.168.250.100:8501`. `RDC R000` returned `E38182E38184E38186E38188E3818A` (UTF-8 `あいうえお`) and `RDC R001` returned `E3818BE3818DE3818FE38191E38193` (UTF-8 `かきくけこ`). Both payloads fail strict Shift_JIS and CP932 decoding. This proves that a universal Shift_JIS assumption is unsafe; it does not prove that all `RDC` comments are UTF-8 or identify how the comment-writing path determines stored bytes. The approved explicit-selection/raw-byte contract therefore does not depend on resolving that mechanism.

## HL-EVAL-007 — Require exact Python operating-mode responses

### Implementation scope

- Synchronous, asynchronous, and queued operating-mode confirmation APIs
- Session invalidation after a malformed or undefined PLC response

### Target contract

The complete response body must be exactly `"0"` or `"1"`. Any other body, including `2`, `01`, whitespace, signs, empty text, or trailing data, is a `HostLinkProtocolError`, invalidates the connection, and is never retried or reinterpreted.

### Compatibility impact

Previously accepted undefined values and leaked built-in conversion errors become one strict protocol-error contract.

### Acceptance criteria

1. Exact `0` and `1` responses return their documented operating modes.
2. `2`, `01`, ` 1`, `+1`, `1x`, empty, and nonnumeric responses raise `HostLinkProtocolError` and invalidate the exact connection that received them.
3. Sync, async, and queued paths behave identically and do not automatically retry or reconnect.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-008 — Audit and correct every Python sample

### Implementation scope

- Every tracked Python sample and all user-documentation snippets that present executable Python
- Address/dtype syntax, counts, profiles, transports, ports, validation, timeout/reconnect/shutdown behavior, and write-safety guidance

### Target contract

Every sample is executable against the supported public API and demonstrates current library behavior. Word addresses use explicit dtypes where required; specifically, the known `dm20` and `dm100` examples become `dm20:u` and `dm100:u`. Samples do not depend on undocumented defaults or unsafe production-write implications.

### Compatibility impact

Examples and snippets change; the runtime API is not changed by this item.

### Acceptance criteria

1. Every sample address, dtype, count, profile, transport, port, timeout, reconnect, shutdown, and write note is reviewed against the approved contract.
2. All Python sample files pass syntax/import checks and argument parsing or dry-run smoke checks without opening a PLC connection.
3. User-documentation snippets agree with the corrected samples and supported public API.
4. No live PLC communication is used as the sample correctness gate.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-009 — Validate Python poll intervals before communication

### Implementation scope

- Public polling helpers and their synchronous, asynchronous, and queued entry points where applicable

### Target contract

A poll interval must be a finite numeric value greater than zero, with `bool` explicitly excluded. Zero, negative values, NaN, infinities, strings, and other nonnumeric inputs raise `ValueError` before communication or snapshot production; any positive finite value, including a very small value, is accepted.

### Compatibility impact

Inputs that previously caused tight loops, delayed failures, or implicit conversion now fail immediately.

### Acceptance criteria

1. Positive finite integer and floating-point intervals are accepted.
2. Zero, negatives, NaN, positive/negative infinity, booleans, and strings raise `ValueError` before communication.
3. Direct and queued polling paths share the same validation and do not produce a snapshot after rejection.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-010 — Require exact Python integers for integer-only public arguments

### Implementation scope

- Every public integer-only argument, including bank numbers, forced-consecutive counts, numeric mode values, unit/address/count fields, and bit indexes
- Sync, async, queued, helper, and frame-generation paths

### Target contract

Integer-only inputs require `type(value) is int`. Booleans, floats including `1.0`, numeric strings, and objects with implicit numeric conversion are rejected with `ValueError` before frame generation or transport. Existing ranges remain in force, and officially supported textual modes such as `PROGRAM` and `RUN` remain separate explicit alternatives.

### Compatibility impact

Implicitly converted or accidentally accepted values now fail early. Valid integers and explicitly documented string enums remain supported.

### Acceptance criteria

1. Every public integer-only parameter is inventoried and validated with the same exact-type rule before range checking.
2. Representative `True`, `1.0`, `"1"`, NaN-like objects, and out-of-range integers fail with `ValueError` and cause zero sends.
3. Valid boundary integers and documented textual mode names retain their supported behavior.
4. Sync, async, queued, helper, and frame-generation entry points cannot bypass validation.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-011 — Keep the Python sdist limited to build and installation inputs

### Implementation scope

- Python sdist manifest/package metadata and packaging checks
- Documentation that identifies the authoritative source for samples and user guides

### Target contract

The Python sdist does not include `samples/` or `docsrc/`; it contains only files required to build, install, license, and identify the package. GitHub is the source for maintained samples, and the shared documentation site is the source for user guides. No exact current release number is duplicated in user documentation.

### Compatibility impact

This confirms the intended distribution boundary rather than adding files to the sdist. Consumers needing samples or guides use the documented sources.

### Acceptance criteria

1. A freshly built sdist excludes `samples/` and `docsrc/` and contains every file needed for isolated build/install and package metadata validation.
2. Package checks do not rely on files intentionally excluded from the sdist.
3. User and maintainer documentation clearly distinguish the registry sdist, GitHub source archive, GitHub samples, and shared docs site.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HL-EVAL-024 — Make the GitHub source archive self-contained for standard build and test commands

### Implementation scope

- Git attributes/archive rules, tests, fixtures, project configuration, and source-archive release gate

### Target contract

The GitHub source archive includes the repository tests and all fixtures required by them. From a clean extracted archive, the documented standard build and test commands complete without references to intentionally omitted files. Registry packages remain minimal and follow their separate package-content contracts.

### Compatibility impact

GitHub source archives become larger because test assets are included; installed registry package contents do not expand as a consequence.

### Acceptance criteria

1. An archive produced from the repository HEAD contains the test suite and every required fixture.
2. The documented standard build, static-check, and test commands run from the extracted archive and execute the expected nonzero test set.
3. The release gate creates a fresh archive, extracts it, and verifies those commands without using checkout-only files.
4. Wheel and sdist content checks independently enforce their approved minimal-package contracts.

### Completion checklist

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification is recorded as not required, or each required check has evidence or an explicit release disposition.
- [x] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.
