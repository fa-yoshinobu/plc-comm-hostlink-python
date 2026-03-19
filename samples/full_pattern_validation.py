import sys
import asyncio
from hostlink import AsyncHostLinkClient
from hostlink.errors import HostLinkError


async def validate_all_patterns(host, port, transport):
    print(f"=== FULL PATTERN VALIDATION ON {host}:{port} ({transport}) ===")

    async with AsyncHostLinkClient(host, port=port, transport=transport) as plc:
        # 1. System Info
        print("\n[Group 1: System Info]")
        info = await plc.query_model()
        print(f"  ?K (Model): {info.model} ({info.code})")
        mode = await plc.confirm_operating_mode()
        print(f"  ?M (Mode): {mode}")
        err = await plc.check_error_no()
        print(f"  ?E (Error): {err}")
        await plc.set_time()  # Current time
        print("  WRT (Time): OK")

        # 2. Basic Read/Write with All Suffixes
        print("\n[Group 2: Data Formats (.U, .S, .D, .L, .H)]")
        formats = [
            ("DM0", ".U", 1234),
            ("DM2", ".S", -1234),
            ("DM4", ".D", 70000),
            ("DM6", ".L", -70000),
            ("DM8", ".H", 0xABCD),
            ("DM10", "", 5555),
        ]
        for dev, fmt, val in formats:
            await plc.write(dev, val, data_format=fmt)
            read_val = await plc.read(dev, data_format=fmt)
            status = "PASS" if read_val == val else f"FAIL(got {read_val})"
            print(f"  {dev}{fmt or ' (none)'}: {val} -> {read_val} [{status}]")

        # 3. Consecutive Commands (RDS/WRS/RDE/WRE)
        print("\n[Group 3: Consecutive Commands]")
        test_vals = [10, 20, 30]
        await plc.write_consecutive("DM20", test_vals, data_format=".U")
        res = await plc.read_consecutive("DM20", 3, data_format=".U")
        print(
            f"  RDS/WRS: {test_vals} -> {res} [{'PASS' if res == test_vals else 'FAIL'}]"
        )

        await plc.write_consecutive_legacy("DM30", test_vals, data_format=".U")
        res = await plc.read_consecutive_legacy("DM30", 3, data_format=".U")
        print(
            f"  RDE/WRE: {test_vals} -> {res} [{'PASS' if res == test_vals else 'FAIL'}]"
        )

        # 4. Forced Bit Operations
        print("\n[Group 4: Forced Bit Ops]")
        # Using MR0 as test bit
        await plc.forced_set("MR0")
        res1 = await plc.read("MR0")
        await plc.forced_reset("MR0")
        res2 = await plc.read("MR0")
        print(
            f"  ST/RS MR0: Set={res1}, Reset={res2} [{'PASS' if res1 == 1 and res2 == 0 else 'FAIL'}]"
        )

        await plc.forced_set_consecutive("MR10", 5)
        print("  STS MR10 5: OK")
        await plc.forced_reset_consecutive("MR10", 5)
        print("  RSS MR10 5: OK")

        # 5. Timer/Counter Set Values (WS/WSS)
        print("\n[Group 5: Timer/Counter Set Values]")
        # Note: Writing to T/C set values (WS)
        try:
            await plc.write_set_value("T0", 500)
            await plc.write_set_value_consecutive("T1", [100, 200])
            print("  WS/WSS T0-T2: OK")
        except HostLinkError as e:
            print(f"  WS/WSS: SKIPPED or Error (Check if T0 exists/writable): {e}")

        # 6. Monitoring
        print("\n[Group 6: Monitoring]")
        await plc.register_monitor_bits("MR0", "MR1", "MR2")
        bits = await plc.read_monitor_bits()
        print(f"  MBR (Bits): {bits}")

        await plc.register_monitor_words("DM0.U", "DM1.S")
        words = await plc.read_monitor_words()
        print(f"  MWR (Words): {words}")

        # 7. Others
        print("\n[Group 7: Advanced / Others]")
        try:
            comment = await plc.read_comments("DM0")
            print(f"  RDC (Comment DM0): '{comment}'")
        except Exception:
            print("  RDC: No comment or not supported")

        await plc.switch_bank(0)
        print("  BE (Bank 0): OK")

        # Mode switching (PROGRAM -> RUN)
        print("\n[Group 8: Mode Control]")
        print("  Switching to PROGRAM...")
        await plc.change_mode("PROGRAM")
        m_prog = await plc.confirm_operating_mode()
        print("  Switching to RUN...")
        await plc.change_mode("RUN")
        m_run = await plc.confirm_operating_mode()
        print(
            f"  Mode Change: PROG={m_prog}, RUN={m_run} [{'PASS' if m_prog == 0 and m_run == 1 else 'FAIL'}]"
        )

    print("\n=== ALL PATTERN VALIDATION COMPLETED ===")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.250.101"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"
    asyncio.run(validate_all_patterns(host, port, transport))
