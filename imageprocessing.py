import datetime
import logging
# import asyncio
import aiohttp
import io
import numpy as np
from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator
)

# from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import (
    CONF_URL,
    # CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    CONF_NAME,
    # CONF_VERIFY_SSL,
)

# from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImageProcessor:
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry
    ):
        """Initialize the Image processing class."""
        self.hass = hass
        self.config_entry = config_entry
        self.http_session = None
        self.update_coordinator = None

        self.available = False
        self.progress = None

        self.color_norm = None

        self.unsub_config_entry_listener = None

    async def get_image(self):
        return await get_image(self.hass, self.http_session,
                               self.config_entry.data)

    def _get_color_norm(self, image):
        [r, g, b] = [np.squeeze(i) for i in np.split(image, 3, axis=2)]
        rn = np.linalg.norm(r, 'fro')
        bn = np.linalg.norm(b, 'fro')
        gn = np.linalg.norm(g, 'fro')
        rgn = np.linalg.norm(r-g, 'fro')
        gbn = np.linalg.norm(g-b, 'fro')
        brn = np.linalg.norm(b-r, 'fro')
        return (rgn/(rn+gn) + gbn/(gn+bn) + brn/(bn+rn))/3

    # def _get_bw(self, image):
    #     return (self._get_color_norm(image) < 0.01)

    @property
    def bw(self):
        if self.color_norm is not None:
            return (self.color_norm < 0.01)
        else:
            return None

    async def refresh_image(self):
        _LOGGER.debug(f"Checking BW for {self.config_entry.data[CONF_NAME]}")
        try:
            image = await self.get_image()
        except aiohttp.client_exceptions.ClientConnectorError as e:
            _LOGGER.warning(f"Connection error: {str(e)}")
            self.available = False
        except aiohttp.client_exceptions.ClientResponseError as e:
            _LOGGER.error(f"HTTP Error {str(e)}")
            self.available = False
        else:
            self.available = True
        self.color_norm = self._get_color_norm(image)

    @property
    def url(self):
        return self.config_entry.data[CONF_URL]

    async def request_update(self):
        """Request an update."""
        _LOGGER.info(
            f"Update request received for {self.config_entry.data[CONF_NAME]}"
        )
        if self.progress is not None:
            _LOGGER.debug("Another update is in progress")
            await self.progress
            return

        self.progress = self.hass.async_create_task(self.async_update())
        await self.progress
        _LOGGER.debug("Update completed")

        self.progress = None

    async def _async_real_update(self):
        """Update Image information."""
        await self.refresh_image()
        _LOGGER.debug(
            f"BW value is {self.bw} for {self.config_entry.data[CONF_NAME]}"
        )

    async def async_update(self):
        await self.update_coordinator.async_request_refresh()

    async def async_setup(self):
        """Set up the Image processing class."""
        # try:
        #     await self.get_image()
        # except aiohttp.client_exceptions.ClientConnectorError as e:
        #     _LOGGER.warning(f"Connection error: {str(e)}")
        #     raise ConfigEntryNotReady
        # except aiohttp.client_exceptions.ClientResponseError as e:
        #     if e.status == 401:
        #         _LOGGER.warning("Bad credentials")
        #         return False
        #     else:
        #         _LOGGER.error(f"HTTP Error {str(e)}")
        #         raise ConfigEntryNotReady
        _LOGGER.debug("Initializing HTTP session")
        self.http_session = aiohttp.ClientSession()

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry,
                "binary_sensor"
            )
        )

        _LOGGER.debug("Setting up coordinator")
        self.update_coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="EnricoImage updater",
            update_method=self._async_real_update,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=datetime.timedelta(
                seconds=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL,
                    self.config_entry.data.get(CONF_SCAN_INTERVAL, 60)
                )
            )
        )

        _LOGGER.debug("Performing first refresh")
        # await self.async_update()
        await self.update_coordinator.async_refresh()

        self.unsub_config_entry_listener = self.config_entry.\
            add_update_listener(_update_listener)

        return True

    # async def async_reset(self):
    #     _LOGGER.info("Reset received")
    #     await self.async_unload()

    async def async_unload(self):
        _LOGGER.info(
            f"Unloading component {self.config_entry.data[CONF_NAME]}"
        )
        await self.http_session.close()
        _LOGGER.debug("HTTP session closed")
        if self.unsub_config_entry_listener is not None:
            self.unsub_config_entry_listener()
        _LOGGER.debug("Unsubbed from update")

        # # Remove all child entities
        # results = await asyncio.gather(
        #     self.hass.config_entries.async_forward_entry_unload(
        #         self.config_entry, "binary_sensor"
        #     )
        # )
        # _LOGGER.debug(f"Removed children: {str(results)}")
        # return False not in results

        return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Config update received")
    await hass.config_entries.async_reload(entry.entry_id)


async def get_image(hass, http_session, config):
    url = config[CONF_URL]
    if not config.get(CONF_VERIFY_SSL, True):
        _LOGGER.debug("Disabling SSL verify")
        http_ssl = None
    else:
        http_ssl = False
    if (CONF_USERNAME in config) and \
       (CONF_PASSWORD in config):
        _LOGGER.debug("Using HTTP basic auth")
        http_auth = aiohttp.BasicAuth(
            config[CONF_USERNAME],
            config[CONF_PASSWORD]
        )
    else:
        http_auth = None

    http_session_was_closed = False
    if http_session.closed:
        _LOGGER.error("Closed HTTP session received by get_image, will reopen")
        http_session = aiohttp.ClientSession()
        http_session_was_closed = True

    _LOGGER.debug("Making request")
    request = await http_session.get(
        url,
        auth=http_auth,
        ssl=http_ssl
    )
    request.raise_for_status()

    _LOGGER.debug("Creating image")
    image = np.asarray(Image.open(io.BytesIO(await request.read())))

    if http_session_was_closed:
        _LOGGER.debug("Closing HTTP session (the one received was closed)")
        http_session.close()

    return image
