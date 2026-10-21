// Live-data layer. Without VITE_API_URL the app runs exactly as the original prototype (hardcoded data.js).
// With it, `hydrate*` fetch from the API and swap the contents of the SAME arrays the screens already import,
// so the screen code stays almost untouched. Screens re-render because App bumps a version after each hydrate.
import { createApi, formatPrice } from './api'
import { walks, neighbourhoods, passportSlots, bookingsData, notificationsData, reviews } from './data'

export const LIVE = Boolean(import.meta.env.VITE_API_URL)
const endedListeners = new Set()
export const api = LIVE
  ? createApi({ baseUrl: import.meta.env.VITE_API_URL, onSessionEnded: r => endedListeners.forEach(f => f(r)) })
  : null
export const onSessionEnded = f => { endedListeners.add(f); return () => endedListeners.delete(f) }

const BGS = ['#A28D6E', '#2E2520', '#B8A898']
const swap = (arr, next) => { arr.splice(0, arr.length, ...next) }
const stars = n => (n == null ? '' : '★'.repeat(Math.round(n)) + '☆'.repeat(5 - Math.round(n)))
const slugOf = name => name.toLowerCase().replace(/\s+/g, '-')

export function friendlyError(e, fallback = 'Something went wrong. Please try again.') {
  if (e && e.fields && Object.keys(e.fields).length) return Object.values(e.fields)[0]
  if (e && e.message && e.status) return e.message
  if (e instanceof TypeError) return "Can't reach the server. Check your connection and try again."
  return fallback
}

export function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 90) return 'Just now'
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  if (s < 172800) return 'Yesterday'
  if (s < 7 * 86400) return `${Math.round(s / 86400)}d ago`
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
const dayLabel = iso => new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })

export function toWalk(t, d = {}, i = 0) {
  const x = { ...t, ...d }
  const hood = x.neighbourhood || {}
  return {
    id: x.id, icon: hood.emoji, t: x.name, tag: hood.name, neighbourhood: hood.slug,
    meta: `${x.distance_km}km · ${x.duration_min} min`, bg: BGS[i % BGS.length],
    price: formatPrice(x.price_paise), pricePaise: x.price_paise, free: x.is_free,
    stars: stars(x.avg_rating), rating: x.avg_rating == null ? 'New' : Number(x.avg_rating).toFixed(1),
    reviewCount: x.rating_count || 0,
    distance: `${x.distance_km} km`, duration: `${x.duration_min} min`,
    start: x.start_point || '', theme: x.theme || '', desc: x.description || '',
    stops: (x.stops_preview || []).map(s => ({ e: s.icon, n: s.name, d: s.blurb })),
    difficulty: x.difficulty || '', language: (x.languages || []).join(' · '),
    included: x.includes || [], tags: x.tags || [],
    sample: x.preview_audio_title ? { title: x.preview_audio_title, stop: 2 } : null, sampleUrl: x.preview_audio_url || null,
    status: x.status, purchaseId: x.purchase_id || null, featured: !!x.is_featured,
  }
}

// Public catalogue: walks (with detail), neighbourhoods, recent reviews. Safe to call signed out.
export async function hydrateCatalog() {
  const [list, hoods, recent] = await Promise.all([api.tours.list(), api.neighbourhoods.list({ includeEmpty: true }), api.reviews.recent({ limit: 20 })])
  const details = await Promise.all(list.map(t => api.tours.detail(t.id).catch(() => ({}))))
  swap(walks, list.map((t, i) => toWalk(t, details[i], i)))
  swap(neighbourhoods, hoods.map((n, i) => ({
    slug: n.slug, name: n.name, emoji: n.emoji, bg: BGS[i % 2 ? 1 : 0],
    tagline: `${n.tagline || n.city} · ${n.tour_count} walk${n.tour_count === 1 ? '' : 's'} available`, description: n.description || '',
  })))
  const byId = Object.fromEntries(walks.map(w => [w.id, w]))
  swap(reviews, recent.map((r, i) => ({
    id: r.id, walkId: r.tour_id, name: r.user_name, tour: byId[r.tour_id] ? byId[r.tour_id].t : r.tour_name,
    stars: stars(r.rating), text: r.content || '', color: BGS[i % BGS.length],
  })).filter(r => r.text))
}

