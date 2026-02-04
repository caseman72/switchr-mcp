import { getSwitchrClient } from './switchr-client.js';
import { getConfig } from './config.js';

let deviceCache = {
  devices: [],
  sensors: [],
  lastRefresh: null
};

function normalizeNickname(nickname) {
  return (nickname || '').toLowerCase().trim();
}

function shouldRefresh() {
  if (!deviceCache.lastRefresh) return true;
  const config = getConfig();
  const refreshInterval = config.devices.refreshIntervalMinutes * 60 * 1000;
  return Date.now() - deviceCache.lastRefresh > refreshInterval;
}

export async function discoverDevices(forceRefresh = false) {
  if (!forceRefresh && !shouldRefresh()) {
    return deviceCache;
  }

  const switchr = getSwitchrClient();
  const { devices } = await switchr.getDevices(forceRefresh);

  const sensors = devices.filter(d =>
    d.deviceType === 'Meter' ||
    d.deviceType === 'MeterPlus' ||
    d.deviceType === 'WoIOSensor'
  );

  deviceCache = {
    devices: devices.map(d => ({
      id: d.deviceId,
      name: d.deviceName,
      type: d.deviceType,
      hubDeviceId: d.hubDeviceId,
      enableCloudService: d.enableCloudService,
      raw: d
    })),
    sensors: sensors.map(d => ({
      id: d.deviceId,
      name: d.deviceName,
      type: d.deviceType,
      hubDeviceId: d.hubDeviceId,
      raw: d
    })),
    lastRefresh: Date.now()
  };

  return deviceCache;
}

export function getAllDevices() {
  return deviceCache.devices;
}

export function getSensors() {
  return deviceCache.sensors;
}

export function findDevice(idOrName) {
  const normalizedSearch = normalizeNickname(idOrName);

  return deviceCache.devices.find(device => {
    const matchesId = device.id === idOrName;
    const matchesName = normalizeNickname(device.name) === normalizedSearch;
    return matchesId || matchesName;
  });
}

export function findSensor(idOrName) {
  const normalizedSearch = normalizeNickname(idOrName);

  return deviceCache.sensors.find(sensor => {
    const matchesId = sensor.id === idOrName;
    const matchesName = normalizeNickname(sensor.name) === normalizedSearch;
    return matchesId || matchesName;
  });
}

export async function getDeviceStatus(device) {
  const switchr = getSwitchrClient();
  const status = await switchr.getStatus(device.id);

  return {
    id: device.id,
    name: device.name,
    type: device.type,
    ...status
  };
}

export async function getTemperature(sensor, unit = 'F') {
  const switchr = getSwitchrClient();
  const temp = await switchr.getTemperature(sensor.id, unit);

  return {
    id: sensor.id,
    name: sensor.name,
    type: sensor.type,
    ...temp
  };
}

export async function getAllTemperatures(unit = 'F') {
  const switchr = getSwitchrClient();
  return switchr.getAllTemperatures(unit);
}

export function getDeviceCache() {
  return deviceCache;
}
