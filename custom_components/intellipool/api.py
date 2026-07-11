"""Intellipool API client – supports local HTTP and cloud (intellipool.eu) modes."""
from __future__ import annotations

import asyncio
import html as _html
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    CLOUD_BASE_URL,
    CLOUD_COMMAND_PATH,
    CLOUD_DATA_FIELD_SERIAL,
    CLOUD_DATA_PATH,
    CLOUD_LOGIN_FIELD_PASS,
    CLOUD_LOGIN_FIELD_USER,
    CLOUD_LOGIN_PATH,
    CLOUD_POOL_LIST_PATH,
    CONN_TYPE_CLOUD,
    CONN_TYPE_LOCAL,
    KEY_AIR_TEMP,
    KEY_AUX_1,
    KEY_AUX_2,
    KEY_AUX_3,
    KEY_BATTERY_VOLTAGE,
    KEY_CHLORINATOR,
    KEY_FILTRATION,
    KEY_HEATING,
    KEY_INFO_MESSAGE,
    KEY_LIGHT,
    KEY_ORP,
    KEY_ORP_DOSING,
    KEY_PH,
    KEY_PH_DOSING,
    KEY_PUMP,
    KEY_PUMP_FLOW,
    KEY_PUMP_POWER,
    KEY_PUMP_SPEED,
    KEY_SALINITY,
    KEY_SIGNAL_STRENGTH,
    KEY_TARGET_ORP,
    KEY_TARGET_PH,
    KEY_TARGET_TEMP,
    KEY_WATER_TEMP,
    LOCAL_COMMAND_PATHS,
    LOCAL_PROBE_PATHS,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)


class CannotConnect(Exception):
    """Raised when we cannot connect to the device or service."""


class InvalidAuth(Exception):
    """Raised when credentials are rejected."""


class EndpointNotFound(Exception):
    """Raised when the local device does not expose a known API endpoint."""


