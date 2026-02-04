import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import {
  discoverDevices,
  getAllDevices,
  getSensors,
  findDevice,
  findSensor,
  getDeviceStatus,
  getTemperature,
  getAllTemperatures,
  getDeviceCache
} from './device-manager.js';
import { getSwitchrClient } from './switchr-client.js';
import { createToolWrapper } from './request-monitor.js';

export function createMcpServer() {
  const server = new McpServer({
    name: 'switchr-mcp',
    version: '1.0.0'
  });

  // Tool: list_devices
  server.tool(
    'list_devices',
    'List all discovered SwitchBot devices. Optionally filter to show only temperature sensors.',
    {
      sensorsOnly: z.boolean().optional()
        .describe('If true, only return temperature sensors (Meter, MeterPlus, WoIOSensor)'),
      refresh: z.boolean().optional()
        .describe('Force refresh device list from SwitchBot API')
    },
    createToolWrapper('list_devices', async ({ sensorsOnly = false, refresh = false }) => {
      await discoverDevices(refresh);
      const cache = getDeviceCache();

      const devices = sensorsOnly ? getSensors() : getAllDevices();

      const deviceList = devices.map(d => ({
        id: d.id,
        name: d.name,
        type: d.type,
        hubDeviceId: d.hubDeviceId
      }));

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            count: deviceList.length,
            devices: deviceList,
            lastRefresh: cache.lastRefresh ? new Date(cache.lastRefresh).toISOString() : null
          }, null, 2)
        }]
      };
    })
  );

  // Tool: get_device_status
  server.tool(
    'get_device_status',
    'Get detailed status of any SwitchBot device. Returns device-specific properties like power state, battery level, etc.',
    {
      deviceId: z.string().describe('Device ID or device name')
    },
    createToolWrapper('get_device_status', async ({ deviceId }) => {
      await discoverDevices();
      const device = findDevice(deviceId);

      if (!device) {
        return {
          content: [{
            type: 'text',
            text: JSON.stringify({ error: `Device not found: ${deviceId}` })
          }],
          isError: true
        };
      }

      const status = await getDeviceStatus(device);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(status, null, 2)
        }]
      };
    })
  );

  // Tool: get_temperature
  server.tool(
    'get_temperature',
    'Get temperature and humidity reading from a specific SwitchBot temperature sensor.',
    {
      deviceId: z.string().describe('Device ID or device name of the temperature sensor'),
      unit: z.enum(['F', 'C']).optional()
        .describe('Temperature unit: "F" for Fahrenheit (default), "C" for Celsius')
    },
    createToolWrapper('get_temperature', async ({ deviceId, unit = 'F' }) => {
      await discoverDevices();
      const sensor = findSensor(deviceId);

      if (!sensor) {
        return {
          content: [{
            type: 'text',
            text: JSON.stringify({ error: `Temperature sensor not found: ${deviceId}` })
          }],
          isError: true
        };
      }

      const temp = await getTemperature(sensor, unit);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(temp, null, 2)
        }]
      };
    })
  );

  // Tool: get_all_temperatures
  server.tool(
    'get_all_temperatures',
    'Get temperature and humidity readings from all SwitchBot temperature sensors at once.',
    {
      unit: z.enum(['F', 'C']).optional()
        .describe('Temperature unit: "F" for Fahrenheit (default), "C" for Celsius')
    },
    createToolWrapper('get_all_temperatures', async ({ unit = 'F' }) => {
      await discoverDevices();
      const temperatures = await getAllTemperatures(unit);

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            count: temperatures.length,
            readings: temperatures
          }, null, 2)
        }]
      };
    })
  );

  // Tool: get_api_status
  server.tool(
    'get_api_status',
    'Get SwitchBot API rate limit status. Returns remaining calls and reset time.',
    {},
    createToolWrapper('get_api_status', async () => {
      const switchr = getSwitchrClient();
      const rateLimit = switchr.getRateLimitStatus();
      const cache = getDeviceCache();

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            rate_limit: {
              remaining: rateLimit.remaining,
              reset_by: rateLimit.resetBy ? new Date(rateLimit.resetBy).toISOString() : null,
              reset_in_seconds: rateLimit.resetIn ? Math.ceil(rateLimit.resetIn / 1000) : null
            },
            cache: {
              last_refresh: cache.lastRefresh ? new Date(cache.lastRefresh).toISOString() : null,
              device_count: getAllDevices().length,
              sensor_count: getSensors().length
            }
          }, null, 2)
        }]
      };
    })
  );

  return server;
}
