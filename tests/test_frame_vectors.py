"""Cross-language spec compliance: HostLink frame body vectors.

Each vector in hostlink_frame_vectors.json defines the expected ASCII frame body
sent by the client for a given command. The same JSON is consumed by the .NET test
suite, ensuring Python and .NET send identical frames to the PLC.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from hostlink import HostLinkClient
from hostlink.device import DeviceAddress, parse_device
from hostlink.errors import HostLinkProtocolError

_VECTORS_PATH = Path(__file__).parent / "vectors" / "hostlink_frame_vectors.json"
_VECTORS = json.loads(_VECTORS_PATH.read_text())["vectors"]


class _FakeHostLinkClient(HostLinkClient):
    def __init__(self) -> None:
        super().__init__("127.0.0.1", plc_profile="keyence:kv-8000", port=8501, transport="tcp")
        self.sent_frames: list[bytes] = []

    def _exchange(self, payload: bytes) -> bytes:
        self.sent_frames.append(payload)
        return b"OK\r\n"


def _run_command(client: _FakeHostLinkClient, vec: dict[str, Any]) -> None:
    cmd = vec["command"]
    if cmd == "read":
        device, data_format = _device_and_format(vec["device"])
        client.read(device, data_format=data_format)
    elif cmd == "read_consecutive":
        device, data_format = _device_and_format(vec["device"])
        client.read_consecutive(device, vec["count"], data_format=data_format)
    elif cmd == "write":
        device, data_format = _device_and_format(vec["device"])
        client.write(device, vec["value"], data_format=data_format)
    elif cmd == "write_consecutive":
        device, data_format = _device_and_format(vec["device"])
        client.write_consecutive(device, vec["values"], data_format=data_format)
    elif cmd == "change_mode":
        client.change_mode(vec["mode"])
    elif cmd == "clear_error":
        client.clear_error()
    elif cmd == "check_error_no":
        client.check_error_no()
    elif cmd == "query_model":
        client.query_model()
    elif cmd == "confirm_operating_mode":
        client.confirm_operating_mode()
    elif cmd == "set_time":
        client.set_time(tuple(vec["args"]))  # type: ignore[arg-type]
    elif cmd == "forced_set":
        client.forced_set(vec["device"])
    elif cmd == "forced_reset":
        client.forced_reset(vec["device"])
    elif cmd == "forced_set_consecutive":
        client.forced_set_consecutive(vec["device"], vec["count"])
    elif cmd == "forced_reset_consecutive":
        client.forced_reset_consecutive(vec["device"], vec["count"])
    elif cmd == "read_format":
        client.read(vec["device"], data_format=vec["data_format"])
    elif cmd == "read_monitor_bits":
        client.read_monitor_bits()
    elif cmd == "read_monitor_words":
        client.read_monitor_words()
    elif cmd == "read_consecutive_legacy":
        device, data_format = _device_and_format(vec["device"])
        client.read_consecutive_legacy(device, vec["count"], data_format=data_format)
    elif cmd == "write_consecutive_legacy":
        device, data_format = _device_and_format(vec["device"])
        client.write_consecutive_legacy(device, vec["values"], data_format=data_format)
    elif cmd == "register_monitor_bits":
        client.register_monitor_bits(*vec["devices"])
    elif cmd == "register_monitor_words":
        client.register_monitor_words([_monitor_entry(device) for device in vec["devices"]])
    elif cmd == "write_set_value":
        device, data_format = _device_and_format(vec["device"])
        client.write_set_value(device, vec["value"], data_format=data_format)
    elif cmd == "write_set_value_consecutive":
        device, data_format = _device_and_format(vec["device"])
        client.write_set_value_consecutive(device, vec["values"], data_format=data_format)
    elif cmd == "switch_bank":
        client.switch_bank(vec.get("bank", vec.get("bank_no")))
    elif cmd == "read_expansion_unit_buffer":
        client.read_expansion_unit_buffer(
            vec.get("unit", vec.get("unit_no")),
            vec.get("address", vec.get("buffer_address")),
            vec["count"],
            data_format=vec.get("data_format", ""),
        )
    elif cmd == "write_expansion_unit_buffer":
        client.write_expansion_unit_buffer(
            vec.get("unit", vec.get("unit_no")),
            vec.get("address", vec.get("buffer_address")),
            vec["values"],
            data_format=vec.get("data_format", ""),
        )
    elif cmd == "read_comments":
        client.read_comments(vec["device"])
    else:
        raise ValueError(f"Unknown command: {cmd}")


def _device_and_format(device: str) -> tuple[str, str | None]:
    parsed = parse_device(device)
    base = DeviceAddress(parsed.device_type, parsed.number, "").to_text()
    return base, parsed.suffix or None


def _monitor_entry(device: str) -> str | tuple[str, str]:
    base, data_format = _device_and_format(device)
    return base if data_format is None else (base, data_format)


@pytest.mark.parametrize("vec", _VECTORS, ids=lambda v: v["id"])
def test_frame_body(vec: dict[str, Any]) -> None:
    client = _FakeHostLinkClient()
    try:
        _run_command(client, vec)
    except HostLinkProtocolError:
        if not client.sent_frames:
            raise
    except Exception:
        pass  # Ignore parse/value errors on the fake "OK" response; only care what was sent
    expected = (vec["expected_body"] + "\r").encode("ascii")
    assert client.sent_frames, f"[{vec['id']}] No frame was sent"
    assert client.sent_frames[-1] == expected, f"[{vec['id']}] got {client.sent_frames[-1]!r}, expected {expected!r}"
