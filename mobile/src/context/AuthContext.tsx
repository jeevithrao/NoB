import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/endpoints';
import { setAccessToken } from '../api/client';
import { STORAGE_KEYS } from '../api/constants';
import { uuidv4 } from '../api/uuid';
import type { User } from '../types';

interface AuthContextValue {
  isLoading: boolean;
  user: User | null;
  deviceId: string;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** device_identifier is a UUID generated on first launch and persisted
 * locally (not a hardware serial) — this is what purchases.device_id and
 * the single-active-session check bind against, per the Business Rules doc. */
async function getOrCreateDeviceId(): Promise<string> {
  const existing = await AsyncStorage.getItem(STORAGE_KEYS.DEVICE_ID);
  if (existing) return existing;
  const created = uuidv4();
  await AsyncStorage.setItem(STORAGE_KEYS.DEVICE_ID, created);
  return created;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [deviceId, setDeviceId] = useState('');

  useEffect(() => {
    (async () => {
      const id = await getOrCreateDeviceId();
      setDeviceId(id);

      const [storedAccess, storedUser] = await AsyncStorage.multiGet([
        STORAGE_KEYS.ACCESS_TOKEN,
        STORAGE_KEYS.USER,
      ]);
      const accessToken = storedAccess[1];
      const userJson = storedUser[1];

      if (accessToken && userJson) {
        setAccessToken(accessToken);
        setUser(JSON.parse(userJson));
        // Verify the session is still active server-side (it may have been
        // invalidated by a login on another device while this app was shut).
        try {
          const freshUser = await authApi.me();
          setUser(freshUser);
        } catch {
          await clearSession();
        }
      }
      setIsLoading(false);
    })();
  }, []);

  async function persistSession(accessToken: string, refreshToken: string, sessionUser: User) {
    setAccessToken(accessToken);
    await AsyncStorage.multiSet([
      [STORAGE_KEYS.ACCESS_TOKEN, accessToken],
      [STORAGE_KEYS.REFRESH_TOKEN, refreshToken],
      [STORAGE_KEYS.USER, JSON.stringify(sessionUser)],
    ]);
    setUser(sessionUser);
  }

  async function clearSession() {
    setAccessToken(null);
    await AsyncStorage.multiRemove([STORAGE_KEYS.ACCESS_TOKEN, STORAGE_KEYS.REFRESH_TOKEN, STORAGE_KEYS.USER]);
    setUser(null);
  }

  async function login(email: string, password: string) {
    const tokens = await authApi.login(email, password, deviceId);
    await persistSession(tokens.access_token, tokens.refresh_token, tokens.user);
  }

  async function signup(email: string, password: string, fullName: string) {
    const tokens = await authApi.signup(email, password, fullName, deviceId);
    await persistSession(tokens.access_token, tokens.refresh_token, tokens.user);
  }

  async function logout() {
    try {
      await authApi.logout();
    } catch {
      // Even if the network call fails, still clear local state.
    }
    await clearSession();
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
