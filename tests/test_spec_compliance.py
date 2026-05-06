import unittest

from hostlink import (
    HostLinkClient,
    KvDeviceRangeCategory,
    KvDeviceRangeNotation,
    available_device_range_models,
    device_range_catalog_for_model,
)
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

    def test_rdc_accepts_xym_alias_device_types(self) -> None:
        plc = FakeHostLinkClient()
        plc.queue("DM COMMENT                      ")
        self.assertEqual(plc.read_comments("D10"), "DM COMMENT")
        self.assertEqual(plc.sent_frames[-1], b"RDC D10\r")

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

    def test_parse_device_accepts_high_xym_m_addresses(self) -> None:
        self.assertEqual(parse_device("M63872").to_text(), "M63872")
        with self.assertRaises(HostLinkProtocolError):
            parse_device("M64000")

    def test_parse_device_uses_bit_bank_format_for_keyence_bit_devices(self) -> None:
        self.assertEqual(parse_device("R0").to_text(), "R000")
        self.assertEqual(parse_device("R1").to_text(), "R001")
        self.assertEqual(parse_device("R15").to_text(), "R015")
        self.assertEqual(parse_device("R100").to_text(), "R100")
        self.assertEqual(parse_device("MR115").to_text(), "MR115")
        self.assertEqual(parse_device("CR0").to_text(), "CR000")

    def test_parse_device_rejects_invalid_bit_bank_numbers(self) -> None:
        for text in ("R016", "MR116", "LR99916", "CR7916"):
            with self.subTest(text=text):
                with self.assertRaises(HostLinkProtocolError):
                    parse_device(text)

    def test_device_range_catalog_resolves_runtime_models(self) -> None:
        self.assertIn("KV-7000(XYM)", available_device_range_models())

        catalog = device_range_catalog_for_model("KV-8000A")
        self.assertEqual(catalog.model, "KV-8000")
        self.assertEqual(catalog.model_code, "")
        self.assertFalse(catalog.has_model_code)
        self.assertEqual(catalog.entry("DM").address_range, "DM00000-DM65534")

        tm = catalog.entry("TM")
        self.assertEqual(tm.category, KvDeviceRangeCategory.WORD)
        self.assertFalse(tm.is_bit_device)

    def test_device_range_catalog_splits_xym_alias_ranges(self) -> None:
        catalog = device_range_catalog_for_model("KV-3000/5000(XYM)")
        entry = catalog.entry("R")

        self.assertEqual(entry.device, "R")
        self.assertEqual(entry.category, KvDeviceRangeCategory.BIT)
        self.assertTrue(entry.is_bit_device)
        self.assertEqual(entry.notation, KvDeviceRangeNotation.HEXADECIMAL)
        self.assertEqual(entry.upper_bound, 999 * 16 + 15)
        self.assertEqual(entry.point_count, 1000 * 16)
        self.assertEqual(entry.address_range, "X0-999F,Y0-999F")
        self.assertIn("multiple alias devices", entry.notes)
        self.assertEqual([segment.device for segment in entry.segments], ["X", "Y"])
        self.assertEqual(entry.segments[0].upper_bound, 999 * 16 + 15)
        self.assertEqual(entry.segments[1].upper_bound, 999 * 16 + 15)
        self.assertEqual(catalog.entry("X").device_type, "R")

        kv8000 = device_range_catalog_for_model("KV-8000(XYM)")
        r = kv8000.entry("R")
        self.assertEqual(r.upper_bound, 1999 * 16 + 15)
        self.assertEqual(r.point_count, 2000 * 16)
        self.assertEqual(r.segments[0].upper_bound, 1999 * 16 + 15)
        self.assertEqual(r.segments[1].upper_bound, 1999 * 16 + 15)

        dm = catalog.entry("DM")
        self.assertEqual(dm.device, "D")
        self.assertEqual(dm.category, KvDeviceRangeCategory.WORD)
        self.assertEqual(dm.upper_bound, 65534)
        self.assertEqual(dm.point_count, 65535)
        self.assertEqual(dm.segments[0].address_range, "D0-65534")
        self.assertEqual(catalog.entry("D").device_type, "DM")

    def test_device_range_catalog_publishes_corrected_ranges(self) -> None:
        nano = device_range_catalog_for_model("KV-N24nn")
        self.assertEqual(nano.entry("CM").address_range, "CM0000-CM8999")
        self.assertFalse(nano.entry("EM").supported)
        self.assertIsNone(nano.entry("EM").address_range)

        xym = device_range_catalog_for_model("KV-3000/5000(XYM)")
        self.assertEqual(xym.entry("CR").address_range, "CR0000-CR3915")

    def test_device_range_catalog_rejects_unsupported_model(self) -> None:
        with self.assertRaises(HostLinkProtocolError):
            device_range_catalog_for_model("KV-1000")


if __name__ == "__main__":
    unittest.main()