@dataclass
class PoolData:
    """Snapshot of all pool measurements and states."""

    # Measurements
    water_temperature: float | None = None
    air_temperature: float | None = None
    ph: float | None = None
    orp: float | None = None         # mV
    salinity: float | None = None    # g/L
    pump_speed: float | None = None  # %
    pump_flow: float | None = None   # m³/h
    pump_power: float | None = None  # W

    # Binary states
    pump: bool | None = None
    heating: bool | None = None
    light: bool | None = None
    chlorinator: bool | None = None
    ph_dosing: bool | None = None
    orp_dosing: bool | None = None
    filtration: bool | None = None
    aux_1: bool | None = None
    aux_2: bool | None = None
    aux_3: bool | None = None

    # Diagnostics
    battery_voltage: float | None = None  # V
    signal_strength: float | None = None  # dB
    cover: bool | None = None
    info_message: str | None = None
    updated: str | None = None

    # Setpoints
    target_temperature: float | None = None
    target_ph: float | None = None
    target_orp: float | None = None

    # Raw response for debugging
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            KEY_WATER_TEMP: self.water_temperature,
            KEY_AIR_TEMP: self.air_temperature,
            KEY_PH: self.ph,
            KEY_ORP: self.orp,
            KEY_SALINITY: self.salinity,
            KEY_PUMP_SPEED: self.pump_speed,
            KEY_PUMP_FLOW: self.pump_flow,
            KEY_PUMP_POWER: self.pump_power,
            KEY_BATTERY_VOLTAGE: self.battery_voltage,
            KEY_SIGNAL_STRENGTH: self.signal_strength,
            KEY_INFO_MESSAGE: self.info_message,
            KEY_PUMP: self.pump,
            KEY_HEATING: self.heating,
            KEY_LIGHT: self.light,
            KEY_CHLORINATOR: self.chlorinator,
            KEY_PH_DOSING: self.ph_dosing,
            KEY_ORP_DOSING: self.orp_dosing,
            KEY_FILTRATION: self.filtration,
            KEY_AUX_1: self.aux_1,
            KEY_AUX_2: self.aux_2,
            KEY_AUX_3: self.aux_3,
            KEY_TARGET_TEMP: self.target_temperature,
            KEY_TARGET_PH: self.target_ph,
            KEY_TARGET_ORP: self.target_orp,
        }


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ("1", "true", "on", "yes", "active")
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_local_response(data: dict) -> PoolData:
    """
    Map a local device JSON response to PoolData.

    The INTP-1010B local API is not officially documented.  This mapper
    tries multiple common key names used by embedded pool controllers.
    Update this function once you have captured actual device traffic.

    Tip: run the built-in discovery service (see README) to capture the raw
    JSON and then adjust the key names below to match your device.
    """

    def get(*keys):
        for k in keys:
            if k in data:
                return data[k]
            # nested under "measures", "status", "equipment", "pool", etc.
            for parent in ("measures", "status", "equipment", "pool", "sensor",
                           "relay", "circuit", "device", "data"):
                if parent in data and isinstance(data[parent], dict):
                    if k in data[parent]:
                        return data[parent][k]
        return None

    return PoolData(
        water_temperature=_parse_float(
            get("waterTemp", "water_temp", "waterTemperature",
                "temperature", "poolTemp", "temp_eau", "bwt")),
        air_temperature=_parse_float(
            get("airTemp", "air_temp", "airTemperature", "temp_air")),
        ph=_parse_float(get("ph", "pH", "phValue", "ph_value")),
        orp=_parse_float(
            get("orp", "ORP", "orp_value", "redox", "Redox")),
        salinity=_parse_float(
            get("salinity", "salt", "saltLevel", "salinite")),
        pump_speed=_parse_float(
            get("pumpSpeed", "pump_speed", "pumpRPM", "vitessePompe", "rpm")),
        pump_flow=_parse_float(
            get("pumpFlow", "pump_flow", "flow", "debit")),
        pump_power=_parse_float(
            get("pumpPower", "pump_power", "power", "puissance")),
        pump=_parse_bool(
            get("pump", "pumpOn", "pump_on", "pump_status", "pompe")),
        heating=_parse_bool(
            get("heating", "heater", "heaterOn", "chauffage", "heat")),
        light=_parse_bool(
            get("light", "lights", "lighting", "lightOn", "eclairage")),
        chlorinator=_parse_bool(
            get("chlorinator", "chlor", "electrolyse", "electrolyseur")),
        ph_dosing=_parse_bool(
            get("phDosing", "ph_dosing", "pompeAcide", "acidPump")),
        orp_dosing=_parse_bool(
            get("orpDosing", "orp_dosing", "chloreDosing")),
        filtration=_parse_bool(
            get("filtration", "filter", "filterOn")),
        aux_1=_parse_bool(get("aux1", "aux_1", "auxiliaire1", "relay1")),
        aux_2=_parse_bool(get("aux2", "aux_2", "auxiliaire2", "relay2")),
        aux_3=_parse_bool(get("aux3", "aux_3", "auxiliaire3", "relay3")),
        target_temperature=_parse_float(
            get("targetTemp", "target_temp", "consigneTemp", "setpointTemp")),
        target_ph=_parse_float(
            get("targetPh", "target_ph", "consignePh", "phSetpoint")),
        target_orp=_parse_float(
            get("targetOrp", "target_orp", "consigneOrp", "orpSetpoint")),
        raw=data,
    )


def _text_num(s: str | None) -> float | None:
    """Extract the first number from a text label (handles '+23.5 °C', '104 mV')."""
    if s is None:
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s.replace(",", "."))
    return float(m.group()) if m else None


def _clean_text(s: str | None) -> str:
    """Unescape HTML entities and collapse whitespace."""
    return re.sub(r"\s+", " ", _html.unescape(s or "")).strip()


