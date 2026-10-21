// Runs the whole app flow through api.js against a running API (mock payments).
//   node docs/frontend-kit/smoke.mjs [http://localhost:8000]
// Proves the client and the API agree, the same way the real screens will use them.
import { createApi, formatPrice, metaLine } from './api.js'

const base = process.argv[2] || 'http://localhost:8000'
const events = []
const api = createApi({ baseUrl: base, onSessionEnded: r => events.push(r) })
let n = 0
const ok = (name, extra = '') => console.log(`OK   ${String(++n).padStart(2)} ${name}${extra ? '  ' + extra : ''}`)
const must = (cond, msg) => {
  if (!cond) {
    console.error('FAIL', msg)
    process.exit(1)
  }
}
const expectError = async (name, code, fn) => {
  try {
    await fn()
  } catch (e) {
    must(e instanceof api.ApiError && e.code === code, `${name}: expected ${code}, got ${e.code || e}`)
    return ok(name, `-> ${code}`)
  }
  must(false, `${name}: expected ${code} but it succeeded`)
}

const email = `kit_${Math.random().toString(36).slice(2, 10)}@example.com`
const handle = 'kit_' + Math.random().toString(36).slice(2, 8)
const user = await api.auth.signup({ email, password: 'correct-horse-1', fullName: 'Kit Tester', acceptedTerms: true })
must(user.email === email, 'signup'); ok('signup')
await expectError('signup without accepting terms', 'VALIDATION_ERROR', () =>
  createApi({ baseUrl: base }).auth.signup({ email: 'x' + email, password: 'correct-horse-1', acceptedTerms: false }))

// Explore + filters
const tours = await api.tours.list()
must(tours.length >= 4, 'tours'); ok('list tours', `${tours.length} walks`)
const first = tours[0]
ok('card fields', `${first.name} | ${formatPrice(first.price_paise)} | ${metaLine(first)} | ${first.neighbourhood.name} ${first.neighbourhood.emoji}`)
const heritage = await api.tours.list({ theme: ['Heritage'] })
must(heritage.every(t => t.theme === 'Heritage') && heritage.length >= 1, 'theme filter'); ok('filter by theme')
const quick = await api.tours.list({ maxDuration: 75, free: false })
must(quick.every(t => t.duration_min <= 75 && !t.is_free), 'duration filter'); ok('filter by duration + paid')
ok('featured', `${(await api.tours.featured()).length} walks`)
const hoods = await api.neighbourhoods.list()
const hood = await api.neighbourhoods.detail(hoods[0].slug)
must(hood.tours.length >= 1, 'neighbourhood detail'); ok('neighbourhood hub', hood.name)

// Walk detail
const paid = tours.find(t => !t.is_free)
const detail = await api.tours.detail(paid.id)
must(detail.stops_preview.length >= 3 && detail.start_point && detail.tags.length, 'detail fields'); ok('walk detail', `${detail.stops_preview.length} stops, start: ${detail.start_point}`)
must(!JSON.stringify(detail.stops_preview).includes('audio'), 'preview leaks audio')
const sample = await fetch(api.mediaUrl(detail.preview_audio_url))
must(sample.ok, 'preview audio'); ok('audio sample plays', detail.preview_audio_title)

// Buy -> bind -> download -> walk
await expectError('walking before buying', 'TOUR_NOT_OWNED', () => api.sessions.start(paid.id))
const bought = await api.purchases.buy(paid.id)
must(bought.status === 'completed', 'mock purchase'); ok('buy (mock payments)')
await api.purchases.bindDevice(bought.purchase_id); ok('bind device')
const pkg = await api.tours.package(paid.id)
const audio = await fetch(api.mediaUrl(pkg.stops[0].audio_url))
must(pkg.stops.length === detail.stops_preview.length && audio.ok, 'package'); ok('package + first audio file', `${pkg.stops.length} stops`)
const session = await api.sessions.start(paid.id)
await api.sessions.sendEvents(session.id, pkg.stops.map(s => ({ stopId: s.id, type: 'arrived' })))
const resumed = await api.sessions.start(paid.id)
must(resumed.id === session.id && resumed.stops_visited === pkg.stops.length, 'resume'); ok('events saved; start again resumes')
await api.sessions.complete(session.id)
const sum = await api.sessions.summary(session.id)
must(sum.completed && sum.stamp_earned, 'summary'); ok('walk complete', `stamp earned: ${sum.stamp_earned}`)
await expectError('replaying a finished walk', 'TOUR_ALREADY_COMPLETED', () => api.sessions.start(paid.id))

