import asyncio
import unittest
from hostlink import AsyncHostLinkClient
from hostlink.errors import HostLinkError


class MockHostLinkServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self.server = None
        self.responses = {}

    async def handle_client(self, reader, writer):
        try:
            while True:
                try:
                    data = await reader.readuntil(b"\r")
                except asyncio.IncompleteReadError:
                    break
                if not data:
                    break
                cmd = data.decode("ascii").strip()
                response = self.responses.get(cmd, "OK")
                writer.write(response.encode("ascii") + b"\r\n")
                await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


class TestAsyncHostLinkClient(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = MockHostLinkServer()
        await self.server.start()
        self.client = AsyncHostLinkClient(
            "127.0.0.1", port=self.server.port, auto_connect=False
        )

    async def asyncTearDown(self):
        await self.client.close()
        await self.server.stop()

    async def test_read_dm0(self):
        self.server.responses["RD DM0.U"] = "1234"
        val = await self.client.read("DM0.U")
        self.assertEqual(val, 1234)

    async def test_write_dm0(self):
        self.server.responses["WR DM0.U 5678"] = "OK"
        await self.client.write("DM0.U", 5678)
        # No exception means OK

    async def test_error_response(self):
        self.server.responses["RD DM999.U"] = "E1"
        with self.assertRaises(HostLinkError) as cm:
            await self.client.read("DM999.U")
        self.assertEqual(cm.exception.code, "E1")

    async def test_change_mode(self):
        self.server.responses["M1"] = "OK"
        await self.client.change_mode("RUN")

    async def test_multiple_reads(self):
        self.server.responses["RDS DM0.U 2"] = "100 200"
        vals = await self.client.read_consecutive("DM0.U", 2)
        self.assertEqual(vals, [100, 200])


if __name__ == "__main__":
    unittest.main()
