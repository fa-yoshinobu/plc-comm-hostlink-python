import asyncio
import socket
import threading
import time
import unittest
from datetime import datetime
from hostlink import HostLinkClient, AsyncHostLinkClient, HostLinkError, HostLinkConnectionError, HostLinkProtocolError


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
        self.port = self.sock.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def _run(self):
        if self.transport == "tcp":
            self.sock.listen(1)
            self.sock.settimeout(0.5)
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    with conn:
                        conn.settimeout(0.5)
                        while self.running:
                            try:
                                data = conn.recv(1024)
                                if not data: break
                                lines = data.decode("ascii").split("\r")
                                for line in lines:
                                    if not line: continue
                                    self.last_received.append(line.strip())
                                    resp = self.responses.get(line.strip(), "OK")
                                    conn.sendall((resp + "\r\n").encode("ascii"))
                            except socket.timeout:
                                continue
                except socket.timeout:
                    continue
        else:
            self.sock.settimeout(0.5)
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    line = data.decode("ascii").strip()
                    if line == "STOP": break
                    self.last_received.append(line)
                    resp = self.responses.get(line, "OK")
                    self.sock.sendto((resp + "\r\n").encode("ascii"), addr)
                except socket.timeout:
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
            except: pass
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
        self.server.responses["?M"] = "1"
        self.assertEqual(self.client.confirm_operating_mode(), 1)

    def test_set_time(self):
        dt = datetime(2026, 3, 18, 15, 30, 45)
        self.client.set_time(dt)
        self.assertEqual(self.server.last_received[-1], "WRT 26 03 18 15 30 45 3")

    def test_forced_set_reset(self):
        self.client.forced_set("R0")
        self.assertEqual(self.server.last_received[-1], "ST R0")
        self.client.forced_reset("R1")
        self.assertEqual(self.server.last_received[-1], "RS R1")
        self.client.forced_set_consecutive("R10", 5)
        self.assertEqual(self.server.last_received[-1], "STS R10 5")
        self.client.forced_reset_consecutive("R20", 3)
        self.assertEqual(self.server.last_received[-1], "RSS R20 3")

    def test_write_set_value(self):
        self.client.write_set_value("T0", 100)
        self.assertEqual(self.server.last_received[-1], "WS T0.D 100")
        self.client.write_set_value_consecutive("C0", [10, 20])
        self.assertEqual(self.server.last_received[-1], "WSS C0.D 2 10 20")

    def test_monitor(self):
        self.client.register_monitor_bits("R0", "R1", "R2")
        self.assertEqual(self.server.last_received[-1], "MBS R0 R1 R2")
        self.client.register_monitor_words("DM0", "DM1")
        self.assertEqual(self.server.last_received[-1], "MWS DM0.U DM1.U")
        self.server.responses["MBR"] = "1 0 1"
        self.assertEqual(self.client.read_monitor_bits(), [1, 0, 1])
        self.server.responses["MWR"] = "100 200"
        self.assertEqual(self.client.read_monitor_words(), ["100", "200"])

    def test_expansion_unit(self):
        self.server.responses["URD 01 100 .U 2"] = "123 456"
        vals = self.client.read_expansion_unit_buffer(1, 100, 2)
        self.assertEqual(vals, [123, 456])
        self.client.write_expansion_unit_buffer(1, 200, [789, 1011], data_format=".S")
        self.assertEqual(self.server.last_received[-1], "UWR 01 200 .S 2 789 1011")

    def test_read_comments(self):
        self.server.responses["RDC R0"] = "TEST COMMENT                    "
        self.assertEqual(self.client.read_comments("R0"), "TEST COMMENT")

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
