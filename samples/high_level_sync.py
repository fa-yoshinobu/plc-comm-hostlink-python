# ruff: noqa: E402
"""
KEYENCE Host Link - High-Level CLI Sample
=========================================
Synchronous command-line entrypoint that uses the recommended high-level
helper API internally via asyncio.run().

Usage
-----
    python samples/high_level_sync.py --host 192.168.250.100 [--port 8501]
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
    normalize_address,
    open_and_connect,
    poll,
    read_dwords_chunked,
    read_dwords_single_request,
    read_named,
    read_typed,
    read_words_chunked,
    read_words_single_request,
    write_bit_in_word,
    write_typed,
)
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KEYENCE Host Link synchronous CLI using the high-level helper API",
    )
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--port", type=int, default=8501, help="Host Link port (default 8501)")
    parser.add_argument(
        "--transport",
        choices=("tcp", "udp"),
        default="tcp",
        help="Transport protocol (default tcp)",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds (default 3.0)")
    parser.add_argument("--poll-count", type=int, default=3, help="Number of poll snapshots (default 3)")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    print(f"[normalize_address] dm20 -> {normalize_address('dm20')}")
    print(f"[normalize_address] dm20.a -> {normalize_address('dm20.a')}")

    async with await open_and_connect(
        HostLinkConnectionOptions(
            host=args.host,
            port=args.port,
            transport=args.transport,
            timeout=args.timeout,
        )
    ) as client:
        print(f"Connected to {args.host}:{args.port} via {args.transport}")

        dm0 = await read_typed(client, "DM0", "U")
        dm1 = await read_typed(client, "DM1", "S")
        dm2 = await read_typed(client, "DM2", "D")
        dm4 = await read_typed(client, "DM4", "F")
        print(f"[read_typed] DM0(U)={dm0} DM1(S)={dm1} DM2(D)={dm2} DM4(F)={dm4}")

        await write_typed(client, "DM10", "U", dm0)
        await write_typed(client, "DM11", "S", dm1)
        await write_typed(client, "DM12", "D", dm2)
        await write_typed(client, "DM14", "F", dm4)
        print("[write_typed] Mirrored DM0/DM1/DM2/DM4 into DM10/DM11/DM12/DM14")

        words = await read_words_single_request(client, "DM20", 6)
        dwords = await read_dwords_single_request(client, "DM30", 3)
        print(f"[read_words_single_request] DM20-DM25 = {words}")
        print(f"[read_dwords_single_request] DM30-DM35 = {dwords}")

        large_words = await read_words_chunked(client, "DM1000", 1000)
        large_dwords = await read_dwords_chunked(client, "DM2000", 120)
        print(f"[read_words_chunked] DM1000-DM1999 = {len(large_words)} words")
        print(f"[read_dwords_chunked] DM2000-DM2239 = {len(large_dwords)} dwords")

        await write_bit_in_word(client, "DM50", bit_index=0, value=True)
        await write_bit_in_word(client, "DM50", bit_index=3, value=False)
        print("[write_bit_in_word] Updated DM50 bit0=True bit3=False")

        snapshot = await read_named(
            client,
            ["DM10", "DM11:S", "DM12:D", "DM14:F", "DM50.0", "DM50.3"],
        )
        print(f"[read_named] {snapshot}")

        print(f"[poll] Capturing {args.poll_count} snapshots")
        seen = 0
        async for snap in poll(client, ["DM10", "DM11:S", "DM14:F", "DM50.0"], interval=1.0):
            seen += 1
            print(f"  [{seen}] {snap}")
            if seen >= args.poll_count:
                break

        print("Done.")


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except HostLinkConnectionError as ex:
        print(f"Connection error: {ex}", file=sys.stderr)
        sys.exit(1)
    except HostLinkProtocolError as ex:
        print(f"Protocol error: {ex}", file=sys.stderr)
        sys.exit(1)
    except HostLinkError as ex:
        print(f"PLC error: code={ex.code} response={ex.response}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
