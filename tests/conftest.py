"""Pytest fixtures for the Home Assistant integration tests.

These run under pytest-homeassistant-custom-component (a real HA instance).
The pure-logic tests (test_*_parser.py, test_write_paths.py) are standalone
scripts run with `python3 tests/<file>.py` and are independent of this file.
"""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the intellipool custom integration in every HA test."""
    yield
