import random
import sys
import time

from hostlink import HostLinkClient


def run_exhaustive_test(host, port, transport, start_addr=0, end_addr=500):
    print(f"=== EXHAUSTIVE ADDRESS CONSISTENCY TEST: DM{start_addr} to DM{end_addr} ===")

    with HostLinkClient(host, port=port, transport=transport) as plc:
        success_count = 0
        fail_count = 0
        start_time = time.perf_counter()

        # 1. Sweep Test (Single Word .U)
        print(f"\n[Phase 1] Sequential Sweep (DM{start_addr}-{end_addr})")
        for addr in range(start_addr, end_addr + 1):
            dev = f"DM{addr}.U"
            val = random.randint(0, 65535)

            try:
                plc.write(dev, val)
                read_back = plc.read(dev)

                if read_back == val:
                    success_count += 1
                else:
                    print(f"  FAILED at {dev}: Sent {val}, Got {read_back}")
                    fail_count += 1

                if addr % 100 == 0:
                    print(f"  Progress: {addr}/{end_addr}...")
            except Exception as e:
                print(f"  Error at {dev}: {e}")
                fail_count += 1

        # 2. Offset/Interference Test (32-bit vs 16-bit)
        print("\n[Phase 2] 32-bit Overlap/Interference Test")
        # Write 32-bit to DM100. Read DM100 and DM101 individually.
        # DM100.D (32bit) = DM100(Low 16) + DM101(High 16)
        test_val_32 = 0x1234ABCD
        try:
            plc.write("DM100.D", test_val_32)
            read_back_32 = plc.read("DM100.D")
            low_word = plc.read("DM100.H")  # Should be ABCD
            high_word = plc.read("DM101.H")  # Should be 1234

            print(f"  DM100.D Write: {hex(test_val_32)}")
            print(f"  DM100.D Read:  {hex(read_back_32)}")
            print(f"  DM100.H (Low): {hex(low_word)}")
            print(f"  DM101.H (High):{hex(high_word)}")

            if read_back_32 == test_val_32 and low_word == 0xABCD and high_word == 0x1234:
                print("  => 32-bit Mapping PASS")
                success_count += 1
            else:
                print("  => 32-bit Mapping FAIL")
                fail_count += 1
        except Exception as e:
            print(f"  Error in Phase 2: {e}")
            fail_count += 1

        # 3. Random Jumps
        print("\n[Phase 3] Random Jump Access (50 samples)")
        for _ in range(50):
            addr = random.randint(start_addr, end_addr)
            dev = f"DM{addr}.S"
            val = random.randint(-32768, 32767)
            try:
                plc.write(dev, val)
                if plc.read(dev) == val:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1

        end_time = time.perf_counter()
        total_time = end_time - start_time

        print(f"\n=== TEST COMPLETED IN {total_time:.2f}s ===")
        print(f"  TOTAL SUCCESS: {success_count}")
        print(f"  TOTAL FAILURES: {fail_count}")
        print(f"  THROUGHPUT: {success_count / total_time:.2f} ops/sec")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.250.100"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"
    run_exhaustive_test(host, port, transport)
