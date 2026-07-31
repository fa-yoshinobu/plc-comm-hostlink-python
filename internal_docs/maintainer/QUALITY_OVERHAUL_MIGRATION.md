# HostLink Python quality-overhaul contract and migration

Branch: `quality/2026-07-overhaul`  
Authoritative approvals: archived workspace record `omittable_configuration_decisions_20260711.md`
Related findings: B-18 through B-29 in archived workspace record `library_bug_consistency_review_20260710.md`

This record describes the Python implementation of approved cross-family D-001 and HostLink decisions D-052 through D-064. A checked item requires recorded evidence. The user ran the authorized HostLink Claude review batch outside Codex on 2026-07-12; repository-specific findings and their disposition are recorded below. No live PLC operation was performed for this correction batch.

## D-001 — Explicit destination port

Scope: sync/async clients, connection options, user samples, multi-PLC/config inputs, and maintainer validation tools.

Target contract: every communicating entry point receives an explicit integer port in `1..65535`. New UI defaults in other products do not authorize a Python runtime fallback.

Acceptance criteria:

1. Public constructors/options reject omission, Boolean, zero, negative, overflow, and wrong-type values before transport creation.
2. Single-PLC CLI tools require the port argument; multi-PLC/config inputs require it per endpoint or through an explicitly supplied common value.
3. Source inspection finds no runnable `8501` port fallback.

- [x] Implementation and sample/tool migration completed.
- [x] `release_check.bat` passed Ruff, mypy, docs/sample/release checks, 197 tests, and distribution validation after the final diff.
- [x] Codex reviewed constructor validation, CLI/config parsing, and no-fallback source search.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: endpoint validation and argument requirements are locally testable; no communication was performed.
- [x] Documentation and changelog agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-052 — Explicit transport

Scope: `HostLinkClient`, `AsyncHostLinkClient`, `HostLinkConnectionOptions`, helpers, samples, and user documentation.

Target contract: `transport` is required and accepts only `tcp` or `udp`; it is never inferred from omission or an invalid value.

Compatibility impact: calls that omitted transport must add `transport="tcp"` or `transport="udp"`.

Acceptance criteria:

1. Missing transport is rejected by the Python call signature before transport creation.
2. Empty and unknown transport values are rejected before transport creation.
3. Explicit TCP and UDP values are retained unchanged after normalization.
4. Every communicating sample/tool passes a transport explicitly; no executable TCP fallback remains.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: no live communication is required for constructor validation.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-053 — Three-second timeout default

Scope: sync/async constructors and `HostLinkConnectionOptions`.

Target contract: timeout may be omitted and is exactly 3 seconds; explicit values must be positive and finite.

Compatibility impact: invalid values that previously reached a socket are now rejected locally.

Acceptance criteria:

1. All three public construction paths use 3 seconds when timeout is omitted.
2. Positive finite explicit values are preserved.
3. zero, negative, Boolean, NaN, infinity, and nonnumeric values are rejected before communication.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: timeout configuration validation is locally testable; timeout recovery uses local TCP/UDP fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-054 — CR-only command framing

Scope: protocol frame builder, clients, and removed LF options.

Target contract: every normal HostLink request ends with one CR byte; no public LF-append switch exists.

Compatibility impact: `append_lf_on_send` and related builder arguments are removed.

Acceptance criteria:

1. Deterministic frame-builder tests end every command in `0x0D`.
2. Public constructors and builders expose no LF option.
3. User documentation contains no LF setting.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: fixed frame bytes are covered by deterministic repository-local command tests; no PLC communication required.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-055 — Library-owned receive buffering and cap

Scope: sync/async TCP and UDP receive paths.

Target contract: receive chunking and the 65,536-byte absolute response-body cap are internal; overflow invalidates the transport.

Compatibility impact: public `buffer_size` is removed and cannot be used to weaken or tighten protocol validation.

Acceptance criteria:

1. Public signatures contain no buffer-size parameter.
2. TCP accepts exactly 65,536 body bytes and rejects 65,537.
3. UDP receives enough data to detect cap overflow and invalidates the socket on overflow.
4. UDP requires a CR/LF terminator and invalidates the transport on missing framing.
5. RD, RDS/RDE, monitor reads, and URD reject shorter or longer token lists than the command-derived expected count.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, local transport, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: framing and cap behavior use deterministic local transport fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-056 — Maintainer-only opt-in trace

Scope: hidden sync/async diagnostic hook.

Target contract: tracing is disabled by default, omitted from user APIs/docs, observes one send and receive event in order, and cannot change command success.

Compatibility impact: public trace types and public `trace_hook` are removed; maintainers may set the protected `_maintainer_trace_hook` field only in controlled investigations.

Acceptance criteria:

