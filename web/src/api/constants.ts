// Vite exposes env vars prefixed with VITE_ on import.meta.env.
// Create a .env.local with VITE_API_BASE_URL if the backend isn't on localhost:8000.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'nob:access_token',
  REFRESH_TOKEN: 'nob:refresh_token',
  USER: 'nob:user',
  DEVICE_ID: 'nob:device_id',
} as const;