// Reactions
await api.social.rate(paid.id, 5)
await api.social.like(paid.id)
await api.social.comment(paid.id, 'Lovely walk')
const r = await api.reviews.recent({ tourId: paid.id })
const mine = r.filter(x => x.user_name === 'Kit T.' && x.content === 'Lovely walk')
must(mine.length >= 1 && mine[0].rating === 5, 'review feed'); ok('rate + like + comment', mine[0].user_name)

// Free walk, bookings, passport, profile, notifications
const free = tours.find(t => t.is_free)
await api.purchases.buy(free.id); ok('claim free walk')
const bookings = await api.purchases.bookings('upcoming')
must(bookings.length === 1 && bookings[0].booking_ref.startsWith('NOB-'), 'bookings'); ok('bookings: ready to walk', bookings[0].booking_ref)
const past = await api.purchases.bookings('past')
must(past.length === 1 && past[0].my_rating === 5 && past[0].completed_at, 'past'); ok('bookings: completed')
const pass = await api.me.passport()
must(pass.total_neighbourhoods === 12 && pass.stamps_collected === 1, 'passport'); ok('passport', `${pass.stamps_collected} of ${pass.total_neighbourhoods}`)
const stats = await api.me.stats()
must(stats.walks_completed === 1 && stats.reviews_count === 1, 'stats'); ok('profile stats', JSON.stringify(stats))
await api.me.update({ fullName: 'Kit Tester', username: '@' + handle })
must((await api.me.profile()).username === handle, 'profile'); ok('edit profile')
await api.me.preferences({ analyticsOptIn: true })
const bell = await api.notifications.list()
must(bell.unread_count >= 3, 'bell'); ok('notifications', `${bell.unread_count} unread: ${bell.items.map(i => i.type).join(', ')}`)
await api.notifications.markAllRead()
must((await api.notifications.list()).unread_count === 0, 'read all'); ok('mark all read')
await api.notifications.dismiss(bell.items[0].id); ok('dismiss one')

// Second browser = second device
const other = createApi({ baseUrl: base, onSessionEnded: r => events.push(r) })
const free2 = tours.filter(t => !t.is_free)[1]
await api.purchases.buy(free2.id)
const b2 = (await api.purchases.bookings('upcoming')).find(b => b.tour.id === free2.id)
await api.purchases.bindDevice(b2.purchase_id)
await other.auth.login({ email, password: 'correct-horse-1' })
must(events.length === 0, 'no events yet')
await expectError('old browser is signed out after login elsewhere', 'SESSION_INVALIDATED', () => api.me.profile())
must(events[0] === 'other_device', 'onSessionEnded callback'); ok('onSessionEnded fired', events[0])
const row = (await other.purchases.bookings('upcoming')).find(x => x.purchase_id === b2.purchase_id)
must(row.device_status === 'other_device', 'device status'); ok('booking shows it is on another device')
await expectError('walking from the new device', 'BOUND_TO_OTHER_DEVICE', () => other.sessions.start(free2.id))
await other.purchases.rebindDevice(b2.purchase_id)
await other.sessions.start(free2.id); ok('moved to this device, walk starts')

// Export + delete
const data = await other.me.exportData()
must(data.profile.email === email && data.purchases.length === 3, 'export'); ok('download my data', `${data.purchases.length} purchases`)
await other.me.deleteAccount()
must(!other.isSignedIn(), 'tokens cleared'); ok('account deleted, local session cleared')
await expectError('deleted account cannot log in', 'INVALID_CREDENTIALS', () => other.auth.login({ email, password: 'correct-horse-1' }))
console.log('\nALL STEPS PASSED')
