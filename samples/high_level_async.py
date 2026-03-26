# ruff: noqa: E402
"""
KEYENCE Host Link - High-Level Asynchronous API Sample
======================================================
Demonstrates all high-level *async* utility helpers shipped with the
hostlink package (read_typed, write_typed, read_named, read_words,
read_dwords, write_bit_in_word, poll, open_and_connect).

Usage
-----
    python samples/high_level_async.py --host 192.168.250.100 [--port 8501]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import (
    open_and_connect,
    poll,
    read_dwords,
    read_named,
    read_typed,
    read_words,
    write_bit_in_word,
    write_typed,
)
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="KEYENCE Host Link asynchronous high-level API sample",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--host", required=True, help="PLC IP address or hostname")
    p.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Host Link TCP port (default 8501)",
    )
    p.add_argument(
        "--poll-count",
        type=int,
        default=3,
        help="Number of poll snapshots to capture (default 3)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------


async def demo_open_and_connect(host: str, port: int) -> None:
    """
    open_and_connect - create and open the connected client used by the helper API.

    Parameters:
        host  - KV PLC IP / hostname
        port  - KV Ethernet port (default 8501 inside open_and_connect)

    Returns a connected client object for the helper functions below.
    """
    client = await open_and_connect(host, port=port)
    print(f"[open_and_connect] Connected to {host}:{port}")
    await client.close()


async def demo_typed_rw(client) -> None:
    """
    read_typed / write_typed - single device with type conversion.

    dtype codes (match the Host Link .format suffixes):
        "U"  unsigned 16-bit int  (1 word)
        "S"  signed 16-bit int    (1 word)
        "D"  unsigned 32-bit int  (2 words, low-word first)
        "L"  signed 32-bit int    (2 words)
        "F"  IEEE 754 float32     (2 words)

    Use case: writing a signed 32-bit setpoint to DM200-DM201 from an
              asyncio-based HMI coroutine.
    """
    val_s = await read_typed(client, "DM100", "S")
    val_l = await read_typed(client, "DM200", "L")
    val_f = await read_typed(client, "DM300", "F")
    print(f"[read_typed] DM100(S)={val_s}  DM200(L)={val_l}  DM300(F)={val_f}")

    await write_typed(client, "DM100", "S", -500)
    await write_typed(client, "DM200", "L", 123456)
    await write_typed(client, "DM300", "F", 12.5)
    print("[write_typed] Wrote -500->DM100, 123456->DM200, 12.5->DM300")


async def demo_array_reads(client) -> None:
    """
    read_words / read_dwords - read contiguous word / dword blocks.

    read_words(client, device, count)  - returns list[int] (16-bit)
    read_dwords(client, device, count) - returns list[int] (32-bit, uint)

    Use case: reading a data table of 10 consecutive words in one
              Host Link command instead of 10 individual reads.
    """
    words = await read_words(client, "DM0", 10)
    print(f"[read_words]  DM0-DM9  = {words}")

    dwords = await read_dwords(client, "DM0", 4)
    print(f"[read_dwords] DM0-DM7 (as 4 x uint32) = {dwords}")


async def demo_bit_in_word(client) -> None:
    """
    write_bit_in_word - set/clear one bit inside a word device.

    Performs a read-modify-write: reads the word, flips bit_index, writes back.
    bit_index 0 = LSB, 15 = MSB.

    Use case: toggling an individual control flag in a shared status register
              without corrupting the other 15 bits - common when the PLC
              uses each bit for a different axis or function.
    """
    await write_bit_in_word(client, "DM50", bit_index=4, value=True)
    print("[write_bit_in_word] Set   bit 4 of DM50")
    await write_bit_in_word(client, "DM50", bit_index=4, value=False)
    print("[write_bit_in_word] Clear bit 4 of DM50")


async def demo_read_named(client) -> None:
    """
    read_named - read multiple devices with mixed types in one call.

    Address notation:
        "DM100"    unsigned 16-bit (default)
        "DM100:S"  signed 16-bit
        "DM100:D"  unsigned 32-bit (2 words)
        "DM100:L"  signed 32-bit
        "DM100.3"  bit 3 inside DM100 (bool); bit index is hexadecimal (0-F)
        "DM100.A"  bit 10 inside DM100 (A = 0x0A = 10)

    Use case: reading a heterogeneous parameter block in a single asyncio call -
              saves multiple round-trips when monitoring several device types.
    """
    snapshot = await read_named(
        client,
        [
            "DM100",
            "DM200:L",
            "DM50.3",
            "DM50.A",
        ],
    )
    for addr, value in snapshot.items():
        print(f"[read_named] {addr} = {value!r}")


async def demo_poll(client, count: int) -> None:
    """
    poll - async generator that yields a snapshot dict every *interval* seconds.

    Use case: asyncio-based monitoring loop that feeds PLC data to a
              dashboard or historian while the event loop handles other tasks.
    """
    print(f"\nPolling {count} snapshots:")
    i = 0
    async for snap in poll(client, ["DM100", "DM200:L", "DM50.3"], interval=1.0):
        print(f"  [{i + 1}] {snap}")
        i += 1
        if i >= count:
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> None:
    # 1. open_and_connect shortcut
    await demo_open_and_connect(args.host, args.port)

    # 2-6. connect once, run all demos
    client = await open_and_connect(args.host, port=args.port)
    try:
        await demo_typed_rw(client)
        await demo_array_reads(client)
        await demo_bit_in_word(client)
        await demo_read_named(client)
        await demo_poll(client, args.poll_count)
    finally:
        await client.close()

    print("Done.")


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except HostLinkConnectionError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except HostLinkProtocolError as e:
        print(f"Protocol error: {e}", file=sys.stderr)
        sys.exit(1)
    except HostLinkError as e:
        print(f"PLC error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
