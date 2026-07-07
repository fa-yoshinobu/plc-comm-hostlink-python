"""Tests for canonical Host Link profile fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from hostlink.device_ranges import (
    _range_table,
    device_range_catalog_for_plc_profile,
)
from hostlink.plc_profiles import (
    available_plc_profiles,
    display_name,
)


def test_embedded_range_table_matches_canonical_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "kv_device_ranges.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    table = _range_table()

    expected_profile_ids = list(expected["profiles"])
    assert expected_profile_ids == available_plc_profiles()
    assert expected_profile_ids == [profile.name for profile in table.profiles]
    assert [profile.source_label for profile in table.profiles] == [
        profile["source_label"] for profile in expected["profiles"].values()
    ]
    assert [display_name(profile_id) for profile_id in expected_profile_ids] == [
        profile["display_name"] for profile in expected["profiles"].values()
    ]

    assert len(expected["device_range_rows"]) == len(table.rows)
    for expected_row, actual_row in zip(expected["device_range_rows"], table.rows, strict=True):
        assert expected_row["device_type"] == actual_row.device_type
        assert expected_row["notation"] == actual_row.notation.value
        assert list(expected_row["ranges"].values()) == list(actual_row.ranges)


def test_range_catalog_matches_canonical_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "kv_device_ranges.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    catalogs = {profile_id: device_range_catalog_for_plc_profile(profile_id) for profile_id in expected["profiles"]}

    for row in expected["device_range_rows"]:
        device_type = row["device_type"]
        for profile_id, expected_range in row["ranges"].items():
            entry = catalogs[profile_id].entry(device_type)
            assert entry is not None
            if expected_range == "-":
                assert not entry.supported
                assert entry.address_range is None
            else:
                assert entry.supported
                assert entry.address_range == expected_range
