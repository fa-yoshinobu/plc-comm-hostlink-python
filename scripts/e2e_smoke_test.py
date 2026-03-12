from __future__ import annotations

import argparse
import sys
from typing import Any

from hostlink import HostLinkClient
from hostlink.errors import HostLinkError


def _print_ok(message: str) -> None:
    print(f"[OK] {message}")


def _print_ng(message: str) -> None:
    print(f"[NG] {message}")


def _as_scalar(value: Any) -> int | str:
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError(f"Expected scalar response, got list: {value}")
        return value[0]
    if isinstance(value, (int, str)):
        return value
    raise ValueError(f"Unsupported value type: {type(value)!r}")


def run(args: argparse.Namespace) -> int:
    failures = 0

    try:
        with HostLinkClient(
            args.host,
            port=args.port,
            transport=args.transport,
            timeout=args.timeout,
            append_lf_on_send=args.append_lf,
        ) as plc:
            _print_ok(f"Connected to {args.host}:{args.port} ({args.transport.upper()})")

            model = plc.query_model()
            _print_ok(f"?K model_code={model.code} model={model.model}")

            mode = plc.confirm_operating_mode()
            _print_ok(f"?M operating_mode={mode}")

            err = plc.check_error_no()
            _print_ok(f"?E error_no={err}")

            one = plc.read(args.read_device, data_format=args.read_format)
            _print_ok(f"RD {args.read_device}{args.read_format or ''} => {one}")

            many = plc.read_consecutive(args.read_device, args.read_count, data_format=args.read_format)
            _print_ok(f"RDS {args.read_device}{args.read_format or ''} {args.read_count} => {many}")

            if args.allow_write:
                original = _as_scalar(plc.read(args.write_device, data_format=args.write_format))
                _print_ok(f"WR target original={original}")

                plc.write(args.write_device, args.write_value, data_format=args.write_format)
                updated = _as_scalar(plc.read(args.write_device, data_format=args.write_format))
                _print_ok(f"WR wrote={args.write_value} readback={updated}")

                plc.write(args.write_device, original, data_format=args.write_format)
                restored = _as_scalar(plc.read(args.write_device, data_format=args.write_format))
                _print_ok(f"WR restored={restored}")
            else:
                print("[SKIP] Write test disabled. Use --allow-write to enable.")

            if args.test_error_response:
                try:
                    plc.send_raw("INVALID")
                    _print_ng("Expected E1 for invalid command, but command succeeded")
                    failures += 1
                except HostLinkError as exc:
                    if exc.code == "E1":
                        _print_ok("Invalid command returned E1 as expected")
                    else:
                        _print_ng(f"Invalid command returned unexpected code: {exc.code}")
                        failures += 1
            else:
                print("[SKIP] Error-response test disabled.")

    except Exception as exc:  # noqa: BLE001
        _print_ng(f"Unhandled exception: {exc}")
        return 1

    if failures:
        _print_ng(f"Finished with {failures} failure(s)")
        return 1
    _print_ok("Smoke test completed successfully")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KEYENCE Host Link E2E smoke test")
    parser.add_argument("--host", required=True, help="PLC IP/hostname")
    parser.add_argument("--port", type=int, default=8501, help="Host Link port (default: 8501)")
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp", help="Transport (default: tcp)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket timeout seconds (default: 3.0)")
    parser.add_argument("--append-lf", action="store_true", help="Send CRLF instead of CR")

    parser.add_argument("--read-device", default="DM0", help="Device for read checks (default: DM0)")
    parser.add_argument(
        "--read-format",
        default=".U",
        choices=("", ".U", ".S", ".D", ".L", ".H"),
        help="Data format for read checks (default: .U)",
    )
    parser.add_argument("--read-count", type=int, default=2, help="Count for consecutive read check")

    parser.add_argument("--allow-write", action="store_true", help="Enable write/restore roundtrip test")
    parser.add_argument("--write-device", default="DM1", help="Device for write test (default: DM1)")
    parser.add_argument(
        "--write-format",
        default=".U",
        choices=("", ".U", ".S", ".D", ".L", ".H"),
        help="Data format for write test (default: .U)",
    )
    parser.add_argument("--write-value", type=int, default=1234, help="Value used in write roundtrip test")

    parser.add_argument(
        "--test-error-response",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable invalid-command test expecting E1 (default: enabled)",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(run(args))

