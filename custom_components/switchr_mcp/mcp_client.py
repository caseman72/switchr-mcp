"""Minimal MCP-over-SSE client used by switchr_mcp platforms."""
import asyncio
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


async def call_mcp_tool(host: str, port: int, tool_name: str, arguments: dict = None) -> dict:
    """Call an MCP tool via HTTP/SSE and return the parsed text result."""
    base_url = f"http://{host}:{port}"
    arguments = arguments or {}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_url}/sse") as sse_resp:
                session_id = None

                async for line in sse_resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data.startswith("/messages/"):
                            if "session_id=" in data:
                                session_id = data.split("session_id=")[1]
                                break
                        else:
                            try:
                                parsed = json.loads(data)
                                if isinstance(parsed, dict):
                                    endpoint = parsed.get("endpoint", "")
                                    if "session_id=" in endpoint:
                                        session_id = endpoint.split("session_id=")[1]
                                        break
                            except json.JSONDecodeError:
                                continue

                if not session_id:
                    _LOGGER.error("Failed to get MCP session ID")
                    return None

                messages_url = f"{base_url}/messages/?session_id={session_id}"

                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "ha-switchr-mcp", "version": "1.0.0"},
                    },
                }

                async with session.post(messages_url, json=init_request) as init_resp:
                    if init_resp.status != 202:
                        return None

                await asyncio.sleep(0.1)

                notif_request = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
                async with session.post(messages_url, json=notif_request):
                    pass

                tool_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                }

                async with session.post(messages_url, json=tool_request) as tool_resp:
                    if tool_resp.status != 202:
                        return None

                async for line in sse_resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data:"):
                        try:
                            data = json.loads(line[5:].strip())
                            if isinstance(data, dict) and data.get("id") == 2:
                                result = data.get("result", {})
                                content = result.get("content", [])
                                for item in content:
                                    if item.get("type") == "text":
                                        return json.loads(item.get("text", "{}"))
                                return result
                        except json.JSONDecodeError:
                            continue

                return None

    except asyncio.TimeoutError:
        _LOGGER.error("MCP tool call timed out")
        return None
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("MCP tool call failed: %s", e)
        return None


async def fetch_devices(host: str, port: int) -> list:
    """Fetch list of all devices from MCP."""
    result = await call_mcp_tool(host, port, "list_devices", {})
    if result and "devices" in result:
        return result["devices"]
    return []