1. Package exports contain no trace types and public parameter names contain no `trace_hook`.
2. Omission produces no callback or automatic logging.
3. An enabled hidden hook observes raw frames; callback exceptions are isolated.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: hook ordering and isolation are transport-independent and locally verified.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-057 — Constructor never connects

Scope: sync/async constructors and `open_and_connect`.

Target contract: constructors validate and initialize local state only; only explicit `connect`, context entry, or `open_and_connect` creates a transport.

Compatibility impact: `auto_connect` is removed; code relying on constructor I/O must call a named connection operation.

Acceptance criteria:

1. Constructors expose no `auto_connect` argument.
2. Sync construction calls no socket API.
3. Async construction creates no stream or datagram transport.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: constructor side effects are locally observable and require no PLC.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-058 — Explicit connection lifecycle

Scope: all semantic and raw sync/async commands and failure recovery.

Target contract: an unconnected or failed client returns `HostLinkConnectionError` without opening a transport; reconnect and retry are caller decisions.

Compatibility impact: lazy first-command connection and implicit reconnect are removed.

Acceptance criteria:

1. Unconnected raw and semantic operations create no socket/transport and fail as not connected.
2. Explicit connect enables commands and repeated connect is idempotent.
3. timeout, cancellation, EOF, and socket failures discard transport state; the next command does not reconnect.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, local transport, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: lifecycle/error sequences are covered by local TCP/UDP fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-059 — Explicit PLC clock value

Scope: sync/async `set_time` and validation tools.

Target contract: callers must supply a datetime or seven exact calendar fields; no current-time or UTC fallback occurs inside the command.

Compatibility impact: parameterless calls must pass an explicit value such as `datetime.now()`.

Acceptance criteria:

1. Omitting the value is rejected by the signature.
2. nonexistent dates and inconsistent weekdays are rejected before sending.
3. valid explicit values produce deterministic `WRT` fields.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: command construction/validation is deterministic; PLC clock mutation was not performed.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-060 — Raw response bytes

Scope: sync/async `send_raw` and private semantic decoders.

Target contract: raw commands return undecoded body bytes without CR/LF and without PLC error-code conversion; semantic APIs decode privately.

Compatibility impact: callers expecting text or passing a decoder must explicitly decode returned bytes or use a semantic API.

Acceptance criteria:

1. Public raw signatures contain no decoder argument and return bytes.
2. ASCII, PLC error text, and non-ASCII bodies are preserved with only frame terminators removed.
3. semantic APIs still perform encoding, error, and value validation.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, local transport, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: raw framing/decoding contract is locally fixture-tested.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-061 — Fixed comment padding normalization

Scope: sync/async clients and high-level `read_comments`.

Target contract: semantic comment reads remove trailing ASCII `0x20` bytes only, before text decoding; no public padding switch exists.

Compatibility impact: `strip_padding` is removed; exact padded data requires maintainer raw bytes.

Acceptance criteria:

1. Multiple trailing ASCII spaces are removed.
2. tabs, full-width spaces, localized text, and interior spaces are preserved.
3. Public signatures expose no padding option.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: byte fixtures cover normalization and encodings without PLC communication.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-062 — Explicit expansion-buffer format

Scope: sync/async URD/UWR methods and high-level helpers.

Target contract: `.U`, `.S`, `.D`, `.L`, or `.H` is a required separate argument; values, counts, and spans are validated without masking or splitting.

Compatibility impact: omitted/empty/`None` format calls must explicitly supply a format.

Acceptance criteria:

1. Missing/empty format is rejected before transport.
2. All five formats enforce exact numeric/token boundaries.
3. 32-bit formats account for two buffer words and reject end crossings.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: this batch changes pre-send format/range policy and deterministic frames only; existing profile-specific URD/UWR support is not newly claimed, so no live check is required for this item.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-063 — No public automatic chunking

Scope: package exports, helpers, samples, and documentation.

Target contract: public block read/write helpers remain single-request. The sole
automatic multi-request exception is the approved read-only `read_named`/`poll`
aggregate, which preserves caller order, keeps entries indivisible, owns one
FIFO turn, documents non-atomic timing, and returns no partial result.

Compatibility impact: all public `*chunked` helpers are removed without aliases.

Acceptance criteria:

1. Chunk helpers are absent from package exports and generated API documentation.
2. Samples do not use a hidden range-splitting helper. `read_named`/`poll` explicitly document that mixed logical results may require sequential requests and are not atomic snapshots.
3. single-request helpers reject protocol limits instead of splitting;
   `read_named`/`poll` may split only necessary read-only aggregate work.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, sample, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: request count and pre-send limits are locally deterministic.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## D-064 — Separate required numeric data format

