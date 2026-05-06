import asyncio
import socket
import threading
import unittest
from datetime import datetime

from hostlink import (
    AsyncHostLinkClient,
    HostLinkClient,
    HostLinkError,
    HostLinkProtocolError,
    poll,
    read_comments,
    read_named,
    read_typed,
    write_typed,
)
from hostlink.device import DeviceAddress, parse_device


class MockSyncServer:
    def __init__(self, transport="tcp"):
        self.transport = transport
        self.host = "127.0.0.1"
        self.port = 0
        self.sock = None
        self.running = False
        self.responses = {}
        self.last_received = []

    def start(self):
        stype = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
        self.sock = socket.socket(socket.AF_INET, stype)
        self.sock.bind((self.host, 0))
        if self.transport == "tcp":
            # Make the listening socket ready before clients attempt to connect.
            self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def _run(self):
        if self.transport == "tcp":
            self.sock.settimeout(0.5)
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    with conn:
                        conn.settimeout(0.5)
                        while self.running:
                            try:
                                data = conn.recv(1024)
                                if not data:
                                    break
                                lines = data.decode("ascii").split("\r")
                                for line in lines:
                                    if not line:
                                        continue
                                    self.last_received.append(line.strip())
                                    resp = self.responses.get(line.strip(), "OK")
                                    conn.sendall((resp + "\r\n").encode("ascii"))
                            except TimeoutError:
                                continue
                except TimeoutError:
                    continue
        else:
            self.sock.settimeout(0.5)
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    line = data.decode("ascii").strip()
                    if line == "STOP":
                        break
                    self.last_received.append(line)
                    resp = self.responses.get(line, "OK")
                    self.sock.sendto((resp + "\r\n").encode("ascii"), addr)
                except TimeoutError:
                    continue

    def stop(self):
        self.running = False
        if self.sock:
            try:
                if self.transport == "tcp":
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.1)
                        s.connect((self.host, self.port))
                else:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.sendto(b"STOP", (self.host, self.port))
            except Exception:
                pass
        self.thread.join()


