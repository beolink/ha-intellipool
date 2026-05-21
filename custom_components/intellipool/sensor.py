"""Sensor entities for Intellipool."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    KEY_AIR_TEMP,
    KEY_ORP,
    KEY_PH,
    KEY_PUMP_FLOW,
    KEY_PUMP_POWER,
    KEY_PUMP_SPEED,
    KEY_SALINITY,
    KEY_WATER_TEMP,
    MANUFACTURER,
    MODEL,
)
from .coordinator import IntelliPoolCoordinator


@dataclass(frozen=True)
class IntelliPoolSensorDescription(SensorEntityDescription):
    data_key: str = ""


SENSOR_DESCRIPTIONS: tuple[IntelliPoolSensorDescription, ...] = (
    IntelliPoolSensorDescription(
        key="water_temperature",
        data_key=KEY_WATER_TEMP,
        name="Vattentemperatur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-water",
    ),
    IntelliPoolSensorDescription(
        key="air_temperature",
        data_key=KEY_AIR_TEMP,
        name="Lufttemperatur",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    IntelliPoolSensorDescription(
        key="ph",
        data_key=KEY_PH,
        name="pH",
        native_unit_of_measurement="pH",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ph",
        suggested_display_precision=2,
    ),
    IntelliPoolSensorDescription(
        key="orp",
        data_key=KEY_ORP,
        name="ORP (Redox)",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
    ),
    IntelliPoolSensorDescription(
        key="salinity",
        data_key=KEY_SALINITY,
        name="Salthalt",
        native_unit_of_measurement="g/L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        suggested_display_precision=1,
    ),
    IntelliPoolSensorDescription(
        key="pump_speed",
        data_key=KEY_PUMP_SPEED,
        name="Pumphastighet",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:pump",
    ),
    IntelliPoolSensorDescription(
        key="pump_flow",
        data_key=KEY_PUMP_FLOW,
        name="Pumpflöde",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:waves-arrow-right",
        suggested_display_precision=1,
    ),
    IntelliPoolSensorDescription(
        key="pump_power",
        data_key=KEY_PUMP_POWER,
        name="Pumpeffekt",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt-circle",
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
        IntelliPoolSensor(coordinator, entry, desc)
        for desc in SENSOR_DESCRIPTIONS
        if data.get(desc.data_key) is not None
    ]

    if not entities:
        # Add all sensors even if data is None; they'll show as unavailable
        entities = [
            IntelliPoolSensor(coordinator, entry, desc)
            for desc in SENSOR_DESCRIPTIONS
        ]

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    from homeassistant.const import CONF_HOST
    host = entry.data.get(CONF_HOST, "intellipool.eu")
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Intellipool",
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{host}" if entry.data.get(CONF_HOST) else "https://www.intellipool.eu",
    )


class IntelliPoolSensor(CoordinatorEntity[IntelliPoolCoordinator], SensorEntity):
    entity_description: IntelliPoolSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliPoolCoordinator,
        entry: ConfigEntry,
        description: IntelliPoolSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.as_dict().get(self.entity_description.data_key)
