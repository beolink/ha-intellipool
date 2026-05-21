"""Config flow for Pentair Intellipool."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, EndpointNotFound, InvalidAuth, IntelliPoolCloudAPI, IntelliPoolLocalAPI
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_POOL_ID,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONN_TYPE_CLOUD,
    CONN_TYPE_LOCAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=CONN_TYPE_LOCAL): vol.In(
            [CONN_TYPE_LOCAL, CONN_TYPE_CLOUD]
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

STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_POOL_ID, default=""): str,
    }
)


class IntelliPoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Intellipool config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._conn_type: str | None = None
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_connection_type(user_input)

    async def async_step_connection_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._conn_type = user_input[CONF_CONNECTION_TYPE]
            self._data[CONF_CONNECTION_TYPE] = self._conn_type
            if self._conn_type == CONN_TYPE_LOCAL:
                return await self.async_step_local()
            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="connection_type",
            data_schema=STEP_TYPE_SCHEMA,
            description_placeholders={},
        )

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
                title = f"Intellipool @ {user_input[CONF_HOST]}"
                return self.async_create_entry(title=title, data=self._data)

        return self.async_show_form(
            step_id="local",
            data_schema=STEP_LOCAL_SCHEMA,
            errors=errors,
        )

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
                if api.pool_id:
                    user_input[CONF_POOL_ID] = api.pool_id
                self._data.update(user_input)
                title = f"Intellipool ({user_input[CONF_USERNAME]})"
                return self.async_create_entry(title=title, data=self._data)

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_SCHEMA,
            errors=errors,
        )

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
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    int, vol.Range(min=10, max=300)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
