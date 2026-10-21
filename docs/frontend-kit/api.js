// NoB API client: drop into the frontend as src/api.js.
// Framework-agnostic ES module (fetch only). Docs: docs/frontend-kit/README.md
//
//   import { createApi, formatPrice } from './api.js'
//   export const api = createApi({ baseUrl: import.meta.env.VITE_API_URL, onSessionEnded: reason => ... })
//
// Handles: bearer token + automatic refresh (single flight), the per-browser device id,
// the {error:{code,message,fields}} envelope, repeated query params, and 204 responses.

export class ApiError extends Error {
  constructor(status, code, message, fields = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code // e.g. 'TOUR_NOT_OWNED', 'BOUND_TO_OTHER_DEVICE', 'VALIDATION_ERROR'
    this.fields = fields // { fieldName: message } for VALIDATION_ERROR
  }
}

const memoryStorage = () => {
  const m = new Map()
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) }
}

const uuid = () =>
  globalThis.crypto && crypto.randomUUID
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
      })

export function createApi({ baseUrl = 'http://localhost:8000', storage, fetchImpl, onSessionEnded } = {}) {
  const store = storage || (typeof localStorage !== 'undefined' ? localStorage : memoryStorage())
  const doFetch = fetchImpl || ((...a) => globalThis.fetch(...a))
  const base = baseUrl.replace(/\/$/, '')
  const K = { access: 'nob.access', refresh: 'nob.refresh', device: 'nob.device' }

  // ---- device id: stable per browser. Clearing site data makes a NEW device
  // (the user then moves their walks over with purchases.rebindDevice).
  const deviceId = () => {
    let id = store.getItem(K.device)
    if (!id) store.setItem(K.device, (id = 'web-' + uuid()))
    return id
  }
  const setTokens = ({ access_token, refresh_token }) => {
    if (access_token) store.setItem(K.access, access_token)
    if (refresh_token) store.setItem(K.refresh, refresh_token)
  }
  const clearTokens = () => {
    store.removeItem(K.access)
    store.removeItem(K.refresh)
  }
  const isSignedIn = () => !!store.getItem(K.access)

  const qs = query => {
    const p = new URLSearchParams()
    Object.entries(query || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      ;(Array.isArray(v) ? v : [v]).forEach(x => p.append(k, String(x)))
    })
    const s = p.toString()
    return s ? '?' + s : ''
  }

  const toError = async res => {
    let body = null
    try {
      body = await res.json()
    } catch (_) {}
    const e = body && body.error
    return new ApiError(res.status, (e && e.code) || 'HTTP_ERROR', (e && e.message) || res.statusText || 'Request failed', (e && e.fields) || {})
  }

  let refreshing = null
  const refresh = () => {
    if (!refreshing) {
      refreshing = (async () => {
        const token = store.getItem(K.refresh)
        if (!token) throw new ApiError(401, 'NO_REFRESH_TOKEN', 'Signed out')
        const res = await doFetch(base + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: token, device_identifier: deviceId() }),
        })
        if (!res.ok) throw await toError(res)
        setTokens(await res.json())
      })().finally(() => (refreshing = null))
    }
    return refreshing
  }

  async function request(method, path, { query, body, auth = true, headers = {}, retry = true } = {}) {
    const h = { Accept: 'application/json', ...headers }
    if (body !== undefined) h['Content-Type'] = 'application/json'
    const token = store.getItem(K.access)
    if (auth && token) h.Authorization = 'Bearer ' + token
    const res = await doFetch(base + path + qs(query), { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) })

    if (res.status === 401 && auth && token) {
      const err = await toError(res)
      if (err.code === 'TOKEN_EXPIRED' && retry) {
        try {
          await refresh()
          return request(method, path, { query, body, auth, headers, retry: false })
        } catch (_) {
          /* fall through to sign-out */
        }
      }
      // SESSION_INVALIDATED = signed in on another device; anything else = bad/expired login
      clearTokens()
      if (onSessionEnded) onSessionEnded(err.code === 'SESSION_INVALIDATED' ? 'other_device' : 'expired')
      throw err
    }
    if (!res.ok) throw await toError(res)
    if (res.status === 204) return null
    const type = res.headers.get('content-type') || ''
    return type.includes('json') ? res.json() : res
  }

  const get = (p, o) => request('GET', p, o)
  const post = (p, body, o) => request('POST', p, { ...o, body })
  const put = (p, body, o) => request('PUT', p, { ...o, body })
  const patch = (p, body, o) => request('PATCH', p, { ...o, body })
  const del = (p, o) => request('DELETE', p, o)

  const signedIn = async data => {
    setTokens(data)
    return data.user
  }

  return {
    deviceId, isSignedIn, ApiError,

    // ---------- auth ----------
    auth: {
      signup: ({ email, password, fullName, acceptedTerms, marketingOptIn = false }) =>
        post('/auth/signup', { email, password, full_name: fullName, accepted_terms: acceptedTerms, marketing_opt_in: marketingOptIn, device_identifier: deviceId() }, { auth: false }).then(signedIn),
      login: ({ email, password }) =>
        post('/auth/login', { email, password, device_identifier: deviceId() }, { auth: false }).then(signedIn),
      google: idToken => post('/auth/google', { id_token: idToken, device_identifier: deviceId() }, { auth: false }).then(signedIn),
      requestOtp: email => post('/auth/request-otp', { email }, { auth: false }),
      verifyOtp: ({ email, code }) => post('/auth/verify-otp', { email, otp: code, device_identifier: deviceId() }, { auth: false }).then(signedIn),
      forgotPassword: email => post('/auth/forgot-password', { email }, { auth: false }),
      resetPassword: ({ email, code, newPassword }) => post('/auth/reset-password', { email, otp: code, new_password: newPassword }, { auth: false }),
      logout: async () => {
        try {
          await post('/auth/logout')
        } finally {
          clearTokens()
        }
      },
    },

    // ---------- catalogue (public; personalised when signed in) ----------
    tours: {
      // filters: { q, neighbourhood: ['malleshwaram'], theme: ['Heritage'], free, minPrice, maxPrice (paise),
      //            minDuration, maxDuration (minutes), sort: newest|price_asc|price_desc|duration|popular|rating, limit, offset }
      list: (f = {}) => get('/tours', { query: { q: f.q, neighbourhood: f.neighbourhood, theme: f.theme, free: f.free, min_price: f.minPrice, max_price: f.maxPrice, min_duration: f.minDuration, max_duration: f.maxDuration, sort: f.sort, limit: f.limit, offset: f.offset } }),
      featured: () => get('/tours/featured'),
      detail: id => get('/tours/' + id), // includes stops_preview, start_point, tags, preview_audio_url...
      package: id => get(`/tours/${id}/package`, { headers: { 'X-Device-Id': deviceId() } }), // stops with coordinates + signed audio_url (owners only)
    },
    neighbourhoods: {
      list: (opts = {}) => get('/neighbourhoods', { query: { include_empty: opts.includeEmpty } }),
      detail: slugOrId => get('/neighbourhoods/' + slugOrId),
    },
    reviews: { recent: ({ tourId, limit } = {}) => get('/reviews', { query: { tour_id: tourId, limit } }) },

    // ---------- buying + bookings ----------
    purchases: {
      // Mock mode: returns status 'completed' straight away. Real mode: open Razorpay Checkout with gateway_config, then verify().
      buy: tourId => post('/purchases', { tour_id: tourId }),
      verify: (purchaseId, r) => post(`/purchases/${purchaseId}/verify`, { razorpay_order_id: r.razorpay_order_id, razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature }),
      get: id => get('/purchases/' + id),
      bookings: (tab = 'all') => get('/purchases', { query: { tab } }), // 'upcoming' | 'past' | 'all'
      bindDevice: id => post(`/purchases/${id}/bind-device`, { device_identifier: deviceId() }),
      rebindDevice: id => post(`/purchases/${id}/rebind-device`, { device_identifier: deviceId() }), // "Use on this device"
      cancel: id => post(`/purchases/${id}/refund`), // only before the walk starts, within 14 days
    },

    // ---------- walking ----------
    sessions: {
      start: tourId => post('/sessions', { tour_id: tourId }), // starts OR resumes
      // events: [{ stopId, type: 'arrived'|'audio_started'|'audio_finished'|'skipped', at?: Date, id?: string }]
      sendEvents: (sessionId, events) =>
        post(`/sessions/${sessionId}/events/batch`, {
          events: events.map(e => ({ client_event_id: e.id || uuid(), stop_id: e.stopId, event_type: e.type, occurred_at: (e.at || new Date()).toISOString() })),
        }),
      complete: sessionId => post(`/sessions/${sessionId}/complete`),
      summary: sessionId => get(`/sessions/${sessionId}/summary`), // the "Walk complete" screen
    },

    // ---------- reactions (only after completing the walk) ----------
    social: {
      rate: (tourId, rating) => put(`/tours/${tourId}/rating`, { rating }),
      rating: tourId => get(`/tours/${tourId}/rating`),
      like: tourId => post(`/tours/${tourId}/like`),
      unlike: tourId => del(`/tours/${tourId}/like`),
      comment: (tourId, text) => post(`/tours/${tourId}/comments`, { comment_text: text }),
      comments: tourId => get(`/tours/${tourId}/comments`),
      save: tourId => post('/saved-tours', { tour_id: tourId }),
      unsave: tourId => del('/saved-tours/' + tourId),
      saved: () => get('/saved-tours'),
    },

    // ---------- me ----------
    me: {
      profile: () => get('/me'),
      update: ({ fullName, username }) => patch('/me', { ...(fullName !== undefined && { full_name: fullName }), ...(username !== undefined && { username }) }),
      preferences: p => patch('/me/preferences', { notifications_enabled: p.notificationsEnabled, analytics_opt_in: p.analyticsOptIn, marketing_opt_in: p.marketingOptIn }),
      stats: () => get('/me/stats'),
      passport: ({ includeEmpty = true } = {}) => get('/me/passport', { query: { include_empty: includeEmpty } }),
      exportData: () => get('/me/export'),
      deleteAccount: async () => {
        await request('DELETE', '/me', { body: { confirm: 'DELETE' } })
        clearTokens()
      },
    },
    notifications: {
      list: ({ limit, unreadOnly } = {}) => get('/me/notifications', { query: { limit, unread_only: unreadOnly } }), // { unread_count, items }
      markRead: id => post(`/me/notifications/${id}/read`),
      markAllRead: () => post('/me/notifications/read-all'),
      dismiss: id => del('/me/notifications/' + id),
    },

    // Turn a relative media path from the API into a playable URL.
    mediaUrl: u => (!u ? u : /^https?:/.test(u) ? u : base + u),
  }
}

// ---------- display helpers (the API sends raw numbers) ----------
export const formatPrice = paise => (paise <= 0 ? 'Free' : '₹' + (paise % 100 ? (paise / 100).toFixed(2) : paise / 100))
export const formatDistance = km => (km == null ? '' : `${km} km`)
export const formatDuration = min => (min == null ? '' : `${min} min`)
export const metaLine = t => [t.distance_km != null && `${t.distance_km}km`, t.duration_min != null && `${t.duration_min} min`].filter(Boolean).join(' · ')
export const starString = (n, outOf = 5) => '★'.repeat(Math.round(n || 0)) + '☆'.repeat(outOf - Math.round(n || 0))
