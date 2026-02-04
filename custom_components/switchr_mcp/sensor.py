"""Sensor platform for SwitchBot MCP temperature sensors."""
import logging
import json
import asyncio
from datetime import timedelta

import aiohttp

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfTemperature, PERCENTAGE

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=120)

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

    # Get list of temperature sensors from MCP
    devices = await fetch_sensors(host, port)

    entities = []
    for device in devices:
        # Create single combined sensor per device
        entities.append(WoIOSensor(host, port, device))

    async_add_entities(entities)


async def fetch_sensors(host: str, port: int) -> list:
    """Fetch list of temperature sensors from MCP."""
    result = await call_mcp_tool(host, port, "list_devices", {"sensorsOnly": True})
    if result and "devices" in result:
        return result["devices"]
    return []


async def call_mcp_tool(host: str, port: int, tool_name: str, arguments: dict = None) -> dict:
    """Call an MCP tool via HTTP/SSE."""
    base_url = f"http://{host}:{port}"
    arguments = arguments or {}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_url}/sse") as sse_resp:
                session_id = None

                async for line in sse_resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        data = line[5:].strip()
                        if data.startswith('/messages/'):
                            if 'session_id=' in data:
                                session_id = data.split('session_id=')[1]
                                break
                        else:
                            try:
                                parsed = json.loads(data)
                                if isinstance(parsed, dict):
                                    endpoint = parsed.get('endpoint', '')
                                    if 'session_id=' in endpoint:
                                        session_id = endpoint.split('session_id=')[1]
                                        break
                            except json.JSONDecodeError:
                                continue

                if not session_id:
                    _LOGGER.error("Failed to get MCP session ID")
                    return None

                messages_url = f"{base_url}/messages/?session_id={session_id}"

                # Initialize
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "ha-switchr-mcp", "version": "1.0.0"}
                    }
                }

                async with session.post(messages_url, json=init_request) as init_resp:
                    if init_resp.status != 202:
                        return None

                await asyncio.sleep(0.1)

                # Notify initialized
                notif_request = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                }
                async with session.post(messages_url, json=notif_request):
                    pass

                # Call tool
                tool_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }

                async with session.post(messages_url, json=tool_request) as tool_resp:
                    if tool_resp.status != 202:
                        return None

                # Read response
                async for line in sse_resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        try:
                            data = json.loads(line[5:].strip())
                            if isinstance(data, dict) and data.get('id') == 2:
                                result = data.get('result', {})
                                content = result.get('content', [])
                                for item in content:
                                    if item.get('type') == 'text':
                                        return json.loads(item.get('text', '{}'))
                                return result
                        except json.JSONDecodeError:
                            continue

                return None

    except asyncio.TimeoutError:
        _LOGGER.error("MCP tool call timed out")
        return None
    except Exception as e:
        _LOGGER.error("MCP tool call failed: %s", e)
        return None


class WoIOSensor(SensorEntity):
    """Combined sensor for SwitchBot WoIOSensor device."""

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
