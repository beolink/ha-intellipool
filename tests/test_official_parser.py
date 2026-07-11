"""Tests for the official domotique-piscine.eu /probes parser and failsafe merge.

Standalone (no Home Assistant install needed):

    python3 tests/test_official_parser.py

Verified against real INTP-1010B output captured 2026-07-11.
"""
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


def _load_api():
    aiohttp = types.ModuleType("aiohttp")

    class _CT:
        def __init__(self, *a, **k):
            pass

    aiohttp.ClientTimeout = _CT
    aiohttp.ClientSession = object
    aiohttp.ClientError = Exception
    aiohttp.ClientConnectionError = Exception
    aiohttp.ClientConnectorError = Exception
    aiohttp.BasicAuth = lambda *a, **k: None
    aiohttp.TCPConnector = lambda *a, **k: None
    sys.modules["aiohttp"] = aiohttp

    pkg = types.ModuleType("intellipool")
    pkg.__path__ = [os.path.join(ROOT, "custom_components", "intellipool")]
    sys.modules["intellipool"] = pkg

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    base = os.path.join(ROOT, "custom_components", "intellipool")
    load("intellipool.const", os.path.join(base, "const.py"))
    return load("intellipool.api", os.path.join(base, "api.py"))


SAMPLE = {
    "values": [
        {"typeInfo": "OMEOTECH_FLAG_HEATING", "value": "false"},
        {"typeInfo": "OMEOTECH_FLAG_FILTRATION", "value": "true"},
        {"typeInfo": "ORP", "value": "104", "unit": "mV"},
        {"typeInfo": "OMEOTECH_FLAG_LIGHTING", "value": "false"},
        {"typeInfo": "AIR_TEMP", "value": "+24.0", "unit": "°C"},
        {"typeInfo": "DATETIME", "value": "2026/07/11 12:11"},
        {"typeInfo": "OMEOTECH_FLAG_AUX1", "value": "false"},
        {"typeInfo": "WATER_TEMP", "value": "+23.5", "unit": "°C"},
        {"typeInfo": "CONDUCTIVITY", "value": "2.3", "unit": "g/L"},
        {"typeInfo": "PH", "value": "6.8"},
    ]
}

EXPECTED = {
    "water_temperature": 23.5,
    "air_temperature": 24.0,
    "ph": 6.8,
    "orp": 104.0,
    "salinity": 2.3,
    "filtration": True,
    "pump": True,
    "heating": False,
    "light": False,
    "aux_1": False,
    "updated": "2026/07/11 12:11",
}


def test_parse_official():
    api = _load_api()
    pd = api._map_official_response(SAMPLE)
    data = pd.as_dict()
    for key, exp in EXPECTED.items():
        # `updated` is an attribute, not an exposed entity key.
        got = pd.updated if key == "updated" else data.get(key)
        assert got == exp, f"{key}: expected {exp!r}, got {got!r}"


def test_failsafe_merge():
    """The official base should be enriched with the primary's extra fields."""
    api = _load_api()
    official = api._map_official_response(SAMPLE)  # no pump rpm/power/setpoints
    primary = api.PoolData(
        water_temperature=99.0,  # should NOT overwrite official's value
        pump_speed=700.0,        # should fill in (official lacks it)
        pump_power=45.0,
        target_temperature=25.0,
        battery_voltage=5.95,
    )
    merged = api.merge_pool_data(official, primary)
    assert merged.water_temperature == 23.5, "must keep official base value"
    assert merged.pump_speed == 700.0, "must fill missing field from primary"
    assert merged.pump_power == 45.0
    assert merged.target_temperature == 25.0
    assert merged.battery_voltage == 5.95


if __name__ == "__main__":
    test_parse_official()
    test_failsafe_merge()
    print("All official-API + failsafe tests passed.")
