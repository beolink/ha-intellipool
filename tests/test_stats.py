"""What the anonymous daily report may contain (stats_extra.py).

Runs standalone (no Home Assistant install needed):

    python3 tests/test_stats.py

Not that the numbers are pretty, but that only agreed values can leave: pool
readings inside a physically sane range, a fixed model slug and nothing that
came from the device or the user as text.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "custom_components", "intellipool"))

import stats_extra  # noqa: E402


def test_transport_is_reported_from_a_closed_set():
    assert stats_extra.connection_slug("cloud") == "cloud"
    assert stats_extra.connection_slug("OFFICIAL") == "official"
    assert stats_extra.connection_slug("min egen server") == "other"
    assert stats_extra.connection_slug(None) == "unknown"


def test_readings_are_mapped_and_rounded():
    m = stats_extra.readings({
        "water_temperature": 27.44, "air_temperature": 31.2, "ph": 7.26,
        "orp": 712.6, "salinity": 3400.0, "pump_speed": 2400.0,
    })
    assert m == {"water_temp_c": 27.4, "outdoor_mean_c": 31.2, "ph": 7.3,
                 "orp_mv": 712.6, "salt_ppm": 3400.0, "pump_rpm": 2400.0}


def test_nonsense_readings_are_dropped_not_reported():
    # 9999 is the classic "sensor missing" sentinel; reporting it would drag
    # every fleet median it touches.
    assert stats_extra.readings({"ph": 9999, "water_temperature": -300}) == {}
    assert stats_extra.readings({"ph": None}) == {}
    assert stats_extra.readings({"ph": "sju"}) == {}
    assert stats_extra.readings(None) == {}


def test_booleans_are_not_mistaken_for_measurements():
    assert stats_extra.readings({"ph": True}) == {}


def test_report_holds_only_the_agreed_keys():
    extra = stats_extra.build_extra(
        connection="cloud", has_failsafe=True, control_enabled=True,
        heating=True, chlorinator=False,
        data={"water_temperature": 27.0},
    )
    assert set(extra) == {"models", "features", "metrics"}
    assert extra["models"] == ["intp_1010b"]
    assert set(extra["features"]) == {"cloud", "official_api", "local", "failsafe",
                                      "control", "heating", "chlorinator"}
    for value in extra["features"].values():
        assert isinstance(value, bool)


def test_pool_id_can_not_reach_the_report():
    # The serial and the pool id live in the same data the coordinator holds.
    extra = stats_extra.build_extra(
        connection="cloud", has_failsafe=False, control_enabled=False,
        heating=False, chlorinator=False,
        data={"pool_id": 35558, "serial": "35558", "water_temperature": 27.0},
    )
    assert extra["metrics"] == {"water_temp_c": 27.0}


if __name__ == "__main__":
    test_transport_is_reported_from_a_closed_set()
    test_readings_are_mapped_and_rounded()
    test_nonsense_readings_are_dropped_not_reported()
    test_booleans_are_not_mistaken_for_measurements()
    test_report_holds_only_the_agreed_keys()
    test_pool_id_can_not_reach_the_report()
    print("All statistics tests passed.")
