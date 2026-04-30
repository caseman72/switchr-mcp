"""Button platform for SwitchBot Bot (finger simulator) devices via MCP."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .mcp_client import call_mcp_tool, fetch_devices

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot MCP button entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    port = data["port"]

    devices = await fetch_devices(host, port)

    entities = []
    for device in devices:
        if device.get("type") == "Bot":
            entities.append(BotPressButton(host, port, device))

    async_add_entities(entities)


class BotPressButton(ButtonEntity):
    """Press a SwitchBot Bot (finger simulator). Suitable for pressMode bots."""

    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, host: str, port: int, device: dict):
        self._host = host
        self._port = port
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = f"{self._device_name} Press"
        self._attr_unique_id = f"switchr_{self._device_id}_press"

    async def async_press(self) -> None:
        result = await call_mcp_tool(
            self._host,
            self._port,
            "press_bot",
            {"deviceId": self._device_id},
        )
        if not result or "error" in result:
            _LOGGER.error("press_bot failed for %s: %s", self._device_name, result)
