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
from homeassistant.const import REVOLUTIONS_PER_MINUTE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    INTELLIFLO_SPEED_MAP,
    INTELLIFLO_SPEED_STEP,
    KEY_TARGET_ORP,
    KEY_TARGET_PH,
    KEY_TARGET_TEMP,
)
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info

# IntelliFlo speed numbers: HA command key → (device field, display name).
INTELLIFLO_SPEEDS = (
    ("speed_setpoint", "setpoint_intelliflo_speed", "Filtreringshastighet (börvärde)"),
    ("speed_electrolysis", "electrolysis_filtration_speed", "Varvtal elektrolys"),
    ("speed_heating", "heating_filtration_speed", "Varvtal uppvärmning"),
    ("speed_aux1", "aux1_filtration_speed", "Varvtal Aux 1"),
    ("speed_choc", "mode_choc_speed", "Varvtal chock"),
)


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
    entities: list[NumberEntity] = [
        IntelliPoolNumber(coordinator, entry, desc) for desc in NUMBER_DESCRIPTIONS
    ]
    entities += [
        IntelliPoolIntelliFloSpeed(coordinator, entry, key, field, name)
        for key, field, name in INTELLIFLO_SPEEDS
    ]
    async_add_entities(entities)


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


class IntelliPoolIntelliFloSpeed(
    CoordinatorEntity[IntelliPoolCoordinator], NumberEntity
):
    """A single IntelliFlo variable-speed setting (RPM)."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = REVOLUTIONS_PER_MINUTE
    _attr_native_step = INTELLIFLO_SPEED_STEP
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        command_key: str,
        device_field: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._command_key = command_key
        self._field = device_field
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{command_key}"
        self._attr_device_info = _device_info(entry)

    def _state(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.intelliflo_state

    @property
    def native_min_value(self) -> float:
        return float(self._state().get("speed_range_min", 0) or 0)

    @property
    def native_max_value(self) -> float:
        return float(self._state().get("speed_range_max", 3450) or 3450)

    @property
    def native_value(self) -> float | None:
        raw = self._state().get(self._field)
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send_command(self._command_key, value)
