# HostLink Python quality-overhaul contract and migration

## Superseding decision: explicit word-bit write (2026-08-07)

Earlier removal decisions below remain historical evidence but no longer
describe the target surface. Sync/async client methods and the async
`write_bit_in_word` helper are restored for every Host Link device family whose
canonical default representation and `WR` command both provide one complete
16-bit `.U` word. The device text is immutable across the read and write; there
is no alternate route, fallback, resend, or readback. GOAL-BIT-002 in
`D:\APP\cross_library_bit_write_contract_goal_20260807.md` is authoritative.

GOAL-HOSTLINK-EXPANSION-RMW-001 extends that contract to the existing URD/UWR
route through sync/async client methods and the async
`write_bit_in_expansion_unit_buffer` helper. Unit, address, and `.U` format are
immutable across both requests; ordinary and expansion routes never fall back
to one another.

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
aggregate, which preserves public result order, optimizes wire order, keeps
entries indivisible, owns one FIFO turn, documents non-atomic timing, and
returns no partial result.

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
6. Direct-bit numeric single reads require exactly one packed scalar response
   token. `.U`/`.S`/`.H` span 16 direct-bit addresses and `.D`/`.L` span 32;
   any command-derived response-shape mismatch invalidates the session before
   another request. This corrects the former 16/32-token assumption using the
   KV-X500 live response vectors recorded by `LIVE-HL-001`.

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

## GOAL-SERIAL-DEFER-002-CONNECT — Complete synchronous connection deadline

Implementation scope: synchronous `HostLinkClient.connect()` and context
entry for TCP and UDP. Existing explicit-only lifecycle remains authoritative;
Host Link Python has no lazy command connection path.

Target contract: one overflow-checked monotonic `connect_timeout` deadline is
formed immediately before IPv4 resolution or socket work. Literal IPv4 bypasses
DNS. Hostname resolution selects the first matching IPv4 result in resolver
order. Resolution, socket creation/connect, required TCP no-delay/keepalive
configuration, close-generation validation, and final state adoption share the
same deadline. A platform resolver may finish on its daemon worker after the
public operation returns, but it retains no client authority: no late result is
adopted, no request is sent, and every partial socket is closed.

Compatibility impact: no public signature changes. Synchronous hostname
connections that previously allowed DNS time in addition to
`connect_timeout` now return the stable `HostLinkTimeoutError` at the
configured bound. IPv4-only and explicit-connect behavior are unchanged.

Machine-verifiable acceptance criteria:

1. TCP and UDP explicit connect create exactly one monotonic deadline before
   resolver/socket work and adopt state only before that deadline.
2. Literal IPv4 uses no resolver; hostname resolution requests `AF_INET` and
   selects the first matching IPv4 endpoint without IPv6 or route fallback.
3. Delayed DNS and delayed socket connect return promptly as timeout, send zero
   requests, leave no connected state, and never adopt their late result.
4. Concurrent `close()` remains distinguishable as
   `HostLinkClosedError`; final adoption is atomic with generation validation.
5. TCP no-delay and keepalive complete before adoption. Configuration failure
   preserves its native cause, closes the candidate, and returns
   `HostLinkTransportError`.
6. Values exceeding platform wait representation fail before transport.
7. Existing request send/receive/decode deadline and explicit-not-connected
   tests remain authoritative; no lazy connect, retry, or resend is introduced.

- [x] Implementation completed in this repository.
- [x] Deterministic test code added for every repository-specific criterion.
- [x] Ruff, formatting, mypy, unit/integration, package, and source-archive checks passed for the final source state.
- [x] Codex self-review completed against the actual diff and approved connection contract.
- [x] Live PLC verification is not required; resolver delay, adoption, cleanup, and error classification are local deterministic behavior.
- [x] User documentation, contract record, changelog, and implementation agree.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: on Windows with Python 3.10.20, Ruff lint and formatting,
mypy, high-level/public-API documentation checks, maintained-sample validation,
release-workflow validation, and all 284 tests passed; coverage was 86%. The
wheel/sdist gate passed with 14 wheel files, 20 sdist files, and an isolated
consumer checking 11 public symbols. The synthetic current-worktree source
archive contained 76 files, 13 sample files, and 13 test files, then passed its
extracted full gate and isolated package-consumer check. The initial Ruff B904
and formatting findings in `client.py` were corrected before this complete
rerun. No live PLC communication was performed.

Self-review disposition:

- Accepted: applying the platform wait maximum in the shared timeout validator
  would also change the unaffected async/request contracts. The bound now
  applies only when the synchronous absolute connect deadline is formed.
- Accepted: a worker that returned from DNS after concurrent `close()` could
  otherwise proceed to socket creation before noticing abandonment. Explicit
  abandonment checks now precede every later transport phase, and partial
  sockets close in the worker `finally` path.
- Accepted: final connected-state publication needed one linearization point
  with `close()`. `adopt_if_current` validates the admission generation and
  publishes the configured socket under the same guard.
- Accepted: resolver exhaustion before deadline must remain transport failure,
  not timeout. Test code now checks `HostLinkTransportError` and preservation
  of the native `socket.gaierror` cause.
