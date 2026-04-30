"""Switch platform for SwitchBot Plug Mini devices via MCP."""
import logging

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
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
    """Set up SwitchBot MCP switch entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    port = data["port"]

    devices = await fetch_devices(host, port)

    entities = []
    for device in devices:
        device_type = device.get("type", "")
        if device_type.startswith("Plug Mini") or device_type == "Plug":
            entities.append(PlugMiniSwitch(host, port, device))

    async_add_entities(entities)


class PlugMiniSwitch(SwitchEntity):
    """SwitchBot Plug Mini exposed as a switch."""

    _attr_should_poll = True
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:power-socket-us"

    def __init__(self, host: str, port: int, device: dict):
        self._host = host
        self._port = port
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = self._device_name
        self._attr_unique_id = f"switchr_{self._device_id}_switch"
        self._attr_is_on = None
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        result = await call_mcp_tool(
            self._host,
            self._port,
            "get_plug_status",
            {"deviceId": self._device_id},
        )
        if result and "error" not in result:
            self._attr_is_on = result.get("power") == "on"
            self._attr_extra_state_attributes = {
                "watts": result.get("watts"),
                "voltage": result.get("voltage"),
                "device_id": self._device_id,
            }

    async def async_turn_on(self, **kwargs) -> None:
        result = await call_mcp_tool(
            self._host,
            self._port,
            "turn_on",
            {"deviceId": self._device_id},
        )
        if result and "error" not in result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        result = await call_mcp_tool(
            self._host,
            self._port,
            "turn_off",
            {"deviceId": self._device_id},
        )
        if result and "error" not in result:
            self._attr_is_on = False
            self.async_write_ha_state()
