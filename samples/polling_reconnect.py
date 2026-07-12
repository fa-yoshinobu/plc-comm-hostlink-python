# ruff: noqa: E402
"""Read-only Host Link polling sample with automatic reconnect."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import HostLinkConnectionOptions, open_and_connect, read_typed
from hostlink.errors import HostLinkConnectionError, HostLinkError

RETRYABLE_ERRORS = (OSError, ConnectionError, TimeoutError, EOFError, asyncio.TimeoutError, HostLinkConnectionError)


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read one KEYENCE Host Link value forever and reconnect after transport loss."
    )
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--port", type=int, required=True, help="Required Host Link TCP port")
    parser.add_argument("--plc-profile", required=True, help="Canonical PLC profile, for example keyence:kv-8000")
    parser.add_argument("--device", default="DM100", help="Device to poll (default DM100)")
    parser.add_argument("--dtype", choices=("BIT", "U", "S", "D", "L", "F"), default="U", help="Read type")
    parser.add_argument("--interval", type=positive_float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--timeout", type=positive_float, default=3.0, help="Socket timeout in seconds")
    parser.add_argument("--initial-backoff", type=positive_float, default=1.0, help="First reconnect delay")
    parser.add_argument("--max-backoff", type=positive_float, default=30.0, help="Maximum reconnect delay")
    return parser.parse_args()


def log_state(state: str, message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"{timestamp} [{state}] {message}", flush=True)


def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, RETRYABLE_ERRORS)


async def close_quietly(client: Any | None) -> None:
    if client is None:
        return
    try:
        await client.close()
    except Exception:
        pass


async def poll_forever(args: argparse.Namespace) -> None:
    options = HostLinkConnectionOptions(
        host=args.host,
        plc_profile=args.plc_profile,
        port=args.port,
        transport="tcp",
        timeout=args.timeout,
    )

    client: Any | None = None
    backoff = args.initial_backoff
    connected_once = False

    try:
        while True:
            if client is None:
                log_state("reconnecting", f"tcp {args.host}:{args.port} profile={args.plc_profile}")
                try:
                    client = await open_and_connect(options)
                except Exception as exc:
                    if not is_retryable(exc):
                        raise
                    log_state("reconnecting", f"connect failed: {exc}; retry in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, args.max_backoff)
                    continue

                if connected_once:
                    log_state("recovered", f"{args.device}:{args.dtype}")
                else:
                    log_state("connected", f"{args.device}:{args.dtype}")
                    connected_once = True
                backoff = args.initial_backoff

            try:
                value = await read_typed(client, args.device, args.dtype)
                log_state("read", f"{args.device}:{args.dtype}={value!r}")
                await asyncio.sleep(args.interval)
            except Exception as exc:
                if not is_retryable(exc):
                    raise
                log_state("lost", str(exc) or exc.__class__.__name__)
                await close_quietly(client)
                client = None
                log_state("reconnecting", f"retry in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, args.max_backoff)
    finally:
        await close_quietly(client)


def main() -> int:
    args = parse_args()
    if args.max_backoff < args.initial_backoff:
        raise SystemExit("--max-backoff must be greater than or equal to --initial-backoff")
    try:
        asyncio.run(poll_forever(args))
    except KeyboardInterrupt:
        log_state("closed", "interrupted by Ctrl+C")
        return 0
    except HostLinkError as exc:
        log_state("lost", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
