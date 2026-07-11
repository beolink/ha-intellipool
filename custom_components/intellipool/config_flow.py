"""Config flow for Pentair Intellipool."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnect,
    EndpointNotFound,
    InvalidAuth,
    IntelliPoolCloudAPI,
    IntelliPoolLocalAPI,
    IntelliPoolOfficialAPI,
)
from .const import (
    CONF_API_KEY,
    CONF_CONNECTION_TYPE,
    CONF_INSTALL_ID,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_STALE_MINUTES,
    CONN_TYPE_CLOUD,
    CONN_TYPE_LOCAL,
    CONN_TYPE_OFFICIAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
)
from .discovery import DiscoveredDevice, discover_devices

_LOGGER = logging.getLogger(__name__)

CONF_DISCOVERED_HOST = "discovered_host"

STEP_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_CLOUD): vol.In(
            [CONN_TYPE_CLOUD, CONN_TYPE_OFFICIAL, CONN_TYPE_LOCAL]
        ),
    }
)

STEP_LOCAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)

# Cloud step: credentials + OPTIONAL official-API failsafe (key + install id).
STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_POOL_ID, default=""): str,
        vol.Optional(CONF_INSTALL_ID, default=""): str,
        vol.Optional(CONF_API_KEY, default=""): str,
    }
)

STEP_OFFICIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTALL_ID): str,
        vol.Required(CONF_API_KEY): str,
    }
)


def _discovered_options(devices: list[DiscoveredDevice]) -> dict[str, str]:
    """Build a dict of label → value for the discovery picker."""
    opts: dict[str, str] = {}
    for dev in devices:
        label_parts = [dev.host]
        if dev.hostname:
            label_parts.append(f"({dev.hostname})")
        if dev.fingerprint_match:
            label_parts.append(f"[{dev.fingerprint_match}]")
        label_parts.append(f"port {dev.port}")
        label_parts.append(f"– {dev.confidence} confidence")
        opts[" ".join(label_parts)] = f"{dev.host}:{dev.port}"
    opts["Ange IP manuellt / Enter IP manually"] = "manual"
    return opts


class IntelliPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Intellipool config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._conn_type: str | None = None
        self._data: dict[str, Any] = {}
        self._discovered: list[DiscoveredDevice] = []
        # Pre-filled values from passive discovery (zeroconf/dhcp)
        self._prefill_host: str | None = None
        self._prefill_port: int = DEFAULT_PORT
        self._prefill_hostname: str | None = None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_connection_type(user_input)

    # ------------------------------------------------------------------
    # Step: choose connection type
    # ------------------------------------------------------------------

    async def async_step_connection_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._conn_type = user_input[CONF_CONNECTION_TYPE]
            self._data[CONF_CONNECTION_TYPE] = self._conn_type
            if self._conn_type == CONN_TYPE_LOCAL:
                return await self.async_step_scan()
            if self._conn_type == CONN_TYPE_OFFICIAL:
                return await self.async_step_official()
            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="connection_type",
            data_schema=STEP_TYPE_SCHEMA,
        )

    # ------------------------------------------------------------------
    # Step: official API (domotique-piscine.eu)
    # ------------------------------------------------------------------

    async def async_step_official(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = IntelliPoolOfficialAPI(
                install_id=user_input[CONF_INSTALL_ID],
                api_key=user_input[CONF_API_KEY],
                session=session,
            )
            try:
                await api.get_data()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected official API error")
                errors["base"] = "unknown"
            else:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=f"Intellipool (API {user_input[CONF_INSTALL_ID]})",
                    data=self._data,
                )

        return self.async_show_form(
            step_id="official",
            data_schema=STEP_OFFICIAL_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step: active network scan
    # ------------------------------------------------------------------

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Kick off a subnet + hostname scan, then show the picker."""
        if user_input is not None:
            choice = user_input.get(CONF_DISCOVERED_HOST, "manual")
            if choice == "manual" or not choice:
                # Jump straight to manual form, possibly pre-filled
                return await self.async_step_local()

            # Parse "ip:port" from choice
            try:
                host, port_str = choice.rsplit(":", 1)
                port = int(port_str)
            except ValueError:
                host = choice
                port = DEFAULT_PORT

            # Match the chosen device to pre-fill api_path
            for dev in self._discovered:
                if dev.host == host and dev.port == port:
                    self._prefill_host = host
                    self._prefill_port = port
                    self._data[CONF_CONNECTION_TYPE] = CONN_TYPE_LOCAL
                    # Skip the manual form — go straight to confirm
                    return await self._confirm_local(host, port, dev.api_path)
            self._prefill_host = host
            self._prefill_port = port
            return await self.async_step_local()

        # Run discovery (up to 20 s so the UI doesn't time out)
        _LOGGER.info("Running Intellipool network discovery…")
        try:
            self._discovered = await discover_devices(timeout=20.0)
        except Exception:
            _LOGGER.exception("Discovery failed, falling back to manual entry")
            self._discovered = []

        if not self._discovered and self._prefill_host is None:
            # Nothing found and no passive hint — go straight to manual
            return await self.async_step_local()

        options = _discovered_options(self._discovered)
        schema = vol.Schema(
            {
                vol.Required(CONF_DISCOVERED_HOST): vol.In(options),
            }
        )
        return self.async_show_form(
            step_id="scan",
            data_schema=schema,
            description_placeholders={
                "count": str(len(self._discovered)),
            },
        )

    async def _confirm_local(
        self, host: str, port: int, api_path: str | None
    ) -> FlowResult:
        """Verify the discovered device and create the entry."""
        session = async_get_clientsession(self.hass)
        api = IntelliPoolLocalAPI(host=host, port=port, session=session)
        if api_path:
            api._data_path = api_path  # skip re-discovery
        try:
            await api.get_data()
        except (CannotConnect, EndpointNotFound, Exception) as err:
            _LOGGER.warning("Could not confirm discovered device %s: %s", host, err)
            # Fall through to manual so user can adjust credentials
            return await self.async_step_local()

        self._data.update(
            {
                CONF_CONNECTION_TYPE: CONN_TYPE_LOCAL,
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_SSL: port in (443, 8443),
            }
        )
        return self.async_create_entry(
            title=f"Intellipool @ {host}",
            data=self._data,
        )

    # ------------------------------------------------------------------
    # Step: manual local entry
    # ------------------------------------------------------------------

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = IntelliPoolLocalAPI(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                ssl=user_input.get(CONF_SSL, False),
                username=user_input.get(CONF_USERNAME) or None,
                password=user_input.get(CONF_PASSWORD) or None,
                session=session,
            )
            try:
                path = await api.discover()
                _LOGGER.info("Local device found at path: %s", path)
            except EndpointNotFound:
                errors["base"] = "endpoint_not_found"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during local discovery")
                errors["base"] = "unknown"
            else:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=f"Intellipool @ {user_input[CONF_HOST]}",
                    data=self._data,
                )

        # Pre-fill from passive/active discovery if available
        default_host = self._prefill_host or vol.UNDEFINED
        default_port = self._prefill_port

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=default_host): str,
                vol.Optional(CONF_PORT, default=default_port): int,
                vol.Optional(CONF_SSL, default=default_port in (443, 8443)): bool,
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )
        return self.async_show_form(
            step_id="local",
            data_schema=schema,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step: cloud
    # ------------------------------------------------------------------

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = IntelliPoolCloudAPI(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                pool_id=user_input.get(CONF_POOL_ID) or None,
                session=session,
            )
            try:
                await api.login()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected cloud login error")
                errors["base"] = "unknown"
            else:
                serial = api.pool_id or (user_input.get(CONF_POOL_ID) or None)
                # Validate the optional failsafe key, if both parts were given.
                fs_key = user_input.get(CONF_API_KEY) or ""
                fs_install = user_input.get(CONF_INSTALL_ID) or ""
                if fs_key and fs_install:
                    fs = IntelliPoolOfficialAPI(
                        install_id=fs_install, api_key=fs_key, session=session
                    )
                    if not await fs.test_connection():
                        errors["base"] = "bad_failsafe"
                if not serial and "base" not in errors:
                    # Login worked but we could not auto-detect the pool serial.
                    errors["base"] = "no_serial"
                if not errors:
                    user_input[CONF_POOL_ID] = serial
                    self._data.update(user_input)
                    return self.async_create_entry(
                        title=f"Intellipool ({user_input[CONF_USERNAME]})",
                        data=self._data,
                    )

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Passive discovery handlers (zeroconf + dhcp)
    # ------------------------------------------------------------------

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a device discovered via mDNS."""
        host = str(discovery_info.host)
        port = discovery_info.port or DEFAULT_PORT
        hostname = discovery_info.hostname.rstrip(".")

        _LOGGER.info(
            "Intellipool zeroconf discovery: %s (%s:%d)", hostname, host, port
        )

        await self.async_set_unique_id(f"zeroconf_{host}_{port}")
        self._abort_if_unique_id_configured()

        self._prefill_host = host
        self._prefill_port = port
        self._prefill_hostname = hostname
        self._data[CONF_CONNECTION_TYPE] = CONN_TYPE_LOCAL

        self.context["title_placeholders"] = {"host": hostname or host}
        return await self.async_step_local()

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> FlowResult:
        """Handle a device discovered via DHCP."""
        host = discovery_info.ip
        hostname = discovery_info.hostname

        _LOGGER.info(
            "Intellipool DHCP discovery: %s (%s)", hostname, host
        )

        await self.async_set_unique_id(f"dhcp_{host}")
        self._abort_if_unique_id_configured()

        self._prefill_host = host
        self._prefill_hostname = hostname
        self._data[CONF_CONNECTION_TYPE] = CONN_TYPE_LOCAL

        self.context["title_placeholders"] = {"host": hostname or host}
        return await self.async_step_local()

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IntelliPoolOptionsFlow:
        return IntelliPoolOptionsFlow(config_entry)


class IntelliPoolOptionsFlow(config_entries.OptionsFlow):
    """Handle options (e.g. scan interval)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_stale = self.config_entry.options.get(
            CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    int, vol.Range(min=10, max=300)
                ),
                vol.Optional(CONF_STALE_MINUTES, default=current_stale): vol.All(
                    int, vol.Range(min=5, max=240)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
