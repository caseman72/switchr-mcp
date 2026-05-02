"""Switch platform for SwitchBot Plug Mini devices via MCP.

State is driven by the shared PlugCoordinator (one MCP call per cycle for
all plug entities, same as the sensor platform). turn_on/turn_off still
calls the MCP turn_on/turn_off tool directly, then triggers a coordinator
refresh so HA reflects the new state immediately.
"""
import logging

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlugCoordinator
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
    plug_coordinator: PlugCoordinator = data["plug_coordinator"]

    devices = await fetch_devices(host, port)

    entities = []
    for device in devices:
        device_type = device.get("type", "")
        if device_type.startswith("Plug Mini") or device_type == "Plug":
            entities.append(PlugMiniSwitch(plug_coordinator, host, port, device))

    async_add_entities(entities)


class PlugMiniSwitch(CoordinatorEntity[PlugCoordinator], SwitchEntity):
    """SwitchBot Plug Mini exposed as a switch, state from coordinator."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_icon = "mdi:power-socket-us"

    def __init__(self, coordinator: PlugCoordinator, host: str, port: int, device: dict):
        super().__init__(coordinator)
        self._host = host
        self._port = port
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = self._device_name
        self._attr_unique_id = f"switchr_{self._device_id}_switch"

    @property
    def _plug(self) -> dict:
        return (self.coordinator.data or {}).get(self._device_id) or {}

    @property
    def is_on(self) -> bool | None:
        power = self._plug.get("power")
        if power is None:
            return None
        return power == "on"

    @property
    def extra_state_attributes(self) -> dict:
        plug = self._plug
        return {
            "watts": plug.get("watts"),
            "voltage": plug.get("voltage"),
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
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        result = await call_mcp_tool(
            self._host,
            self._port,
            "turn_off",
            {"deviceId": self._device_id},
        )
        if result and "error" not in result:
            await self.coordinator.async_request_refresh()
