"""
Basic Communication Test for KEYENCE KV Host Link.
Usage: python basic_test.py <host> [port] [transport: tcp/udp]
"""

import sys
from hostlink import HostLinkClient
from hostlink.errors import HostLinkError, HostLinkConnectionError


def main():
    if len(sys.argv) < 2:
        print("Usage: python basic_test.py <host> [port] [transport: tcp/udp]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"

    print(f"Connecting to {host}:{port} via {transport}...")

    try:
        with HostLinkClient(host, port=port, transport=transport) as plc:
            # 1. Query Model (?K)
            model_info = plc.query_model()
            print(f"PLC Model Code: {model_info.code}")
            if model_info.model:
                print(f"Resolved Model Name: {model_info.model}")

            # 2. Check Operating Mode (?M)
            mode = plc.confirm_operating_mode()
            mode_str = "RUN" if mode == 1 else "PROGRAM"
            print(f"Current Operating Mode: {mode_str}")

            # 3. Simple Read/Write Test (DM0.S - Signed Word)
            print("Reading DM0.S...")
            val = plc.read("DM0.S")
            print(f"Current DM0 value: {val}")

            new_val = (val + 1) % 32768 if isinstance(val, int) else 1
            print(f"Writing {new_val} to DM0.S...")
            plc.write("DM0.S", new_val)

            val_after = plc.read("DM0.S")
            print(f"Verified DM0 value: {val_after}")

            if val_after == new_val:
                print("--- SUCCESS: Communication test completed! ---")
            else:
                print("--- ERROR: Value mismatch in verification ---")

    except HostLinkConnectionError as e:
        print(f"Connection error: {e}")
    except HostLinkError as e:
        print(f"PLC returned error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
