"""DataUpdateCoordinator for Intellipool with an official-API failsafe."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    CannotConnect,
    IntelliPoolAPI,
    IntelliPoolOfficialAPI,
    PoolData,
    merge_pool_data,
)
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
    SOURCE_FALLBACK,
    SOURCE_PRIMARY,
)

_LOGGER = logging.getLogger(__name__)


class IntelliPoolCoordinator(DataUpdateCoordinator[PoolData]):
    """Polls Intellipool; falls back to the official API when the primary fails.

    The primary source (usually the intellipool.eu scrape) is richer. The
    optional fallback (official domotique-piscine.eu API) is used when the
    primary raises an error OR when its data stops updating (stale timestamp).
    In the fallback case the primary's last-known extra fields (pump RPM/power,
    setpoints, battery…) are merged in so those entities don't go unavailable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: IntelliPoolAPI,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        fallback: IntelliPoolOfficialAPI | None = None,
        stale_minutes: int = DEFAULT_STALE_MINUTES,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._fallback = fallback
        self._stale = timedelta(minutes=stale_minutes)
        self._last_updated_value: str | None = None
        self._last_change_at = None  # utc time the primary timestamp last moved
        self._last_primary: PoolData | None = None

    def _note_primary_freshness(self, data: PoolData) -> bool:
        """Track the primary timestamp; return True if the data is fresh."""
        now = dt_util.utcnow()
        stamp = data.updated
        if stamp != self._last_updated_value:
            self._last_updated_value = stamp
            self._last_change_at = now
        if self._last_change_at is None:
            return True
        # No timestamp at all → cannot judge staleness, treat as fresh.
        if stamp is None:
            return True
        return (now - self._last_change_at) <= self._stale

    async def _async_update_data(self) -> PoolData:
        primary_data: PoolData | None = None
        primary_error: Exception | None = None
        try:
            primary_data = await self.api.get_data()
        except (CannotConnect, Exception) as err:  # noqa: BLE001
            primary_error = err
            _LOGGER.debug("Primary source failed: %s", err)

        if primary_data is not None:
            self._last_primary = primary_data
            if self._note_primary_freshness(primary_data):
                primary_data.source = SOURCE_PRIMARY
                return primary_data
            _LOGGER.info(
                "Primary data is stale (unchanged > %s); trying failsafe",
                self._stale,
            )

        # Primary failed or is stale → use the official API failsafe.
        if self._fallback is not None:
            try:
                fb = await self._fallback.get_data()
                fb.source = SOURCE_FALLBACK
                # Fill fields the official API lacks from the last good primary.
                merged = merge_pool_data(fb, self._last_primary)
                return merged
            except (CannotConnect, Exception) as fb_err:  # noqa: BLE001
                _LOGGER.debug("Failsafe source also failed: %s", fb_err)
                if primary_data is not None:
                    # Stale but present beats nothing.
                    primary_data.source = SOURCE_PRIMARY
                    return primary_data
                raise UpdateFailed(
                    f"Both sources failed (primary: {primary_error}, "
                    f"failsafe: {fb_err})"
                ) from fb_err

        # No fallback configured.
        if primary_data is not None:
            primary_data.source = SOURCE_PRIMARY
            return primary_data
        raise UpdateFailed(f"Intellipool connection error: {primary_error}")

    async def async_send_command(self, key: str, value: Any) -> None:
        """Send a command and immediately refresh data."""
        await self.api.send_command(key, value)
        await self.async_request_refresh()