Scope: low-level read/write/consecutive/set-value/monitor-word APIs and high-level address grammar.

Target contract: numeric low-level access uses a base device plus separate explicit format. Suffix-bearing low-level devices are rejected. Direct-bit bare devices remain unambiguous. High-level `.D` is bit 13 and `:D` is dword.

Compatibility impact: `read("DM0.U")` becomes `read("DM0", data_format=".U")`; suffix/argument override behavior is removed.

Acceptance criteria:

1. Missing/empty numeric format and suffix-bearing low-level input are rejected before transport.
2. `.U/.S/.D/.L/.H` boundaries and response tokens are strictly validated without masks or string fallback.
3. monitor-word entries carry explicit per-device formats; direct-bit calls may omit format only where command/device semantics are bit-only.
4. high-level `DM100.D` and `DM100:D` retain distinct bit-13 and dword meanings.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] Claude source review completed; the user ran the authorized batch outside Codex.
- [x] Every Python Claude finding dispositioned and affected checks rerun.
- [x] Live-PLC disposition recorded: input semantics and wire frames are deterministic; no PLC communication required.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [x] Final cross-language acceptance verified in the archived workspace record `hostlink_cross_implementation_final_comparison_20260712.md`.

## PY-HL-CLAUDE-20260712 — Independent-review corrections

Scope: Claude HostLink findings 3, 4, 5, 9, 10, 18, 19, 20, and 21 for
the Python repository, plus the cross-language clock-century consistency found
during Codex self-review.

Target contract: response shapes are derived from the issued command and
validated exactly; UDP requires a terminator and invalidates malformed
transport; direct-bit tokens are only `0`/`1`/`ON`/`OFF`; raw bodies cannot inject control
characters; empty named work and Float32 overflow fail predictably; clock years
are 2000 through 2099; current E2E tooling uses only current public APIs.
Cross-implementation vectors belong to the separate cross-verification
repository, not this library.

Compatibility impact: malformed-but-previously-accepted responses, empty named
operations, raw control characters, out-of-century datetimes, and Float32
overflow now fail. The later approved FIFO aggregate contract supersedes the
former `read_named` no-split rule: oversized read-only groups may now split at
entry boundaries after complete preflight.

Acceptance criteria:

1. RD uses exactly one token except documented timer/counter composite RD,
   RDS/RDE and URD use exactly the requested count, and monitor reads use the
   successful registration count.
2. Missing UDP terminators, invalid bit tokens, and raw CR/LF/control bytes
   raise `HostLinkProtocolError`; uncertain UDP state is discarded.
3. `read_named([])`, `poll([])`, Float32 ±overflow, and datetime years outside
   2000..2099 reject before send with the documented exception family.
4. The E2E script requires profile/endpoint intent and verifies raw `b"E1"`;
   no removed LF option or decoded-raw behavior remains.
5. A 1001-word named range rejects before send and no library-local
   cross-implementation vector or runner remains.
6. Direct-bit numeric single reads require 16 or 32 response tokens according
   to the explicit format, and any command-derived response-shape mismatch
   invalidates the session before another request.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Full static, unit, sample, documentation, build, and package checks passed (`release_check.bat`, 197 tests, zero skip).
- [x] Codex self-review completed against response shapes, public API, validation order, UDP/TCP state, exception families, docs, tools, and package contents.
- [x] Claude source review completed; the user ran the authorized batch and its result is preserved in the workspace.
- [x] Codex dispositioned all Python findings and reran affected checks.
- [x] No additional live-PLC check is required for response-shape, local UDP framing, validation, and tooling corrections.
- [x] Documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified for this repository; HostLink family-level acceptance remains separate.

## Migration summary

```python
# Before
client = HostLinkClient(host, plc_profile=profile)
value = client.read("DM0.U")

# After
client = HostLinkClient(host, port=8501, transport="tcp", plc_profile=profile)
client.connect()
value = client.read("DM0", data_format=".U")
```

Use `send_raw` only for maintainer investigation. It now returns response-body `bytes`. Normal applications should use semantic methods and must not recreate removed hidden defaults or automatic chunking wrappers.

## Verification evidence

- Unit/contract suite: `release_check.bat` passed with `197 passed`, zero skip, on Python 3.14.3.
- Type checking: `python -m mypy src/hostlink` passed; Ruff, docs/sample checks, build, Twine, wheel, and sdist checks passed.
- Claude: the user ran the authorized HostLink batch outside Codex; its result and Codex disposition are preserved in the workspace review record.
- Live PLC: on 2026-07-12, the public async high-level API connected to KEYENCE KV-X500 profile `keyence:kv-x500` at `192.168.250.100:8501` over TCP and read one unsigned word from `DM0`; the result was `5878`. No write, retry, or fallback was performed. This evidence is limited to that endpoint, profile, device, transport, and operation.

