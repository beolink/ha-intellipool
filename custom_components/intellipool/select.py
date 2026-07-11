"""Select entities for Intellipool mode controls (filtration, lighting)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FILTRATION_MODES, LIGHTING_MODES
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info


@dataclass(frozen=True)
class IntelliPoolSelectDescription(SelectEntityDescription):
    command_key: str = ""       # e.g. "filtration_mode"
    device_field: str = ""      # e.g. "filtration" (key in command_state)
    value_labels: dict | None = None  # value → label


SELECT_DESCRIPTIONS: tuple[IntelliPoolSelectDescription, ...] = (
    IntelliPoolSelectDescription(
        key="filtration_mode",
        command_key="filtration_mode",
        device_field="filtration",
        value_labels=FILTRATION_MODES,
        name="Filtreringsläge",
        icon="mdi:pump",
    ),
    IntelliPoolSelectDescription(
        key="lighting_mode",
        command_key="lighting_mode",
        device_field="lighting",
        value_labels=LIGHTING_MODES,
        name="Belysningsläge",
        icon="mdi:lightbulb",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntelliPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntelliPoolSelect(coordinator, entry, desc) for desc in SELECT_DESCRIPTIONS
    )


class IntelliPoolSelect(CoordinatorEntity[IntelliPoolCoordinator], SelectEntity):
    entity_description: IntelliPoolSelectDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        description: IntelliPoolSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)
        self._attr_options = list(description.value_labels.values())
        # label → value reverse lookup
        self._to_value = {v: k for k, v in description.value_labels.items()}

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.command_state.get(
            self.entity_description.device_field
        )
        return self.entity_description.value_labels.get(raw) if raw is not None else None

    async def async_select_option(self, option: str) -> None:
        value = self._to_value.get(option)
        if value is None:
            return
        await self.coordinator.async_send_command(
            self.entity_description.command_key, value
        )
