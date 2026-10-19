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
from homeassistant.data_entry_flow import FlowResultType
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
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Intellipool (official)",
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "12345",
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

    # Schedule text entities are created.
    sched = next(
        (e for e in ours if e.unique_id == f"{entry.entry_id}_schedule_filtration"),
        None,
    )
    assert sched is not None
    assert sched.domain == "text"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


def test_reporting_stays_on_but_readings_are_opt_in() -> None:
    """Two separate switches, both opt-in.

    stats_enabled decides whether a report is sent at all, readings_enabled
    whether the pool's measured values ride along. Neither is assumed.
    """
    from custom_components.intellipool.stats import readings_enabled, stats_enabled

    never_asked = MockConfigEntry(domain=DOMAIN, data={}, options={})
    assert stats_enabled(never_asked) is False
    assert readings_enabled(never_asked) is False

    said_yes_to_report = MockConfigEntry(domain=DOMAIN, data={"send_statistics": True})
    assert stats_enabled(said_yes_to_report) is True
    assert readings_enabled(said_yes_to_report) is False

    said_yes = MockConfigEntry(
        domain=DOMAIN, data={"send_statistics": True, "send_readings": True},
    )
    assert readings_enabled(said_yes) is True
    assert stats_enabled(said_yes) is True

    reporting_off = MockConfigEntry(
        domain=DOMAIN, data={}, options={"send_statistics": False},
    )
    assert stats_enabled(reporting_off) is False

    # Options win over the stored answer, in both directions.
    readings_off_later = MockConfigEntry(
        domain=DOMAIN, data={"send_readings": True},
        options={"send_readings": False},
    )
    assert readings_enabled(readings_off_later) is False
    readings_on_later = MockConfigEntry(
        domain=DOMAIN, data={}, options={"send_readings": True},
    )
    assert readings_enabled(readings_on_later) is True


async def test_options_flow_opens_and_saves(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Configure must not raise AttributeError.

    config_entry is a read-only property on OptionsFlow, so an options flow
    that assigns to it dies the moment the user picks Configure. This walks the
    real flow instead of inspecting the class.
    """
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "12345",
            CONF_API_KEY: "key",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    defaults = result["data_schema"]({})
    # Migrated from version 1, so the entry's existing reporting state is
    # recorded rather than reset.
    assert defaults["send_statistics"] is True
    assert defaults["send_readings"] is False

    done = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 60, "stale_minutes": 30,
                    "send_statistics": True, "send_readings": False},
    )
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert done["data"]["scan_interval"] == 60


async def test_config_flow_asks_before_reporting_anything(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Setup ends on the statistics question, and both boxes default to no."""
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INSTALL_ID: "12345", CONF_API_KEY: "key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "statistics"
    defaults = result["data_schema"]({})
    assert defaults["send_statistics"] is False
    assert defaults["send_readings"] is False

    # Accepting the form as presented must not switch anything on.
    created = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert created["type"] is FlowResultType.CREATE_ENTRY
    assert created["data"]["send_statistics"] is False
    assert created["data"]["send_readings"] is False


async def test_readings_are_left_out_of_the_payload_without_consent(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The gate is in the payload, not only in the form.

    Without consent the report still goes, carrying models and features, but
    the measured values are absent.
    """
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    aioclient_mock.post(re.compile(r"https://stats\.rnet\.se/"), json={"status": "ok"})

    base = {
        CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
        CONF_INSTALL_ID: "12345",
        CONF_API_KEY: "key",
    }
    silent = MockConfigEntry(domain=DOMAIN, data=base)
    silent.add_to_hass(hass)
    assert await hass.config_entries.async_setup(silent.entry_id)
    await hass.async_block_till_done()
    reporter = _reporter_for(hass, silent)
    assert "metrics" not in reporter.extra()
    assert reporter.extra()["models"] == ["intp_1010b"]

    consented = MockConfigEntry(domain=DOMAIN, data={**base, "send_readings": True})
    consented.add_to_hass(hass)
    assert await hass.config_entries.async_setup(consented.entry_id)
    await hass.async_block_till_done()
    assert "metrics" in _reporter_for(hass, consented).extra()


def _reporter_for(hass: HomeAssistant, entry: MockConfigEntry):
    """The reporter is held by the entry's unload callbacks, not hass.data."""
    for job in entry._on_unload or []:
        holder = getattr(job, "__self__", None)
        if holder is not None and hasattr(holder, "extra"):
            return holder
    raise AssertionError("no reporter registered for this entry")


async def test_upgrading_does_not_silence_an_existing_install(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reporting became opt-in, but entries that were already reporting keep going.

    The migration writes the state they had into the entry, so flipping the
    default cannot quietly switch anyone off, and the switch stays visible
    under Configure.
    """
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    aioclient_mock.post(re.compile(r"https://stats\.rnet\.se/"), json={"status": "ok"})
    from custom_components.intellipool.stats import readings_enabled, stats_enabled

    old = MockConfigEntry(
        domain=DOMAIN, version=1,
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "12345",
            CONF_API_KEY: "key",
        },
    )
    old.add_to_hass(hass)
    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()

    assert old.version == 2
    assert stats_enabled(old) is True
    # The readings were never agreed to, so they stay out.
    assert readings_enabled(old) is False
    assert "metrics" not in _reporter_for(hass, old).extra()


async def test_an_install_that_had_opted_out_stays_out(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A switched-off entry must not be switched back on by the migration."""
    aioclient_mock.get(
        re.compile(r"https://api\.domotique-piscine\.eu/api/install/12345/probes"),
        json=PROBES_JSON,
    )
    from custom_components.intellipool.stats import stats_enabled

    off = MockConfigEntry(
        domain=DOMAIN, version=1,
        data={
            CONF_CONNECTION_TYPE: CONN_TYPE_OFFICIAL,
            CONF_INSTALL_ID: "12345",
            CONF_API_KEY: "key",
        },
        options={"send_statistics": False},
    )
    off.add_to_hass(hass)
    assert await hass.config_entries.async_setup(off.entry_id)
    await hass.async_block_till_done()

    assert off.version == 2
    assert stats_enabled(off) is False