class TestComprehensiveSync(unittest.TestCase):
    def setUp(self):
        self.server = MockSyncServer(transport="tcp")
        self.server.start()
        self.client = HostLinkClient("127.0.0.1", port=self.server.port, auto_connect=True)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_basic_commands(self):
        self.client.change_mode("RUN")
        self.assertEqual(self.server.last_received[-1], "M1")
        self.client.change_mode(0)
        self.assertEqual(self.server.last_received[-1], "M0")
        self.client.clear_error()
        self.assertEqual(self.server.last_received[-1], "ER")
        self.server.responses["?E"] = "000"
        self.assertEqual(self.client.check_error_no(), "000")
        self.server.responses["?K"] = "63"
        info = self.client.query_model()
        self.assertEqual(info.code, "63")
        catalog = self.client.read_device_range_catalog()
        self.assertEqual(catalog.model, "KV-X500")
        self.assertEqual(catalog.model_code, "63")
        self.server.responses["?M"] = "1"
        self.assertEqual(self.client.confirm_operating_mode(), 1)

    def test_udp_send_raw_accepts_large_datagram_response(self):
        server = MockSyncServer(transport="udp")
        server.start()
        client = HostLinkClient("127.0.0.1", port=server.port, transport="udp", auto_connect=True)
        try:
            large_response = "7" * 9000
            server.responses["LARGE"] = large_response

            self.assertEqual(client.send_raw("LARGE"), large_response)
        finally:
            client.close()
            server.stop()

    def test_set_time(self):
        dt = datetime(2026, 3, 18, 15, 30, 45)
        self.client.set_time(dt)
        self.assertEqual(self.server.last_received[-1], "WRT 26 03 18 15 30 45 3")

    def test_forced_set_reset(self):
        self.client.forced_set("R0")
        self.assertEqual(self.server.last_received[-1], "ST R000")
        self.client.forced_reset("R1")
        self.assertEqual(self.server.last_received[-1], "RS R001")
        self.client.forced_set_consecutive("R10", 5)
        self.assertEqual(self.server.last_received[-1], "STS R010 5")
        self.client.forced_reset_consecutive("R100", 3)
        self.assertEqual(self.server.last_received[-1], "RSS R100 3")

    def test_write_set_value(self):
        self.client.write_set_value("T0", 100)
        self.assertEqual(self.server.last_received[-1], "WS T0.D 100")
        self.client.write_set_value_consecutive("C0", [10, 20])
        self.assertEqual(self.server.last_received[-1], "WSS C0.D 2 10 20")

    def test_monitor(self):
        self.client.register_monitor_bits("R0", "R1", "R2")
        self.assertEqual(self.server.last_received[-1], "MBS R000 R001 R002")
        self.client.register_monitor_words("DM0", "DM1")
        self.assertEqual(self.server.last_received[-1], "MWS DM0.U DM1.U")
        self.server.responses["MBR"] = "1 0 1"
        self.assertEqual(self.client.read_monitor_bits(), [1, 0, 1])
        self.server.responses["MWR"] = "100 200"
        self.assertEqual(self.client.read_monitor_words(), ["100", "200"])

    def test_xym_bit_device_numbers_use_decimal_bank_and_hex_bit(self):
        self.assertEqual(parse_device("X390").number, 39 * 16)
        self.assertEqual(parse_device("X400").number, 40 * 16)
        self.assertEqual(DeviceAddress("X", 39 * 16 + 15).to_text(), "X39F")
        self.assertEqual(DeviceAddress("X", 40 * 16).to_text(), "X400")
        self.assertEqual(parse_device("Y1999F").number, 1999 * 16 + 15)

        with self.assertRaisesRegex(HostLinkProtocolError, "bank digits must be decimal"):
            parse_device("X3F0")
        with self.assertRaisesRegex(HostLinkProtocolError, "bank digits must be decimal"):
            parse_device("Y19A0")
        with self.assertRaisesRegex(HostLinkProtocolError, "out of range"):
            parse_device("Y20000")

    def test_expansion_unit(self):
        self.server.responses["URD 01 100 .U 2"] = "123 456"
        vals = self.client.read_expansion_unit_buffer(1, 100, 2)
        self.assertEqual(vals, [123, 456])
        self.client.write_expansion_unit_buffer(1, 200, [789, 1011], data_format=".S")
        self.assertEqual(self.server.last_received[-1], "UWR 01 200 .S 2 789 1011")

    def test_read_comments(self):
        self.server.responses["RDC R000"] = "TEST COMMENT                    "
        self.assertEqual(self.client.read_comments("R0"), "TEST COMMENT")
        self.server.responses["RDC D10"] = "DM COMMENT                      "
        self.assertEqual(self.client.read_comments("D10"), "DM COMMENT")

    def test_switch_bank(self):
        self.client.switch_bank(5)
        self.assertEqual(self.server.last_received[-1], "BE 5")

    def test_errors(self):
        self.server.responses["RD DM0.U"] = "E0"
        with self.assertRaises(HostLinkError):
            self.client.read("DM0.U")
        with self.assertRaises(HostLinkProtocolError):
            self.client.read("INVALID")

    def test_udp(self):
        udp_server = MockSyncServer(transport="udp")
        udp_server.start()
        try:
            with HostLinkClient("127.0.0.1", port=udp_server.port, transport="udp") as client:
                client.write("DM0.U", 123)
                self.assertEqual(udp_server.last_received[-1], "WR DM0.U 123")
        finally:
            udp_server.stop()

    def test_consecutive_commands(self):
        self.server.responses["RDS DM0.U 3"] = "10 20 30"
        self.assertEqual(self.client.read_consecutive("DM0.U", 3), [10, 20, 30])
        self.client.write_consecutive("DM10.U", [100, 200])
        self.assertEqual(self.server.last_received[-1], "WRS DM10.U 2 100 200")

    def test_hex_reads_return_hex_strings(self):
        self.server.responses["RD DM2.H"] = "00FF"
        self.assertEqual(self.client.read("DM2.H"), "00FF")
        self.server.responses["RDS DM2.H 2"] = "00FF 000A"
        self.assertEqual(self.client.read_consecutive("DM2.H", 2), ["00FF", "000A"])

    def test_legacy_commands(self):
        self.server.responses["RDE DM0.U 2"] = "1 2"
        self.assertEqual(self.client.read_consecutive_legacy("DM0.U", 2), [1, 2])
        self.client.write_consecutive_legacy("DM10.U", [5, 6])
        self.assertEqual(self.server.last_received[-1], "WRE DM10.U 2 5 6")


class TestComprehensiveAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = MockSyncServer(transport="tcp")
        self.server.start()
        self.client = AsyncHostLinkClient("127.0.0.1", port=self.server.port)

    async def asyncTearDown(self):
        await self.client.close()
        self.server.stop()

    async def test_async_basic(self):
        await self.client.change_mode("RUN")
        self.assertEqual(self.server.last_received[-1], "M1")
        self.server.responses["RD DM0.U"] = "555"
        val = await self.client.read("DM0.U")
        self.assertEqual(val, 555)

    async def test_async_udp(self):
        udp_server = MockSyncServer(transport="udp")
        udp_server.start()
        try:
            async with AsyncHostLinkClient("127.0.0.1", port=udp_server.port, transport="udp") as client:
                await client.write("DM10.U", 999)
                self.assertEqual(udp_server.last_received[-1], "WR DM10.U 999")
                udp_server.responses["RD DM10.U"] = "999"
                val = await client.read("DM10.U")
                self.assertEqual(val, 999)
        finally:
            udp_server.stop()

    async def test_async_parallel(self):
        self.server.responses["RD DM0.U"] = "0"
        self.server.responses["RD DM1.U"] = "1"
        tasks = [self.client.read("DM0.U"), self.client.read("DM1.U")]
        results = await asyncio.gather(*tasks)
        self.assertIn(0, results)
        self.assertIn(1, results)

    async def test_async_consecutive_commands(self):
        self.server.responses["RDS DM0.U 3"] = "10 20 30"
        self.assertEqual(await self.client.read_consecutive("DM0.U", 3), [10, 20, 30])
        await self.client.write_consecutive("DM10.U", [100, 200])
        self.assertEqual(self.server.last_received[-1], "WRS DM10.U 2 100 200")

    async def test_async_hex_reads_return_hex_strings(self):
        self.server.responses["RD DM2.H"] = "00FF"
        self.assertEqual(await self.client.read("DM2.H"), "00FF")
        self.server.responses["RDS DM2.H 2"] = "00FF 000A"
        self.assertEqual(await self.client.read_consecutive("DM2.H", 2), ["00FF", "000A"])

    async def test_async_float_helpers(self):
        self.server.responses["RDS DM0.U 2"] = "0 16288"
        self.server.responses["RDS DM2.U 2"] = "0 16712"
        self.assertAlmostEqual(await read_typed(self.client, "DM2", "F"), 12.5)

        await write_typed(self.client, "DM2", "F", 12.5)
        self.assertEqual(self.server.last_received[-1], "WRS DM2.U 2 0 16712")

        self.server.last_received.clear()
        self.server.responses["RDS DM0.U 4"] = "0 16288 0 16712"
        result = await read_named(self.client, ["DM0:F", "DM2:F"])
        self.assertEqual(result, {"DM0:F": 1.25, "DM2:F": 12.5})
        self.assertEqual(self.server.last_received, ["RDS DM0.U 4"])

    async def test_async_read_named_batches_contiguous_word_reads(self):
        self.server.responses["RDS DM100.U 8"] = "1025 65535 2 1 57920 1 0 16712"

        result = await read_named(
            self.client,
            ["DM100", "DM100.0", "DM100.A", "DM101:S", "DM102:D", "DM104:L", "DM106:F"],
        )

        self.assertEqual(
            result,
            {
                "DM100": 1025,
                "DM100.0": True,
                "DM100.A": True,
                "DM101:S": -1,
                "DM102:D": 65538,
                "DM104:L": 123456,
                "DM106:F": 12.5,
            },
        )
        self.assertEqual(self.server.last_received, ["RDS DM100.U 8"])

    async def test_async_read_named_batches_bit_bank_direct_bits_across_display_bank_boundary(self):
        self.server.responses["RDS CR3614 4"] = "0 1 0 1"

        result = await read_named(self.client, ["CR3614", "CR3615", "CR3700", "CR3701"])

        self.assertEqual(
            result,
            {
                "CR3614": False,
                "CR3615": True,
                "CR3700": False,
                "CR3701": True,
            },
        )
        self.assertEqual(self.server.last_received, ["RDS CR3614 4"])

    async def test_async_read_comments_helper_and_read_named_comment(self):
        self.server.responses["RDC DM150"] = "MAIN COMMENT                    "
        comment = await read_comments(self.client, "DM150")
        self.assertEqual(comment, "MAIN COMMENT")

        self.server.last_received.clear()
        self.server.responses["RD DM100.U"] = "321"
        self.server.responses["RDC DM101"] = "ALARM COMMENT                   "
        result = await read_named(self.client, ["DM100", "DM101:COMMENT"])
        self.assertEqual(result, {"DM100": 321, "DM101:COMMENT": "ALARM COMMENT"})
        self.assertEqual(self.server.last_received, ["RD DM100.U", "RDC DM101"])

    async def test_async_poll_reuses_compiled_read_plan(self):
        self.server.responses["RDS DM100.U 3"] = "1 0 16320"
        snapshots: list[dict[str, int | float | bool | str]] = []

        async for snapshot in poll(self.client, ["DM100", "DM100.0", "DM101:F"], interval=0.001):
            snapshots.append(snapshot)
            if len(snapshots) == 1:
                self.server.responses["RDS DM100.U 3"] = "3 0 16416"
            if len(snapshots) >= 2:
                break

        self.assertEqual(
            snapshots,
            [
                {"DM100": 1, "DM100.0": True, "DM101:F": 1.5},
                {"DM100": 3, "DM100.0": True, "DM101:F": 2.5},
            ],
        )
        self.assertEqual(self.server.last_received, ["RDS DM100.U 3", "RDS DM100.U 3"])

    async def test_async_legacy_commands(self):
        self.server.responses["RDE DM0.U 2"] = "1 2"
        self.assertEqual(await self.client.read_consecutive_legacy("DM0.U", 2), [1, 2])
        await self.client.write_consecutive_legacy("DM10.U", [5, 6])
        self.assertEqual(self.server.last_received[-1], "WRE DM10.U 2 5 6")

    async def test_async_expansion(self):
        self.server.responses["URD 00 500 .U 1"] = "999"
        val = await self.client.read_expansion_unit_buffer(0, 500, 1)
        self.assertEqual(val, [999])
        await self.client.write_expansion_unit_buffer(0, 600, [111])
        self.assertEqual(self.server.last_received[-1], "UWR 00 600 .U 1 111")


if __name__ == "__main__":
    unittest.main()
