import AsyncStorage from '@react-native-async-storage/async-storage';
import { STORAGE_KEYS } from './constants';
import type { DownloadedTour, SessionEventIn } from '../types';

export async function saveDownloadedTour(tourId: string, data: DownloadedTour): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.DOWNLOADED_TOUR_PREFIX + tourId, JSON.stringify(data));
}

export async function getDownloadedTour(tourId: string): Promise<DownloadedTour | null> {
  const raw = await AsyncStorage.getItem(STORAGE_KEYS.DOWNLOADED_TOUR_PREFIX + tourId);
  return raw ? JSON.parse(raw) : null;
}

/** Session events are queued here first — written locally the instant they
 * happen so a GPS trigger during the walk never depends on network
 * availability — then flushed to the backend opportunistically. */
export async function queueSessionEvent(sessionId: string, event: SessionEventIn): Promise<void> {
  const key = STORAGE_KEYS.PENDING_EVENTS_PREFIX + sessionId;
  const raw = await AsyncStorage.getItem(key);
  const queue: SessionEventIn[] = raw ? JSON.parse(raw) : [];
  queue.push(event);
  await AsyncStorage.setItem(key, JSON.stringify(queue));
}

export async function getQueuedEvents(sessionId: string): Promise<SessionEventIn[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_EVENTS_PREFIX + sessionId);
  return raw ? JSON.parse(raw) : [];
}

export async function clearQueuedEvents(sessionId: string): Promise<void> {
  await AsyncStorage.removeItem(STORAGE_KEYS.PENDING_EVENTS_PREFIX + sessionId);
}
