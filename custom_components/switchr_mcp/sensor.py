"""Sensor platform for SwitchBot MCP devices.

Plug Mini sensors (Power/Voltage/Current/Energy) read from a shared
PlugCoordinator that does one `get_all_plugs` call per cycle. Temperature
sensors (Meter/MeterPlus/WoIOSensor) still poll individually since their
cadence is slower and they aren't bunched per-device.
"""
import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfEnergy,
)

from .const import DOMAIN
from .coordinator import PlugCoordinator
from .mcp_client import call_mcp_tool, fetch_devices

SCAN_INTERVAL = timedelta(seconds=180)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot MCP sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    port = data["port"]
    plug_coordinator: PlugCoordinator = data["plug_coordinator"]

    devices = await fetch_devices(host, port)

    entities = []
    for device in devices:
        device_type = device.get("type", "")
        if device_type in ("Meter", "MeterPlus", "WoIOSensor"):
            entities.append(WoIOSensor(host, port, device))
        elif device_type.startswith("Plug Mini") or device_type == "Plug":
            entities.append(PlugMiniPower(plug_coordinator, device))
            entities.append(PlugMiniVoltage(plug_coordinator, device))
            entities.append(PlugMiniCurrent(plug_coordinator, device))
            entities.append(PlugMiniEnergy(plug_coordinator, device))

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


class PlugMiniBase(CoordinatorEntity[PlugCoordinator], SensorEntity):
    """Base for Plug Mini sensors that read from PlugCoordinator."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _suffix = ""
    _value_key = ""

    def __init__(self, coordinator: PlugCoordinator, device: dict):
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = f"{self._device_name} {self._suffix}"
        self._attr_unique_id = f"switchr_{self._device_id}_{self._suffix.lower()}"

    @property
    def _plug(self) -> dict:
        return (self.coordinator.data or {}).get(self._device_id) or {}

    @property
    def native_value(self):
        return self._plug.get(self._value_key)

    @property
    def extra_state_attributes(self) -> dict:
        plug = self._plug
        return {
            "power_state": plug.get("power"),
            "device_id": self._device_id,
        }


class PlugMiniPower(PlugMiniBase):
    """Instantaneous power draw (W) for a SwitchBot Plug Mini."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:flash"
    _suffix = "Power"
    _value_key = "watts"


class PlugMiniVoltage(PlugMiniBase):
    """Line voltage (V) for a SwitchBot Plug Mini."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_icon = "mdi:sine-wave"
    _suffix = "Voltage"
    _value_key = "voltage"


class PlugMiniCurrent(PlugMiniBase):
    """Current draw (mA) for a SwitchBot Plug Mini."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
    _attr_icon = "mdi:current-ac"
    _suffix = "Current"
    _value_key = "currentMilliamps"


class PlugMiniEnergy(CoordinatorEntity[PlugCoordinator], SensorEntity, RestoreEntity):
    """Cumulative energy (kWh) for a SwitchBot Plug Mini.

    Trapezoidal integration of instantaneous power between successive
    coordinator updates. Persists across HA restarts via RestoreEntity.
    Suitable for the HA Energy dashboard (TOTAL_INCREASING, kWh).
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: PlugCoordinator, device: dict):
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._device_name = device["name"]
        self._attr_name = f"{self._device_name} Energy"
        self._attr_unique_id = f"switchr_{self._device_id}_energy"
        self._total_kwh = 0.0
        self._last_update: datetime | None = None
        self._last_watts: float | None = None
        self._attr_native_value = 0.0
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state not in (None, "unknown", "unavailable"):
            try:
                self._total_kwh = float(last.state)
                self._attr_native_value = round(self._total_kwh, 4)
            except (ValueError, TypeError):
                pass
        # Apply current coordinator data immediately on add
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        plug = (self.coordinator.data or {}).get(self._device_id) or {}
        watts = plug.get("watts")
        if watts is None:
            super()._handle_coordinator_update()
            return

        now = datetime.now(timezone.utc)
        if self._last_update is not None and self._last_watts is not None:
            dt_hours = (now - self._last_update).total_seconds() / 3600
            avg_watts = (watts + self._last_watts) / 2
            self._total_kwh += (avg_watts * dt_hours) / 1000

        self._last_update = now
        self._last_watts = watts
        self._attr_native_value = round(self._total_kwh, 4)
        self._attr_extra_state_attributes = {
            "current_watts": watts,
            "device_id": self._device_id,
        }
        super()._handle_coordinator_update()
