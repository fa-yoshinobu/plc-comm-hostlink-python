# TODO: Host Link Communication Python

Current active TODOs only.

## Current Status

The eight approved implementation items are complete in the working tree. The
evidence-dependent comment-encoding decision remains open, and no
comment-decoder implementation change is authorized until `HL-EVAL-TODO-006`
is approved.

### Verification evidence — 2026-08-01

- Current-worktree CI passed 244 pytest cases plus 18 API-reference generator
  subtests, sample checks, formatting/static checks, build, and package checks.
- A synthetic current-worktree Git tree produced a self-contained source
  archive; its clean extracted test/build gate passed with 210 tests.
- The distribution-content guard kept the registry package minimal while the
  GitHub source archive retained tests and fixtures.
- Codex reviewed the actual diff, public surface, validation order, error and
  connection behavior, samples, documentation, and cross-language contracts.
- These deterministic validation and packaging corrections do not require
  live PLC communication. `HL-EVAL-TODO-006` is intentionally still open.

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

### Implementation scope

- Python `RDC` device-comment decoding and its sync/async helper and client APIs
- Cross-language comparison with the Rust, Node-RED, and .NET Host Link implementations
- Shared Host Link user documentation where the resulting behavior is common

### Target state

The encoding of `RDC` device-comment response bytes is defined from direct KEYENCE Host Link evidence for every affected PLC profile. The Python implementation does not infer a target contract merely from successful decoding, a general KV string-encoding statement, or existing UTF-8-first/Shift_JIS-fallback behavior.

Until the evidence is complete and the resulting target contract is explicitly approved, the comment-encoding behavior remains undecided and no implementation change is authorized.

### Compatibility impact

Undecided. The investigation must identify whether the approved result preserves the current UTF-8-first/Shift_JIS-fallback behavior, fixes one encoding, selects encoding by PLC profile, or introduces an explicit API setting. Any public API, default, decoding, error, or migration impact must be recorded before implementation.

### Acceptance criteria

1. Official KEYENCE communication documentation is checked for the `RDC` response encoding for KV-NANO, KV-3000/KV-5000, KV-7000/KV-8000, and KV-X500 families; evidence is recorded per profile rather than inferred across families.
2. The exact codec contract is identified, including whether “Shift_JIS” means strict Shift_JIS, Windows-31J/CP932-compatible decoding, or another defined mapping.
3. Ambiguous byte sequences that are valid under both UTF-8 and Shift_JIS are included in deterministic decoder vectors, and the expected result follows the approved evidence rather than decoder ordering.
4. If official documentation does not settle a profile, that profile remains `unverified` until an exact live-PLC evidence plan is written with the PLC/profile, endpoint, address, read intent, registered comment value, purpose, expected raw-byte evidence, and restoration requirement, then separately approved by the user with `OK` before communication.
5. A maintainer decision record defines the encoding selection mechanism, malformed-byte behavior, connection invalidation behavior, public API impact, compatibility impact, and cross-language mapping before source implementation begins.
6. User documentation, tests, generated API reference, and migration notes agree with the approved contract in every affected implementation.

### Evidence and completion checklist

- [ ] Official `RDC` encoding evidence recorded for every affected PLC family/profile.
- [ ] Shift_JIS versus Windows-31J/CP932 mapping resolved for all four language runtimes.
- [ ] Ambiguous and malformed byte vectors defined with evidence-backed expected results.
- [ ] Need for live PLC verification decided; any required exact live batch is separately documented and approved.
- [ ] Target contract and compatibility impact explicitly approved by the user.
- [ ] Implementation completed in every affected repository.
- [ ] Tests added or updated for every acceptance criterion.
- [ ] Relevant static checks, unit tests, integration tests, examples, and package/build checks passed.
- [ ] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [ ] Required live-PLC checks passed, or each unavailable check has an explicit release disposition.
- [ ] Documentation, migration notes, changelog, and generated API reference agree with the implementation.
- [ ] Final acceptance criteria verified and the item marked complete.

### Current evidence boundary

The current implementations try UTF-8 first and fall back to Shift_JIS. KEYENCE material stating that KV-series strings use Shift_JIS is relevant but does not by itself establish the byte contract of every Host Link `RDC` response. It is supporting evidence only, not approval of a Shift_JIS-only implementation.

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
