"""Pentair Intellipool integration for Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, IntelliPoolAPI, IntelliPoolOfficialAPI
from .const import (
    ATTR_DAYS,
    CONF_API_KEY,
    CONF_CONNECTION_TYPE,
    CONF_INSTALL_ID,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_STALE_MINUTES,
    CONN_TYPE_LOCAL,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
    SERVICE_IMPORT_HISTORY,
)
from .coordinator import IntelliPoolCoordinator
from .history import async_import_history

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TEXT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intellipool from a config entry."""
    conn_type = entry.data[CONF_CONNECTION_TYPE]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    api = IntelliPoolAPI(
        connection_type=conn_type,
        host=entry.data.get(CONF_HOST),
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        ssl=entry.data.get(CONF_SSL, False),
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        pool_id=entry.data.get(CONF_POOL_ID),
        install_id=entry.data.get(CONF_INSTALL_ID),
        api_key=entry.data.get(CONF_API_KEY),
        session=async_get_clientsession(hass),
    )

    try:
        await api.async_init()
    except CannotConnect as err:
        _LOGGER.error("Intellipool connection failed: %s", err)
        return False

    # Optional failsafe: the official API, used when the primary goes stale/down.
    # (Not built when the primary IS the official API.)
    fallback = None
    api_key = entry.data.get(CONF_API_KEY)
    install_id = entry.data.get(CONF_INSTALL_ID)
    if conn_type != "official" and api_key and install_id:
        fallback = IntelliPoolOfficialAPI(
            install_id=install_id,
            api_key=api_key,
            session=async_get_clientsession(hass),
        )
        _LOGGER.debug("Official-API failsafe enabled (install %s)", install_id)

    coordinator = IntelliPoolCoordinator(
        hass,
        api,
        scan_interval,
        fallback=fallback,
        stale_minutes=entry.options.get(
            CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: IntelliPoolCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (e.g. changed scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


IMPORT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DAYS, default=DEFAULT_HISTORY_DAYS): vol.All(
            int, vol.Range(min=1, max=365)
        ),
    }
)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY):
        return

    async def _handle_import_history(call: ServiceCall) -> None:
        days = call.data.get(ATTR_DAYS, DEFAULT_HISTORY_DAYS)
        for entry_id, coordinator in list(hass.data.get(DOMAIN, {}).items()):
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            try:
                await async_import_history(hass, entry, coordinator, days)
            except CannotConnect as err:
                _LOGGER.warning(
                    "History import skipped for %s: %s", entry.title, err
                )

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        _handle_import_history,
        schema=IMPORT_HISTORY_SCHEMA,
    )
