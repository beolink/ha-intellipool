"""DataUpdateCoordinator for Intellipool."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, IntelliPoolAPI, PoolData
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IntelliPoolCoordinator(DataUpdateCoordinator[PoolData]):
    """Polls the Intellipool controller and distributes data to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IntelliPoolAPI,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> PoolData:
        try:
            return await self.api.get_data()
        except CannotConnect as err:
            raise UpdateFailed(f"Intellipool connection error: {err}") from err

    async def async_send_command(self, key: str, value: Any) -> None:
        """Send a command and immediately refresh data."""
        await self.api.send_command(key, value)
        await self.async_request_refresh()
