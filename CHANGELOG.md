# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-19

### Added
- Comprehensive `docs/user/USER_GUIDE.md` for end-users.
- Documentation for `AsyncHostLinkClient` in `docs/user/API_REFERENCE.md`.
- Connectivity verification evidence: `docs/validation/reports/QA_REPORT_20260319_KV7500.md`.
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
