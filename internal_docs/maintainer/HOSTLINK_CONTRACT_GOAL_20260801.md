# Host Link Python Contract Completion Goal — 2026-08-01

These approved target-state records supersede conflicting historical behavior.
They apply to the normal synchronous and asynchronous clients and the public
helper layer. Deterministic local transport fixtures are sufficient evidence;
no live PLC communication is required because these items govern local
admission, validation, timeout, framing, error, and aggregation behavior.

## HL-CONTRACT-001 — Exact transport capacity boundaries

### Implementation scope

Request construction and TCP/UDP response collection.

### Target contract

The request body and response body each have an absolute 65,536-byte maximum.
The exact maximum succeeds, while maximum plus one fails before transport or
before response acceptance and retires an uncertain transport.

### Compatibility impact

Oversized raw requests and responses that were previously transport-dependent
now fail deterministically.

### Acceptance criteria

1. A 65,536-byte request body builds one 65,537-byte CR-terminated frame.
2. A 65,537-byte request body causes zero sends and no state change.
3. TCP and UDP accept a 65,536-byte response body and reject 65,537 bytes.
4. Semantic response shapes remain command-derived and exact.

## HL-CONTRACT-002 — Absolute request and separate connect deadlines

### Implementation scope

Sync/async TCP and UDP connection and request paths.

### Target contract

`connect_timeout` is a separate connection-establishment deadline. Each
request snapshots `timeout` immediately before first send/write and uses one
absolute deadline across transmit, drain, receive, and decoding. Timeout or
cancellation retires the transport.

### Compatibility impact

Slow partial traffic and slow writer drain can no longer restart the deadline.

### Acceptance criteria

1. Positive finite validation applies independently to both deadlines.
2. Sync and async trickle/drain fixtures cannot exceed one request deadline by
   restarting per-I/O timeouts.
3. Timed-out/cancelled transports cannot associate a late response with a
   later request.
4. All connection creation is explicitly IPv4-only.

## HL-CONTRACT-003 — FIFO admission and immediate close

### Implementation scope

Normal sync/async clients, queued operations, and aggregate reads.

### Target contract

Operations are admitted in arrival FIFO order. Inputs are snapshotted before
admission. Waiting async cancellation sends nothing. `close()` does not wait
behind active work: it retires the active generation and rejects active and
already queued work immediately.

### Compatibility impact

Scheduling is now predictable. Code relying on lock barging or close waiting
must not do so.

### Acceptance criteria

1. Sync and async overlapping operations emit requests in arrival order.
2. A cancelled async waiter emits no request and raises the typed cancellation.
3. Close rejects queued work as closed and interrupts active transport I/O.
4. A state-changing active request rejected after possible send reports an
   unknown outcome with reason `closed`.

## HL-CONTRACT-004 — Machine-readable failures and no resend

### Implementation scope

Public exception exports and all semantic/raw request paths.

### Target contract

Timeout, cancellation, closed, not-connected, transport, malformed response,
PLC NG, and state-changing outcome unknown are distinguishable public types or
reasons. Native causes are retained. Unknown raw commands are treated as
state-changing. No request, including a read, is automatically resent after a
possible send.

### Compatibility impact

Exact generic-error matching changes. State-changing failures may now require
explicit reconciliation rather than retry.

### Acceptance criteria

1. Every failure category is public and machine-readable.
2. `HostLinkOutcomeUnknownError` exposes stable `reason` and typed `detail`.
3. Native timeout/cancellation/I/O causes remain in the exception chain.
4. Local fixtures prove one send only on every failed exchange path.

## HL-CONTRACT-005 — Ordered read aggregation and removal of unsafe RMW

### Implementation scope

`read_named`, `poll`, package exports, sync/async clients, samples, and docs.

### Target contract

Named reads completely preflight caller input, preserve declaration-order
request emission, keep each entry indivisible, and may split only necessary
read-only work while holding one FIFO turn. Multi-request results are non-atomic
and errors return no partial dictionary. State-changing multi-request work is
not synthesized. The public `write_bit_in_word` read-modify-write API is
removed without an alias.

### Compatibility impact

Named request ordering is observable and stable. Applications using the
removed RMW helper must use PLC-side atomic behavior or exclusive word
ownership.

### Acceptance criteria

1. Invalid later entries cause zero sends.
2. Request order matches caller order across device types and comments.
3. Oversized read-only aggregates split only at entry boundaries in one FIFO
   turn and return no partial result on failure.
4. `write_bit_in_word` is absent from clients, helpers, exports, samples, and
   generated/public API documentation.

## Completion evidence

- [x] Implementation completed in this repository for all five items.
- [x] Tests added or updated for every acceptance criterion in sync and async paths.
- [x] Relevant static checks, unit tests, integration tests, examples, Python 3.10, and package/build checks passed.
- [x] Codex self-review completed against the approved contract and cross-language consistency requirements.
- [x] Live-PLC verification recorded as not required for these deterministic local contracts.
- [x] Documentation, migration notes, changelog, and API reference agree with the implementation.
- [x] Final acceptance criteria verified and the record marked complete.

Evidence: normal CI and Python 3.10 each passed 253 tests; API generation ran
18 subtests; Ruff, mypy, sample validation, and strict MkDocs succeeded; wheel
and sdist content, Twine metadata, Python 3.10 isolated consumers, and the
synthetic current-worktree source archive's extracted 253-test/build gate all
passed. Codex self-review inspected the actual diff, public exports, sync/async
FIFO transitions, validation order, absolute deadline including decode,
error/cause classification, close/cancel recovery, named-read segmentation,
samples, docs, packaging, and cross-language contract alignment. No accepted
self-review finding remains open.

### Self-review dispositions

- Accepted and corrected: Python 3.10 distinguishes `asyncio.TimeoutError`
  from built-in `TimeoutError`, and a cancellation-derived exception that
  subclasses `asyncio.CancelledError` remains task-cancelled rather than a
  catchable library error. The async timeout catch and public cancellation
  type were corrected, then the full Python 3.10 suite was rerun.
- Accepted and corrected: the first implementation ended the deadline after
  receive. Explicit post-decode deadline checks and sync/async decode-delay
  tests now cover the approved decode boundary.
- Accepted and corrected: a later direct-bit Float32 named read could pass the
  plan builder and fail only during execution. Full preflight now rejects it
  before every send, with zero-send regression evidence.
- Accepted and corrected: user documentation, one public helper docstring, and
  a sample still called potentially multi-request aggregate results snapshots.
  They now use collection/result terminology, while admission-time input
  snapshot wording remains because it describes immutable caller inputs.
- Rejected: none.
- Duplicate: none.
- Deferred: none for `HL-CONTRACT-001` through `HL-CONTRACT-005`.
