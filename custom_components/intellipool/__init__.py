"""Pentair Intellipool integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, IntelliPoolAPI
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONN_TYPE_LOCAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import IntelliPoolCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.NUMBER,
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
    )

    try:
        await api.async_init()
    except CannotConnect as err:
        _LOGGER.error("Intellipool connection failed: %s", err)
        return False

    coordinator = IntelliPoolCoordinator(hass, api, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
