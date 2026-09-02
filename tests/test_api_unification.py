from __future__ import annotations

import pytest

import hostlink
from hostlink import (
    AsyncHostLinkClient,
    HostLinkClient,
    HostLinkCommentEncoding,
    read_comment,
    read_comments,
    read_dwords,
    write_named,
)


class _RecordingSyncClient(HostLinkClient):
    def __init__(self, response: bytes = b"OK\r\n") -> None:
        super().__init__("127.0.0.1", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
        self.response = response
        self.sent: list[bytes] = []

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.sent.append(payload)
        return self.response


class _RecordingAsyncClient(AsyncHostLinkClient):
    def __init__(self, response: bytes = b"OK\r\n") -> None:
        super().__init__("127.0.0.1", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
        self.response = response
        self.sent: list[bytes] = []

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.sent.append(payload)
        return self.response


def test_sync_canonical_names_and_deprecated_aliases_have_identical_wire_and_results() -> None:
    canonical_error = _RecordingSyncClient(b"000\r\n")
    alias_error = _RecordingSyncClient(b"000\r\n")
    assert canonical_error.read_error_number() == "000"
    with pytest.warns(DeprecationWarning, match="read_error_number"):
        assert alias_error.check_error_no() == "000"
    assert alias_error.sent == canonical_error.sent == [b"?E\r"]

    canonical_comment = _RecordingSyncClient(b"LABEL\r\n")
    alias_comment = _RecordingSyncClient(b"LABEL\r\n")
    assert canonical_comment.read_comment("DM0", HostLinkCommentEncoding.UTF8) == "LABEL"
    with pytest.warns(DeprecationWarning, match="read_comment"):
        assert alias_comment.read_comments("DM0", HostLinkCommentEncoding.UTF8) == "LABEL"
    assert alias_comment.sent == canonical_comment.sent == [b"RDC DM0\r"]

    canonical_preset = _RecordingSyncClient()
    alias_preset = _RecordingSyncClient()
    canonical_preset.write_timer_counter_preset("T0", 123, data_format=".D")
    canonical_preset.write_timer_counter_preset_consecutive("C0", [10, 20], data_format=".D")
    with pytest.warns(DeprecationWarning, match="write_timer_counter_preset"):
        alias_preset.write_set_value("T0", 123, data_format=".D")
    with pytest.warns(DeprecationWarning, match="write_timer_counter_preset_consecutive"):
        alias_preset.write_set_value_consecutive("C0", [10, 20], data_format=".D")
    assert alias_preset.sent == canonical_preset.sent == [b"WS T0.D 123\r", b"WSS C0.D 2 10 20\r"]


@pytest.mark.asyncio
async def test_async_canonical_names_and_deprecated_aliases_have_identical_wire_and_results() -> None:
    canonical_error = _RecordingAsyncClient(b"000\r\n")
    alias_error = _RecordingAsyncClient(b"000\r\n")
    assert await canonical_error.read_error_number() == "000"
    with pytest.warns(DeprecationWarning, match="read_error_number"):
        assert await alias_error.check_error_no() == "000"
    assert alias_error.sent == canonical_error.sent == [b"?E\r"]

    canonical_comment = _RecordingAsyncClient(b"LABEL\r\n")
    alias_comment = _RecordingAsyncClient(b"LABEL\r\n")
    assert await canonical_comment.read_comment("DM0", HostLinkCommentEncoding.UTF8) == "LABEL"
    with pytest.warns(DeprecationWarning, match="read_comment"):
        assert await alias_comment.read_comments("DM0", HostLinkCommentEncoding.UTF8) == "LABEL"
    assert alias_comment.sent == canonical_comment.sent == [b"RDC DM0\r"]

    canonical_preset = _RecordingAsyncClient()
    alias_preset = _RecordingAsyncClient()
    await canonical_preset.write_timer_counter_preset("T0", 123, data_format=".D")
    await canonical_preset.write_timer_counter_preset_consecutive("C0", [10, 20], data_format=".D")
    with pytest.warns(DeprecationWarning, match="write_timer_counter_preset"):
        await alias_preset.write_set_value("T0", 123, data_format=".D")
    with pytest.warns(DeprecationWarning, match="write_timer_counter_preset_consecutive"):
        await alias_preset.write_set_value_consecutive("C0", [10, 20], data_format=".D")
    assert alias_preset.sent == canonical_preset.sent == [b"WS T0.D 123\r", b"WSS C0.D 2 10 20\r"]


@pytest.mark.asyncio
async def test_high_level_renames_are_exported_and_deprecated_aliases_forward_once() -> None:
    assert hostlink.read_comment is read_comment
    assert hostlink.write_named is write_named

    canonical = _RecordingAsyncClient(b"COMMENT\r\n")
    alias = _RecordingAsyncClient(b"COMMENT\r\n")
    assert await read_comment(canonical, "DM0", HostLinkCommentEncoding.UTF8) == "COMMENT"
    with pytest.warns(DeprecationWarning, match="read_comment"):
        assert await read_comments(alias, "DM0", HostLinkCommentEncoding.UTF8) == "COMMENT"
    assert alias.sent == canonical.sent == [b"RDC DM0\r"]

    dword_client = _RecordingAsyncClient(b"1 0\r\n")
    with pytest.warns(DeprecationWarning, match="read_dwords_single_request"):
        assert await read_dwords(dword_client, "DM0", 1) == [1]
    assert dword_client.sent == [b"RDS DM0.U 2\r"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"DM100:U": 123, "DM101:U": 456}, b"WRS DM100.U 2 123 456\r"),
        ({"DM0:D": 0x12345678, "DM2:D": 0x89ABCDEF}, b"WRS DM0.U 4 22136 4660 52719 35243\r"),
        ({"DM10:L": -2}, b"WRS DM10.U 2 65534 65535\r"),
        ({"DM200:F": 2.5, "DM202:F": 3.5}, b"WRS DM200.U 4 0 16416 0 16480\r"),
        ({"R115:BIT": True, "R200:BIT": False}, b"WRS R115 2 1 0\r"),
        ({"T10:D": 111, "T11:D": 222}, b"WSS T10.D 2 111 222\r"),
        ({"Z1:D": 70000, "Z2:D": 80000}, b"WRS Z1.D 2 70000 80000\r"),
        ({"M100:U": 1}, b"WR M100.U 1\r"),
        ({"DM300:U,3": [1, 2, 3]}, b"WRS DM300.U 3 1 2 3\r"),
    ],
)
async def test_write_named_valid_updates_send_exactly_one_expected_request(
    updates: dict[str, object], expected: bytes
) -> None:
    client = _RecordingAsyncClient()
    await write_named(client, updates)  # type: ignore[arg-type]
    assert client.sent == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {},
        {"DM0:U": 1, "DM1:S": -1},
        {"DM0:U": 1, "DM2:U": 2},
        {"DM1:U": 1, "DM0:U": 2},
        {"DM0:U": 1, "dm000:U": 2},
        {"DM0:U": 1, "AT0:D": 2},
        {"DM0.0": True},
        {"DM0:U,2": [1]},
        {"DM0:U": 1, "DM1:U": 70000},
    ],
)
async def test_write_named_rejects_complete_invalid_update_before_any_send(updates: dict[str, object]) -> None:
    client = _RecordingAsyncClient()
    with pytest.raises((TypeError, ValueError, hostlink.HostLinkProtocolError)):
        await write_named(client, updates)  # type: ignore[arg-type]
    assert client.sent == []


@pytest.mark.asyncio
async def test_write_named_rejects_request_limit_before_send() -> None:
    oversized_updates = (
        {f"DM{index}:U": index & 0xFFFF for index in range(1001)},
        {f"DM{index * 2}:D": index for index in range(501)},
        {f"T{index}:D": index for index in range(121)},
    )
    for updates in oversized_updates:
        client = _RecordingAsyncClient()
        with pytest.raises((ValueError, hostlink.HostLinkProtocolError)):
            await write_named(client, updates)
        assert client.sent == []


@pytest.mark.asyncio
async def test_write_named_accepts_each_exact_request_limit_as_one_send() -> None:
    boundary_updates = (
        {f"DM{index}:U": index & 0xFFFF for index in range(1000)},
        {f"DM{index * 2}:D": index for index in range(500)},
        {f"T{index}:D": index for index in range(120)},
    )
    for updates in boundary_updates:
        client = _RecordingAsyncClient()
        await write_named(client, updates)
        assert len(client.sent) == 1


def test_sync_helper_bulk_copy_was_not_added() -> None:
    assert not hasattr(HostLinkClient, "write_named")
