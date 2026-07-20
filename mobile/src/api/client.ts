import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL, STORAGE_KEYS } from './constants';
import type { ApiError } from '../types';

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let inMemoryAccessToken: string | null = null;

export function setAccessToken(token: string | null) {
  inMemoryAccessToken = token;
}

async function getAccessToken(): Promise<string | null> {
  if (inMemoryAccessToken) return inMemoryAccessToken;
  const stored = await AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
  inMemoryAccessToken = stored;
  return stored;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  auth?: boolean; // defaults to true
}

/**
 * Thin fetch wrapper used by every endpoint function in api/endpoints.ts.
 * Callers get back parsed JSON directly, or a thrown ApiRequestError with the
 * backend's {code, message} — screens can switch on `.code` for things like
 * BOUND_TO_OTHER_DEVICE or TOUR_ALREADY_COMPLETED without string-matching.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = await getAccessToken();
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
