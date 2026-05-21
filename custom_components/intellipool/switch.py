"""Switch entities for Intellipool circuits and relays."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_AUX_1,
    KEY_AUX_2,
    KEY_AUX_3,
    KEY_CHLORINATOR,
    KEY_FILTRATION,
    KEY_HEATING,
    KEY_LIGHT,
    KEY_ORP_DOSING,
    KEY_PH_DOSING,
    KEY_PUMP,
    MANUFACTURER,
    MODEL,
)
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info


@dataclass(frozen=True)
class IntelliPoolSwitchDescription(SwitchEntityDescription):
    data_key: str = ""
    command_key: str = ""


SWITCH_DESCRIPTIONS: tuple[IntelliPoolSwitchDescription, ...] = (
    IntelliPoolSwitchDescription(
        key="pump",
        data_key=KEY_PUMP,
        command_key=KEY_PUMP,
        name="Pump",
        icon="mdi:pump",
    ),
    IntelliPoolSwitchDescription(
        key="filtration",
        data_key=KEY_FILTRATION,
        command_key=KEY_FILTRATION,
        name="Filtrering",
        icon="mdi:filter",
    ),
    IntelliPoolSwitchDescription(
        key="heating",
        data_key=KEY_HEATING,
        command_key=KEY_HEATING,
        name="Uppvärmning",
        icon="mdi:radiator",
    ),
    IntelliPoolSwitchDescription(
        key="light",
        data_key=KEY_LIGHT,
        command_key=KEY_LIGHT,
        name="Belysning",
        icon="mdi:lightbulb",
    ),
    IntelliPoolSwitchDescription(
        key="chlorinator",
        data_key=KEY_CHLORINATOR,
        command_key=KEY_CHLORINATOR,
        name="Elektrolys/Klorering",
        icon="mdi:water-plus",
    ),
    IntelliPoolSwitchDescription(
        key="ph_dosing",
        data_key=KEY_PH_DOSING,
        command_key=KEY_PH_DOSING,
        name="pH-dosering",
        icon="mdi:flask",
    ),
    IntelliPoolSwitchDescription(
        key="orp_dosing",
        data_key=KEY_ORP_DOSING,
        command_key=KEY_ORP_DOSING,
        name="ORP-dosering",
        icon="mdi:flask-outline",
    ),
    IntelliPoolSwitchDescription(
        key="aux_1",
        data_key=KEY_AUX_1,
        command_key=KEY_AUX_1,
        name="Extra 1 (AUX)",
        icon="mdi:toggle-switch",
    ),
    IntelliPoolSwitchDescription(
        key="aux_2",
        data_key=KEY_AUX_2,
        command_key=KEY_AUX_2,
        name="Extra 2 (AUX)",
        icon="mdi:toggle-switch",
    ),
    IntelliPoolSwitchDescription(
        key="aux_3",
        data_key=KEY_AUX_3,
        command_key=KEY_AUX_3,
        name="Extra 3 (AUX)",
        icon="mdi:toggle-switch",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntelliPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data.as_dict() if coordinator.data else {}

    entities = [
        IntelliPoolSwitch(coordinator, entry, desc)
        for desc in SWITCH_DESCRIPTIONS
        if data.get(desc.data_key) is not None
    ]

    if not entities:
        entities = [
            IntelliPoolSwitch(coordinator, entry, desc)
            for desc in SWITCH_DESCRIPTIONS
        ]

    async_add_entities(entities)


class IntelliPoolSwitch(CoordinatorEntity[IntelliPoolCoordinator], SwitchEntity):
    entity_description: IntelliPoolSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        description: IntelliPoolSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.as_dict().get(self.entity_description.data_key)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(
            self.entity_description.command_key, True
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(
            self.entity_description.command_key, False
        )
