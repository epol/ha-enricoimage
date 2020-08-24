"""BW image sensor"""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import (
    ConfigEntry,
    # SOURCE_IMPORT,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
# from homeassistant.helpers import entity_registry
from homeassistant.const import (
    CONF_NAME,
    # CONF_URL,
    # CONF_SCAN_INTERVAL,
    # CONF_VERIFY_SSL,
)

from .imageprocessing import ImageProcessor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# async def async_setup_platform(
#     hass: HomeAssistant, config, async_add_entities, discovery_info=None
# ):
#     _LOGGER.info("Platform setup")
#     hass.async_create_task(
#         hass.config_entries.flow.async_init(
#             DOMAIN, context={"source": SOURCE_IMPORT}, data=config
#         )
#     )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities
):
    _LOGGER.info("Entry setup")
    """Set up binary sensor for image processing."""
    imp = hass.data[DOMAIN][config_entry.entry_id]

    # # Try to restore a old entity
    # registry = await entity_registry.async_get_registry(hass)

    # for entity in registry.entities.values():
    #     if (
    #         entity.config_entry_id == config_entry.entry_id
    #         and entity.domain == "binary_sensor"
    #     ):

    async_add_entities([ImageProcessorColor(imp)], False)


class ImageProcessorColor(BinarySensorEntity):
    """Representation of Color sensor."""

    def __init__(self, imp: ImageProcessor):
        """Initialize the sensor."""
        self.imp = imp

    # @property
    # def entity_picture(self):
    #     """Return the URL of the polled picture"""
    #     return self.imp.config_entry.data[CONF_URL]

    @property
    def icon(self) -> str:
        """Return a icon according to the state"""
        if self.imp.bw is None:
            return "mdi:timer-sand"
        if self.imp.bw:
            return "mdi:invert-colors-off"
        else:
            return "mdi:invert-colors"

    @property
    def is_on(self):
        """Return true if the image is BW."""
        _LOGGER.debug(f"BW result: {self.imp.bw} (will be negated)")
        if self.imp.bw is not None:
            return not self.imp.bw

    @property
    def device_state_attributes(self) -> dict:
        return {
            "Color norm": self.imp.color_norm,
            # "Original URL": self.imp.config_entry.data[CONF_URL],
        }

    @property
    def device_class(self):
        """Return the device class."""
        return "light"

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{self.imp.config_entry.data[CONF_NAME]}-color"

    @property
    def should_poll(self) -> bool:
        """Let HA poll this sensor"""
        return False

    # @property
    # def unique_id(self) -> str:
    #     """Unique ID of the sensor"""
    #     return f"{hash(self.imp.config_entry.data[CONF_URL]):x}-color-bs"

    @property
    def available(self) -> bool:
        """Check if backend is available"""
        return self.imp.available

    async def async_update(self):
        """Recalcolate img state."""
        _LOGGER.debug("Update request received")
        await self.imp.request_update()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.imp.update_coordinator.async_add_listener(
                self.async_write_ha_state
            )
        )
