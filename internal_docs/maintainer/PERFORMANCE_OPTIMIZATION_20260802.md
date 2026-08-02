# HostLink performance optimization acceptance record (2026-08-02)

## PERF2-001 — Incremental TCP receive framing

Target contract: one client-owned growable accumulator retains incomplete TCP data, scanning resumes from the previous cursor, and a completed response is published as independent immutable `bytes`.

Acceptance evidence:

- [x] Sync and async TCP paths share the incremental accumulator.
- [x] A 65,536-byte body delivered one byte at a time is scanned and copied within linear recorded bounds.
- [x] Close releases retained accumulator capacity.

## PERF2-006 — O(1) async FIFO maintenance

Target contract: enqueue, head removal, and cancellation removal do not shift or linearly search queued waiters; invalidation may traverse the queue once.

Acceptance evidence:

- [x] Admission uses ticket-keyed `OrderedDict` insertion/removal and oldest-item dequeue.
- [x] Source-contract and existing lifecycle/concurrency tests cover the queue behavior.

## PERF2-013 — Workerless numeric IPv4 sync connect

Target contract: numeric IPv4 sync connections use nonblocking `connect_ex`, readiness waiting, and `SO_ERROR` under one absolute deadline without DNS or a helper thread. Hostnames retain isolated resolver work. Close prevents late adoption and wakes a registered connection candidate.

Acceptance evidence:

- [x] Deterministic tests prove the numeric path uses no resolver or worker thread.
- [x] Timeout, close wake, and generation/current-operation adoption checks are covered.

No public API, wire request, or supported behavior changed. User/API documentation needs no migration update. Live PLC verification is not required because the optimized paths are covered with local sockets and do not change protocol framing or request count.
