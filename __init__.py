"""Enrico image BW detection"""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_URL,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv

import voluptuous as vol

from .const import (
    DOMAIN,
)
from .imageprocessing import ImageProcessor

EPIMAGE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_URL): cv.string,
            vol.Optional(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
            vol.Optional(CONF_SCAN_INTERVAL, default=60):
                cv.time_period_seconds
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [EPIMAGE_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Import the ImageProcessor component from config."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}

    if DOMAIN in conf:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up the ImageProcessor component."""

    imp = ImageProcessor(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = imp

    if not await imp.async_setup():
        return False

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(
        config_entry,
        "binary_sensor"
    )
    await hass.data[DOMAIN][config_entry.entry_id].async_unload()
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
