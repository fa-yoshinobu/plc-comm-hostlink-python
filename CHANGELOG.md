# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Added `MANIFEST.in` pruning for `docsrc/maintainer/` and `docsrc/validation/` so source distributions exclude maintainer-only and validation-only documentation explicitly.

### Added
- Added `scripts/check_high_level_docs.py` to verify that all public high-level helper functions keep user-facing docstring coverage.
- Added `scripts/check_user_samples.py` to validate user-facing sample scripts by compiling them and running `--help`.
- Added `release_check.bat` as a one-step release gate that runs CI and then rebuilds the published docs.
- Added three focused user-facing high-level samples: `samples/basic_high_level_rw.py`, `samples/named_snapshot.py`, and `samples/polling_monitor.py`.

### Changed
- Updated README, user docs, and samples to describe the current helper API coverage.
- Clarified that low-level `.H` reads return uppercase hex strings.
- Added helper-level `.F` float32 conversion for typed and named reads/writes.
- Updated `run_ci.bat` to include high-level docs coverage checks and user-facing sample validation.
- Expanded the user docs and sample docs with API-to-sample mapping tables for the recommended helper workflows.
- Updated `.gitignore` to ignore coverage artifacts such as `.coverage*` and `htmlcov/`.

## [0.1.2] - 2026-03-19

### Added
- Comprehensive `docsrc/user/USER_GUIDE.md` for end-users.
- Documentation for `AsyncHostLinkClient` in `docsrc/user/API_REFERENCE.md`.
- Connectivity verification evidence: `docsrc/validation/reports/QA_REPORT_20260319_KV7500.md`.
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

