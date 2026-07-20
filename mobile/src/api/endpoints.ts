import { apiRequest } from './client';
import type {
  AuthTokens,
  CommentOut,
  PurchaseCreateResponse,
  TourDetail,
  TourListItem,
  TourPackage,
  TourSession,
  SessionEventIn,
  User,
} from '../types';

// ---- Auth ----

export const authApi = {
  signup: (email: string, password: string, fullName: string, deviceIdentifier: string) =>
    apiRequest<AuthTokens>('/auth/signup', {
      method: 'POST',
      auth: false,
      body: { email, password, full_name: fullName, device_identifier: deviceIdentifier },
    }),

  login: (email: string, password: string, deviceIdentifier: string) =>
    apiRequest<AuthTokens>('/auth/login', {
      method: 'POST',
      auth: false,
      body: { email, password, device_identifier: deviceIdentifier },
    }),

  logout: () => apiRequest<void>('/auth/logout', { method: 'POST' }),

  me: () => apiRequest<User>('/auth/me'),
};

// ---- Tours ----

export const toursApi = {
  list: (city = 'Bangalore') => apiRequest<TourListItem[]>(`/tours?city=${encodeURIComponent(city)}`),

  get: (tourId: string) => apiRequest<TourDetail>(`/tours/${tourId}`),

  getPackage: (tourId: string) => apiRequest<TourPackage>(`/tours/${tourId}/package`),

  like: (tourId: string) => apiRequest(`/tours/${tourId}/like`, { method: 'POST' }),
  unlike: (tourId: string) => apiRequest(`/tours/${tourId}/like`, { method: 'DELETE' }),

  listComments: (tourId: string) => apiRequest<CommentOut[]>(`/tours/${tourId}/comments`),
  addComment: (tourId: string, commentText: string) =>
    apiRequest<CommentOut>(`/tours/${tourId}/comments`, {
      method: 'POST',
      body: { comment_text: commentText },
    }),
};

// ---- Purchases ----

export const purchasesApi = {
  create: (tourId: string) =>
    apiRequest<PurchaseCreateResponse>('/purchases', { method: 'POST', body: { tour_id: tourId } }),

  bindDevice: (purchaseId: string, deviceIdentifier: string) =>
    apiRequest(`/purchases/${purchaseId}/bind-device`, {
      method: 'POST',
      body: { device_identifier: deviceIdentifier },
    }),
};

// ---- Sessions (walks) ----

export const sessionsApi = {
  createOrResume: (tourId: string) =>
    apiRequest<TourSession>('/sessions', { method: 'POST', body: { tour_id: tourId } }),

  submitEventsBatch: (sessionId: string, events: SessionEventIn[]) =>
    apiRequest<{ accepted: number; duplicate: number; session: TourSession }>(
      `/sessions/${sessionId}/events/batch`,
      { method: 'POST', body: { events } }
    ),

  complete: (sessionId: string) =>
    apiRequest<TourSession>(`/sessions/${sessionId}/complete`, { method: 'POST' }),
};

// ---- Saved tours ----

export const savedToursApi = {
  save: (tourId: string) => apiRequest('/saved-tours', { method: 'POST', body: { tour_id: tourId } }),
  unsave: (tourId: string) => apiRequest(`/saved-tours/${tourId}`, { method: 'DELETE' }),
  list: () => apiRequest<{ tour_id: string; saved_at: string }[]>('/saved-tours'),
};
