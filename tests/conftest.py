"""Pytest fixtures for the Home Assistant integration tests.

These run under pytest-homeassistant-custom-component (a real HA instance).
The pure-logic tests (test_*_parser.py, test_write_paths.py) are standalone
scripts run with `python3 tests/<file>.py` and are independent of this file.
"""
import pytest

# The pure-logic tests stub aiohttp at import time and are meant to run as
# standalone scripts (python3 tests/<file>.py). Keep pytest from collecting them
# so they never share a process with the real-HA test.
collect_ignore = [
    "test_summary_parser.py",
    "test_official_parser.py",
    "test_write_paths.py",
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the intellipool custom integration in every HA test."""
    yield
