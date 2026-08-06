from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hostlink import write_typed
from hostlink.errors import HostLinkProtocolError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        False,
        True,
    ],
)
async def test_write_typed_bit_preserves_native_boolean(value: bool) -> None:
    client = AsyncMock()
    await write_typed(client, "R0", "BIT", value)
    client.write.assert_awaited_once_with("R0", value, data_format=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [0, 1, "0", "1", "OFF", "ON", "false", "true", "", "disabled", 2, -1, 0.5, float("nan"), float("inf")],
)
async def test_write_typed_bit_rejects_ambiguous_values(value: int | float | str) -> None:
    client = AsyncMock()
    with pytest.raises(HostLinkProtocolError, match="BIT write value|direct bit"):
        await write_typed(client, "R0", "BIT", value)
    client.write.assert_not_awaited()
