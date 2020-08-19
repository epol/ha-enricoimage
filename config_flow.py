from homeassistant.core import callback
from homeassistant import config_entries
# from homeassistant import data_entry_flow

import voluptuous as vol
import logging
from typing import Any, Dict, Optional

import aiohttp

from .const import DOMAIN

from homeassistant.const import (
    CONF_URL,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)

from .imageprocessing import get_image

_LOGGER = logging.getLogger(__name__)

# @config_entries.HANDLERS.register(DOMAIN)
# class EPImageConfigFlow(data_entry_flow.FlowHandler):


class EPImageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EPImageOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle config flow initialized by user"""
        errors = {}
        if user_input is not None:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_URL] == user_input[CONF_URL]:
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            try:
                http_session = aiohttp.ClientSession()
                await get_image(self.hass, http_session, user_input)
            except aiohttp.client_exceptions.ClientConnectorError as e:
                _LOGGER.warning(f"Connection error: {str(e)}")
                errors["base"] = "cannot_connect"
            except aiohttp.client_exceptions.ClientResponseError as e:
                if e.status == 401:
                    _LOGGER.warning("Bad credentials")
                    errors[CONF_USERNAME] = "wrong_credentials"
                    errors[CONF_PASSWORD] = "wrong_credentials"
                else:
                    _LOGGER.error(f"HTTP Error {str(e)}")
                    errors["base"] = "http_error"
            finally:
                await http_session.close()

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        # Specify items in the order they are to be displayed in the UI
        data_schema = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_URL): str,
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=60
            ): int,
        }

        if self.show_advanced_options:
            pass

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors
        )


class EPImageOptionsFlow(config_entries.OptionsFlow):
    """Handle EPImage options."""

    def __init__(self, config_entry):
        """Initialize EPImage options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None
                              ) -> Dict[str, Any]:
        """Manage the EPImage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL,
                    self.config_entry.data.get(CONF_SCAN_INTERVAL, 60)
                ),
            ): int,
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options)
        )
