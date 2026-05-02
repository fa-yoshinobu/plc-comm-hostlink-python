from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from hostlink import (
    HostLinkConnectionOptions,
    format_address,
    normalize_address,
    open_and_connect,
    parse_address,
    read_dwords_chunked,
    read_dwords_single_request,
    read_expansion_unit_buffer,
    read_words_chunked,
    read_words_single_request,
    try_parse_address,
    write_dwords_chunked,
    write_dwords_single_request,
    write_expansion_unit_buffer,
    write_words_chunked,
    write_words_single_request,
)


class TestAddressSurface(unittest.TestCase):
    def test_normalize_address_uppercases_and_preserves_bit_suffix(self) -> None:
        self.assertEqual(normalize_address("dm100.a"), "DM100.A")

    def test_parse_address_returns_public_metadata(self) -> None:
        parsed = parse_address("dm100.a")
        self.assertEqual(parsed.text, "DM100.A")
        self.assertEqual(parsed.base_device, "DM100")
        self.assertEqual(parsed.dtype, "BIT_IN_WORD")
        self.assertEqual(parsed.bit_index, 10)
        self.assertTrue(parsed.is_bit_in_word)
        self.assertEqual(format_address(parsed), "DM100.A")

    def test_try_parse_address_returns_none_for_invalid_text(self) -> None:
        self.assertIsNone(try_parse_address("DM1A"))
        self.assertEqual(format_address("dm100:f"), "DM100:F")


class TestHighLevelSurface(unittest.IsolatedAsyncioTestCase):
    async def test_open_and_connect_accepts_options(self) -> None:
        options = HostLinkConnectionOptions("127.0.0.1", port=8501, append_lf_on_send=True)
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
            append_lf_on_send=True,
            auto_connect=False,
        )
        inner.connect.assert_awaited_once()

    async def test_read_words_single_request(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [1, 2, 3]
        values = await read_words_single_request(client, "DM0", 3)
        self.assertEqual(values, [1, 2, 3])
        client.read_consecutive.assert_awaited_once_with("DM0", 3, data_format=".U")

    async def test_read_dwords_single_request(self) -> None:
        client = AsyncMock()
        client.read_consecutive.return_value = [1, 0, 2, 0]
        values = await read_dwords_single_request(client, "DM0", 2)
        self.assertEqual(values, [1, 2])

    async def test_read_words_chunked(self) -> None:
        client = AsyncMock()
        client.read_consecutive.side_effect = [[0, 1, 2, 3], [4, 5]]
        values = await read_words_chunked(client, "DM0", 6, max_per_request=4)
        self.assertEqual(values, [0, 1, 2, 3, 4, 5])
        self.assertEqual(client.read_consecutive.await_args_list[0].args, ("DM0", 4))
        self.assertEqual(client.read_consecutive.await_args_list[1].args, ("DM4", 2))

    async def test_read_dwords_chunked_preserves_dword_boundaries(self) -> None:
        client = AsyncMock()
        client.read_consecutive.side_effect = [[1, 0, 2, 0], [3, 0, 4, 0]]
        values = await read_dwords_chunked(client, "DM0", 4, max_dwords_per_request=2)
        self.assertEqual(values, [1, 2, 3, 4])
        self.assertEqual(client.read_consecutive.await_args_list[0].args, ("DM0", 4))
        self.assertEqual(client.read_consecutive.await_args_list[1].args, ("DM4", 4))

    async def test_write_words_single_request(self) -> None:
        client = AsyncMock()
        await write_words_single_request(client, "DM0", [1, 2, 3])
        client.write_consecutive.assert_awaited_once_with("DM0", [1, 2, 3], data_format=".U")

    async def test_write_dwords_single_request(self) -> None:
        client = AsyncMock()
        await write_dwords_single_request(client, "DM0", [1, 2])
        client.write_consecutive.assert_awaited_once_with("DM0", [1, 0, 2, 0], data_format=".U")

    async def test_write_words_chunked(self) -> None:
        client = AsyncMock()
        await write_words_chunked(client, "DM0", [0, 1, 2, 3, 4, 5], max_per_request=4)
        self.assertEqual(client.write_consecutive.await_args_list[0].args, ("DM0", [0, 1, 2, 3]))
        self.assertEqual(client.write_consecutive.await_args_list[1].args, ("DM4", [4, 5]))

    async def test_write_dwords_chunked(self) -> None:
        client = AsyncMock()
        await write_dwords_chunked(client, "DM0", [1, 2, 3], max_dwords_per_request=2)
        self.assertEqual(client.write_consecutive.await_args_list[0].args, ("DM0", [1, 0, 2, 0]))
        self.assertEqual(client.write_consecutive.await_args_list[1].args, ("DM4", [3, 0]))

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