- Accepted: a secondary candidate-close exception could mask the required
  timeout, closed, or transport classification. Partial-connect cleanup now
  suppresses close-only failures while preserving the primary error.
- Rejected: adding lazy first-command connection would contradict the approved
  D-057/D-058 explicit lifecycle and existing not-connected behavior.
- Rejected: adding multi-address retry would change the established
  first-matching-IPv4 selection policy; this implementation keeps that policy
  and bounds the one selected candidate.
- No duplicate or deferred self-review finding remains.

## GOAL-CROSS-OS-CI-001 — Required Windows representative contract smoke

Implementation scope: the repository CI workflow and existing deterministic
loopback/deadline tests. Runtime code, public API, packaging, release workflows,
and the Linux Python-version matrix are unchanged.

Target contract: the primary Ubuntu full gate remains authoritative. One
additional non-optional Windows job on Python 3.13 runs only representative
local contracts for fragmented CR/LF receive, one request deadline across a
trickled response, UDP late-response retirement and reconnect, async
cancellation retirement, and late partial-socket cleanup during connect. The
selection also requires pre-adoption TCP configuration failure to close the
candidate and preserve its native cause. The job has a ten-minute bound and
performs no package build or hardware communication.

Compatibility impact: none; this adds CI evidence only.

Machine-verifiable acceptance criteria:

1. `.github/workflows/test.yml` contains exactly one `windows-latest` contract-
   smoke job in addition to the unchanged Ubuntu full matrix.
2. The Windows job is required by workflow semantics: it has no conditional,
   failure suppression, or `continue-on-error` path.
3. The selected loopback tests cover fragmented receive, bounded request and
   connect completion, cancellation/retirement, reconnect, and rejection of a
   delayed response or socket from the retired generation.
4. The Windows job installs only pytest and pytest-asyncio, runs the explicit
   bounded test list, and does not build, package, publish, or contact a PLC.

