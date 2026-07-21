import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/endpoints';
import { setAccessToken } from '../api/client';
import { STORAGE_KEYS } from '../api/constants';
import { uuidv4 } from '../lib/uuid';
import type { User } from '../api/types';

interface AuthContextValue {
  isLoading: boolean;
  user: User | null;
  deviceId: string;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** A per-browser device id, generated once and persisted — this is what
 * purchases.device_id and the single-active-session check bind against. */
function getOrCreateDeviceId(): string {
  const existing = localStorage.getItem(STORAGE_KEYS.DEVICE_ID);
  if (existing) return existing;
  const created = uuidv4();
  localStorage.setItem(STORAGE_KEYS.DEVICE_ID, created);
  return created;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [deviceId] = useState(getOrCreateDeviceId);

  useEffect(() => {
    function handleSessionExpired() {
      setUser(null);
    }
    window.addEventListener('nob:session-expired', handleSessionExpired);
    return () => window.removeEventListener('nob:session-expired', handleSessionExpired);
  }, []);

  useEffect(() => {
    (async () => {
      const accessToken = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
      const userJson = localStorage.getItem(STORAGE_KEYS.USER);

      if (accessToken && userJson) {
        setUser(JSON.parse(userJson));
        try {
          const freshUser = await authApi.me();
          setUser(freshUser);
          localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(freshUser));
        } catch {
          clearSession();
        }
      }
      setIsLoading(false);
    })();
  }, []);

  function persistSession(accessToken: string, refreshToken: string, sessionUser: User) {
    setAccessToken(accessToken);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(sessionUser));
    setUser(sessionUser);
  }

  function clearSession() {
    setAccessToken(null);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    setUser(null);
  }

  async function login(email: string, password: string) {
    const tokens = await authApi.login(email, password, deviceId);
    persistSession(tokens.access_token, tokens.refresh_token, tokens.user);
  }

  async function signup(email: string, password: string, fullName: string) {
    const tokens = await authApi.signup(email, password, fullName, deviceId);
    persistSession(tokens.access_token, tokens.refresh_token, tokens.user);
  }

  async function logout() {
    try {
      await authApi.logout();
    } catch {
      // Clear local state regardless of whether the network call succeeded.
    }
    clearSession();
  }

  return (
    <AuthContext.Provider value={{ isLoading, user, deviceId, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