def _map_cloud_response(raw_html: str) -> PoolData:
    """
    Parse the HTML summary fragment returned by POST /pool/poolSummary.

    intellipool.eu is a server-rendered PHP/w2ui app: the "summary" endpoint
    returns an HTML dialog (NOT JSON) whose structure is stable. This parser
    is verified against real INTP-1010B output (see tests/sample_summary.html).
    """
    data = PoolData(raw={"html": raw_html})

    # --- status LEDs encoded in image filenames, e.g. .../led/filtration_on.png
    leds = re.findall(r"/led/([a-z0-9_]+)\.png", raw_html)

    def led_state(prefix: str) -> bool | None:
        if f"{prefix}_on" in leds:
            return True
        if f"{prefix}_off" in leds:
            return False
        return None

    data.filtration = led_state("filtration")
    data.light = led_state("lighting")
    data.heating = led_state("heating")
    data.cover = led_state("rollo_cover")
    # The filtration pump follows the filtration state.
    if data.filtration is not None:
        data.pump = data.filtration

    # --- measurement rows (each is a flat <div class="summary-item"> … </div>)
    for block in re.findall(
        r'<div class="summary-item"[^>]*>(.*?)</div>', raw_html, re.S
    ):
        tm = re.search(r'summary-title"?\s*>\s*<label>(.*?)</label>', block, re.S)
        title = _clean_text(tm.group(1)) if tm else ""
        vm = re.search(
            r'summary-value(?:-ok|-bad)?"?\s*>\s*<label>(.*?)</label>', block, re.S
        )
        value = _clean_text(vm.group(1)) if vm else ""
        sm = re.search(
            r'summary-setpoint"?\s*>\s*<label>(.*?)</label>', block, re.S
        )
        setpoint = _clean_text(sm.group(1)) if sm else ""

        t = title.lower()
        val = _text_num(value)
        sp = _text_num(setpoint)
        sp_mode = None
        if setpoint:
            mode_match = re.match(r"\s*([A-Za-z]+)\s*:", setpoint)
            sp_mode = mode_match.group(1).lower() if mode_match else None
        dosing_on = sp_mode not in (None, "off")

        if "air" in t:
            data.air_temperature = val
        elif "water" in t:
            data.water_temperature = val
            data.target_temperature = sp
        elif t == "ph":
            data.ph = val
            data.target_ph = sp
            data.ph_dosing = dosing_on
        elif "conduct" in t:
            data.salinity = val
        elif "orp" in t or "redox" in t:
            data.orp = val
            data.target_orp = sp
            data.orp_dosing = dosing_on
        elif "speed" in t:
            data.pump_speed = val  # RPM
        elif "capacity" in t or "watt" in value.lower():
            data.pump_power = val

    # --- diagnostics from <img> title attributes and info text ---
    bm = re.search(r'class="battery"[^>]*title="([^"]*)"', raw_html)
    data.battery_voltage = _text_num(bm.group(1)) if bm else None
    rm = re.search(r'class="radio"[^>]*title="([^"]*)"', raw_html)
    data.signal_strength = _text_num(rm.group(1)) if rm else None
    im = re.search(r'class="ui-error-info">(.*?)</p>', raw_html, re.S)
    data.info_message = _clean_text(im.group(1)) if im else None
    dm = re.search(r'class="date">(.*?)</label>', raw_html, re.S)
    data.updated = _clean_text(dm.group(1)) if dm else None

    return data


# ---------------------------------------------------------------------------
# Local API
# ---------------------------------------------------------------------------

