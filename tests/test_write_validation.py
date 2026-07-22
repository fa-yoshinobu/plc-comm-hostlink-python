from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hostlink import write_typed
from hostlink.errors import HostLinkProtocolError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (False, 0),
        (True, 1),
        (0, 0),
        (1, 1),
        ("0", 0),
        ("1", 1),
        ("OFF", 0),
        ("ON", 1),
        ("false", 0),
        ("true", 1),
    ],
)
async def test_write_typed_bit_parses_explicit_values(value: int | bool | str, expected: int) -> None:
    client = AsyncMock()
    await write_typed(client, "R0", "BIT", value)
    client.write.assert_awaited_once_with("R0", expected, data_format=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["", "disabled", 2, -1, 0.5, float("nan"), float("inf")])
async def test_write_typed_bit_rejects_ambiguous_values(value: int | float | str) -> None:
    client = AsyncMock()
    with pytest.raises(HostLinkProtocolError, match="BIT write value|direct bit"):
        await write_typed(client, "R0", "BIT", value)
    client.write.assert_not_awaited()
