"""Real-Home-Assistant pipeline test (hermetic).

Loads the integration in a genuine HA instance and asserts that pool data flows
all the way into HA sensor entities. The official-API HTTP call is mocked with
the EXACT JSON a real INTP-1010B returned on 2026-07-11, so the full HA wiring
(config entry → coordinator → entity platforms → states) runs against real-shaped
data — no network, no secrets.

Run:  ha-venv/bin/pytest tests/test_ha_integration.py -v
"""
import re

from homeassistant.config_entries import ConfigEntryState
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

# Exact /probes payload captured from the real device.
PROBES_JSON = {
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


async def test_data_flows_into_ha_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/45558/probes"),
        json=PROBES_JSON,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Intellipool (official)",
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "45558",
            CONF_API_KEY: "test-key",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 1) Entry loaded cleanly in real HA.
    assert entry.state is ConfigEntryState.LOADED

    # 2) Coordinator ingested the data.
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data.water_temperature == 23.5
    assert coordinator.data.ph == 6.8
    assert coordinator.data.orp == 104.0
    assert coordinator.data.source == "primary"

    # 3) The sensor entities exist and carry the live values.
    registry = er.async_get(hass)
    ours = [e for e in registry.entities.values() if e.config_entry_id == entry.entry_id]
    assert ours, "no entities registered"

    def sensor_state(key):
        uid = f"{entry.entry_id}_{key}"
        ent = next(
            (e for e in ours if e.unique_id == uid and e.domain == "sensor"), None
        )
        assert ent is not None, f"sensor {key} not registered"
        st = hass.states.get(ent.entity_id)
        assert st is not None
        return st.state

    assert sensor_state("water_temperature") == "23.5"
    assert sensor_state("ph") == "6.8"
    assert sensor_state("orp") == "104.0"
    assert sensor_state("salinity") == "2.3"
    assert sensor_state("data_source") == "primary"

    # Switch reflects filtration=true → pump on.
    pump = next(
        (e for e in ours if e.unique_id == f"{entry.entry_id}_pump"), None
    )
    assert pump is not None
    assert hass.states.get(pump.entity_id).state == "on"

    # Mode select entities are created (current option unknown via official API).
    filt_select = next(
        (e for e in ours if e.unique_id == f"{entry.entry_id}_filtration_mode"), None
    )
    assert filt_select is not None
    assert filt_select.domain == "select"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
