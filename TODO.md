# TODO: Host Link Communication Python

This file tracks the remaining tasks and issues for the Host Link Communication (Keyence KV) library.

## 1. Protocol Implementation Gaps
- [ ] **Full Spec Coverage**: Complete the implementation for all commands listed in `docs/maintainer/SPEC_COVERAGE.md`.
- [ ] **Expansion Unit Access**: Add high-level helpers for accessing buffer memory in expansion units.

## 2. Testing & Validation
- [ ] **Hardware QA Reports**: Create detailed evidence reports for various KV series PLCs in `docs/validation/reports/`.
- [ ] **Stress Testing**: Perform stability tests under high-frequency read/write cycles.

## 3. Documentation & Maintenance
- [ ] **User Guide**: Create a comprehensive `docs/user/USER_GUIDE.md` with setup screenshots.
- [ ] **Distribution Configuration**: Update `pyproject.toml` to implement strict exclusion of `docs/maintainer/` and `docs/validation/`.
- [ ] **Static Analysis**: Achieve 100% compliance with `ruff` and `mypy`.
