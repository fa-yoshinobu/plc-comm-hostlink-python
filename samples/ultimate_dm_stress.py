import sys
import random
import time
from hostlink import HostLinkClient


def run_ultimate_test(host, port, transport):
    start_addr = 0
    end_addr = 5000
    print(f"=== ULTIMATE DM CONSISTENCY SWEEP: DM{start_addr} to DM{end_addr} ===")

    with HostLinkClient(host, port=port, transport=transport) as plc:
        success = 0
        fail = 0
        start_time = time.perf_counter()

        # Phase 1: Full Sequential Sweep (16-bit)
        print(f"\n[Phase 1] Sequential Sweep DM{start_addr}-{end_addr} (16-bit .U)")
        for addr in range(start_addr, end_addr + 1):
            val = random.randint(0, 65535)
            dev = f"DM{addr}"
            try:
                plc.write(dev, val)
                res = plc.read(dev)
                if res == val:
                    success += 1
                else:
                    print(f"  MISMATCH at {dev}: Sent {val}, Got {res}")
                    fail += 1
            except Exception as e:
                print(f"  ERROR at {dev}: {e}")
                fail += 1

            if addr % 1000 == 0:
                print(f"  Progress: {addr}/{end_addr}...")

        # Phase 2: 32-bit Alignment Sweep (DM0-DM500)
        # Checking if odd/even boundaries cause any issues
        print("\n[Phase 2] 32-bit Alignment Sweep (DM0-DM500)")
        for addr in range(0, 501):
            val = random.randint(0, 0xFFFFFFFF)
            dev = f"DM{addr}.D"
            try:
                plc.write(dev, val)
                res = plc.read(dev)
                if res == val:
                    success += 1
                else:
                    print(f"  MISMATCH at {dev}: Sent {val}, Got {res}")
                    fail += 1
            except Exception as e:
                print(f"  ERROR at {dev}: {e}")
                fail += 1
            if addr % 100 == 0:
                print(f"  Progress: {addr}/500...")

        # Phase 3: Rolling Bulk Test (Checking packet boundaries)
        print("\n[Phase 3] Rolling Bulk Test (100 words x 50 offsets)")
        bulk_size = 100
        for offset in range(0, 51):
            start_dev = f"DM{offset}"
            write_vals = [random.randint(0, 65535) for _ in range(bulk_size)]
            try:
                plc.write_consecutive(start_dev, write_vals)
                read_vals = plc.read_consecutive(start_dev, bulk_size)
                if list(write_vals) == list(read_vals):
                    success += 1
                else:
                    print(f"  BULK FAIL at {start_dev}")
                    fail += 1
            except Exception as e:
                print(f"  BULK ERROR at {start_dev}: {e}")
                fail += 1

        total_time = time.perf_counter() - start_time
        print(f"\n=== ULTIMATE TEST COMPLETED IN {total_time:.2f}s ===")
        print(f"  TOTAL SUCCESS: {success}")
        print(f"  TOTAL FAILURES: {fail}")
        print(f"  THROUGHPUT: {(success + fail) / total_time:.2f} ops/sec")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.250.101"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"
    run_ultimate_test(host, port, transport)
