import { API_BASE_URL, STORAGE_KEYS } from './constants';
import type { ApiError, AuthTokens } from './types';

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function setAccessToken(token: string | null) {
  if (token) localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);
  else localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
}

function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}

/** Dedupes concurrent refresh attempts — if five requests 401 at once, only
 * one actual /auth/refresh call goes out and the rest await its result. */
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
    const deviceId = localStorage.getItem(STORAGE_KEYS.DEVICE_ID);
    if (!refreshToken || !deviceId) throw new Error('No refresh token available');

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken, device_identifier: deviceId }),
    });

    if (!response.ok) {
      // Refresh token is dead too (expired, or session invalidated by a
      // login elsewhere) — clear everything and let the app fall back to
      // its logged-out state. AuthContext listens for this event so
      // ProtectedRoute redirects to /login without client.ts needing router access.
      localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);
      window.dispatchEvent(new Event('nob:session-expired'));
      throw new Error('Session expired');
    }

    const tokens = (await response.json()) as AuthTokens;
    setAccessToken(tokens.access_token);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(tokens.user));
    return tokens.access_token;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  auth?: boolean; // defaults to true
  _isRetry?: boolean; // internal — prevents infinite refresh loops
}

/**
 * Thin fetch wrapper used by every function in api/endpoints.ts. Callers get
 * parsed JSON back directly, or a thrown ApiRequestError carrying the
 * backend's {code, message} so screens can branch on `.code` (e.g.
 * BOUND_TO_OTHER_DEVICE, TOUR_ALREADY_COMPLETED) without string-matching.
 *
 * A 401 with code TOKEN_EXPIRED transparently triggers one refresh-and-retry
 * before surfacing an error, so a 60-minute access token never interrupts
 * someone mid-walk.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, _isRetry = false } = options;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const err = data as ApiError;
    const code = err?.error?.code ?? 'UNKNOWN_ERROR';

    if (response.status === 401 && code === 'TOKEN_EXPIRED' && auth && !_isRetry) {
      try {
        await refreshAccessToken();
        return apiRequest<T>(path, { ...options, _isRetry: true });
      } catch {
        // Fall through to throwing the original error below.
      }
    }

    throw new ApiRequestError(response.status, code, err?.error?.message ?? `Request failed with status ${response.status}`);
  }

  return data as T;
}
