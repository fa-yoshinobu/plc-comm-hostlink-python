# ruff: noqa: E402
"""Polling example using the high-level poll helper."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import HostLinkConnectionOptions, open_and_connect, poll
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Host Link polling example")
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--port", type=int, default=8501, help="Host Link port (default 8501)")
    parser.add_argument("--poll-count", type=int, default=5, help="Number of snapshots to print (default 5)")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default 1.0)")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    options = HostLinkConnectionOptions(host=args.host, port=args.port)
    async with await open_and_connect(options) as client:
        seen = 0
        async for snapshot in poll(client, ["DM0", "DM1:S", "DM4:F", "DM10.0"], interval=args.interval):
            seen += 1
            print(f"[{seen}] {snapshot}")
            if seen >= args.poll_count:
                break


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
