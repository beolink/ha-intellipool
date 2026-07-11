"""Text entities for Intellipool 24-hour schedules (filtration/lighting/aux1).

Each schedule is a 24-character string, one digit per hour (0 = off, 1 = on),
e.g. "111111000000000000111111". Editing writes it via the setpoints form.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SCHEDULE_FIELD_MAP
from .coordinator import IntelliPoolCoordinator
from .sensor import _device_info


@dataclass(frozen=True)
class IntelliPoolScheduleDescription(TextEntityDescription):
    command_key: str = ""    # e.g. "schedule_filtration"
    timer_field: str = ""    # e.g. "timer_filtration"


SCHEDULE_DESCRIPTIONS: tuple[IntelliPoolScheduleDescription, ...] = (
    IntelliPoolScheduleDescription(
        key="schedule_filtration",
        command_key="schedule_filtration",
        timer_field="timer_filtration",
        name="Filtreringsschema",
        icon="mdi:calendar-clock",
    ),
    IntelliPoolScheduleDescription(
        key="schedule_lighting",
        command_key="schedule_lighting",
        timer_field="timer_lighting",
        name="Belysningsschema",
        icon="mdi:calendar-clock",
    ),
    IntelliPoolScheduleDescription(
        key="schedule_aux1",
        command_key="schedule_aux1",
        timer_field="timer_aux1",
        name="Aux 1-schema",
        icon="mdi:calendar-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntelliPoolCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntelliPoolSchedule(coordinator, entry, desc)
        for desc in SCHEDULE_DESCRIPTIONS
    )


class IntelliPoolSchedule(CoordinatorEntity[IntelliPoolCoordinator], TextEntity):
    entity_description: IntelliPoolScheduleDescription
    _attr_has_entity_name = True
    _attr_native_min = 24
    _attr_native_max = 24
    _attr_pattern = r"[01]{24}"
    _attr_mode = "text"

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        description: IntelliPoolScheduleDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        timers = self.coordinator.data.setpoint_state.get("timer", {})
        return timers.get(self.entity_description.timer_field)

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.async_send_command(
            self.entity_description.command_key, value
        )