export const profile = { user: null, stats: null }

// Per-user data: bookings, passport, notifications, profile + stats. Requires a signed-in user.
export async function hydrateUser() {
  const [up, past, pass, notes, me, stats] = await Promise.all([
    api.purchases.bookings('upcoming'), api.purchases.bookings('past'), api.me.passport(), api.notifications.list(), api.me.profile(), api.me.stats(),
  ])
  const row = (b, i) => ({
    id: b.purchase_id, ref: b.booking_ref, tourId: b.tour.id, walkName: b.tour.name, neighbourhood: b.tour.neighbourhood.name,
    price: formatPrice(b.amount_paise), icon: b.tour.neighbourhood.emoji, bg: BGS[i % BGS.length],
    walkStatus: b.walk_status, canRefund: b.can_refund, deviceStatus: b.device_status, rebindAvailableAt: b.rebind_available_at,
    walkedOn: b.completed_at ? dayLabel(b.completed_at) : '', reviewed: b.my_rating != null,
  })
  swap(bookingsData.upcoming, up.map(row))
  swap(bookingsData.past, past.map(row))
  swap(passportSlots, pass.stamps.map(s => ({
    slug: s.neighbourhood.slug, name: s.neighbourhood.name, emoji: s.emoji || s.neighbourhood.emoji, collected: s.stamped,
    walkName: s.walk_name || '', date: s.stamped_at ? new Date(s.stamped_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }) : '',
  })))
  swap(notificationsData, notes.items.map(n => ({
    id: n.id, type: n.type, icon: '', title: n.title, subtitle: n.subtitle, time: ago(n.created_at),
    today: Date.now() - new Date(n.created_at).getTime() < 86400000, unread: !n.is_read,
  })))
  profile.user = me
  profile.stats = stats
}

export function clearUserData() {
  swap(bookingsData.upcoming, []); swap(bookingsData.past, []); swap(passportSlots, []); swap(notificationsData, [])
  profile.user = null; profile.stats = null
}

export function downloadJson(data, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a'); a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export { slugOf }


// In live mode never show the prototype's demo rows, even for a moment.
if (LIVE) {
  ;[walks, neighbourhoods, passportSlots, reviews, notificationsData, bookingsData.upcoming, bookingsData.past].forEach(a => { a.length = 0 })
}

export const uid = () => (globalThis.crypto && crypto.randomUUID ? crypto.randomUUID() : 'e' + Date.now() + Math.random().toString(16).slice(2))
export const lastWalk = { summary: null }

// Download every stop's audio once, keep it in the Cache API (keyed WITHOUT the signature so a later,
// freshly signed URL still hits it) and hand back playable blob URLs. This fixes two things at once:
// signed URLs expire after an hour but a walk can run longer, and the walk works with no signal.
export async function prepareAudio(stops, onProgress = () => {}) {
  const store = typeof caches !== 'undefined' ? await caches.open('nob-audio-v1').catch(() => null) : null
  const out = {}
  let done = 0
  for (const s of stops) {
    const url = api.mediaUrl(s.audioUrl)
    const key = url.split('?')[0]
    let res = store ? await store.match(key) : null
    if (!res) {
      const net = await fetch(url)
      if (!net.ok) throw new Error(`Audio for "${s.n}" could not be downloaded (${net.status}).`)
      if (store) await store.put(key, net.clone())
      res = net
    }
    out[s.id] = URL.createObjectURL(await res.blob())
    onProgress(++done, stops.length)
  }
  return out
}
