# ruff: noqa: E402
"""
KEYENCE Host Link - High-Level Synchronous API Sample
=====================================================
Demonstrates all high-level methods of HostLinkClient (synchronous).

Usage
-----
    python samples/high_level_sync.py --host 192.168.250.100 [--port 8501]
    python samples/high_level_sync.py --host 192.168.250.100 --port 8501 --transport udp

Default port: 8501  (KV Ethernet module default)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hostlink import HostLinkClient
from hostlink.errors import HostLinkConnectionError, HostLinkError, HostLinkProtocolError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="KEYENCE Host Link synchronous high-level API sample",
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
        "--transport",
        choices=("tcp", "udp"),
        default="tcp",
        help="Transport protocol (default tcp)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Socket timeout in seconds (default 3.0)",
    )
    p.add_argument(
        "--poll-count",
        type=int,
        default=3,
        help="Number of manual poll iterations (default 3)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    # HostLinkClient options:
    #   host              - KV PLC IP / hostname
    #   port              - KV Ethernet module port; set in KV Studio
    #                       (default 8501)
    #   transport         - "tcp" (default) or "udp"
    #   timeout           - socket timeout; increase on slow or wireless links
    #   append_lf_on_send - some KV firmware variants require an extra LF
    #                       byte at the end of each command frame; set True
    #                       if you see HostLinkProtocolError on well-formed
    #                       commands
    #   trace_hook        - optional callback(HostLinkTraceFrame) for raw
    #                       frame logging; useful for debugging
    with HostLinkClient(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        append_lf_on_send=False,
    ) as plc:
        print(f"Connected to {args.host}:{args.port} via {args.transport}")

        # ---------------------------------------------------------------
        # 1. read / write - basic single-device access
        #
        # plc.read(device)               - returns raw unsigned 16-bit int
        # plc.read(device, data_format)  - converts using the specified format
        #
        # data_format codes (pass as second argument or embed in address):
        #   ".S"  signed 16-bit  (default for DM/EM/FM/W when implicit)
        #   ".D"  unsigned 32-bit (2 consecutive words)
        #   ".L"  signed 32-bit
        #   ".F"  IEEE-754 float32 (2 consecutive words)
        #   ".H"  hexadecimal string
        #
        # Use case: reading and writing a setpoint stored in DM100.
        # ---------------------------------------------------------------
        raw = plc.read("DM100")
        print(f"[read]       DM100 (raw)  = {raw}")

        signed = plc.read("DM100", data_format=".S")
        print(f"[read .S]    DM100 signed = {signed}")

        float_val = plc.read("DM200", data_format=".F")
        print(f"[read .F]    DM200 float  = {float_val}")

        plc.write("DM100", 1234)
        print("[write]      Wrote 1234 -> DM100")

        plc.write("DM200", "3.14", data_format=".F")
        print("[write .F]   Wrote 3.14  -> DM200")

        # ---------------------------------------------------------------
        # 2. read_consecutive / write_consecutive
        #
        # Read or write a contiguous block of word devices.
        # count - number of consecutive words starting at the given address.
        #
        # Use case: reading a parameter table stored in DM0-DM9 in a single
        #           round-trip instead of 10 separate read commands.
        # ---------------------------------------------------------------
        words = plc.read_consecutive("DM0", 10)
        print(f"[read_consecutive]  DM0-DM9  = {words}")

        plc.write_consecutive("DM0", [i * 10 for i in range(10)])
        print("[write_consecutive] Wrote 0, 10, 20, ..., 90 -> DM0-DM9")

        # ---------------------------------------------------------------
        # 3. register_monitor_words / read_monitor_words
        #
        # Register a list of arbitrary (non-consecutive) devices once,
        # then poll all of them in a single round-trip with read_monitor_words.
        #
        # register_monitor_words(devices) - tells the KV to cache the device
        #     list; only needs to be called once per connection.
        # read_monitor_words()            - reads all registered devices in
        #     one command; much faster than individual reads when devices
        #     are scattered across different areas.
        #
        # Use case: monitoring a mix of data registers, bit relays, and timer
        #           current values that are spread across multiple device areas
        #           and need frequent, low-latency updates.
        # ---------------------------------------------------------------
        plc.register_monitor_words("DM100", "DM200", "R0", "R10")
        print("[register_monitor_words] Registered DM100, DM200, R0, R10")

        for i in range(args.poll_count):
            mon = plc.read_monitor_words()
            print(f"[read_monitor_words] poll {i + 1}: {mon}")

        # ---------------------------------------------------------------
        # 4. query_model / confirm_operating_mode
        #
        # query_model()            - returns ModelInfo(code, model)
        #     code  - raw model code string returned by the KV
        #     model - human-readable model name (e.g. "KV-7500"), or None
        #             if the code is not in the built-in lookup table
        #
        # confirm_operating_mode() - returns 0 (PROGRAM) or 1 (RUN)
        #
        # Use case: safety check before sending write commands -
        #           refuse to write if the PLC is in RUN mode.
        # ---------------------------------------------------------------
        model = plc.query_model()
        print(f"[query_model]            code={model.code}  model={model.model}")

        mode = plc.confirm_operating_mode()
        print(f"[confirm_operating_mode] mode={'RUN' if mode == 1 else 'PROGRAM'}")

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except HostLinkConnectionError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except HostLinkProtocolError as e:
        print(f"Protocol error: {e}", file=sys.stderr)
        sys.exit(1)
    except HostLinkError as e:
        print(f"PLC error: code={e.code}  response={e.response}", file=sys.stderr)
        sys.exit(1)
