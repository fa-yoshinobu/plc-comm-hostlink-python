# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Corrected XYM `X` / `Y` alias catalog bounds so published ranges such as `X0-999F` are exposed as decimal-bank plus hexadecimal-bit logical counts.
- Batched `read_named()` direct-bit reads across `R` / `MR` / `LR` / `CR` bit-bank display boundaries such as `CR3615` to `CR3700`.

## 0.1.9 - 2026-05-02

### Added
- Added public address helper APIs: `parse_address`, `try_parse_address`, and `format_address`.
- Added high-level async expansion unit buffer helpers for `URD` / `UWR`.

### Changed
- Documented the helper naming, explicit connection option, address helper, and semantic atomicity policy.

## 0.1.8 - 2026-04-27

### Changed
- Added X/Y monitor registration support verified on KV-7500.
- Normalized X/Y bit addresses as decimal bank plus hexadecimal bit notation, rejecting invalid forms such as `X3F0` before sending.
- Added M/L monitor bit registration support while keeping M/L out of monitor word registration.

## 0.1.7 - 2026-04-27

### Added
- Added the embedded KEYENCE KV device range catalog and `read_device_range_catalog()` helpers.

### Changed
- Aligned Host Link device parsing with the .NET/Rust libraries, including the extended `M0..M63999` XYM range.
- Normalized `R`, `MR`, `LR`, and `CR` bit-bank addresses and rejected invalid lower-two-digit bit numbers.

## 0.1.6 - 2026-04-14

### Changed
- Reorganized the public MkDocs content around end-user getting-started, supported-register, and latest-verification pages while keeping maintainer docs internal.
- Separated local and publish docs builds so publication settings no longer affect local documentation checks.
- Tightened source-distribution packaging so maintainer-only docs stay out of shipped release artifacts.

## 0.1.5 - 2026-04-01

## 0.1.4 - 2026-03-29

### Added
- Added `scripts/check_high_level_docs.py` to verify that all public helper functions keep user-facing docstring coverage.
- Added `scripts/check_user_samples.py` to validate user-facing sample scripts by compiling them and running `--help`.
- Added `release_check.bat` as a one-step release gate that runs CI (lint/format/mypy/docs coverage/samples/tests) and then rebuilds the published MkDocs site.
- Added three high-level user samples: `samples/basic_high_level_rw.py`, `samples/named_snapshot.py`, and `samples/polling_monitor.py`.
- Added `MANIFEST.in` pruning for `internal_docs/` so source distributions omit maintainer-only docs.

### Changed
- Updated README, user docs, and samples to describe the current helper API coverage, including API-to-sample mapping tables.
- Clarified that low-level `.H` reads return uppercase hex strings and added helper-level `.F` float32 conversion for typed/named reads.
- Updated `run_ci.bat` to include high-level docs coverage checks and user-facing sample validation runs.
- Expanded `.gitignore` to exclude coverage artifacts such as `.coverage*` and `htmlcov/`.

## [0.1.2] - 2026-03-19

### Added
- Comprehensive `docsrc/user/USER_GUIDE.md` for end-users.
- Documentation for `AsyncHostLinkClient` in `docsrc/user/API_REFERENCE.md`.
- Internal connectivity verification evidence: `internal_docs/validation/reports/QA_REPORT_20260319_KV7500.md`.
- Stability and stress test samples in `samples/` directory.

### Changed
- **Optimized Performance**: Enabled `TCP_NODELAY` and removed `asyncio.wait_for` overhead in `AsyncHostLinkClient` receive logic.
- Improved type safety in `hostlink/client.py` (fixed Mypy errors regarding `Iterable` vs `Sequence`).

### Fixed
- Fixed Ruff linting errors (E722, F401) in core library and tests.
- Fixed an `async/await` missing bug in `AsyncHostLinkClient.register_monitor_bits`.

## [0.1.0] - 2025-05-18

### Added
- Initial implementation of KEYENCE KV Host Link protocol for Python.
- Support for TCP/UDP transport.
- Comprehensive unit tests and SPEC coverage documentation.
