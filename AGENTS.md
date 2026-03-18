# Agent Guide: HOST LINK COMMUNICATION Python

This repository is part of the PLC Communication Workspace and follows the global standards defined in `D:\PLC_COMM_PROJ\AGENTS.md`.

## 1. Project-Specific Context
- **Protocol**: HOST LINK COMMUNICATION
- **Target Hardware**: KEYENCE KV series (KV-8000, KV-7500, etc.)
- **Language**: Python (3.11+)
- **Role**: Core Communication Library for KEYENCE Upper Link protocol.

## 2. Mandatory Rules (Global Standards)
- **Language**: All code, comments, and documentation MUST be in **English**.
- **Encoding**: Use **UTF-8 (without BOM)** for all files to prevent Mojibake.
- **Mandatory Static Analysis**:
  - All changes must pass `ruff` (linting/formatting) and `mypy` (type checking).
  - Use `ruff check .` and `ruff format .` before committing.
- **Documentation Structure**: Follow the Modern Documentation Policy:
  - `docs/user/`: User manuals and API guides. [DIST]
  - `docs/maintainer/`: Protocol specs and internal logic. [REPO]
  - `docs/validation/`: Hardware QA reports and bug analysis. [REPO]
- **Distribution Control**: Ensure `pyproject.toml` excludes `docs/maintainer/`, `docs/validation/`, `tests/`, `scripts/`, and `TODO.md` from PyPI/Wheel packages.

## 3. Reference Materials
- **Official Specs**: Refer to `local_folder/kv/HOST LINK.pdf` for the authoritative English manual (Local only).
- **Evidence**: Check `docs/validation/reports/` for verified communication results with KEYENCE KV-series PLCs.

## 4. Development Workflow
- **Issue Tracking**: Log remaining tasks in `TODO.md`.
- **Change Tracking**: Update `CHANGELOG.md` for every fix or feature.
- **QA Requirement**: Every hardware-related fix must include an evidence report in `docs/validation/reports/`.
