"""Regression test for the intellipool.eu /pool/poolSummary HTML parser.

Runs standalone (no Home Assistant install needed):

    python3 tests/test_summary_parser.py

Verified against real INTP-1010B output captured 2026-07-11.
"""
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


def _load_api():
    """Load intellipool.api in isolation, stubbing aiohttp and the package init."""
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


EXPECTED = {
    "water_temperature": 23.5,
    "air_temperature": 23.5,
    "ph": 6.8,
    "orp": 104.0,
    "salinity": 2.3,
    "pump_speed": 700.0,
    "pump_power": 45.0,
    "battery_voltage": 5.95,
    "signal_strength": -80.0,
    "info_message": "Exceeding disinfectant regulation",
    "pump": True,
    "heating": False,
    "light": False,
    "filtration": True,
    "ph_dosing": False,
    "orp_dosing": True,
    "target_temperature": 25.0,
    "target_ph": 7.0,
    "target_orp": 550.0,
}


def test_parse_summary():
    api = _load_api()
    raw = open(os.path.join(HERE, "sample_summary.html")).read()
    data = api._map_cloud_response(raw).as_dict()
    for key, exp in EXPECTED.items():
        assert data.get(key) == exp, f"{key}: expected {exp!r}, got {data.get(key)!r}"


def test_extract_serial():
    api = _load_api()
    client = api.IntelliPoolCloudAPI("user", "pass")
    client._extract_serial("x javascript:displaySummary('35558'); y")
    assert client._pool_id == "35558"


if __name__ == "__main__":
    test_parse_summary()
    test_extract_serial()
    print("All parser tests passed.")
