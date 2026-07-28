/**
 * When running on a physical device/simulator, `localhost` means the device
 * itself, not your dev machine — swap this to your machine's LAN IP (e.g.
 * http://192.168.1.23:8000) or an ngrok/tunnel URL. Android emulators can
 * use http://10.0.2.2:8000 to reach the host machine.
 */
export const API_BASE_URL = 'http://192.168.1.5:8000';

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'nob:access_token',
  REFRESH_TOKEN: 'nob:refresh_token',
  USER: 'nob:user',
  DEVICE_ID: 'nob:device_id',
  DOWNLOADED_TOUR_PREFIX: 'nob:downloaded_tour:', // + tour_id
  PENDING_EVENTS_PREFIX: 'nob:pending_events:', // + session_id
} as const;
