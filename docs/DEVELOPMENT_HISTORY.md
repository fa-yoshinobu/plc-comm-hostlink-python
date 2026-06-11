# Development History

## 2026-06-11 Archived Refactor Plan

The previous `refactor-instructions.md` was archived into this history file.

### Scope

- Library: Python KEYENCE KV Host Link package, published as `kv-hostlink` `0.1.11`.
- Primary task: add sync/async wire-parity tests, then reduce duplicated command logic in `HostLinkClient` and `AsyncHostLinkClient`.
- Optional small task: move read-plan internals from `utils.py` into a private module.

### Contracts To Preserve

- Public exports and module paths from `src/hostlink/__init__.py`.
- Exact ASCII Host Link command strings, including CR termination.
- Protocol fixed points shared with sibling stacks: `AT` pre-send write rejection, timer/counter restrictions, and extended-unit access behavior.
- `read_named` batching rules and result ordering.
- Dependency-free package metadata, version `0.1.11`, and changelog.

### Debt Notes

- D1: no characterization test guaranteed that sync and async clients emitted identical wire strings for equivalent calls.
- D2: command methods were hand-mirrored between sync and async clients; frame building and response decoding were to be extracted into private `HostLinkBase` helpers.
- D3: read-plan optimization lived in the documented `utils.py` user-facing module; moving it was optional.

### Planned Verification

- Run ruff, format check, mypy, documentation checks, sample checks, and pytest before and after changes.
- Add parity tests using mock transports that compare sync and async output to each other.
- Extract one command group at a time: read, write, monitor, operation control, and extended-unit commands.
- Stop and ask if parity tests revealed an existing sync/async drift.

### Out Of Scope

- Public API, module-path, frame-string, or exception-message changes.
- Device range changes, scripts, samples, docs source changes, release work, or real PLC tests.
