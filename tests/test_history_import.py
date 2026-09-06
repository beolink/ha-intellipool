"""Verify the historic-import path in real Home Assistant.

Sets up the integration (so the sensor entities exist), then runs
async_import_history with a fake coordinator returning canned hourly history,
and asserts async_import_statistics is called with the right hourly points on
the water-temperature sensor's statistic id.
"""
import re
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.intellipool.const import (
    CONF_API_KEY,
    CONF_CONNECTION_TYPE,
    CONF_INSTALL_ID,
    CONN_TYPE_OFFICIAL,
    DOMAIN,
)
from custom_components.intellipool.history import async_import_history

PROBES_JSON = {
    "values": [
        {"typeInfo": "WATER_TEMP", "value": "+23.5", "unit": "°C"},
        {"typeInfo": "PH", "value": "6.8"},
        {"typeInfo": "OMEOTECH_FLAG_FILTRATION", "value": "true"},
    ]
}

# One day of hourly history (only a few hours have data).
HISTORY_RECORDS = [
    {
        "typeInfo": "WATER_TEMP",
        "min": "+23.3",
        "max": "+23.9",
        "avg": "+23.6",
        "values": ["+23.5", "+23.6", "--", "+23.9"] + ["--"] * 20,
    },
    {
        "typeInfo": "PH",
        "values": ["6.8", "6.7", "6.8", "6.8"] + ["--"] * 20,
    },
]


class _FakeApi:
    """Returns one canned day of hourly history for whichever date is asked."""

    def __init__(self):
        self.requested_dates = []

    async def get_history(self, date, type_date="DAY"):
        self.requested_dates.append(date)
        return HISTORY_RECORDS


class _FakeCoordinator:
    def __init__(self):
        self.api = _FakeApi()


async def test_history_import_writes_statistics(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "12345",
            CONF_API_KEY: "test-key",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    water = next(
        e for e in registry.entities.values()
        if e.unique_id == f"{entry.entry_id}_water_temperature"
    )

    coordinator = _FakeCoordinator()
    with patch(
        "custom_components.intellipool.history.async_import_statistics"
    ) as mock_import:
        result = await async_import_history(hass, entry, coordinator, days=1)

    # Exactly one day was requested, as YYYY-MM-DD.
    assert len(coordinator.api.requested_dates) == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", coordinator.api.requested_dates[0])

    # Water-temp sensor got 3 hourly points (indices 0,1,3; index 2 was '--').
    assert result[water.entity_id] == 3
    assert mock_import.called

    # Inspect one of the import calls for the water-temp sensor.
    calls = {
        c.args[1].get("statistic_id"): c.args[2] for c in mock_import.call_args_list
    }
    assert water.entity_id in calls
    water_stats = calls[water.entity_id]
    assert len(water_stats) == 3
    # Values are ascending by hour and carry the reading as mean/min/max.
    assert water_stats[0]["mean"] == 23.5
    assert water_stats[1]["mean"] == 23.6
    assert water_stats[2]["mean"] == 23.9
    # Statistics metadata targets the entity (source "recorder").
    meta = next(
        c.args[1] for c in mock_import.call_args_list
        if c.args[1].get("statistic_id") == water.entity_id
    )
    assert meta["source"] == "recorder"
    assert meta["has_mean"] is True

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
