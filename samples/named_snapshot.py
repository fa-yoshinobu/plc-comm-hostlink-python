# ruff: noqa: E402
"""Mixed snapshot example using the high-level read_named helper."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import HostLinkConnectionOptions, open_and_connect, read_named
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Host Link mixed snapshot example")
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--plc-profile", required=True, help="Canonical PLC profile, for example keyence:kv-8000")
    parser.add_argument("--port", type=int, default=8501, help="Host Link port (default 8501)")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    options = HostLinkConnectionOptions(host=args.host, plc_profile=args.plc_profile, port=args.port)
    # Connect to the command-line host/port; default examples use 192.168.250.100:8501.
    async with await open_and_connect(options) as client:
        # Read a mixed snapshot containing word values and bit-in-word values.
        # See docsrc/user/GOTCHAS.md before adapting bit notation for X/Y or relay devices.
        snapshot = await read_named(
            client,
            ["DM0", "DM1:S", "DM2:D", "DM4:F", "DM10.0", "DM10.A"],
        )
        for address, value in snapshot.items():
            print(f"{address} = {value}")


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
