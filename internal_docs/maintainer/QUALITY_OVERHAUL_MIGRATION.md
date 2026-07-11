# HostLink Python quality-overhaul contract and migration

Branch: `quality/2026-07-overhaul`  
Authoritative approvals: `D:\APP\omittable_configuration_decisions_20260711.md`  
Related findings: B-18 through B-29 in `D:\APP\library_bug_consistency_review_20260710.md`

This record describes the Python implementation of approved decisions D-052 through D-064. A checked item requires recorded evidence. Claude has not been invoked; its items remain pending explicit user authorization. No live PLC operation was performed for this batch.

## D-052 — Explicit transport

Scope: `HostLinkClient`, `AsyncHostLinkClient`, `HostLinkConnectionOptions`, helpers, samples, and user documentation.

Target contract: `transport` is required and accepts only `tcp` or `udp`; it is never inferred from omission or an invalid value.

Compatibility impact: calls that omitted transport must add `transport="tcp"` or `transport="udp"`.

Acceptance criteria:

1. Missing transport is rejected by the Python call signature before transport creation.
2. Empty and unknown transport values are rejected before transport creation.
3. Explicit TCP and UDP values are retained unchanged after normalization.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: no live communication is required for constructor validation.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: timeout configuration validation is locally testable; timeout recovery uses local TCP/UDP fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

## D-054 — CR-only command framing

Scope: protocol frame builder, clients, and removed LF options.

Target contract: every normal HostLink request ends with one CR byte; no public LF-append switch exists.

Compatibility impact: `append_lf_on_send` and related builder arguments are removed.

Acceptance criteria:

1. Frame vectors end in `0x0D`.
2. Public constructors and builders expose no LF option.
3. User documentation contains no LF setting.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, vector, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: fixed frame bytes are covered by deterministic vectors; no PLC communication required.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

## D-055 — Library-owned receive buffering and cap

Scope: sync/async TCP and UDP receive paths.

Target contract: receive chunking and the 65,536-byte absolute response-body cap are internal; overflow invalidates the transport.

Compatibility impact: public `buffer_size` is removed and cannot be used to weaken or tighten protocol validation.

Acceptance criteria:

1. Public signatures contain no buffer-size parameter.
2. TCP accepts exactly 65,536 body bytes and rejects 65,537.
3. UDP receives enough data to detect cap overflow and invalidates the socket on overflow.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, local transport, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: framing and cap behavior use deterministic local transport fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: hook ordering and isolation are transport-independent and locally verified.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: constructor side effects are locally observable and require no PLC.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: lifecycle/error sequences are covered by local TCP/UDP fixtures.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [x] Static, unit, vector, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: command construction/validation is deterministic; PLC clock mutation was not performed.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: raw framing/decoding contract is locally fixture-tested.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: byte fixtures cover normalization and encodings without PLC communication.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [x] Static, unit, vector, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: this batch changes pre-send format/range policy and deterministic frames only; existing profile-specific URD/UWR support is not newly claimed, so no live check is required for this item.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

## D-063 — No public automatic chunking

Scope: package exports, helpers, samples, and documentation.

Target contract: only single-request word/dword operations remain; the application owns any multi-request loop and its timing/partial-success semantics.

Compatibility impact: all public `*chunked` helpers are removed without aliases.

Acceptance criteria:

1. Chunk helpers are absent from package exports and generated API documentation.
2. Samples do not combine multiple PLC requests into one apparent snapshot/result.
3. single-request helpers reject protocol limits instead of splitting.

- [x] Implementation completed for HostLink Python.
- [x] Tests added or updated for every criterion.
- [x] Static, unit, documentation, sample, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: request count and pre-send limits are locally deterministic.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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
- [x] Static, unit, vector, sample, documentation, and package checks passed.
- [x] Codex self-review completed against the approved contract.
- [ ] Claude source review completed. Pending explicit user authorization.
- [ ] Every Claude finding dispositioned and affected checks rerun. Pending review.
- [x] Live-PLC disposition recorded: input semantics and wire frames are deterministic; no PLC communication required.
- [x] Documentation, migration notes, changelog, and API reference agree.
- [ ] Final cross-language acceptance verified.

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

- Unit/contract suite: repository CI passed with `217 passed` on Python 3.14.3; final evidence is also recorded in the root overhaul goal.
- Type checking: `python -m mypy src/hostlink` passed.
- Claude: not invoked; explicit authorization is still required.
- Live PLC: not invoked.
