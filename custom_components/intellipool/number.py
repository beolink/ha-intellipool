"""Number entities for Intellipool setpoints (pH, ORP, temperature target)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_TARGET_ORP,
    KEY_TARGET_PH,
    KEY_TARGET_TEMP,
)
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info


@dataclass(frozen=True)
class IntelliPoolNumberDescription(NumberEntityDescription):
    data_key: str = ""
    command_key: str = ""


NUMBER_DESCRIPTIONS: tuple[IntelliPoolNumberDescription, ...] = (
    IntelliPoolNumberDescription(
        key="target_ph",
        data_key=KEY_TARGET_PH,
        command_key=KEY_TARGET_PH,
        name="pH-börvärde",
        icon="mdi:ph",
        native_min_value=6.8,
        native_max_value=7.8,
        native_step=0.1,
        mode=NumberMode.BOX,
    ),
    IntelliPoolNumberDescription(
        key="target_orp",
        data_key=KEY_TARGET_ORP,
        command_key=KEY_TARGET_ORP,
        name="ORP-börvärde",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        native_min_value=200,
        native_max_value=800,
        native_step=10,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntelliPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [IntelliPoolNumber(coordinator, entry, desc) for desc in NUMBER_DESCRIPTIONS]
    )


class IntelliPoolNumber(CoordinatorEntity[IntelliPoolCoordinator], NumberEntity):
    entity_description: IntelliPoolNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        description: IntelliPoolNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.as_dict().get(self.entity_description.data_key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send_command(
            self.entity_description.command_key, value
        )