## NR-007: Lifetime traffic statistics

Approved next-release contract: `traffic_stats()` returns immutable lifetime counters; only complete
sends and complete response lines/datagrams count, pre-send and partial failures do not, and
close/reconnect does not reset. Implementation and deterministic tests are required; live PLC
verification is unnecessary. Final packaging and publication acceptance completed with `v3.2.0`.

- [x] Public API and transport-boundary implementation completed.
- [x] Deterministic tests, documentation, changelog, and package gate completed.
- [x] Codex final self-review completed.
- [x] Next-release package acceptance completed. Evidence: the `v3.2.0` tag equals repository HEAD,
  the GitHub Release and PyPI `plc-comm-kv-hostlink` `3.2.0` package are public, tag-commit checks
  passed, and the final six-runtime family source/API comparison was completed on 2026-07-18.

## QREV-20260714-004: Segmentation-independent TCP receive accounting

Scope: synchronous and asynchronous TCP receive framing and `HostLinkTrafficStats.rx_bytes`.

Family equivalence: all four HostLink implementations count TCP `OK\r`, `OK\n`, coalesced `OK\r\n`, and either split CR/LF ordering as 3 bytes; UDP `OK\r\n` remains 4 bytes. Incomplete oversize/EOF/timeout/cancellation data contributes zero, while a complete PLC error line is counted before semantic decoding. The family comparison is preserved in the archived workspace record `communication_library_quality_review_20260714.md`.

Target contract: one completed TCP response counts its body through the first CR or LF. Additional
CR/LF separator bytes are consumed without changing the counter, whether they arrive together or
in a later TCP read. UDP continues to count the complete accepted response datagram.

Compatibility impact: a coalesced CRLF response previously could count both terminators and now
counts only the first; split CRLF already counted one. The corrected value is independent of TCP chunking.

Acceptance criteria:

1. Equivalent CRLF responses produce the same `rx_bytes` when CR and LF are coalesced or split.
2. The separator left after a completed line cannot become an empty or misassociated next response.
3. Complete PLC errors are counted; incomplete oversize, EOF, and timeout paths are not counted. Complete UDP datagram accounting is unchanged.

- [x] Implementation completed in this repository.
- [x] Tests added or updated for every acceptance criterion.
- [x] Profile drift, Ruff, Mypy, documentation, samples, 207 tests, build, and Twine package checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Claude source review completed; findings are preserved in the archived workspace record `claude_review_findings_20260714.md`.
- [x] Codex resolved or dispositioned every applicable Claude finding and reran affected checks.
- [x] Live PLC verification is not required for this deterministic local framing and counter contract.
- [x] Documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## HLPY-ARTIFACT-001 — Installable consumer and complete worktree source archive

Implementation scope: wheel/sdist contract checker, isolated consumer import,
source-archive worktree mode, extracted non-hardware checks, and CI/release
artifact evidence.

Target contract: the wheel gate installs the exact built wheel into a new
virtual environment with no checkout or `PYTHONPATH`, then verifies public
imports, `__all__`, callable signatures, docstrings, version identity, and the
installed module location. Worktree source archives are created from a
synthetic Git tree that includes every modified and untracked non-ignored file
and every tracked deletion, then the extracted archive alone passes the full
non-hardware gate and the same isolated package-consumer gate.

Compatibility impact: none; this strengthens artifact verification without
changing runtime behavior or the public Python API.

Acceptance criteria:

1. Wheel and sdist content rules still reject repository-only files and require
   metadata, license, README, and `py.typed`.
2. The exact wheel installs into a fresh venv, imports only from that venv, and
   exposes eight representative documented public entry points.
3. Worktree mode includes modifications, untracked files, and deletions in one
   synthetic archive; the deleted `samples/named_snapshot.py` remains absent
   while its replacement and new tests are included.
4. The extracted archive passes Ruff, formatting, mypy, documentation/sample/
   workflow checks, 253 tests, package rebuild, and isolated wheel consumption
   without referring to the checkout.

Self-review finding disposition: accepted. The former package checker inspected
filenames only, while the former worktree option archived `HEAD` and therefore
could not represent the current deleted and untracked paths.

- [x] Implementation completed in this repository.
- [x] Consumer and synthetic-worktree regression behavior added to permanent gates.
- [x] Full non-hardware, package, isolated-consumer, and extracted-source checks passed.
- [x] Codex self-review completed against archive completeness and checkout-independent import requirements.
- [x] Live PLC verification is not required; artifact construction and import behavior are deterministic.
- [x] Maintainer record and changelog agree with the implemented gates.
- [x] Final acceptance criteria verified and the item marked complete.
