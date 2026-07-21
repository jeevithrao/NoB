import type { SessionEventIn } from '../api/types';

function key(sessionId: string) {
  return `nob:pending_events:${sessionId}`;
}

export function queueSessionEvent(sessionId: string, event: SessionEventIn): void {
  const raw = localStorage.getItem(key(sessionId));
  const queue: SessionEventIn[] = raw ? JSON.parse(raw) : [];
  queue.push(event);
  localStorage.setItem(key(sessionId), JSON.stringify(queue));
}

export function getQueuedEvents(sessionId: string): SessionEventIn[] {
  const raw = localStorage.getItem(key(sessionId));
  return raw ? JSON.parse(raw) : [];
}

export function clearQueuedEvents(sessionId: string): void {
  localStorage.removeItem(key(sessionId));
}
