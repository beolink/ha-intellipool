"""Climate entity for Intellipool pool heater."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_HEATING,
    KEY_TARGET_TEMP,
    KEY_WATER_TEMP,
)
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info

MIN_TEMP = 10.0
MAX_TEMP = 40.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntelliPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IntelliPoolClimate(coordinator, entry)])


class IntelliPoolClimate(CoordinatorEntity[IntelliPoolCoordinator], ClimateEntity):
    """Climate entity representing the pool heater."""

    _attr_has_entity_name = True
    _attr_name = "Poolvärmning"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5

    def __init__(
        self, coordinator: IntelliPoolCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = _device_info(entry)

    @property
    def current_temperature(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.water_temperature

    @property
    def target_temperature(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        if self.coordinator.data and self.coordinator.data.heating:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_send_command(
            KEY_HEATING, hvac_mode == HVACMode.HEAT
        )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is not None:
            await self.coordinator.async_send_command(KEY_TARGET_TEMP, temp)