class IntelliPoolLocalAPI:
    """Direct HTTP client for the INTP-1010B on the local network."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._data_path: str | None = None
        self._command_path: str | None = None

    @property
    def _base(self) -> str:
        scheme = "https" if self._ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            auth = None
            if self._username:
                auth = aiohttp.BasicAuth(self._username, self._password or "")
            self._session = aiohttp.ClientSession(auth=auth, timeout=TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def discover(self) -> str:
        """Probe the device for a working data endpoint.

        Returns the discovered path.  Raises EndpointNotFound if none respond.
        """
        session = await self._get_session()
        for path in LOCAL_PROBE_PATHS:
            url = f"{self._base}{path}"
            try:
                async with session.get(url, ssl=False) as resp:
                    if resp.status == 200:
                        ctype = resp.headers.get("Content-Type", "")
                        if "json" in ctype or "xml" in ctype or "html" in ctype:
                            _LOGGER.info("Intellipool local API discovered at %s", url)
                            self._data_path = path
                            return path
            except (aiohttp.ClientError, asyncio.TimeoutError):
                continue

        raise EndpointNotFound(
            f"Could not find a local API on {self._base}. "
            "Check the README for protocol discovery instructions."
        )

    async def get_data(self) -> PoolData:
        """Fetch current pool data from the device."""
        if self._data_path is None:
            await self.discover()

        session = await self._get_session()
        url = f"{self._base}{self._data_path}"
        try:
            async with session.get(url, ssl=False) as resp:
                if resp.status == 401:
                    raise InvalidAuth("Local device rejected credentials")
                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype:
                    raw = await resp.json(content_type=None)
                else:
                    # Some devices return plain text or XML; try JSON parse anyway
                    text = await resp.text()
                    try:
                        import json
                        raw = json.loads(text)
                    except Exception:
                        _LOGGER.debug(
                            "Non-JSON response from device:\n%s", text[:500]
                        )
                        raw = {"_raw_text": text}
                _LOGGER.debug("Intellipool local raw data: %s", raw)
                return _map_local_response(raw)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"Cannot reach {url}: {err}") from err

    async def send_command(self, key: str, value: Any) -> None:
        """Send a control command to the device."""
        if self._command_path is None:
            # Try to discover a command endpoint
            session = await self._get_session()
            for path in LOCAL_COMMAND_PATHS:
                url = f"{self._base}{path}"
                try:
                    async with session.options(url, ssl=False) as resp:
                        if resp.status < 500:
                            self._command_path = path
                            break
                except Exception:
                    continue
            if self._command_path is None:
                # Fall back: POST to same path as data with command payload
                self._command_path = self._data_path or LOCAL_COMMAND_PATHS[0]

        session = await self._get_session()
        url = f"{self._base}{self._command_path}"
        payload = {"command": key, "value": value}
        try:
            async with session.post(url, json=payload, ssl=False) as resp:
                if resp.status == 401:
                    raise InvalidAuth("Local device rejected credentials")
                resp.raise_for_status()
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"Command failed: {err}") from err

    async def test_connection(self) -> bool:
        """Return True if the device is reachable."""
        try:
            await self.discover()
            return True
        except (CannotConnect, EndpointNotFound):
            return False


# ---------------------------------------------------------------------------
# Cloud API
# ---------------------------------------------------------------------------

class IntelliPoolCloudAPI:
    """Client for the intellipool.eu cloud service."""

    def __init__(
        self,
        username: str,
        password: str,
        pool_id: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._pool_id = pool_id
        self._session = session
        self._owns_session = session is None
        self._cookies: dict = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 HomeAssistant/Intellipool"},
            )
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> None:
        """Authenticate with intellipool.eu and obtain a session cookie.

        Confirmed flow: POST form-urlencoded ``login`` + ``pass`` to
        ``/pool/poolLogin/login`` (plaintext over TLS, no client-side hashing).
        On failure the server re-renders the login page; on success it
        redirects into the authenticated app. We detect the login-wall to
        distinguish the two.
        """
        session = await self._get_session()
        url = f"{CLOUD_BASE_URL}{CLOUD_LOGIN_PATH}"
        payload = {
            CLOUD_LOGIN_FIELD_USER: self._username,
            CLOUD_LOGIN_FIELD_PASS: self._password,
        }
        try:
            async with session.post(
                url,
                data=payload,
                allow_redirects=True,
            ) as resp:
                if resp.status not in (200, 302):
                    raise CannotConnect(f"Login failed with HTTP {resp.status}")
                body = await resp.text(errors="replace")
                # If we still see the login form, the credentials were rejected.
                if "poolLogin/login" in body and 'name="pass"' in body:
                    raise InvalidAuth("intellipool.eu rejected the credentials")
                _LOGGER.debug("Cloud login OK, landed on %s", resp.url)
                # The authenticated landing page lists pools as
                # javascript:displaySummary('<serial>') links — grab the serial.
                if self._pool_id is None:
                    self._extract_serial(body)
                    if self._pool_id is None:
                        await self._discover_pool_id(session)
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Cloud login error: {err}") from err

    def _extract_serial(self, body: str) -> None:
        """Find the pool serial from displaySummary('...') links in a page."""
        m = re.search(r"displaySummary\(['\"](\d+)['\"]\)", body)
        if m:
            self._pool_id = m.group(1)
            _LOGGER.info("Discovered pool serial: %s", self._pool_id)

    async def _discover_pool_id(self, session: aiohttp.ClientSession) -> None:
        """Fallback: fetch the pool-list page and extract the serial."""
        url = f"{CLOUD_BASE_URL}{CLOUD_POOL_LIST_PATH}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    self._extract_serial(await resp.text(errors="replace"))
        except Exception as err:
            _LOGGER.debug("Could not auto-discover pool serial: %s", err)

    async def get_data(self) -> PoolData:
        """Fetch current pool state from POST /pool/poolSummary (HTML fragment)."""
        if not self._pool_id:
            raise CannotConnect(
                "No pool serial known. Set it in the integration options "
                "(the number in displaySummary('<serial>') on intellipool.eu)."
            )
        session = await self._get_session()
        url = f"{CLOUD_BASE_URL}{CLOUD_DATA_PATH}"
        payload = {CLOUD_DATA_FIELD_SERIAL: self._pool_id}
        try:
            html_body = await self._post_summary(session, url, payload)
            # A session timeout returns the login page instead of the summary.
            if "poolLogin/login" in html_body or "summary" not in html_body:
                _LOGGER.debug("Cloud session expired, re-authenticating")
                await self.login()
                html_body = await self._post_summary(session, url, payload)
            _LOGGER.debug("Intellipool cloud raw data (%d bytes)", len(html_body))
            return _map_cloud_response(html_body)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"Cloud data fetch failed: {err}") from err

    async def _post_summary(
        self, session: aiohttp.ClientSession, url: str, payload: dict
    ) -> str:
        async with session.post(url, data=payload) as resp:
            resp.raise_for_status()
            return await resp.text(errors="replace")

    async def send_command(self, key: str, value: Any) -> None:
        """Send a control command via the cloud service."""
        session = await self._get_session()
        url = f"{CLOUD_BASE_URL}{CLOUD_COMMAND_PATH}"
        payload: dict[str, Any] = {"command": key, "value": value}
        if self._pool_id:
            payload["poolId"] = self._pool_id
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 401:
                    await self.login()
                    async with session.post(url, json=payload) as resp2:
                        resp2.raise_for_status()
                else:
                    resp.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"Cloud command failed: {err}") from err

    async def test_connection(self) -> bool:
        """Return True if credentials are valid."""
        try:
            await self.login()
            return True
        except (CannotConnect, InvalidAuth):
            return False

    @property
    def pool_id(self) -> str | None:
        return self._pool_id


# ---------------------------------------------------------------------------
# Unified wrapper
# ---------------------------------------------------------------------------

class IntelliPoolAPI:
    """Unified API client – delegates to local or cloud backend."""

    def __init__(
        self,
        connection_type: str,
        host: str | None = None,
        port: int = 80,
        ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        pool_id: str | None = None,
    ) -> None:
        self._type = connection_type
        if connection_type == CONN_TYPE_LOCAL:
            self._backend: IntelliPoolLocalAPI | IntelliPoolCloudAPI = (
                IntelliPoolLocalAPI(
                    host=host or "",
                    port=port,
                    ssl=ssl,
                    username=username,
                    password=password,
                )
            )
        else:
            self._backend = IntelliPoolCloudAPI(
                username=username or "",
                password=password or "",
                pool_id=pool_id,
            )

    async def async_init(self) -> None:
        """Perform initial authentication / discovery."""
        if self._type == CONN_TYPE_CLOUD:
            await self._backend.login()  # type: ignore[union-attr]
        else:
            await self._backend.discover()  # type: ignore[union-attr]

    async def get_data(self) -> PoolData:
        return await self._backend.get_data()

    async def send_command(self, key: str, value: Any) -> None:
        await self._backend.send_command(key, value)

    async def close(self) -> None:
        await self._backend.close()

    @property
    def is_local(self) -> bool:
        return self._type == CONN_TYPE_LOCAL
