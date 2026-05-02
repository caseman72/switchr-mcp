"""Sensor platform for SwitchBot MCP devices.

Temperature sensors (Meter / MeterPlus / WoIOSensor) only — the plug
entities were removed in 1.1.4. Plug monitoring now happens through the
standard HA SwitchBot integration in BLE mode (via an ESPHome
bluetooth_proxy near the plug), which keeps cloud-API call volume on
this account well under SwitchBot's daily rate limit.
"""
import logging
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .mcp_client import call_mcp_tool, fetch_devices

# 180s gives ~6 calls/min when paired with N temp sensors, leaving safe
# headroom under SwitchBot's ~10K/day per-account rate limit.
SCAN_INTERVAL = timedelta(seconds=180)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot MCP temperature sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    port = data["port"]

    devices = await fetch_devices(host, port)

    entities = []
    for device in devices:
        device_type = device.get("type", "")
        if device_type in ("Meter", "MeterPlus", "WoIOSensor"):
            entities.append(WoIOSensor(host, port, device))

    async_add_entities(entities)


class WoIOSensor(SensorEntity):
    """Combined sensor for SwitchBot WoIOSensor / Meter / MeterPlus device."""

    _attr_should_poll = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_icon = "mdi:thermometer"

    def __init__(self, host: str, port: int, device: dict):
        """Initialize the sensor."""
        self._host = host
        self._port = port
        self._device = device
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = self._device_name
        self._attr_unique_id = f"switchr_{self._device_id}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Fetch initial state when entity is added to HA."""
        await super().async_added_to_hass()
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Fetch the current sensor data."""
        result = await call_mcp_tool(
            self._host,
            self._port,
            "get_temperature",
            {"deviceId": self._device_id, "unit": "F"}
        )

        if result and "error" not in result:
            self._attr_native_value = round(result.get("temperature", 0), 1)
            self._attr_extra_state_attributes = {
                "humidity": result.get("humidity"),
                "battery": result.get("battery"),
                "device_id": self._device_id,
                "device_type": result.get("type"),
            }
