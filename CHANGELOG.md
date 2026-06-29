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

## [Unreleased] - 2026-06-28

### Changed
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
