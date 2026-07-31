# ruff: noqa: E402
"""Basic synchronous Host Link communication check.

The default run is read-only. ``--write-test-device`` enables one random
signed-word write on a controlled test PLC and restores the original value.
Do not use the write option on production equipment.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import HostLinkClient
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive finite number")
    return parsed


def port_number(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("port must be in the range 1..65535")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Basic synchronous KEYENCE Host Link communication check")
    parser.add_argument("--host", required=True, help="PLC IP address or hostname")
    parser.add_argument("--plc-profile", required=True, help="Canonical profile, for example keyence:kv-8000")
    parser.add_argument("--port", type=port_number, required=True, help="Configured Host Link port")
    parser.add_argument("--transport", choices=("tcp", "udp"), required=True, help="Configured transport")
    parser.add_argument("--timeout", type=positive_float, default=3.0, help="Timeout in seconds")
    parser.add_argument("--read-device", default="DM0", help="Signed-word device used for the read-only check")
    parser.add_argument(
        "--write-test-device",
        help="Controlled-test signed-word device to write once and restore; omitted means read-only",
    )
    return parser.parse_args()


def different_random_i16(original: int) -> int:
    rng = random.SystemRandom()
    candidate = rng.randint(-0x8000, 0x7FFF)
    while candidate == original:
        candidate = rng.randint(-0x8000, 0x7FFF)
    return candidate


def run(args: argparse.Namespace) -> None:
    with HostLinkClient(
        args.host,
        plc_profile=args.plc_profile,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
    ) as plc:
        model_info = plc.query_model()
        print(f"PLC model code: {model_info.code}")
        if model_info.model:
            print(f"Resolved model name: {model_info.model}")

        mode = plc.confirm_operating_mode()
        print(f"Operating mode: {'RUN' if mode == 1 else 'PROGRAM'}")

        read_value = plc.read(args.read_device, data_format=".S")
        print(f"{args.read_device}.S = {read_value}")

        if args.write_test_device is None:
            print("Read-only check complete; no write was requested.")
            return

        original = plc.read(args.write_test_device, data_format=".S")
        if type(original) is not int:
            raise HostLinkProtocolError("Write-test read did not return one signed integer")
        test_value = different_random_i16(original)
        print(f"Controlled write test: {args.write_test_device}.S <- {test_value}")
        try:
            plc.write(args.write_test_device, test_value, data_format=".S")
            observed = plc.read(args.write_test_device, data_format=".S")
            if observed != test_value:
                raise HostLinkProtocolError(
                    f"Write-test readback mismatch: expected {test_value}, received {observed!r}"
                )
            print("Controlled write test passed.")
        finally:
            plc.write(args.write_test_device, original, data_format=".S")
            print(f"Restored {args.write_test_device}.S to {original}.")


def main() -> int:
    args = parse_args()
    try:
        run(args)
    except HostLinkConnectionError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1
    except HostLinkProtocolError as exc:
        print(f"Protocol error: {exc}", file=sys.stderr)
        return 1
    except HostLinkError as exc:
        print(f"PLC error: code={exc.code} response={exc.response}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
