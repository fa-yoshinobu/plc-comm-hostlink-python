# Performance Tuning Guide

This library is designed for high-frequency PLC communication, reaching 1,000+ operations/sec in optimal conditions. This guide explains how to achieve and maintain this level of performance.

---

## 1. Transport Choice: TCP vs. UDP

The library supports both TCP and UDP. 

- **UDP (Recommended for Speed)**: 
  - Achieves ~1,500 ops/sec (verified on KV-7500).
  - Lowest latency since it avoids TCP handshake and acknowledgement overhead.
  - Recommended for stable local networks.
- **TCP**:
  - Achieves ~1,000 ops/sec.
  - Provides reliability via OS-level retransmission.
  - Recommended for remote or less stable networks.

## 2. TCP Optimizations (TCP_NODELAY)

By default, the library enables **TCP_NODELAY**. This disables the Nagle algorithm, which normally waits to buffer small packets before sending. Since Host Link commands are small strings (e.g., RD DM0\r), TCP_NODELAY is essential for low-latency response.

## 3. Asynchronous Efficiency

The recommended helper workflow is fully asynchronous.

- **Single connection, many awaits**: Reuse one connected client from `open_and_connect`.
- **Queued access**: Multiple coroutines can await helper calls safely on the same connection.
- **Polling helper**: Use `poll` when you want repeated snapshots without rebuilding the address list each time.

## 4. Bulk Reads

Prefer the high-level batch helpers instead of many single-value reads.

- Use `read_words` for contiguous 16-bit word blocks.
- Use `read_dwords` for contiguous 32-bit values.
- Use `read_named` when the snapshot mixes types or bit-in-word values.

These helpers reduce round-trips and usually outperform repeated `read_typed` calls.

## 5. Polling and Snapshots

For cyclic application code:

1. Use `read_named` for one mixed snapshot.
2. Use `poll` for repeated snapshots at a fixed interval.

This is the recommended user-facing pattern for dashboards, logging, and periodic monitoring loops.

## 6. System Load and Latency

Communication speed is ultimately limited by:
- **PLC Scan Time**: If the PLC is under heavy ladder load, it may respond slower to Host Link requests.
- **Network Congestion**: Avoid running heavy file transfers on the same network subnet as the PLC.
- **Python Overhead**: For ultimate performance, minimize complex logic inside the communication loop.
