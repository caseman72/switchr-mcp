import Switchr from '@caseman72/switchr-api';

let switchrInstance = null;

export function getSwitchrClient() {
  if (switchrInstance) {
    return switchrInstance;
  }

  // switchr-api reads credentials from .env.local in:
  // - Current working directory
  // - ~/.config/switchr-api/.env.local
  // - ~/.switchbot.env.local
  switchrInstance = new Switchr();

  return switchrInstance;
}

export function refreshSwitchrClient() {
  switchrInstance = null;
  return getSwitchrClient();
}
