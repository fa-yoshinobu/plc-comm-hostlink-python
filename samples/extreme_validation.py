import sys
import random
import time
import asyncio
from hostlink import AsyncHostLinkClient
from hostlink.errors import HostLinkError


async def run_extreme_test(host, port, transport):
    print(f"=== EXTREME VALIDATION ON {host}:{port} ===")

    async with AsyncHostLinkClient(host, port=port, transport=transport) as plc:
        start_time = time.perf_counter()
        success = 0

        # 1. Bit-by-Bit Sweep (MR0 - MR500)
        # Using ST/RS for bit operations instead of WR
        print("\n[Phase 1] Bit-by-Bit Sweep using ST/RS (MR0-MR500)")
        for i in range(501):
            dev = f"MR{i}"
            val = i % 2
            try:
                if val == 1:
                    await plc.forced_set(dev)
                else:
                    await plc.forced_reset(dev)

                res = await plc.read(dev)
                if res == val:
                    success += 1
                else:
                    print(f"  FAIL at {dev}: Sent {val}, Got {res}")
            except HostLinkError as e:
                print(f"  Error at {dev}: {e}")

            if i % 100 == 0:
                print(f"  Progress: {i}/500...")

        # 2. Maximum Bulk Sweep (Consecutive 1000 units)
        print("\n[Phase 2] Maximum Bulk Sweep (1000 units)")
        bulk_size = 1000
        # Word Bulk (DM) - This should work fine with WR/RD
        for offset in range(3):
            start_dev = f"DM{offset * 1000}"  # Test different ranges
            write_vals = [random.randint(0, 65535) for _ in range(bulk_size)]
            try:
                await plc.write_consecutive(start_dev, write_vals)
                read_vals = await plc.read_consecutive(start_dev, bulk_size)
                if list(write_vals) == list(read_vals):
                    print(f"  Bulk Word DM (Start:{start_dev}, Size:{bulk_size}): PASS")
                    success += 1
                else:
                    print(f"  Bulk Word DM (Start:{start_dev}): FAIL (Mismatch)")
            except HostLinkError as e:
                print(f"  Bulk Word DM Error: {e}")

        # 3. High-Speed Async Cross-Talk Test
        print("\n[Phase 3] Async Cross-Talk (Concurrent DM/MR access)")

        async def word_task():
            for i in range(50):
                await plc.write(f"DM{i}", i)
                await plc.read(f"DM{i}")
            return True

        async def bit_task():
            for i in range(50):
                # For bits, use ST/RS
                if i % 2 == 1:
                    await plc.forced_set(f"MR{i}")
                else:
                    await plc.forced_reset(f"MR{i}")
                await plc.read(f"MR{i}")
            return True

        await asyncio.gather(word_task(), bit_task(), word_task(), bit_task())
        print("  Async Cross-Talk: PASS")
        success += 1

        total_time = time.perf_counter() - start_time
        print(f"\n=== EXTREME TEST COMPLETED IN {total_time:.2f}s ===")
        print(f"  TOTAL VALIDATED STEPS: {success}")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.250.101"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"
    asyncio.run(run_extreme_test(host, port, transport))
