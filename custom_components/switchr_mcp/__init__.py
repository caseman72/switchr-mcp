"""SwitchBot MCP Integration for Home Assistant."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, CONF_MCP_HOST, CONF_MCP_PORT

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBot MCP from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_MCP_HOST, DEFAULT_HOST)
    port = entry.data.get(CONF_MCP_PORT, DEFAULT_PORT)

    hass.data[DOMAIN][entry.entry_id] = {
        "host": host,
        "port": port,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
