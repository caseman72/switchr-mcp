# Switchr MCP Server

A Node.js MCP (Model Context Protocol) server that exposes SwitchBot temperature sensors for monitoring via Claude Desktop or Home Assistant.

## Features

- **Device Discovery**: Automatically discovers all SwitchBot devices (Meter, MeterPlus, WoIOSensor)
- **Temperature Monitoring**: Read temperature and humidity from any sensor
- **Flexible Units**: Support for both Fahrenheit and Celsius
- **Device Lookup**: Find devices by ID or nickname (case-insensitive)
- **Dual Transport**: Supports both stdio (Claude Desktop) and HTTP/SSE (Home Assistant)
- **Request Logging**: Optional logging of all tool calls for debugging

## Installation

```bash
cd switchr-mcp
npm install
```

## Configuration

### SwitchBot Credentials

SwitchBot API credentials are managed by [@caseman72/switchr-api](https://github.com/caseman72/switchr-api) via `.env.local`. The file is searched in:

1. Current working directory
2. `~/.config/switchr-api/.env.local`
3. `~/.switchbot.env.local`

Create a `.env.local` file with your SwitchBot credentials:

```bash
SWITCHBOT_TOKEN=your-switchbot-token
SWITCHBOT_SECRET=your-switchbot-secret
```

Visit the [SwitchBot Developer Portal](https://support.switch-bot.com/hc/en-us/articles/12822710195351-How-to-obtain-a-Token) to obtain your API credentials.

### Server Configuration (Optional)

Copy `config.example.json` to `config.json` to customize server settings:

```json
{
  "server": {
    "transport": "stdio",
    "httpPort": 8001,
    "httpHost": "127.0.0.1"
  },
  "devices": {
    "refreshIntervalMinutes": 60
  },
  "monitoring": {
    "enabled": false,
    "logFile": "./switchr-mcp-requests.log"
  }
}
```

## Usage

### stdio Transport (Claude Desktop)

```bash
node src/index.js
```

### HTTP Transport (Home Assistant)

The HA custom component requires the MCP server to be exposed over HTTP/SSE. Use `mcp-proxy` to bridge the stdio server.

#### Install mcp-proxy

```bash
brew install mcp-proxy
```

#### Start the proxy

```bash
# Binds to all interfaces so Docker can reach it
mcp-proxy --port 8082 --host 0.0.0.0 -- node /path/to/switchr-mcp/src/index.js
```

### Home Assistant Integration

1. Copy the custom component to your HA config directory:
   ```bash
   cp -r custom_components/switchr_mcp ~/.home-assistant/custom_components/
   ```

2. Restart Home Assistant

3. Add the integration: Settings → Devices & Services → Add Integration → "Switchr MCP"

4. Enter connection details:
   - Host: `host.docker.internal` (for Docker) or your Mac's IP
   - Port: `8082`

#### Auto-start mcp-proxy with launchd

Create `~/Library/LaunchAgents/com.switchr.mcp-proxy.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.switchr.mcp-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/mcp-proxy</string>
        <string>--port</string>
        <string>8082</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--</string>
        <string>/opt/homebrew/bin/node</string>
        <string>/path/to/switchr-mcp/src/index.js</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/switchr-mcp</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/switchr-mcp-proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/switchr-mcp-proxy.err</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.switchr.mcp-proxy.plist
```

To stop/unload:
```bash
launchctl unload ~/Library/LaunchAgents/com.switchr.mcp-proxy.plist
```

#### Managing the service

```bash
# Check status
launchctl list | grep switchr

# View logs
tail -f /tmp/switchr-mcp-proxy.err

# Restart
launchctl unload ~/Library/LaunchAgents/com.switchr.mcp-proxy.plist
launchctl load ~/Library/LaunchAgents/com.switchr.mcp-proxy.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.switchr.mcp-proxy.plist
```

### Claude Desktop Integration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "switchr": {
      "command": "node",
      "args": ["/path/to/switchr-mcp/src/index.js"],
      "env": {}
    }
  }
}
```

## MCP Tools

### `list_devices`

List all discovered SwitchBot devices. Optionally filter to show only temperature sensors.

**Parameters:**
- `sensorsOnly` (optional): If true, only return temperature sensors (Meter, MeterPlus, WoIOSensor)
- `refresh` (optional): Force refresh device list from SwitchBot API

### `get_device_status`

Get detailed status of any SwitchBot device. Returns device-specific properties like power state, battery level, etc.

**Parameters:**
- `deviceId`: Device ID or device name

### `get_temperature`

Get temperature and humidity reading from a specific SwitchBot temperature sensor.

**Parameters:**
- `deviceId`: Device ID or device name of the temperature sensor
- `unit` (optional): Temperature unit - `F` for Fahrenheit (default), `C` for Celsius

**Response includes:**
- `temperature`: Current temperature in requested unit
- `humidity`: Current humidity percentage
- `battery`: Battery level percentage

### `get_all_temperatures`

Get temperature and humidity readings from all SwitchBot temperature sensors at once.

**Parameters:**
- `unit` (optional): Temperature unit - `F` for Fahrenheit (default), `C` for Celsius

### `get_api_status`

Get SwitchBot API rate limit status. Returns remaining calls, reset time, and cache info.

**Response includes:**
- `rate_limit.remaining`: API calls remaining
- `rate_limit.reset_by`: When the rate limit resets
- `cache.last_refresh`: When devices were last refreshed
- `cache.device_count`: Total devices discovered
- `cache.sensor_count`: Temperature sensors discovered

## Request Monitoring

Enable request logging in config.json:

```json
{
  "monitoring": {
    "enabled": true,
    "logFile": "./switchr-mcp-requests.log"
  }
}
```

Logs are written in JSON Lines format with timestamps, tool names, parameters, and results.

## License

MIT
