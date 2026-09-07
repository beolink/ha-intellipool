"""What this integration contributes to the anonymous daily report.

Free of Home Assistant imports on purpose, so the tests can prove without a
Home Assistant installation that only agreed numbers leave the house.

A pool's water temperature, pH and chlorine level say something about the pool
and nothing about the people: they do not move when someone comes home, and
they are read once a day, not sampled. Nothing here is a time series.

See https://stats.rnet.se/integritet for the full list and the reasoning.
"""

from __future__ import annotations

from typing import Any, Mapping

#: The one controller this integration speaks to. A model string is never
#: passed through from the device, so no future firmware can leak a name.
MODEL = "intp_1010b"

#: Where the data comes from. Closed set: anything else becomes "other".
CONNECTIONS = {"cloud", "official", "local"}

#: field in PoolData -> metric name, with the range that is physically sane.
#: A reading outside it is a parse artefact, not a pool, and is dropped rather
#: than allowed to drag a fleet median around.
_READINGS: dict[str, tuple[str, float, float]] = {
    "water_temperature": ("water_temp_c", -5.0, 50.0),
    "air_temperature": ("outdoor_mean_c", -40.0, 55.0),
    "ph": ("ph", 4.0, 10.0),
    "orp": ("orp_mv", 0.0, 1500.0),
    "salinity": ("salt_ppm", 0.0, 15000.0),
    "pump_speed": ("pump_rpm", 0.0, 5000.0),
}


def connection_slug(connection: str | None) -> str:
    if not connection:
        return "unknown"
    name = str(connection).strip().lower()
    return name if name in CONNECTIONS else "other"


def readings(data: Mapping[str, Any] | None) -> dict[str, float]:
    """The pool's own numbers, as read at reporting time once a day."""
    if not data:
        return {}
    out: dict[str, float] = {}
    for field, (metric, low, high) in _READINGS.items():
        value = data.get(field)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number or not (low <= number <= high):  # NaN or nonsense
            continue
        out[metric] = round(number, 1)
    return out


def build_extra(
    *,
    connection: str | None,
    has_failsafe: bool,
    control_enabled: bool,
    heating: bool,
    chlorinator: bool,
    data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the Intellipool part of the report."""
    return {
        "models": [MODEL],
        "features": {
            # Which transport carries the data, and whether the official API is
            # configured as a failsafe behind the scrape.
            "cloud": connection_slug(connection) == "cloud",
            "official_api": connection_slug(connection) == "official",
            "local": connection_slug(connection) == "local",
            "failsafe": bool(has_failsafe),
            # Whether the pool is actually driven from Home Assistant, and
            # which of the big consumers exist at all.
            "control": bool(control_enabled),
            "heating": bool(heating),
            "chlorinator": bool(chlorinator),
        },
        "metrics": readings(data),
    }
