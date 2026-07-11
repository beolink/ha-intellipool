"""Backfill historic pool data into Home Assistant long-term statistics."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .api import parse_history_values
from .const import HISTORY_SENSOR_MAP

_LOGGER = logging.getLogger(__name__)


async def async_import_history(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator,
    days: int,
) -> dict[str, int]:
    """Fetch `days` of hourly history and import it as statistics.

    Statistics land on the integration's own sensor entities (source
    "recorder"), so the backfilled data appears on the existing sensor graphs.
    Returns {entity_id: number_of_hourly_points_imported}.
    """
    registry = er.async_get(hass)

    # Map sensor description key → (entity_id, unit) for this entry's sensors.
    prefix = f"{entry.entry_id}_"
    key_to_target: dict[str, tuple[str, str | None]] = {}
    for ent in registry.entities.values():
        if ent.config_entry_id != entry.entry_id or ent.domain != "sensor":
            continue
        if not ent.unique_id.startswith(prefix):
            continue
        key = ent.unique_id[len(prefix):]
        state = hass.states.get(ent.entity_id)
        unit = state.attributes.get("unit_of_measurement") if state else None
        key_to_target[key] = (ent.entity_id, unit)

    # entity_id → {hour_start_datetime: value}
    buckets: dict[str, dict[datetime, float]] = {}
    units: dict[str, str | None] = {}

    today = dt_util.now().date()
    days_with_data = 0
    for offset in range(max(1, days)):
        day = today - timedelta(days=offset)
        date_str = day.strftime("%Y-%m-%d")
        try:
            records = await coordinator.api.get_history(date_str, "DAY")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("History fetch failed for %s: %s", date_str, err)
            continue

        day_start = dt_util.start_of_local_day(
            datetime(day.year, day.month, day.day)
        )
        got = False
        for rec in records:
            key = HISTORY_SENSOR_MAP.get(rec.get("typeInfo"))
            if not key or key not in key_to_target:
                continue
            entity_id, unit = key_to_target[key]
            units[entity_id] = unit
            values = parse_history_values(rec.get("values", []))
            for hour, value in enumerate(values[:24]):
                if value is None:
                    continue
                start = day_start + timedelta(hours=hour)
                buckets.setdefault(entity_id, {})[start] = value
                got = True
        if got:
            days_with_data += 1

    result: dict[str, int] = {}
    for entity_id, by_hour in buckets.items():
        stats = [
            StatisticData(start=start, mean=value, min=value, max=value)
            for start, value in sorted(by_hour.items())
        ]
        if not stats:
            continue
        metadata = StatisticMetaData(
            has_mean=True,
            has_sum=False,
            name=None,
            source="recorder",
            statistic_id=entity_id,
            unit_of_measurement=units.get(entity_id),
        )
        async_import_statistics(hass, metadata, stats)
        result[entity_id] = len(stats)

    _LOGGER.info(
        "Intellipool history import: %d day(s), %d sensor(s)",
        days_with_data,
        len(result),
    )
    return result
