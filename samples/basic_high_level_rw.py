# ruff: noqa: E402
"""Basic high-level typed read/write example for KEYENCE Host Link."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import open_and_connect, read_typed, write_typed
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Basic Host Link high-level read/write example")
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--port", type=int, default=8501, help="Host Link port (default 8501)")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    async with await open_and_connect(args.host, args.port) as client:
        dm0 = await read_typed(client, "DM0", "U")
        dm1 = await read_typed(client, "DM1", "S")
        dm2 = await read_typed(client, "DM2", "D")
        dm4 = await read_typed(client, "DM4", "F")

        print(f"DM0(U) = {dm0}")
        print(f"DM1(S) = {dm1}")
        print(f"DM2(D) = {dm2}")
        print(f"DM4(F) = {dm4}")

        await write_typed(client, "DM100", "U", dm0)
        await write_typed(client, "DM101", "S", dm1)
        await write_typed(client, "DM102", "D", dm2)
        await write_typed(client, "DM104", "F", dm4)
        print("Mirrored source values into DM100/DM101/DM102/DM104")


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
