# ruff: noqa: E402
"""
KEYENCE Host Link - High-Level Asynchronous API Sample
======================================================
Demonstrates the core high-level *async* utility helpers shipped with the
hostlink package (HostLinkConnectionOptions, open_and_connect,
parse_address, format_address, normalize_address, read_typed, write_typed, read_named,
read_words_single_request, read_dwords_single_request,
write_bit_in_word, poll).

Usage
-----
    python samples/high_level_async.py --host 192.168.250.100 --plc-profile keyence:kv-8000 [--port 8501]
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
    HostLinkConnectionOptions,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    poll,
    read_dwords_single_request,
    read_named,
    read_typed,
    read_words_single_request,
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
    p.add_argument("--plc-profile", required=True, help="Canonical PLC profile, for example keyence:kv-8000")
    p.add_argument(
        "--port",
        type=int,
        required=True,
        help="Required Host Link TCP port",
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


async def demo_open_and_connect(host: str, port: int, plc_profile: str) -> None:
    """
    open_and_connect - create and open the connected client used by the helper API.

    Parameters:
        host  - KV PLC IP / hostname
        port  - KV Ethernet port (default 8501 inside open_and_connect)

    Returns a connected client object for the helper functions below.
    """
    # Connect only to the explicitly selected endpoint.
    client = await open_and_connect(
        HostLinkConnectionOptions(host=host, plc_profile=plc_profile, port=port, transport="tcp")
    )
    print(f"[open_and_connect] Connected to {host}:{port}")
    await client.close()


def demo_normalize_address() -> None:
    # Normalize helper-layer addresses before storing or displaying them.
    print(f"[normalize_address] dm100 -> {normalize_address('dm100')}")
    print(f"[normalize_address] dm100.a -> {normalize_address('dm100.a')}")
    parsed = parse_address("dm100.a")
    print(f"[parse_address] dm100.a -> base={parsed.base_device} bit={parsed.bit_index}")
    print(f"[format_address] parsed -> {format_address(parsed)}")


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
    # Read typed values from individual devices.
    val_s = await read_typed(client, "DM100", "S")
    val_l = await read_typed(client, "DM200", "L")
    val_f = await read_typed(client, "DM300", "F")
    print(f"[read_typed] DM100(S)={val_s}  DM200(L)={val_l}  DM300(F)={val_f}")

    original_dm100 = await read_typed(client, "DM100", "S")
    original_dm200 = await read_typed(client, "DM200", "L")
    original_dm300 = await read_typed(client, "DM300", "F")
    # Write only to DM test addresses that are safe in your PLC program.
    try:
        await write_typed(client, "DM100", "S", -500)
        await write_typed(client, "DM200", "L", 123456)
        await write_typed(client, "DM300", "F", 12.5)
        print("[write_typed] Wrote -500->DM100, 123456->DM200, 12.5->DM300")
    finally:
        await write_typed(client, "DM100", "S", original_dm100)
        await write_typed(client, "DM200", "L", original_dm200)
        await write_typed(client, "DM300", "F", original_dm300)
        print("[write_typed] Restored DM100/DM200/DM300")


async def demo_array_reads(client) -> None:
    """
    Explicit contiguous helpers.

    `*_single_request` keeps one logical read on one PLC request. Larger reads
    must be divided deliberately by the application so timing boundaries are visible.

    Use case: reading a data table of 10 consecutive words in one
              Host Link command instead of 10 individual reads.
    """
    # Read consecutive 16-bit words in one PLC request.
    words = await read_words_single_request(client, "DM0", 10)
    print(f"[read_words_single_request]  DM0-DM9  = {words}")

    # Read consecutive 32-bit values in one PLC request.
    dwords = await read_dwords_single_request(client, "DM0", 4)
    print(f"[read_dwords_single_request] DM0-DM7 (as 4 x uint32) = {dwords}")


async def demo_bit_in_word(client) -> None:
    """
    write_bit_in_word - set/clear one bit inside a word device.

    Performs a read-modify-write: reads the word, flips bit_index, writes back.
    bit_index 0 = LSB, 15 = MSB.

    Use case: toggling an individual control flag in a shared status register
              without corrupting the other 15 bits - common when the PLC
              uses each bit for a different axis or function.
    """
    # See docsrc/user/GOTCHAS.md before adapting bit notation for X/Y or relay devices.
    original = await read_named(client, ["DM50.4"])
    original_bit4 = bool(original["DM50.4"])
    try:
        await write_bit_in_word(client, "DM50", bit_index=4, value=True)
        print("[write_bit_in_word] Set   bit 4 of DM50")
        await write_bit_in_word(client, "DM50", bit_index=4, value=False)
        print("[write_bit_in_word] Clear bit 4 of DM50")
    finally:
        await write_bit_in_word(client, "DM50", bit_index=4, value=original_bit4)
        print("[write_bit_in_word] Restored bit 4 of DM50")


async def demo_read_named(client) -> None:
    """
    read_named - read multiple devices with mixed types in one call.

    Address notation:
        "DM100:U"  unsigned 16-bit
        "DM100:S"  signed 16-bit
        "DM100:D"  unsigned 32-bit (2 words)
        "DM100:L"  signed 32-bit
        "DM100.3"  bit 3 inside DM100 (bool); bit index is hexadecimal (0-F)
        "DM100.A"  bit 10 inside DM100 (A = 0x0A = 10)

    Use case: reading a heterogeneous parameter block in a single asyncio call -
              saves multiple round-trips when monitoring several device types.
    """
    # Read a named mixed-type snapshot.
    snapshot = await read_named(
        client,
        [
            "DM100:U",
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
    # Poll a repeated named snapshot until this sample has printed enough rows.
    async for snap in poll(client, ["DM100:U", "DM200:L", "DM50.3"], interval=1.0):
        print(f"  [{i + 1}] {snap}")
        i += 1
        if i >= count:
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> None:
    demo_normalize_address()

    # 1. open_and_connect shortcut
    await demo_open_and_connect(args.host, args.port, args.plc_profile)

    # 2-6. connect once, run all demos
    # Reuse one connection for the remaining helper demos.
    client = await open_and_connect(
        HostLinkConnectionOptions(host=args.host, plc_profile=args.plc_profile, port=args.port, transport="tcp")
    )
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
