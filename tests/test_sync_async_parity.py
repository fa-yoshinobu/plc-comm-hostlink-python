from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import pytest

from hostlink import AsyncHostLinkClient, HostLinkClient


class _RecordingSyncHostLinkClient(HostLinkClient):
    def __init__(self, response: bytes) -> None:
        super().__init__("127.0.0.1", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
        self.response = response
        self.sent_frames: list[bytes] = []

    def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.sent_frames.append(payload)
        return self.response


class _RecordingAsyncHostLinkClient(AsyncHostLinkClient):
    def __init__(self, response: bytes) -> None:
        super().__init__("127.0.0.1", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
        self.response = response
        self.sent_frames: list[bytes] = []

    async def _exchange(self, payload: bytes, **_: object) -> bytes:
        self.sent_frames.append(payload)
        return self.response


_SyncCall = Callable[[_RecordingSyncHostLinkClient], object]
_AsyncCall = Callable[[_RecordingAsyncHostLinkClient], Awaitable[object]]


@dataclass(frozen=True)
class _ParityCase:
    id: str
    sync_call: _SyncCall
    async_call: _AsyncCall
    response: bytes = b"OK\r\n"


_SET_TIME = datetime(2026, 3, 18, 15, 30, 45)

_PARITY_CASES = [
    _ParityCase(
        "change_mode",
        lambda client: client.change_mode("RUN"),
        lambda client: client.change_mode("RUN"),
    ),
    _ParityCase(
        "clear_error",
        lambda client: client.clear_error(),
        lambda client: client.clear_error(),
    ),
    _ParityCase(
        "check_error_no",
        lambda client: client.check_error_no(),
        lambda client: client.check_error_no(),
        response=b"000\r\n",
    ),
    _ParityCase(
        "query_model",
        lambda client: client.query_model(),
        lambda client: client.query_model(),
        response=b"63\r\n",
    ),
    _ParityCase(
        "confirm_operating_mode",
        lambda client: client.confirm_operating_mode(),
        lambda client: client.confirm_operating_mode(),
        response=b"1\r\n",
    ),
    _ParityCase(
        "set_time",
        lambda client: client.set_time(_SET_TIME),
        lambda client: client.set_time(_SET_TIME),
    ),
    _ParityCase(
        "forced_set",
        lambda client: client.forced_set("R0"),
        lambda client: client.forced_set("R0"),
    ),
    _ParityCase(
        "forced_reset",
        lambda client: client.forced_reset("R1"),
        lambda client: client.forced_reset("R1"),
    ),
    _ParityCase(
        "forced_set_consecutive",
        lambda client: client.forced_set_consecutive("R10", 5),
        lambda client: client.forced_set_consecutive("R10", 5),
    ),
    _ParityCase(
        "forced_reset_consecutive",
        lambda client: client.forced_reset_consecutive("R100", 3),
        lambda client: client.forced_reset_consecutive("R100", 3),
    ),
    _ParityCase(
        "read",
        lambda client: client.read("DM100", data_format=".U"),
        lambda client: client.read("DM100", data_format=".U"),
        response=b"123\r\n",
    ),
    _ParityCase(
        "read_format",
        lambda client: client.read("DM100", data_format=".H"),
        lambda client: client.read("DM100", data_format=".H"),
        response=b"00FF\r\n",
    ),
    _ParityCase(
        "read_consecutive",
        lambda client: client.read_consecutive("DM100", 2, data_format=".U"),
        lambda client: client.read_consecutive("DM100", 2, data_format=".U"),
        response=b"10 20\r\n",
    ),
    _ParityCase(
        "read_consecutive_legacy",
        lambda client: client.read_consecutive_legacy("DM100", 2, data_format=".U"),
        lambda client: client.read_consecutive_legacy("DM100", 2, data_format=".U"),
        response=b"10 20\r\n",
    ),
    _ParityCase(
        "write",
        lambda client: client.write("DM100", 1234, data_format=".U"),
        lambda client: client.write("DM100", 1234, data_format=".U"),
    ),
    _ParityCase(
        "write_hex_format",
        lambda client: client.write("DM100", 255, data_format=".H"),
        lambda client: client.write("DM100", 255, data_format=".H"),
    ),
    _ParityCase(
        "write_consecutive",
        lambda client: client.write_consecutive("DM100", [100, 200, 300], data_format=".U"),
        lambda client: client.write_consecutive("DM100", [100, 200, 300], data_format=".U"),
    ),
    _ParityCase(
        "write_consecutive_legacy",
        lambda client: client.write_consecutive_legacy("DM100", [100, 200, 300], data_format=".U"),
        lambda client: client.write_consecutive_legacy("DM100", [100, 200, 300], data_format=".U"),
    ),
    _ParityCase(
        "write_set_value",
        lambda client: client.write_set_value("T0", 1000, data_format=".D"),
        lambda client: client.write_set_value("T0", 1000, data_format=".D"),
    ),
    _ParityCase(
        "write_set_value_consecutive",
        lambda client: client.write_set_value_consecutive("C0", [10, 20], data_format=".D"),
        lambda client: client.write_set_value_consecutive("C0", [10, 20], data_format=".D"),
    ),
    _ParityCase(
        "register_monitor_bits",
        lambda client: client.register_monitor_bits("R0", "R1", "R2"),
        lambda client: client.register_monitor_bits("R0", "R1", "R2"),
    ),
    _ParityCase(
        "register_monitor_words",
        lambda client: client.register_monitor_words([("DM0", ".U"), ("DM1", ".U")]),
        lambda client: client.register_monitor_words([("DM0", ".U"), ("DM1", ".U")]),
    ),
    _ParityCase(
        "read_monitor_bits",
        lambda client: client.read_monitor_bits(),
        lambda client: client.read_monitor_bits(),
        response=b"1 0 1\r\n",
    ),
    _ParityCase(
        "read_monitor_words",
        lambda client: client.read_monitor_words(),
        lambda client: client.read_monitor_words(),
        response=b"100 200\r\n",
    ),
    _ParityCase(
        "read_comments",
        lambda client: client.read_comments("DM150"),
        lambda client: client.read_comments("DM150"),
        response=b"MAIN COMMENT                    \r\n",
    ),
    _ParityCase(
        "switch_bank",
        lambda client: client.switch_bank(5),
        lambda client: client.switch_bank(5),
    ),
    _ParityCase(
        "read_expansion_unit_buffer",
        lambda client: client.read_expansion_unit_buffer(1, 100, 2, data_format=".U"),
        lambda client: client.read_expansion_unit_buffer(1, 100, 2, data_format=".U"),
        response=b"123 456\r\n",
    ),
    _ParityCase(
        "write_expansion_unit_buffer",
        lambda client: client.write_expansion_unit_buffer(1, 200, [789, 1011], data_format=".S"),
        lambda client: client.write_expansion_unit_buffer(1, 200, [789, 1011], data_format=".S"),
    ),
]


def _run_sync(case: _ParityCase) -> list[bytes]:
    client = _RecordingSyncHostLinkClient(case.response)
    caught: Exception | None = None
    try:
        case.sync_call(client)
    except Exception as exc:
        caught = exc
    if not client.sent_frames:
        raise AssertionError(f"{case.id} did not send a sync frame") from caught
    return client.sent_frames


async def _run_async(case: _ParityCase) -> list[bytes]:
    client = _RecordingAsyncHostLinkClient(case.response)
    caught: Exception | None = None
    try:
        await case.async_call(client)
    except Exception as exc:
        caught = exc
    if not client.sent_frames:
        raise AssertionError(f"{case.id} did not send an async frame") from caught
    return client.sent_frames


@pytest.mark.parametrize("case", _PARITY_CASES, ids=lambda case: case.id)
@pytest.mark.asyncio
async def test_sync_async_commands_send_identical_frames(case: _ParityCase) -> None:
    sync_frames = _run_sync(case)
    async_frames = await _run_async(case)

    assert async_frames == sync_frames
