"""Single DataUpdateCoordinator for all SwitchBot Plug Mini devices.

Replaces per-entity polling (5 concurrent SSE handshakes per cycle = mcp-proxy
backpressure) with one batched `get_all_plugs` call per cycle that all plug
entities (Power/Voltage/Current/Energy + Switch) share.

Temp sensors still poll individually for now — their cadence is slower and
they're not bunched per-device the way plugs are.
"""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .mcp_client import call_mcp_tool

_LOGGER = logging.getLogger(__name__)

# 30s gives smooth curves on the Energy dashboard without hammering mcp-proxy.
PLUG_UPDATE_INTERVAL = timedelta(seconds=30)


class PlugCoordinator(DataUpdateCoordinator):
    """Fetch every Plug Mini's status in one MCP call per cycle.

    coordinator.data shape:
        { device_id: { 'power': 'on'|'off', 'watts': float, 'voltage': float,
                       'currentMilliamps': float, ... }, ... }
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int):
        super().__init__(
            hass,
            _LOGGER,
            name="switchr_plugs",
            update_interval=PLUG_UPDATE_INTERVAL,
        )
        self._host = host
        self._port = port

    async def _async_update_data(self) -> dict:
        result = await call_mcp_tool(self._host, self._port, "get_all_plugs", {})
        if not result or "error" in result:
            raise UpdateFailed(f"get_all_plugs returned: {result}")

        plugs = result.get("plugs", [])
        return {p.get("deviceId"): p for p in plugs if p.get("deviceId")}
