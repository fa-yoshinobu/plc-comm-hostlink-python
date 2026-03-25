import socket
import sys


class MockSyncServer:
    def __init__(self, host="127.0.0.1", port=8501, transport="tcp"):
        self.host = host
        self.port = port
        self.transport = transport
        self.sock = None
        self.running = False
        self.responses = {
            "?K": "63",
            "?M": "1",
            "RD DM0.S": "123",
            "WR DM0.S 124": "OK",
        }

    def start(self):
        stype = socket.SOCK_STREAM if self.transport == "tcp" else socket.SOCK_DGRAM
        self.sock = socket.socket(socket.AF_INET, stype)
        self.sock.bind((self.host, self.port))
        if self.transport == "tcp":
            self.sock.listen(1)
        self.running = True
        print(f"Mock PLC Server started on {self.host}:{self.port} ({self.transport})")
        self._run()

    def _run(self):
        try:
            if self.transport == "tcp":
                while self.running:
                    conn, addr = self.sock.accept()
                    with conn:
                        print(f"Connected by {addr}")
                        while self.running:
                            data = conn.recv(1024)
                            if not data:
                                break
                            lines = data.decode("ascii").split("\r")
                            for line in lines:
                                if not line:
                                    continue
                                cmd = line.strip()
                                print(f"Received: {cmd}")

                                # Basic write-back logic for test
                                if cmd.startswith("WR "):
                                    parts = cmd.split(" ")
                                    if len(parts) >= 3:
                                        self.responses[f"RD {parts[1]}"] = parts[2]
                                    resp = "OK"
                                else:
                                    resp = self.responses.get(cmd, "OK")

                                conn.sendall((resp + "\r\n").encode("ascii"))
            else:
                while self.running:
                    data, addr = self.sock.recvfrom(1024)
                    cmd = data.decode("ascii").strip()
                    if cmd == "STOP":
                        break
                    print(f"Received (UDP): {cmd}")
                    resp = self.responses.get(cmd, "OK")
                    self.sock.sendto((resp + "\r\n").encode("ascii"), addr)
        except KeyboardInterrupt:
            pass
        finally:
            self.sock.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
    server = MockSyncServer(port=port)
    server.start()