- [x] Implementation completed in this repository.
- [x] Existing deterministic tests explicitly selected for every acceptance criterion.
- [x] The new Windows CI job passed on GitHub for the final source state.
- [x] The equivalent local Windows contract and full non-hardware gates passed with Python 3.10.20.
- [x] Codex self-review completed after the requested local verification run.
- [x] Live PLC checks are not required; all selected behavior uses localhost loopback or fake sockets.
- [x] Maintainer CI documentation agrees with the workflow; no user migration note or changelog entry is required.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: the local Windows Python 3.10.20 run passed Ruff lint
and formatting, mypy, documentation/sample/workflow checks, all 284 tests,
wheel/sdist and isolated-consumer checks, and the synthetic current-worktree
source archive's extracted full gate. This includes every test selected by the
new Windows representative job. The required GitHub-hosted Windows/Python 3.13
job and the Ubuntu Python 3.10 through 3.13 matrix passed on final merged source
commit `3830947730f6d2a821367aed71373056c7562194` in
[CI run 30705296652](https://github.com/fa-yoshinobu/plc-comm-hostlink-python/actions/runs/30705296652).
This follow-up changes only the maintainer evidence record.

Self-review disposition:

- Accepted and corrected: the first selection covered connect timeout cleanup
  but not a non-timeout connection failure. The existing deterministic TCP
  configuration-failure case is now included.
- Rejected: a second Windows-specific copy of the loopback tests would diverge
  from the Linux full gate. Exact existing test node IDs remain authoritative.
- Duplicate findings: none. Deferred findings: none.

## REAUDIT-001 — TCP response ownership residual limitation

Decision status: accepted finding corrected on 2026-08-02.

Implementation scope: existing sync/async TCP pre-send ownership checks,
connection-scoped monitor state, deterministic transport tests, the user
transport guide, and changelog. Runtime transport behavior and public APIs are
unchanged.

Target contract: Host Link TCP has no request identifier. A client sends no new
request and retires the connection when unowned input is observable before
send, while accepting that input arriving between that check and send cannot be
identified perfectly. Healthy persistent connections remain in use because a
one-request-per-connection design would add handshake latency, invalidate
monitor registration every cycle, and still would not add a protocol request
identifier. `MBS`/`MWS` registration and `MBR`/`MWR` read use the same live
connection; reconnect clears local registration metadata and requires explicit
registration again.

Compatibility impact: none. This records and directly tests the already
approved persistent-connection and observed-abnormal-input behavior.

Machine-verifiable acceptance criteria:

1. Sync and async clients detect already buffered TCP input before send,
   transmit zero bytes, and retire the connection.
2. Monitor registration followed by read succeeds on one physical connection.
3. After reconnect, a monitor read cannot reuse the prior local registration;
   explicit re-registration restores the read.
4. User documentation states the missing request identifier, the residual
   check-to-send race, and the normal-latency reason for rejecting
   one-request-per-connection operation.

- [x] Implementation and documentation correction completed in HostLink Python.
- [x] Direct sync/async ownership and monitor lifecycle tests passed.
- [x] Relevant static, full test, sample, documentation, package/build, and source-archive gates passed.
- [x] Codex self-review completed for send count, retirement, connection identity, monitor reset, and documentation.
- [x] Live PLC verification disposition recorded.
- [x] User documentation, maintainer record, and changelog agree.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: direct sync/async tests prove that observable pre-send
TCP input produces zero transmitted request bytes and retires the connection.
Loopback tests prove registration and monitor read share one accepted TCP
connection, that reconnect does not inherit the prior local registration, and
that explicit re-registration restores the read. `run_ci.bat` passed Ruff,
mypy, documentation/API/sample/workflow checks, and all 351 tests. The
current-worktree source archive repeated the full gate and passed wheel/sdist
construction plus the isolated package consumer. Live PLC verification is not
required because the accepted finding concerns deterministic client-side
ownership checks, connection identity, and local registration-state lifetime;
it does not change or newly claim PLC command support.

Self-review finding classification:

- Accepted and corrected: the implementation had pre-send rejection and
  monitor-state reset, but direct sync/async proof of zero send, physical
  connection reuse, and required re-registration was incomplete.
- Accepted and corrected: the user guide did not state the protocol identifier
  limitation, the residual check-to-send race, or why healthy TCP connections
  are not replaced for every request.
- Rejected findings: none. Duplicate findings: none. Deferred findings: none.

## REAUDIT-004 — Reject bracketed IPv4 input

Implementation scope: sync/async client construction, shared connection
options, deterministic constructor tests, user API/usage documentation, and
migration notes.

Target state: sync/async clients and `HostLinkConnectionOptions` reject an IPv4
literal enclosed in brackets before DNS, socket creation, connection, or send.
IPv4 callers migrate from `[127.0.0.1]` to `127.0.0.1`; existing hostname and
IPv6 handling is unchanged.

Compatibility impact: breaking only for callers that incorrectly supplied an
IPv4 literal in URI-only bracket syntax. They must remove the brackets.

Acceptance criteria:

1. Sync and async client construction rejects bracketed IPv4 locally.
2. Connection options reject the same input locally.
3. Unbracketed IPv4, valid hostnames, and existing IPv6 rejection remain unchanged.
4. No live PLC check is required because this is deterministic pre-transport validation.

- [x] Implementation completed in this repository.
- [x] Tests cover client and connection-options rejection before transport.
- [x] Ruff, mypy, documentation checks, sample checks, and all 335 tests passed.
- [x] Codex self-review found no unresolved implementation or cross-language conflict.
- [x] Live PLC verification is not required for deterministic constructor validation.
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: `run_ci.bat` passed on Windows with Python 3.14.3,
including Ruff lint/format, mypy, documentation/sample/workflow checks, and all
335 tests. No live PLC communication was performed.

## REAUDIT-005 cross-language evidence — Empty public raw input

Decision status: accepted cross-language evidence finding corrected on
2026-08-02.

Implementation scope: sync/async public `send_raw`, frame validation ordering,
and direct rejection tests. Python already rejected an empty command as a
`HostLinkProtocolError`; validation now completes before sync admission or
async FIFO admission.

Target contract: empty public raw input is rejected as a protocol input error
before admission, connection-state inspection, client-state mutation, network
work, or exchange/send. Non-empty raw requests retain their existing framing,
FIFO, timeout, result, and error contracts.

Compatibility impact: none for valid callers. Empty input was already invalid;
only the timing of that existing local rejection moves before admission.

Machine-verifiable acceptance criteria:

1. Sync and async `send_raw("")` raise `HostLinkProtocolError` with neither
   admission context entered nor private exchange invoked.
2. Connection references and traffic counters remain unchanged at zero.
3. Existing non-empty raw command tests and the complete repository gate pass.

- [x] Validation ordering completed in sync and async clients.
- [x] Direct cross-language contract tests passed.
- [x] Relevant static, full test, sample, documentation, package/build, and source-archive gates passed.
- [x] Codex self-review completed for validation order, FIFO, state, network, and error behavior.
- [x] Live PLC verification disposition recorded.
- [x] Maintainer record and changelog agree; no user migration is required.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: direct sync and async tests replace admission and
exchange with fail-fast spies, call the public `send_raw("")`, and observe the
existing `HostLinkProtocolError` before either spy is entered. Connection
references and request/TX/RX counters remain unchanged. `run_ci.bat` and the
current-worktree source-archive/package-consumer gate passed with all 351
tests. Live PLC verification is not required because rejection is complete
before FIFO, connection inspection, socket work, or frame transmission.

Self-review finding classification:

- Accepted and corrected: Python's public raw API rejected empty input, but the
  explicit sync/async proof of rejection before admission and exchange was
  missing, and validation still occurred inside admission.
- Rejected findings: none. Duplicate findings: none. Deferred findings: none.

## REAUDIT-007 — Ruff source formatting

Implementation scope: the pre-existing non-compliant layout in
`src/hostlink/client.py` and the later Ruff gate correction in
`tests/test_sync_connection_deadline.py`; runtime behavior and public API are
unchanged.

Target state: every tracked Python file satisfies the repository's Ruff format
check without changing runtime behavior for the formatting-only correction.

Acceptance criterion: `python -m ruff format --check src tests` succeeds and
the correction changes only source layout.

Compatibility impact: none.

- [x] Formatting-only implementation completed in this repository.
- [x] Ruff formatting check is the machine-verifiable acceptance test.
- [x] The complete repository CI passed.
- [x] Codex self-review confirmed the correction changes only source layout.
- [x] Live PLC verification is not required for formatting-only work.
- [x] Changelog agrees with the correction; no migration or API documentation is required.
- [x] Final acceptance criterion verified and the item marked complete.

Acceptance evidence reverified on 2026-08-02 at source commit `9a586eb`:

- `python -m ruff format --check src tests` passed with all 22 files already
  formatted.
- `run_ci.bat` passed Ruff lint/format, mypy, documentation, API, sample, and
  workflow checks together with all 345 tests.
- `scripts/check_source_archive.ps1` passed the extracted-source full gate,
  wheel/sdist build, and isolated package-consumer check.
- The final test-file correction is one Ruff-only parenthesis-layout change;
  its Python AST is identical before and after the correction. No strings,
  branches, exceptions, public APIs, or communication behavior changed.
- Live PLC verification remains unnecessary because neither formatting
  correction changes executable syntax, request frames, transport behavior,
  response decoding, or profile decisions.

## REAUDIT-008 — Raw request frame capacity

Implementation scope: the shared sync/async TCP/UDP raw-request builder,
boundary tests, user API/usage documentation, and migration notes.

Target state: sync/async TCP and UDP raw command bodies accept at most 65,506
ASCII bytes. The terminating CR produces a maximum complete frame of 65,507
bytes. Larger input fails before connection-state checks or transport work.

Compatibility impact: breaking for maintainer-only `send_raw` callers whose
body is 65,507 through 65,536 ASCII bytes. Those bodies must be reduced or
split into supported command-specific operations.

Acceptance criteria:

1. A 65,506-byte body produces one 65,507-byte frame.
2. A 65,507-byte body is rejected without calling the exchange layer.
3. The boundary is transport-independent and does not relax smaller command-specific limits.
4. No live PLC check is required because frame construction and pre-send rejection are deterministic.

- [x] Implementation completed in this repository.
- [x] Boundary tests cover exact maximum framing and pre-exchange rejection.
- [x] Ruff, mypy, documentation checks, sample checks, and all 335 tests passed.
- [x] Codex self-review confirmed the shared builder covers sync/async and TCP/UDP.
- [x] Live PLC verification is not required for deterministic pre-send framing.
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: the exact accepted body produces a 65,507-byte frame;
the next byte is rejected before the test exchange layer records a frame. The
complete `run_ci.bat` gate passed on the final working-tree source state.

## PERF-001 — Optimize normal named-read wire plans

Decision status: implemented in HostLink Python on 2026-08-02.

Implementation scope: `read_named` request planning and the plan reused by
`poll`. Target contract: complete preflight precedes transport; requests are
grouped by device type in first-occurrence order, sorted by address within each
group, and compatible contiguous or overlapping ranges are merged up to the
request limit. Public dictionary keys remain in caller order. A multi-request
result is non-atomic and is published only after every segment succeeds.

Compatibility impact: wire order may differ from input order and fewer PLC
round trips can occur. Public key/value association and result order remain
unchanged. This supersedes the former one-request-or-reject record only for
normal HostLink named reads and PERF-008C polling.

Machine-verifiable acceptance criteria:

1. Interleaved device types do not split one mergeable device-type range.
2. Descending and overlapping compatible inputs produce the minimum plan under the point limit.
3. Full validation occurs before FIFO admission or send.
4. Returned values map to the original keys in caller order, with no partial result on failure.

- [x] Implementation completed in HostLink Python.
- [x] Tests added or updated for the HostLink Python acceptance criteria.
- [x] Relevant static, full test, sample, documentation, package/build, and current-worktree source-archive gates passed on this source state.
- [x] Codex self-review completed for the diff, validation, mapping, errors, FIFO behavior, and cross-language consistency requirements.
- [x] Live PLC verification is not required for deterministic planning and mapping behavior.
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## PERF-002 — Reuse healthy HostLink UDP sockets

Decision status: implemented in HostLink Python on 2026-08-02.

Implementation scope: synchronous and asynchronous UDP lifecycle. Target
contract: one connected socket and local endpoint is reused after complete valid
responses. Timeout, cancellation, transport/protocol failure, malformed or
extra input, and detected pre-send unowned datagrams discard it. The next
request creates a socket from the cached numeric IPv4 endpoint without DNS.
State-changing post-send failures remain outcome-unknown and are never retried;
explicit close prevents further communication. The accepted residual limitation
is that a late duplicate arriving between the pre-send check and send cannot be
distinguished because Host Link has no request identifier.

Compatibility impact: healthy requests retain one local port instead of using
one port per request. An abnormal exchange can change the port used by the next
request. Non-compliant delayed duplicate responses retain the documented
residual misassociation risk.

Machine-verifiable acceptance criteria:

1. Consecutive successful requests reuse the same sync/async socket and endpoint.
2. Every observable abnormal-input path discards the current socket.
3. A later request creates a fresh socket without DNS and never retries the failed request.
4. Close disposes the socket and makes later communication fail.

- [x] Implementation completed in HostLink Python.
- [x] Deterministic sync/async reuse, delayed-unowned-input, failure, replacement, and close tests added or updated.
- [x] Relevant static, full test, sample, documentation, package/build, and current-worktree source-archive gates passed on this source state.
- [x] Codex self-review completed for sync/async lifecycle, outcome classification, and cross-language consistency requirements.
- [x] Live PLC verification passed for healthy sync/async UDP socket reuse and explicit post-close rejection (`HL-KVX500-02`).
- [x] Live PLC verification passed for sync/async timeout isolation, failed-socket retirement, and DNS-free replacement (`HL-KVX500-02B`).
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

Final live evidence: after the fixed guarded runner was compiled, reviewed, and
separately approved, `HL-KVX500-02` ran read-only against KEYENCE KV-X500
profile `keyence:kv-x500` at `192.168.250.100:8501` over UDP. The synchronous
and asynchronous public clients each retained one socket, socket generation,
and local endpoint across two complete 11-request cycles: 22 successful
requests and 44 raw send/receive frames per client. Each client performed one
socket creation and one bind/connect, performed no resolver-helper or actual
DNS lookup, and did not close or reopen the socket between requests. Explicit
close raised the close count to one and left no active socket. A subsequent
read-only `RD DM120.U` on the same closed client was rejected before send with
`HostLinkNotConnectedError`; raw frames, traffic counters, lifecycle counters,
and socket state remained unchanged for both client variants.

Both cycles and both clients returned direct word values
`[0, 0, "0000", 0, 0, 13]` and normalized MWR values
`[0, 0, "0000", 0, 0, 13]`; the preserved raw MWR fields were
`["00000", "+00000", "0000", "0000000000", "+0000000000", "00013"]`.
RDS and MBR both returned the prepared bit pattern `[1, 0, 1]`. Thus direct
reads equaled monitor reads semantically, the bare direct-bit packed value was
`13`, and the batch performed no device writes. Evidence file:
`D:\APP\live-kvx500-20260802\python_hl_kvx500_02_udp_final_result.json`
(SHA-256
`E4B412D60D989EDF03EFACA8D2C7876B18289B742FA719E27DFD780DCDFB1044`).
The reviewed runner SHA-256 is
`839AC22101C30FB5470B3DB0A42D78C359431D74EEA925D2F4F160462DFF4A86`.

Controlled anomaly evidence: after separate approval of the fixed runner,
`HL-KVX500-02B` used one physical UDP-path interruption and one restoration
while keeping the synchronous and asynchronous public clients alive. All
communication was read-only and strictly sequential. In phase A, each client
read `DM120.U` as `0` on its retained socket. In phase B, each client issued
exactly one request, reached the fixed two-second timeout without retry, and
retired the failed socket so no active socket remained. In phase C, each client
created socket generation 2 from the retained numeric endpoint without another
DNS lookup, read `DM120.U` as `0`, and closed without an active socket. Each
client recorded three requests, 33 transmitted bytes, and 14 received bytes;
the batch performed no writes. Evidence file:
`D:\APP\live-kvx500-20260802\python_hl_kvx500_02b_udp_anomaly_result.json`
(SHA-256
`BE05E1C8D623CE67CC027C88E19295672C0B4994564CE1F61EDD1E4D3103A63F`).

## PERF-008B — Own one FIFO turn for a named-read aggregate

Decision status: implemented in HostLink Python on 2026-08-02.

Implementation scope: normal `read_named`. Target contract: snapshot, parse,
duplicate, profile, capacity, and request-plan checks complete before FIFO
admission. One FIFO turn covers every optimized segment through decode and
all-or-error staging. Pure caller-order result materialization occurs after
release, so no other wire operation can interleave between segments.

Compatibility impact: a later operation can wait for the complete aggregate,
but cannot observe or cause segment interleaving. Separate clients remain the
way to obtain independent latency.

Machine-verifiable acceptance criteria:

1. Invalid input reaches neither FIFO nor transport.
2. A multi-segment aggregate acquires and releases one turn.
3. Later wire operations cannot send before the last segment.
4. Decode/stage failure publishes no partial result and pure materialization is outside the turn.

- [x] Implementation completed in HostLink Python.
- [x] HostLink Python FIFO, plan-order, mapping, and failure tests added or updated.
- [x] Relevant static, full test, sample, documentation, package/build, and current-worktree source-archive gates passed on this source state.
- [x] Codex self-review completed for preflight, FIFO, staging, failure boundaries, and cross-language consistency requirements.
- [x] Live PLC verification is not required for deterministic FIFO ownership.
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## PERF-008C — Reuse one optimized plan per polling stream

Decision status: implemented in HostLink Python on 2026-08-02.

Implementation scope: `poll`. Target contract: addresses are snapshotted,
validated, and compiled once before cycles begin. Every cycle reuses that plan,
owns one FIFO turn for all segments, stages all values, releases the turn, then
materializes/yields and waits the configured post-cycle interval outside FIFO.
Failure publishes no partial sample, retries nothing, and terminates with the
existing structured error.

Compatibility impact: one sample can contain multiple non-atomic PLC reads and
later same-client operations wait until the cycle completes. The configured
interval begins after cycle completion; no fixed-rate catch-up is introduced.

Machine-verifiable acceptance criteria:

1. Planning occurs once before the first cycle and invalid input sends nothing.
2. Every cycle executes the PERF-001 plan in exactly one FIFO turn.
3. No partial, retried, filled, or previous-value sample is published on failure.
4. Yield and interval wait occur outside FIFO, permitting another operation between cycles.

- [x] Implementation completed in HostLink Python.
- [x] HostLink Python plan-reuse and between-cycle FIFO release tests added.
- [x] Relevant static, full test, sample, documentation, package/build, and current-worktree source-archive gates passed on this source state.
- [x] Codex self-review completed for plan reuse, cycle, yield, interval behavior, and cross-language consistency requirements.
- [x] Live PLC verification is not required for deterministic planning and FIFO behavior.
- [x] User documentation, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

## 2026-08-02 performance implementation self-review classification

- Accepted and corrected: named-read wire execution still followed caller order;
  planning now applies PERF-001 grouping, sorting, merging, and caller-order
  result remapping before PERF-008B execution.
- Accepted and corrected: the UDP implementation retained the prior one-socket-
  per-request isolation design; healthy sync/async endpoints are now reused and
  every observed abnormal path discards only the UDP request socket while
  preserving its cached numeric peer.
- Accepted and corrected: user documentation and docstrings still described
  fresh UDP ports and caller-order wire requests; they now describe the approved
  lifecycle, optimized plan, non-atomic result, FIFO, and polling semantics.
- Rejected by approved contract: eliminating the residual delayed-duplicate
  window is not possible without restoring per-request endpoint isolation or a
  protocol request identifier. Observed unowned input is rejected and contained.
- Duplicate findings: none. Deferred findings: none. The final multi-version
  repository/package gates and four-implementation consistency review passed;
  deterministic request-count and lifecycle tests provide the required
  performance-contract evidence without a separate wall-clock benchmark.

## LIVE-HL-003 — Preserve structural timer/counter status

Decision status: approved by the maintainer on 2026-08-02; implemented and
live-verified in HostLink Python.

Implementation scope: synchronous and asynchronous `RD T/C` composite
decoding, typed helpers, documentation, and deterministic response vectors.
Target contract: validate the raw first token as exact `0` or `1` before
numeric parsing. Keep that structural field as integer status and apply the
selected `.U`, `.S`, `.H`, `.D`, or `.L` format only to current and preset.

Compatibility impact: Python already implemented the approved target, so
public signatures and returned Python types do not change. The record and
tests now make the cross-language low-level contract explicit.

Machine-verifiable acceptance criteria:

1. Raw status accepts only exact `0` or `1` and is never numeric-format normalized.
2. Current and preset alone use the requested format and its bounds.
3. `.H` returns status `0`/`1` with four-uppercase-digit current and preset values.
4. Invalid status, shape, numeric text, or range retires the supplying transport.
5. The real KV-X500 vector `0,270F,270F` is shared with the other HostLink implementations.

- [x] Implementation completed in HostLink Python.
- [x] Tests added or updated for every local acceptance criterion.
- [x] Relevant static, unit, integration, sample, documentation, package, and build checks passed on the final source state.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Corrected representative live batch passed after explicit approval.
- [x] User documentation, migration notes, changelog, and API reference agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.

Verification evidence: `run_ci.bat` passed Ruff lint/format, mypy, public and
high-level documentation coverage, sample/workflow validation, and all 392
tests plus 58 subtests. Direct format-matrix tests cover `.U`, `.S`, `.H`,
`.D`, and `.L`; direct transport tests cover missing/extra fields, invalid
current/preset text, every
numeric range, exact-status rejection, and session retirement. The package
content gate built wheel/sdist artifacts and passed an isolated consumer check.

Corrected representative live evidence: the explicitly approved read-only
`HL-KVX500-01` batch ran against profile `keyence:kv-x500` at
`192.168.250.100:8501` over TCP from
2026-08-02T11:11:51.411151Z through 2026-08-02T11:11:51.475295Z. Both the
synchronous and asynchronous public clients returned `R000.H = 0000` and
`T0.H = [0, 270F, 270F]`, preserving status as integer `0` and applying `.H`
only to current and preset. Each client completed exactly 12 requests with
163 transmitted bytes and 139 received bytes. The batch result is `pass`.
Evidence file:
`D:\APP\live-kvx500-20260802\python_hl_kvx500_01_result.json` (SHA-256
`D5F6C926F149658E1A51B9D95D5F036728555854DDAD883E5D6716E8E756C3D2`).
The reviewed runner SHA-256 is
`FBCB158D386D41A38C82F02D76C6C61959C2F3A1A27A0CEA917830494CE7DACC`;
it loaded the approved worktree based on repository HEAD
`9a586ebd77d5f7e675645c08422ff18207f091c9`.

Self-review finding classification:

- Accepted and corrected: cross-language evidence needed the real
  `0,270F,270F` vector plus direct all-format and malformed composite tests.
- Accepted and corrected: user and maintainer documentation did not explicitly
  separate structural status from formatted current/preset fields.
- Rejected findings: none. Duplicate findings: none. Deferred implementation
  findings: none. The corrected representative live batch passed after its
  separate explicit approval.

## LIVE-HL-004 — Bare direct-bit MWS packed-word response

Decision status: approved by the maintainer on 2026-08-02 and implemented in
HostLink Python.

Implementation scope: synchronous and asynchronous monitor-word registration,
ordered MWR response validation, connection-scoped monitor metadata, user/API
documentation, changelog, and deterministic response vectors.

Target contract: only in `MWS`/`MWR`, a bare direct-bit target such as `R5000`
means the packed unsigned 16-bit word beginning at that bit. Registration sends
the exact bare target and does not append `.U`. Its MWR position accepts decimal
text of exactly one through five ASCII digits, with optional leading zeros and
numeric value `0` through `65535`, and uses the existing `list[str]`
monitor-word result. Scalar bare `RD` and `MBS`/`MBR` retain strict bit
semantics.

Compatibility impact: valid bare direct-bit MWR fields such as `00000`,
`00002`, and `00013` no longer raise a protocol error. Public method signatures
and returned Python types do not change. Existing callers receive the same
string representation already used for an explicit unsigned MWR field.

Machine-verifiable acceptance criteria:

1. Sync and async registration of bare `R5000` sends exact `MWS R5000`.
2. Bare direct-bit MWR fields accept `0`, `2`, `13`, `00000`, `00002`,
   `00013`, and `65535`, preserving the selected wire spelling as `str`.
3. Empty, whitespace-only, signed, overflow, non-decimal, over-five-digit, and
   extra-field responses raise `HostLinkProtocolError`, retire the supplying
   transport, and clear metadata.
4. Mixed monitor registrations preserve field order and apply each registered
   numeric format independently.
5. Bare scalar RD and MBS/MBR still reject packed values as invalid bit tokens.
6. Close/reconnect and uncertain failed registration cannot reuse the prior
   packed-word metadata; explicit re-registration restores it.
7. User documentation, API reference, migration record, and changelog describe
   the same command-specific distinction and unchanged public representation.

- [x] Implementation completed for synchronous and asynchronous clients.
- [x] Tests added or updated for every local acceptance criterion.
- [x] Relevant Ruff, mypy, unit, documentation, sample, workflow, and package checks passed.
- [x] Codex self-review completed against the approved contract and shared Host Link semantics.
- [x] Corrected Python sync and async public-API live acceptance passed against the independently prepared KV-X500 bit pattern.
- [x] User documentation, API reference, migration notes, and changelog agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete in HostLink Python.

Verification evidence: the repository gate passed all 392 tests and 58
subtests. Ruff lint/format, mypy, high-level documentation coverage, public API
docstring coverage, user-sample validation, release-workflow validation, and
the package-content/isolated-consumer check passed on the final source state.
Direct sync/async vectors cover short and zero-padded zero, `2`, `13`, maximum,
mixed order, empty, whitespace-only, signed, overflow, non-decimal,
over-five-digit, extra-field shape, session retirement,
close/re-registration, failed registration, scalar RD, and MBS/MBR isolation.
The decisive raw live vector remains recorded in
`D:\APP\live-kvx500-20260802\node_mwr_user_pattern_readback_result.json`.
After the exact guarded Python program was completed, compiled, reviewed, and
separately approved, both sync and async public APIs read `R5000`–`R5015`,
calculated `13`, sent bare `MWS R5000`, and returned preserved monitor string
`00013`. Evidence:
`D:\APP\live-kvx500-20260802\python_mwr_semantic_acceptance_result.json`.
The later complete `HL-KVX500-01` read-only batch also exercised the same mixed
registration through both public clients. Direct results were
`[0, 0, "0000", 0, 0, 13]`; MWR preserved the positionally corresponding
fields as `["00000", "+00000", "0000", "0000000000", "+0000000000",
"00013"]`. Thus the bare final `R5000` field decoded as packed value `13`,
not as one scalar bit, while the five explicit formats retained their own
decoders. Sync and async each completed 12 requests with TX 163 and RX 139
bytes. The result file and hashes are recorded under `LIVE-HL-003` above.

Self-review finding classification:

- Accepted and corrected: bare direct-bit MWS metadata used the empty-format
  strict-bit decoder even though the PLC returns a packed unsigned word.
- Accepted and corrected by `LIVE-HL-004-WIRE-GRAMMAR`: mapping the field to
  generic `.U` would also accept over-five-digit leading-zero spellings; a
  distinct internal monitor format now enforces the approved wire grammar.
- Rejected by the approved wire contract: appending `.U` to the registration
  would decode correctly but would alter the required bare PLC command.
- Accepted and corrected: direct tests did not cover mixed field order, the
  full unsigned boundary, malformed response retirement, or stale metadata for
  both client variants.
- Duplicate findings: none. Deferred implementation findings: none.

### LIVE-HL-004-WIRE-GRAMMAR — Packed direct-bit MWR field grammar

Decision status: approved by the maintainer on 2026-08-02 and implemented in
HostLink Python.

Implementation scope: only the internal monitor metadata and decoder for bare
direct-bit MWS positions. Explicit `.U` monitor fields retain their existing
numeric grammar, and no wire token or public type changes.

Target contract: one bare direct-bit MWR field is exactly one through five
ASCII decimal digits, leading zeros are optional, and its parsed value is
`0..65535`. Empty, whitespace-only, signed, non-decimal, over-five-digit, and
overflowing fields are malformed semantic responses and retire the transport.

Compatibility impact: the approved packed values and existing `list[str]`
representation remain unchanged. Previously accepted noncanonical values with
more than five leading-zero digits are now rejected as protocol errors.

Machine-verifiable acceptance criteria:

1. `0`, `2`, `13`, `00000`, `00002`, `00013`, and `65535` are accepted and
   returned with their original spelling.
2. Empty, whitespace-only, `-1`, `+2`, `65536`, `000000`, non-decimal, and
   extra-field responses are rejected and retire sync/async transports.
3. Bare `MWS R5000` wire output, mixed field order, public `list[str]` type,
   scalar RD, and MBS/MBR behavior remain unchanged.

- [x] Distinct internal monitor metadata and validator implemented.
- [x] Sync and async grammar/retirement tests cover every acceptance vector.
- [x] Relevant full tests, static checks, documentation checks, and package checks passed.
- [x] Codex self-review verified grammar isolation, exact wire, return representation, and retirement.
- [x] Documentation, changelog, and migration record agree.
- [x] Final acceptance criteria verified and the subdecision marked complete in HostLink Python.

## Final non-live disposition recheck — `HL-001`, `HL-003`, and `HL-PY-003`

Final source-state targeted checks passed on 2026-08-02 without PLC communication.

- `HL-001`: sync and async
  `test_*_tcp_rejects_two_nonempty_responses_in_one_receive` plus
  `test_*_tcp_pre_send_unowned_input_sends_nothing_and_retires_connection`
  passed 4/4. They prove deterministic extra-line rejection, transport
  retirement, zero later send, and no response reassignment.
- `HL-003`:
  `test_special_family_float32_typed_named_and_poll_reject_before_fifo`
  passed all five parameter rows. `Z:F` and every other ineligible family are
  rejected before FIFO or transport while the ordinary-word Float32 contract
  remains independently covered.
- `HL-PY-003`:
  `test_async_close_invalidates_and_disposes_late_{tcp,udp}_connection_candidate`
  and
  `test_async_{tcp,udp}_connect_cancellation_closes_late_candidate_once_across_repeated_close`
  passed 4/4. The externally blocked connection factories return candidates
  only after close/cancellation; generation validation prevents publication,
  disposes each late candidate once, and leaves every client transport field
  empty.

Exact commands were `.\.venv\Scripts\python.exe -m pytest -q` with the named
node IDs in `tests/test_overhaul_contract.py` and
`tests/test_transport_recovery.py`.

- [x] `HL-001` deterministic non-live disposition reverified on the final source state.
- [x] `HL-003` deterministic non-live disposition reverified on the final source state.
- [x] `HL-PY-003` deterministic close-generation disposition reverified on the final source state.

## HL-PY-004 — Counted single bit-in-word aggregate read

Decision status: approved by the maintainer on 2026-08-07.

Implementation scope: Python `read_named` and `poll` planning for one otherwise
unmerged bit-in-word point on an optimizable ordinary word-device family.
Ordinary public `read` and non-optimizable individual routes are unchanged.

Target contract: the aggregate planner sends `RDS <device>.U 1`, matching the
.NET, Node.js, and Rust Host Link implementations. It performs exactly one
request and returns the same Boolean value as before.

Compatibility impact: the Python aggregate request gains the explicit counted
read command and count token. There is no public API, result, connection, or
round-trip-count change; callers that assert the former aggregate `RD` bytes
must update that wire expectation.

Machine-verifiable acceptance criteria:

1. A sole `DM100.A` named read sends exactly `RDS DM100.U 1` and resolves the
   selected bit to `bool`.
2. `poll` reuses the same compiled counted request for every cycle.
3. Ordinary `read("DM100", data_format=".U")` continues to send `RD DM100.U`.
4. The published cross-language Host Link wire contract reports the same
   single-point aggregate request for Python, .NET, Node.js, and Rust.

- [x] Python aggregate implementation completed.
- [x] A focused wire/result regression test was added.
- [x] Relevant static, full unit, package-build, and cross-language checks passed.
- [x] Codex self-review completed against the approved contract.
- [x] No live-PLC check is required because exact request/response behavior is covered by the mock wire contract.
- [x] Changelog and maintainer migration record agree with the implementation.
- [x] Final acceptance criteria verified and the item marked complete.
