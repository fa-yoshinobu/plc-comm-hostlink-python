from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import hostlink
from hostlink import (
    HostLinkAddress,
    HostLinkConnectionOptions,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    read_bits_single_request,
    read_dwords_single_request,
    read_expansion_unit_buffer,
    read_words,
    read_words_single_request,
    try_parse_address,
    write_bits_single_request,
    write_dwords_single_request,
    write_expansion_unit_buffer,
    write_words_single_request,
)
from hostlink.device import DEFAULT_FORMAT_BY_DEVICE_TYPE, FLOAT32_ELIGIBLE_DEVICE_TYPES, NATIVE_32BIT_DEVICE_TYPES
from hostlink.errors import HostLinkProtocolError


class TestAddressSurface(unittest.TestCase):
    def test_normalize_address_uppercases_and_preserves_bit_suffix(self) -> None:
        self.assertEqual(normalize_address("dm100.a"), "DM100.A")
        self.assertEqual(normalize_address("dm100.d"), "DM100.D")
        self.assertEqual(normalize_address("dm100:u"), "DM100:U")
        self.assertEqual(normalize_address("dm100:f"), "DM100:F")
        self.assertEqual(normalize_address("dm100:h"), "DM100:H")
        with self.assertRaises(TypeError):
            normalize_address("dm100:f", default_suffix="U")

    def test_parse_address_returns_public_metadata(self) -> None:
        parsed = parse_address("dm100.a")
        self.assertEqual(parsed.text, "DM100.A")
        self.assertEqual(parsed.base_device, "DM100")
        self.assertEqual(parsed.dtype, "BIT_IN_WORD")
        self.assertEqual(parsed.bit_index, 10)
        self.assertTrue(parsed.is_bit_in_word)
        self.assertEqual(format_address(parsed), "DM100.A")

        bit_d = parse_address("dm100.d")
        self.assertEqual(bit_d.dtype, "BIT_IN_WORD")
        self.assertEqual(bit_d.bit_index, 13)

        typed = parse_address("dm100:d")
        self.assertEqual(typed.text, "DM100:D")
        self.assertEqual(typed.dtype, "D")
        hex_typed = parse_address("dm100:h")
        self.assertEqual(hex_typed.text, "DM100:H")
        self.assertEqual(hex_typed.dtype, "H")
        with self.assertRaises(TypeError):
            parse_address("dm100", default_suffix="D")

    def test_try_parse_address_returns_none_for_invalid_text(self) -> None:
        self.assertIsNone(try_parse_address("DM1A"))
        self.assertIsNone(try_parse_address("DM100"))
        self.assertIsNone(try_parse_address("DM100.S"))
        self.assertIsNone(try_parse_address("DM100.10"))
        self.assertIsNone(try_parse_address("DM100:BIT_IN_WORD"))
        self.assertEqual(format_address("dm100:f"), "DM100:F")

    def test_bit_in_word_dtype_requires_explicit_bit_index(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit bit index"):
            parse_address("DM100:BIT_IN_WORD")
        with self.assertRaisesRegex(ValueError, "explicit bit index"):
            normalize_address("DM100:BIT_IN_WORD")

    def test_parser_normalizer_and_formatter_share_semantic_validation(self) -> None:
        invalid = ("DM0:BIT", "R0:F", "T0:F", "C0:F", "AT0:F", "AT0:COMMENT")
        for text in invalid:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_address(text)
                with self.assertRaises(ValueError):
                    normalize_address(text)

        invalid_objects = (
            HostLinkAddress("ignored", "DM0", "BIT"),
            HostLinkAddress("ignored", "R0", "F"),
            HostLinkAddress("ignored", "AT0", "COMMENT"),
        )
        for address in invalid_objects:
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    format_address(address)

        valid = HostLinkAddress("ignored", "dm0001", "u")
        formatted = format_address(valid)
        reparsed = parse_address(formatted)
        self.assertEqual(formatted, "DM1:U")
        self.assertEqual((reparsed.base_device, reparsed.dtype, reparsed.bit_index), ("DM1", "U", None))

    def test_float32_family_eligibility_matches_canonical_metadata_exhaustively(self) -> None:
        expected = frozenset({"DM", "EM", "FM", "ZF", "W", "TM", "CM", "VM", "D", "E", "F"})
        self.assertEqual(FLOAT32_ELIGIBLE_DEVICE_TYPES, expected)
        self.assertEqual(
            FLOAT32_ELIGIBLE_DEVICE_TYPES,
            frozenset(
                device_type
                for device_type, default_format in DEFAULT_FORMAT_BY_DEVICE_TYPE.items()
                if default_format == ".U" and device_type not in NATIVE_32BIT_DEVICE_TYPES
            ),
        )

        for device_type in DEFAULT_FORMAT_BY_DEVICE_TYPE:
            address = f"{device_type}0:F"
            with self.subTest(address=address):
                if device_type in expected:
                    self.assertEqual(parse_address(address).dtype, "F")
                    self.assertEqual(normalize_address(address.lower()), address)
                    self.assertEqual(
                        format_address(HostLinkAddress("ignored", f"{device_type}0", "F")),
                        address,
                    )
                else:
                    with self.assertRaises(ValueError):
                        parse_address(address)
                    with self.assertRaises(ValueError):
                        normalize_address(address)
                    with self.assertRaises(ValueError):
                        format_address(HostLinkAddress("ignored", f"{device_type}0", "F"))


class TestHighLevelSurface(unittest.IsolatedAsyncioTestCase):
    def test_connection_options_require_canonical_plc_profile(self) -> None:
        with self.assertRaises(TypeError):
            HostLinkConnectionOptions("127.0.0.1")
        with self.assertRaises(HostLinkProtocolError):
            HostLinkConnectionOptions("127.0.0.1", plc_profile="KV-8000", port=8501, transport="tcp")

    def test_connection_options_reject_bracketed_ipv4(self) -> None:
        with self.assertRaisesRegex(ValueError, "brackets"):
            HostLinkConnectionOptions(
                "[127.0.0.1]",
                plc_profile="keyence:kv-8000",
                port=8501,
                transport="tcp",
            )

    async def test_open_and_connect_accepts_options(self) -> None:
        options = HostLinkConnectionOptions(
            "127.0.0.1",
            plc_profile="keyence:kv-8000",
            port=8501,
            transport="tcp",
        )
        with patch("hostlink.client.AsyncHostLinkClient") as client_cls:
            inner = AsyncMock()
            client_cls.return_value = inner

            client = await open_and_connect(options)

        self.assertIs(client, inner)
        client_cls.assert_called_once_with(
            "127.0.0.1",
            port=8501,
            transport="tcp",
            timeout=3.0,
            connect_timeout=3.0,
            plc_profile="keyence:kv-8000",
        )
        inner.connect.assert_awaited_once()

    def test_automatic_chunking_helpers_are_not_public(self) -> None:
        for name in (
            "read_words_chunked",
            "read_dwords_chunked",
            "write_words_chunked",
            "write_dwords_chunked",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(hostlink, name))

    async def test_read_words_single_request(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [1, 2, 3]
        values = await read_words_single_request(client, "DM0", 3)
        self.assertEqual(values, [1, 2, 3])
        client.read_consecutive.assert_awaited_once_with("DM0", 3, data_format=".U")

    async def test_bit_single_request_helpers_send_once(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [0, 1, "1"]

        self.assertEqual(await read_bits_single_request(client, "R5000", 3), [False, True, True])
        client.read_consecutive.assert_awaited_once_with("R5000", 3, data_format=None)

        await write_bits_single_request(client, "R5000", [False, True, True])
        client.write_consecutive.assert_awaited_once_with("R5000", [False, True, True], data_format=None)

    async def test_bit_single_request_helpers_reject_before_send(self) -> None:
        client = AsyncMock()

        for device, count in (("DM0", 1), ("R5000.U", 1), ("R5000", 0), ("R5000", 1001)):
            with self.subTest(operation="read", device=device, count=count):
                with self.assertRaises((HostLinkProtocolError, ValueError)):
                    await read_bits_single_request(client, device, count)
        for device, values in (("DM0", [True]), ("R5000.U", [True]), ("R5000", []), ("R5000", [1])):
            with self.subTest(operation="write", device=device, values=values):
                with self.assertRaises((HostLinkProtocolError, ValueError)):
                    await write_bits_single_request(client, device, values)  # type: ignore[arg-type]

        client.read_consecutive.assert_not_awaited()
        client.write_consecutive.assert_not_awaited()

    async def test_read_words_deprecated_alias_delegates_once(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [1]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(await read_words(client, "DM0", 1), [1])

        client.read_consecutive.assert_awaited_once_with("DM0", 1, data_format=".U")

    async def test_read_dwords_single_request(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [1, 0, 2, 0]
        values = await read_dwords_single_request(client, "DM0", 2)
        self.assertEqual(values, [1, 2])

    async def test_write_words_single_request(self) -> None:
        client = AsyncMock()
        await write_words_single_request(client, "DM0", [1, 2, 3])
        client.write_consecutive.assert_awaited_once_with("DM0", [1, 2, 3], data_format=".U")

    async def test_write_dwords_single_request(self) -> None:
        client = AsyncMock()
        await write_dwords_single_request(client, "DM0", [1, 2])
        client.write_consecutive.assert_awaited_once_with("DM0", [1, 0, 2, 0], data_format=".U")

    async def test_read_expansion_unit_buffer_helper(self) -> None:
        client = AsyncMock()
        client.read_expansion_unit_buffer.return_value = [123, 456]

        values = await read_expansion_unit_buffer(client, 1, 100, 2, data_format="U")

        self.assertEqual(values, [123, 456])
        client.read_expansion_unit_buffer.assert_awaited_once_with(1, 100, 2, data_format="U")

    async def test_write_expansion_unit_buffer_helper(self) -> None:
        client = AsyncMock()

        await write_expansion_unit_buffer(client, 1, 200, [789, 1011], data_format="S")

        client.write_expansion_unit_buffer.assert_awaited_once_with(1, 200, [789, 1011], data_format="S")
