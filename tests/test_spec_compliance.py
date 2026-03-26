import unittest

from hostlink import HostLinkClient
from hostlink.device import parse_device, validate_device_span, validate_expansion_buffer_span
from hostlink.errors import HostLinkProtocolError


class FakeHostLinkClient(HostLinkClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1", auto_connect=False)
        self.sent_frames: list[bytes] = []
        self.queued_responses: list[bytes] = []

    def queue(self, text: str) -> None:
        self.queued_responses.append(text.encode("ascii") + b"\r\n")

    def _exchange(self, payload: bytes) -> bytes:
        self.sent_frames.append(payload)
        if self.queued_responses:
            return self.queued_responses.pop(0)
        return b"OK\r\n"


class HostLinkSpecComplianceTest(unittest.TestCase):
    def test_change_mode_command_shape(self) -> None:
        plc = FakeHostLinkClient()
        plc.change_mode("RUN")
        self.assertEqual(plc.sent_frames[-1], b"M1\r")

    def test_set_time_command_shape(self) -> None:
        plc = FakeHostLinkClient()
        plc.set_time((26, 3, 13, 22, 5, 9, 5))
        self.assertEqual(plc.sent_frames[-1], b"WRT 26 03 13 22 05 09 5\r")

    def test_tm_count_limit_enforced(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read_consecutive("TM0", 513)

    def test_tm_32bit_count_limit_enforced(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read_consecutive("TM0.D", 257)

    def test_tc_group_count_limit_enforced(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read_consecutive("TC0", 121)

    def test_ws_only_accepts_t_or_c(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.write_set_value("TC0", 100)

    def test_mbs_rejects_word_device(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.register_monitor_bits("DM200")

    def test_mws_rejects_bit_only_timer_type(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.register_monitor_words("T0")

    def test_rdc_rejects_unsupported_device_type(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read_comments("VB0")

    def test_urd_32bit_count_limit_enforced(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read_expansion_unit_buffer(1, 100, 501, data_format=".D")

    def test_uwr_16bit_count_limit_enforced(self) -> None:
        plc = FakeHostLinkClient()
        values = [0] * 1001
        with self.assertRaises(HostLinkProtocolError):
            plc.write_expansion_unit_buffer(1, 100, values, data_format=".U")

    def test_decimal_device_rejects_hex_digits(self) -> None:
        with self.assertRaises(HostLinkProtocolError):
            parse_device("DM1A")

    def test_parse_device_rejects_float_suffix(self) -> None:
        with self.assertRaises(HostLinkProtocolError):
            parse_device("DM10.F")

    def test_validate_device_span_rejects_32bit_end_crossing(self) -> None:
        with self.assertRaises(HostLinkProtocolError):
            validate_device_span("DM", 65534, ".D", 1)

    def test_validate_expansion_buffer_span_rejects_32bit_end_crossing(self) -> None:
        with self.assertRaises(HostLinkProtocolError):
            validate_expansion_buffer_span(59999, ".D", 1)

    def test_read_rejects_32bit_device_end_crossing(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.read("DM65534.D")
        self.assertEqual(plc.sent_frames, [])

    def test_write_set_value_rejects_default_32bit_device_end_crossing(self) -> None:
        plc = FakeHostLinkClient()
        with self.assertRaises(HostLinkProtocolError):
            plc.write_set_value("T3999", 100)
        self.assertEqual(plc.sent_frames, [])


if __name__ == "__main__":
    unittest.main()
