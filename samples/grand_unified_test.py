import sys
import asyncio
import time
from hostlink import HostLinkClient, AsyncHostLinkClient
from hostlink.errors import HostLinkError


async def grand_unified_test(host, port, transport):
    print(f"=== GRAND UNIFIED STRESS TEST ON {host}:{port} ===")
    start_time_all = time.perf_counter()

    # --- Phase 1: Reconnection Stress ---
    print("\n[Phase 1] Reconnection Stress (50 cycles)")
    reconn_start = time.perf_counter()
    for i in range(50):
        try:
            client = HostLinkClient(
                host, port=port, transport=transport, auto_connect=True
            )
            client.query_model()
            client.close()
            if i % 10 == 0:
                print(f"  Cycle {i}/50...")
        except Exception as e:
            print(f"  Connection failed at cycle {i}: {e}")
    print(f"  Phase 1 Time: {time.perf_counter() - reconn_start:.2f}s")

    # --- Phase 2: System Control & Mode Stress ---
    print("\n[Phase 2] System Control & Mode Toggle")
    async with AsyncHostLinkClient(host, port=port, transport=transport) as plc:
        for i in range(5):
            await plc.set_time()  # Clock Sync
            await plc.change_mode("PROGRAM")
            await plc.change_mode("RUN")
            if i % 2 == 0:
                print(f"  Mode toggle cycle {i}...")
        print("  Phase 2 (System/Mode): OK")

        # --- Phase 3: Monitoring Limits (120 Devices) ---
        print("\n[Phase 3] Max Monitoring Test (120 devices)")
        # Register 120 DM devices
        monitor_devs = [f"DM{i}.U" for i in range(120)]
        await plc.register_monitor_words(*monitor_devs)
        print("  Registered 120 devices for monitoring.")

        mon_start = time.perf_counter()
        for i in range(100):
            res = await plc.read_monitor_words()
            if len(res) != 120:
                print(f"  MONITOR DATA ERROR: Expected 120, got {len(res)}")
        print(f"  Phase 3 (100 Monitor Reads): {time.perf_counter() - mon_start:.2f}s")

        # --- Phase 4: Data Boundary Verification ---
        print("\n[Phase 4] Data Boundary Verification (All Formats)")
        boundaries = [
            ("DM0", ".U", [0, 65535, 32768]),
            ("DM2", ".S", [0, -32768, 32767]),
            ("DM4", ".D", [0, 4294967295, 2147483648]),
            ("DM6", ".L", [0, -2147483648, 2147483647]),
            ("DM10", ".H", [0x0000, 0xFFFF, 0x1234]),
        ]
        for dev, fmt, vals in boundaries:
            for v in vals:
                await plc.write(dev, v, data_format=fmt)
                res = await plc.read(dev, data_format=fmt)
                if res != v:
                    print(f"  BOUNDARY FAIL: {dev}{fmt} Sent {v}, Got {res}")
                else:
                    print(f"  BOUNDARY PASS: {dev}{fmt} value {v}")

        # --- Phase 5: Expansion Unit Sweep ---
        print("\n[Phase 5] Expansion Unit Sweep (Unit 0, BFM 0-100)")
        unit_no = 0
        success_urd = 0
        for addr in range(0, 101):
            try:
                # Read 1 word from Buffer Memory
                res = await plc.read_expansion_unit_buffer(unit_no, addr, 1)
                success_urd += 1
            except HostLinkError:
                pass  # Unit might not exist at this addr
        print(f"  Expansion Unit Read: {success_urd}/101 successful attempts.")

    total_time = time.perf_counter() - start_time_all
    print(f"\n=== GRAND UNIFIED TEST COMPLETED IN {total_time:.2f}s ===")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.250.101"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"
    asyncio.run(grand_unified_test(host, port, transport))
