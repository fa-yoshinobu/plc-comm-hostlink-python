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

AsyncHostLinkClient is built on top of asyncio.StreamReader/Writer. 

- **Internal Lock**: The library handles an internal asyncio.Lock to ensure commands do not overlap in the same connection.
- **Parallel Requests**: You can trigger multiple concurrent tasks. While the hardware handles one request at a time, the library's lock ensures they are queued and executed as fast as the PLC responds.

## 4. Bulk Transfers (RDS/WRS)

Instead of calling read() 1,000 times for 1,000 devices, use **read_consecutive()**.

- **Protocol Limit**: Up to 1,000 words can be transferred in a single command.
- **Latency Advantage**: Reading 1,000 words in one bulk transfer (approx. 5ms) is much faster than 1,000 individual reads (approx. 1,000ms).

## 5. Monitoring (MBS/MWS)

For high-frequency cyclic reading of specific devices:
1. Register them once with register_monitor_words().
2. Repeatedly call read_monitor_words().

This is the most efficient way to query a large set of non-consecutive devices.

## 6. System Load and Latency

Communication speed is ultimately limited by:
- **PLC Scan Time**: If the PLC is under heavy ladder load, it may respond slower to Host Link requests.
- **Network Congestion**: Avoid running heavy file transfers on the same network subnet as the PLC.
- **Python Overhead**: For ultimate performance, minimize complex logic inside the communication loop.
