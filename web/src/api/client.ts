import { API_BASE_URL, STORAGE_KEYS } from './constants';
import type { ApiError } from './types';

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

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  auth?: boolean; // defaults to true
}

/**
 * Thin fetch wrapper used by every function in api/endpoints.ts. Callers get
 * parsed JSON back directly, or a thrown ApiRequestError carrying the
 * backend's {code, message} so screens can branch on `.code` (e.g.
 * BOUND_TO_OTHER_DEVICE, TOUR_ALREADY_COMPLETED) without string-matching.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options;

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
    throw new ApiRequestError(
      response.status,
      err?.error?.code ?? 'UNKNOWN_ERROR',
      err?.error?.message ?? `Request failed with status ${response.status}`
    );
  }

  return data as T;
}
