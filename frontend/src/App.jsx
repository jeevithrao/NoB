import { useState, useEffect, useRef, useLayoutEffect, useId, Fragment } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { walks, neighbourhoods, passportSlots, bookingsData, notificationsData, reviews } from './data'
import { REMOTE, WIKI, localPhoto, wikiImage, altFor } from './images'
import { LIVE, api, profile, hydrateCatalog, hydrateUser, clearUserData, onSessionEnded, friendlyError, downloadJson, uid, lastWalk, prepareAudio } from './live'
import { User, Search, Bell, Home as HomeIcon, Compass, Settings as SettingsIcon, ArrowLeft, Eye, EyeOff, MapPin, Smartphone, CreditCard, Star, X, Lock, Play, Pause, Ticket, BookOpen, Download, Heart, MessageCircle, Map as MapIcon, CheckCircle2, Pencil, Trash2, FileText, Wallet, Mail, Info, LogOut, BarChart3, ChevronRight, WifiOff, Footprints, Languages, Activity, RotateCcw, RotateCw, Crosshair, Maximize2 } from 'lucide-react'
const Ic = ({ i: I, size = 18 }) => <I size={size} strokeWidth={1.8} aria-hidden="true" />

/* ───────── helpers ───────── */
const cx = (...a) => a.filter(Boolean).join(' ')
const mono = { fontFamily: 'var(--font-ui)' }

// Keyboard-operable "button" for elements that stay <div>/<span> for styling reasons (Enter / Space activate it)
const press = (fn, label) => ({
  role: 'button', tabIndex: 0, 'aria-label': label, onClick: fn,
  onKeyDown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) } },
})

// online / offline status (navigator.onLine + browser events); `retry` increments each time the network comes back
function useOnline() {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const on = () => { setOnline(true); setRetry(r => r + 1) }
    const off = () => setOnline(false)
    window.addEventListener('online', on); window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])
  return { online, retry }
}

function useReducedMotion() {
  const q = '(prefers-reduced-motion: reduce)'
  const [r, setR] = useState(() => typeof window !== 'undefined' && window.matchMedia && window.matchMedia(q).matches)
  useEffect(() => {
    if (!window.matchMedia) return
    const m = window.matchMedia(q), f = () => setR(m.matches)
    m.addEventListener('change', f); return () => m.removeEventListener('change', f)
  }, [])
  return r
}

// Modal behaviour: move focus in, keep Tab inside, Escape closes, hand focus back to what opened it
function useDialog(ref, active, onClose) {
  useEffect(() => {
    if (!active || !ref.current) return
    const node = ref.current
    const prev = document.activeElement
    const items = () => [...node.querySelectorAll('button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])')]
    ;(items()[0] || node).focus({ preventScroll: true })
    const onKey = e => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose && onClose(); return }
      if (e.key !== 'Tab') return
      const f = items()
      if (!f.length) { e.preventDefault(); return }
      const a = f[0], z = f[f.length - 1], cur = document.activeElement, inside = node.contains(cur)
      if (e.shiftKey && (cur === a || !inside)) { e.preventDefault(); z.focus() }
      else if (!e.shiftKey && (cur === z || !inside)) { e.preventDefault(); a.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); if (prev && prev.focus && document.contains(prev)) prev.focus({ preventScroll: true }) }
  }, [active])
}

// Shows the place photo (own file → pasted URL → Wikipedia); falls back to `fallback` (the emoji tile)
function Photo({ slug, n = 0, fallback = null, shade = false, alt }) {
  const { retry } = useOnline()
  const [srcs, setSrcs] = useState([])
  const [i, setI] = useState(0)
  const [done, setDone] = useState(false)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    let live = true
    const key = n ? `${slug}-${n}` : slug
    setI(0); setLoaded(false); setDone(false)
    setSrcs([localPhoto(slug, n), ...(REMOTE[key] ? [REMOTE[key]] : [])])
    const title = (WIKI[slug] || [])[n]
    if (title) wikiImage(title).then(u => { if (!live) return; if (u) setSrcs(s => [...s, u.big, u.small]); setDone(true) })
    else setDone(true)
    return () => { live = false }
  }, [slug, n, retry])
  const exhausted = i >= srcs.length
  if (exhausted && done) return fallback
  return (
    <>
      {!loaded && <div className="photo-skel" aria-hidden="true" />}
      {!exhausted && <img key={srcs[i]} className={cx('photo', loaded && 'loaded')} src={srcs[i]} alt={alt ?? altFor(slug, n)} referrerPolicy="no-referrer" onLoad={() => setLoaded(true)} onError={() => setI(x => x + 1)} />}
      {shade && <div className="photo-shade" />}
    </>
  )
}

const TABS = [
  ['home', 'Home', HomeIcon],
  ['explore', 'Explore', Compass],
  ['bookings', 'Bookings', Ticket],
  ['passport', 'Passport', BookOpen],
  ['profile', 'Profile', User],
]
const TabBar = ({ active, go }) => (
  <nav className="tabbar" aria-label="Main">
    {TABS.map(([id, label, I]) => (
      <button key={id} type="button" className={cx('tab-item', active === id && 'active')} aria-current={active === id ? 'page' : undefined} onClick={() => active !== id && go(id)}>
        <I size={22} strokeWidth={active === id ? 2.2 : 1.8} aria-hidden="true" />
        <span>{label}</span>
      </button>
    ))}
  </nav>
)

// `tab` = which bottom tab is active; omit it on screens that must not show the tab bar
const OfflineBar = () => {
  const { online } = useOnline()
  return (
    <div className={cx('offline-bar', !online && 'show')} role="status" aria-hidden={online}>
      {!online && <><WifiOff size={14} aria-hidden="true" /> You're offline. Photos and map tiles may not load until you're back online.</>}
    </div>
  )
}

const Phone = ({ caption, children, overlay, tab, go }) => (
  <div className="phone-col page-entering">
    <div className={cx('phone', tab && 'has-tabs')}>
      <div className="notch" aria-hidden="true" />
      <OfflineBar />
      {children}
      {tab && <TabBar active={tab} go={go} />}
      {overlay}
    </div>
    <div className="caption">{caption}</div>
  </div>
)

const Reviews = ({ list }) =>
  list.map(r => (
    <div className="rcard" key={r.id || r.name}>
      <div className="rheader">
        <div className="ravatar" style={{ background: r.color }}>{r.name[0]}</div>
        <div><div className="rname">{r.name}</div><div className="rtour">{r.tour}</div></div>
      </div>
      <div className="rstars" role="img" aria-label={`${(r.stars.match(/★/g) || []).length} out of 5 stars`}>{r.stars}</div>
      <div className="rtext">{r.text}</div>
    </div>
  ))

// Label + input pair wired with htmlFor/id. `children` (optional) is a render function that receives the id.
function Field({ label, type = 'text', placeholder, autoComplete, children, ...rest }) {
  const id = useId()
  return (
    <div className="field-wrap">
      <label className="field-label" htmlFor={id}>{label}</label>
      {children ? children(id) : <input id={id} className="field" type={type} placeholder={placeholder} autoComplete={autoComplete} {...rest} />}
    </div>
  )
}

function PwField({ id, placeholder, autoComplete, ...rest }) {
  const [show, setShow] = useState(false)
  return (
    <div className="pw-wrap">
      <input id={id} className="field" type={show ? 'text' : 'password'} placeholder={placeholder} autoComplete={autoComplete} {...rest} />
      <button className="pw-toggle" type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(s => !s)}>{show ? <Ic i={EyeOff} /> : <Ic i={Eye} />}</button>
    </div>
  )
}

/* ───────── SPLASH ───────── */
function Splash({ go }) {
  const [w, setW] = useState(0)
  const [k, setK] = useState(0)
  useEffect(() => {
    setW(0)
    const r = requestAnimationFrame(() => requestAnimationFrame(() => setW(100)))
    const t = setTimeout(() => go('about'), 2400)
    return () => { cancelAnimationFrame(r); clearTimeout(t) }
  }, [k])
  return (
    <Phone caption="Entry — loading">
      <div className="screen">
        <div className="ob-splash">
          <div className="ob-logo-wrap">
            <div className="ob-dot-float d1" /><div className="ob-dot-float d2" />
            <div className="ob-headphone"><div className="ob-band" /><div className="ob-cup l" /><div className="ob-cup r" /></div>
          </div>
          <div className="ob-kicker">Audio Guide</div>
          <div className="ob-brandname">Neighbourhoods<br />of Bangalore</div>
          <div className="ob-est">EST. 2023</div>
          <div className="ob-loadbar-wrap">
            <div className="ob-loadbar-track">
              <div className="ob-loadbar-fill" style={{ width: w + '%', transition: w ? 'width 2.2s cubic-bezier(.3,.1,.2,1)' : 'none' }} />
            </div>
          </div>
          <button className="ob-replay-btn" onClick={() => setK(k + 1)}>↺ Replay intro</button>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── ABOUT ───────── */
function About({ go }) {
  const [i, setI] = useState(0)
  const [toast, setToast] = useState(false)
  const finish = () => { setToast(true); setTimeout(() => { setToast(false); go('signup') }, 1300) }
  const rise = i === 1
  return (
    <Phone caption="About (1/2 → 2/2)">
      <div className="screen">
        <div className="ob-about-wrap">
          <div className="ob-track" style={{ transform: `translateX(-${i * 50}%)` }}>
            <div className="ob-panel">
              <div className="ob-abouttop">
                <div className="ob-about-label">About</div>
                <div className="ob-skip-link" {...press(() => setI(1), 'Skip to the last step')}>Skip →</div>
              </div>
              <div className="ob-about-body">
                Neighbourhoods of Bangalore is an audio guide app designed to help you explore the city's diverse neighbourhoods and historic landmarks — on foot and at your own pace. With every step, you'll uncover captivating tales and age-old stories that bring the past to life.
              </div>
              <div className="ob-dots"><div className="ob-d active" /><div className="ob-d" /></div>
              <div className="ob-next-fab" {...press(() => setI(1), 'Next')}><span aria-hidden="true">→</span></div>
            </div>
            <div className="ob-panel">
              <div className="ob-abouttop"><div className="ob-about-label">About</div></div>
              <div className="ob-about-statement" style={rise ? { opacity: 0, animation: 'ob-rise .6s ease forwards' } : undefined}>
                All you need is your curiosity, a pair of headphones, and a sense of wonder. It's more than just a walk — it's a journey through time.
              </div>
              <div className="ob-dots"><div className="ob-d" /><div className="ob-d active" /></div>
              <div className="ob-cta-wrap">
                <button className="ob-cta-btn" style={rise ? { opacity: 0, animation: 'ob-rise .6s ease forwards .3s' } : undefined} onClick={finish}>Yes, I've got 'em all!</button>
              </div>
              <div className={cx('ob-toast', toast && 'show')} role="status">Let's get you signed in →</div>
            </div>
          </div>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── SIGN UP / LOGIN ───────── */
const FormError = ({ msg }) => msg ? <div className="pay-error" role="alert" style={{ marginBottom: 10 }}><span>{msg}</span></div> : null

function Signup({ go, onAuthed }) {
  const [f, setF] = useState({ name: '', email: '', pw: '', pw2: '', tos: false, mkt: false })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = k => e => setF(x => ({ ...x, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const submit = async () => {
    if (!LIVE) return go('location-prime')
    if (!f.email.trim() || !f.pw) return setErr('Enter your email and a password.')
    if (f.pw.length < 8) return setErr('Your password needs at least 8 characters.')
    if (f.pw !== f.pw2) return setErr('The two passwords do not match.')
    if (!f.tos) return setErr('Please accept the Terms of Service and Privacy Policy to continue.')
    setErr(''); setBusy(true)
    try {
      await api.auth.signup({ email: f.email.trim(), password: f.pw, fullName: f.name.trim() || undefined, acceptedTerms: f.tos, marketingOptIn: f.mkt })
      await onAuthed()
      go('location-prime')
    } catch (e) { setErr(friendlyError(e)) } finally { setBusy(false) }
  }
  return (
    <Phone caption="Sign up">
      <div className="screen">
        <div className="signup-hero">
          <div className="back" {...press(() => go('login'))}>← Already have an account?</div>
          <h1>Create your<br />account.</h1>
        </div>
        <div style={{ padding: '18px 18px 0', flex: 1, overflowY: 'auto' }}>
          <Field label="Full name" placeholder="Priya Sharma" autoComplete="name" value={f.name} onChange={set('name')} />
          <Field label="Email address" type="email" placeholder="priya@email.com" autoComplete="email" value={f.email} onChange={set('email')} />
          <Field label="Password">{id => <PwField id={id} placeholder="Min. 8 characters" autoComplete="new-password" value={f.pw} onChange={set('pw')} />}</Field>
          <Field label="Confirm password">{id => <PwField id={id} placeholder="Repeat password" autoComplete="new-password" value={f.pw2} onChange={set('pw2')} />}</Field>
          <div className="consent-row"><input type="checkbox" id="consentTos" checked={f.tos} onChange={set('tos')} /><label htmlFor="consentTos">I agree to the <a>Terms of Service</a> and <a>Privacy Policy</a></label></div>
          <div className="consent-row" style={{ borderTop: 'none', paddingTop: 4 }}><input type="checkbox" id="consentMarketing" checked={f.mkt} onChange={set('mkt')} /><label htmlFor="consentMarketing">Send me updates about new tours and neighbourhoods (optional)</label></div>
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 24 }}>
            <FormError msg={err} />
            <button className="btn-primary" onClick={submit} disabled={busy} aria-busy={busy}>{busy ? 'Creating account…' : 'Create account → Enable location'}</button>
            <div className="or-row"><div className="or-line" /><span className="or-label">or</span><div className="or-line" /></div>
            <button className="social-btn"><span style={{ fontWeight: 800, fontFamily: 'sans-serif' }}>G</span> Continue with Google</button>
          </div>
        </div>
      </div>
    </Phone>
  )
}

function Login({ go, onAuthed, notice }) {
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    if (!LIVE) return go('location-prime')
    if (!email.trim() || !pw) return setErr('Enter your email and password.')
    setErr(''); setBusy(true)
    try {
      await api.auth.login({ email: email.trim(), password: pw })
      await onAuthed()
      go('home')
    } catch (e) { setErr(friendlyError(e)) } finally { setBusy(false) }
  }
  return (
    <Phone caption="Login">
      <div className="screen">
        <div className="login-hero">
          <span>Neighbourhoods of Bengaluru</span>
          <h1>Welcome back.<br />Sign in to walk.</h1>
        </div>
        <div style={{ padding: '20px 18px 0', flex: 1, overflowY: 'auto' }}>
          {notice && <div className="pay-error" role="status" style={{ marginBottom: 10 }}><span>{notice}</span></div>}
          <Field label="Email address" type="email" placeholder="you@email.com" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} />
          <Field label="Password">{id => <PwField id={id} placeholder="••••••••" autoComplete="current-password" value={pw} onChange={e => setPw(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()} />}</Field>
          <div style={{ textAlign: 'right', marginBottom: 16 }}><span {...press(() => {})} style={{ fontSize: 12, color: 'var(--rust)', ...mono, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', minHeight: 44 }}>Forgot password?</span></div>
          <FormError msg={err} />
          <button className="btn-primary" onClick={submit} disabled={busy} aria-busy={busy} style={{ marginBottom: 10 }}>{busy ? 'Signing in…' : 'Sign in → Explore'}</button>
          <div className="or-row"><div className="or-line" /><span className="or-label">or</span><div className="or-line" /></div>
          <button className="social-btn"><span style={{ fontWeight: 800, fontFamily: 'sans-serif' }}>G</span> Continue with Google</button>
          <button className="social-btn"> Sign in with OTP</button>
          <div className="signup-link">New here? <a {...press(() => go('signup'))}>Create an account →</a></div>
        </div>
        <button className="explore-btn-big" onClick={() => go('home')}> {LIVE ? 'Browse walks without signing in' : 'Go to Explore'}</button>
      </div>
    </Phone>
  )
}

/* ───────── LOCATION PRIME ───────── */
const blocks = [[8,8,24,20,.08],[50,8,30,20,.06],[128,8,24,20,.08],[8,44,20,18,.06],[50,44,28,18,.08],[86,44,22,18,.06],[128,44,24,22,.07],[8,80,24,20,.07],[50,80,30,20,.06],[88,80,20,20,.08],[128,80,24,22,.06],[8,115,26,18,.06],[50,115,22,18,.08],[86,115,26,18,.06],[128,115,24,18,.07]]
function LocationPrime({ go }) {
  const [status, setStatus] = useState('idle')
  const ref = useRef('idle')
  const set = s => { ref.current = s; setStatus(s) }
  const request = () => {
    if (!navigator.geolocation) return set('denied')
    navigator.geolocation.getCurrentPosition(() => set('success'), () => set('denied'))
    setTimeout(() => { if (ref.current === 'idle') set('success') }, 1000) // prototype fallback
  }
  useEffect(() => {
    if (status !== 'success') return
    const t = setTimeout(() => go('home'), 2000)
    return () => clearTimeout(t)
  }, [status])
  const line = (k, a, b, c, d) => <line key={k} x1={a} y1={b} x2={c} y2={d} stroke="rgba(0,41,28,0.08)" strokeWidth="1" />
  return (
    <Phone caption="Location permission priming">
      <div className="screen">
        {status !== 'success' && (
          <div className="loc-prime-screen">
            <div className="loc-map-svg-wrap">
              <svg width="160" height="140" viewBox="0 0 160 140" fill="none">
                <rect width="160" height="140" rx="12" fill="rgba(0,41,28,0.04)" />
                {[line(1,0,35,160,35), line(2,0,70,160,70), line(3,0,105,160,105), line(4,40,0,40,140), line(5,80,0,80,140), line(6,120,0,120,140)]}
                <rect x="35" y="0" width="8" height="140" rx="2" fill="rgba(0,41,28,0.07)" />
                <rect x="0" y="32" width="160" height="8" rx="2" fill="rgba(0,41,28,0.07)" />
                <rect x="115" y="0" width="6" height="140" rx="2" fill="rgba(0,41,28,0.05)" />
                <rect x="0" y="68" width="160" height="6" rx="2" fill="rgba(0,41,28,0.05)" />
                {blocks.map(([x, y, w, h, o], i) => <rect key={i} x={x} y={y} width={w} height={h} rx="3" fill={`rgba(0,41,28,${o})`} />)}
              </svg>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }}>
                <div className="loc-pin-pulse" />
                <svg width="24" height="30" viewBox="0 0 24 30" style={{ position: 'absolute', top: -26, left: -12, zIndex: 2 }} fill="none">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 9 12 18 12 18s12-9 12-18C24 5.37 18.63 0 12 0z" fill="#8B4A2C" />
                  <circle cx="12" cy="12" r="4" fill="white" />
                </svg>
              </div>
            </div>
            <div className="loc-heading">We'll need your location</div>
            <div className="loc-body">We use GPS only while you walk — to trigger audio stories as you pass each stop. We never share your location.</div>
            <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 9 }}>
              <button className="btn-primary" onClick={request}><Ic i={MapPin} size={16} /> Enable location</button>
              <button className="btn-ghost" onClick={() => go('home')}>Not now</button>
            </div>
            <div className={cx('loc-denied-text', status === 'denied' && 'show')}>
              Without location, audio stories won't auto-trigger as you walk. You can still play them manually.
              <br /><br />
              <span {...press(() => go('home'))} style={{ cursor: 'pointer', fontWeight: 700, color: 'var(--text)', display: 'inline-flex', alignItems: 'center', minHeight: 44 }}>Continue anyway →</span>
            </div>
          </div>
        )}
        <div className={cx('loc-success-wrap', status === 'success' && 'show')} style={{ padding: '48px 24px', alignItems: 'center', justifyContent: 'center', flex: 1, textAlign: 'center' }}>
          <div className="loc-success-check">✓</div>
          <div className="loc-success-label">Location enabled!</div>
          <div style={{ fontSize: 13, color: 'var(--text-soft)', marginTop: 6 }}>Taking you to explore…</div>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── BOOKING SHEET (detail → payment → paid → start) ───────── */
const methods = [
  ['upi', <Ic i={Smartphone} size={22} />, 'UPI', 'Google Pay, PhonePe, Paytm…'],
  ['card', <Ic i={CreditCard} size={22} />, 'Credit / Debit card', 'Visa, Mastercard, RuPay'],
  ['saved', <Ic i={Star} size={22} />, 'Saved — HDFC Visa', '…4821'],
]
// Paragraph clamped to 3 lines with a Read more / Show less toggle (button only appears if the text is actually cut)
function ReadMore({ children }) {
  const [open, setOpen] = useState(false)
  const [cut, setCut] = useState(false)
  const ref = useRef(null)
  useLayoutEffect(() => { const el = ref.current; if (el && !open) setCut(el.scrollHeight > el.clientHeight + 1) }, [children, open])
  return (
    <>
      <div ref={ref} className={cx('sheet-text', !open && 'clamp')}>{children}</div>
      {(cut || open) && <button type="button" className="readmore-btn" aria-expanded={open} onClick={() => setOpen(o => !o)}>{open ? 'Show less' : 'Read more'}</button>}
    </>
  )
}

function Sheet({ walk, onClose, onStart }) {
  const [show, setShow] = useState(false)
  const [panel, setPanel] = useState('detail')
  const place = neighbourhoods.find(n => n.slug === walk.neighbourhood)
  const [method, setMethod] = useState('upi')
  const [paying, setPaying] = useState(false)
  const sheetRef = useRef(null)
  const [payErr, setPayErr] = useState('')
  useEffect(() => { const r = requestAnimationFrame(() => setShow(true)); return () => cancelAnimationFrame(r) }, [])
  const close = cb => { setShow(false); setTimeout(() => (cb || onClose)(), 400) }
  const to = p => { setPanel(p); if (sheetRef.current) sheetRef.current.scrollTop = 0 }
  const pay = async () => {
    if (!navigator.onLine) { setPayErr("You're offline, so we couldn't take the payment. Check your connection and try again. You haven't been charged."); return }
    if (LIVE) {
      if (!api.isSignedIn()) { setPayErr('Please sign in to get this walk.'); return }
      setPayErr(''); setPaying(true)
      try {
        const b = await api.purchases.buy(walk.id)
        if (b.status !== 'completed') throw Object.assign(new Error('Online payments are not switched on yet.'), { status: 400 })
        await api.purchases.bindDevice(b.purchase_id).catch(e => console.warn('bind-device', e))
        setPaying(false); to('paid')
      } catch (e) { setPaying(false); setPayErr(friendlyError(e, "We couldn't complete the purchase. You have not been charged.")) }
      return
    }
    setPayErr(''); setPaying(true)
    setTimeout(() => { if (!navigator.onLine) { setPaying(false); setPayErr('The connection dropped before the payment finished. You have not been charged. Please try again.'); return } setPaying(false); to('paid') }, 1800)
  }
  const cls = cx('sheet-panel active', panel !== 'detail' && 'sliding-in')
  useDialog(sheetRef, true, () => close())
  useEffect(() => { // a new panel replaces the focused control: put focus on its first control
    const n = sheetRef.current && sheetRef.current.querySelector('button:not([disabled]), [tabindex]:not([tabindex="-1"])')
    if (n && panel !== 'detail') n.focus({ preventScroll: true })
  }, [panel])
  return (
    <div className={cx('sheet-overlay', show && 'show')} onClick={e => e.target === e.currentTarget && close()}>
      <div className="sheet" ref={sheetRef} role="dialog" aria-modal="true" aria-label={walk.t} tabIndex={-1}>
        {panel === 'detail' && (
          <div className={cls}>
            <div className="sheet-scroll">
              <div className="sheet-hero" style={{ background: walk.bg }}>
                <Photo slug={walk.neighbourhood} shade />
                <button className="sheetclose" aria-label="Close" onClick={() => close()}><Ic i={X} size={18} /></button>
                <div className="sheet-title">{walk.t}</div>
                <div className="sheet-sub">{walk.tag}</div>
              </div>
              <div className="sheet-facts">
                <div className="sfact wide"><Ic i={MapPin} size={18} /><div><div className="sk">Meeting point</div><div className="sv">{walk.start}</div></div></div>
                <div className="sfact"><Ic i={Languages} size={18} /><div><div className="sk">Language</div><div className="sv">{walk.language}</div></div></div>
                <div className="sfact"><Ic i={Activity} size={18} /><div><div className="sk">Difficulty</div><div className="sv">{walk.difficulty}</div></div></div>
              </div>
              <div className="sheet-stats">
                <div className="sstat"><div className="sv">{walk.distance}</div><div className="sk">Distance</div></div>
                <div className="sstat"><div className="sv">{walk.duration}</div><div className="sk">Duration</div></div>
                <div className="sstat"><div className="sv">{walk.price}</div><div className="sk">Price</div></div>
              </div>
              <div className="section-label">About {walk.tag}</div>
              <ReadMore>{place && place.description}</ReadMore>
              <div className="section-label">About this walk</div>
              <ReadMore>{walk.desc}</ReadMore>
              <div className="section-label">Stops on this walk</div>
              <ul className="included-list" style={{ padding: '0 16px 14px' }}>
                {(walk.stops || []).map((s, i) => (
                  <li className="included-item" key={i}><span style={{ fontSize: 16 }}>{s.e}</span><span><b style={{ fontWeight: 'normal', color: 'var(--text)' }}>{s.n}</b><br /><span style={{ fontSize: 11, color: 'var(--text-soft)' }}>{s.d}</span></span></li>
                ))}
              </ul>
            </div>
            <div className="bookbar"><div className="bp">{walk.price}<span>One-time purchase</span></div><button className="bookbtn" onClick={() => to('payment')}>Get this walk</button></div>
          </div>
        )}
        {panel === 'payment' && (
          <div className={cls}>
            <div className="sheet-scroll"><div className="payment-panel-inner">
              <div className="payment-panel-title" id="pay-title">How would you like to pay?</div>
              <div role="radiogroup" aria-labelledby="pay-title">
              {methods.map(([id, icon, name, sub]) => (
                <div key={id} className={cx('payment-method-row', method === id && 'selected')} role="radio" aria-checked={method === id} tabIndex={0} onClick={() => setMethod(id)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setMethod(id) } }}>
                  <div className="payment-radio"><div className="payment-radio-dot" /></div>
                  <div className="payment-method-icon">{icon}</div>
                  <div className="payment-method-label"><div className="payment-method-name">{name}</div><div className="payment-method-sub">{sub}</div></div>
                </div>
              ))}
              </div>
              {payErr && <div className="pay-error" role="alert"><WifiOff size={16} aria-hidden="true" /><span>{payErr}</span></div>}
              <div style={{ fontSize: 11, color: 'var(--text-soft)', ...mono, marginTop: 14, padding: 10, background: 'rgba(46,37,32,.04)', borderRadius: 7 }}><Ic i={Lock} size={13} /> Secured by Razorpay. Your payment details are encrypted.</div>
            </div></div>
            <div className="pay-bar">
              <button className={cx('pay-btn', paying && 'loading')} onClick={pay} aria-busy={paying} aria-label={paying ? 'Processing payment' : undefined}>
                <span className="pay-btn-text">Pay {walk.price}</span>
                <div className="pay-spinner" />
              </button>
            </div>
          </div>
        )}
        {panel === 'paid' && (
          <div className={cls}>
            <div className="panel-paid">
              <div className="check">✓</div>
              <div className="pt">You're in!</div>
              <div className="ps">{walk.t} · start whenever you're ready</div>
              <button className="btn-primary" style={{ marginTop: 24 }} onClick={() => to('start')}>Take me to the start</button>
            </div>
          </div>
        )}
        {panel === 'start' && (
          <div className={cls}>
            <div className="startmap"><div className="startpin" /></div>
            <div className="startinfo">
              <div className="sk">Starting point</div>
              <div className="st">{walk.start}</div>
              <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => close(onStart)}>Begin walk</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ───────── HOME ───────── */
const cardStyle = (off, n) =>
  off < 0 ? { opacity: 0, transform: 'translateX(-110%) scale(.85)', zIndex: 0, pointerEvents: 'none' }
  : off === 0 ? { opacity: 1, transform: 'translateX(0) scale(1)', zIndex: n, boxShadow: '0 12px 32px rgba(46,37,32,.16)', pointerEvents: 'auto' }
  : off === 1 ? { opacity: .72, transform: 'translateY(12px) scale(.94)', zIndex: n - 1, boxShadow: '0 6px 16px rgba(46,37,32,.10)', pointerEvents: 'none' }
  : off === 2 ? { opacity: .45, transform: 'translateY(22px) scale(.88)', zIndex: n - 2, pointerEvents: 'none' }
  : { opacity: 0, transform: 'translateY(28px) scale(.84)', zIndex: 0, pointerEvents: 'none' }

function Home({ go, openNb, startWalk }) {
  const [cur, setCur] = useState(0)
  const [booking, setBooking] = useState(null)
  const startX = useRef(null)
  const moved = useRef(false)
  const wrapRef = useRef(null)
  const unread = notificationsData.filter(n => n.unread).length
  useEffect(() => {
    const end = x => {
      if (startX.current == null) return
      const dx = x - startX.current
      startX.current = null
      if (Math.abs(dx) > 40) { moved.current = true; setCur(c => (dx < 0 ? Math.min(c + 1, walks.length - 1) : Math.max(c - 1, 0))) }
    }
    const mu = e => end(e.clientX)
    const te = e => end(e.changedTouches[0].clientX)
    document.addEventListener('mouseup', mu)
    document.addEventListener('touchend', te)
    return () => { document.removeEventListener('mouseup', mu); document.removeEventListener('touchend', te) }
  }, [])
  // keep keyboard focus on the front card when arrow keys change it
  useEffect(() => { const w = wrapRef.current; if (w && w.contains(document.activeElement)) { const c = w.querySelector(`[data-i="${cur}"]`); c && c.focus({ preventScroll: true }) } }, [cur])
  const stackKeys = e => {
    if (e.key === 'ArrowRight') { e.preventDefault(); setCur(c => Math.min(c + 1, walks.length - 1)) }
    if (e.key === 'ArrowLeft') { e.preventDefault(); setCur(c => Math.max(c - 1, 0)) }
  }
  return (
    <Phone tab="home" go={go} caption="Home — swipe cards · tap to get a walk" overlay={booking && <Sheet walk={booking} onClose={() => setBooking(null)} onStart={() => startWalk(booking)} />}>
      <div className="screen">
        <div className="hdr">
          <div className="hdr-top">
            <div className="hdr-title"><span>Bangalore, on foot</span>Ready to walk?</div>
            <button className="frostbtn bell" aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'} title="Notifications" onClick={() => go('notifications')}>
              <Ic i={Bell} />{!!unread && <i className="bell-dot" aria-hidden="true" />}
            </button>
          </div>
          <button className="hdr-search" onClick={() => go('explore')}><Ic i={Search} size={16} /> Search walks &amp; neighbourhoods</button>
        </div>

        <div className="stack-section">
          <div className="stack-label">Featured walks</div>
          <div className="stack-wrap" ref={wrapRef} role="group" aria-roledescription="carousel" aria-label="Featured walks" onKeyDown={stackKeys}>
            {walks.map((w, i) => (
              <div key={w.id} className="stack-card" data-i={i} style={cardStyle(i - cur, walks.length)}
                role="button" tabIndex={i === cur ? 0 : -1} aria-hidden={i === cur ? undefined : true} aria-label={`Get ${w.t}, ${w.tag}, ${w.price}, ${w.distance}, ${w.duration}`}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setBooking(w) } }}
                onMouseDown={e => { moved.current = false; startX.current = e.clientX }}
                onTouchStart={e => { moved.current = false; startX.current = e.touches[0].clientX }}
                onClick={() => { if (moved.current) { moved.current = false; return } setBooking(w) }}>
                <div className="card-img" style={{ background: w.bg }}>
                  <Photo slug={w.neighbourhood} fallback={<div className="card-icon">{w.icon}</div>} />
                  <div className="card-tag">{w.tag}</div>
                  <div className="card-price">{w.price}</div>
                  <div className="card-name-block"><div className="cname">{w.t}</div></div>
                </div>
                <div className="card-bottom">
                  <div className="card-bar-info">
                    <span className="card-rating"><Ic i={Star} size={14} /> {w.rating}</span>
                    <span className="card-meta">{w.meta}</span>
                  </div>
                  <span className="card-cta">Get <Ic i={ChevronRight} size={16} /></span>
                </div>
              </div>
            ))}
          </div>
          <div className="stack-dots" aria-hidden="true">{walks.map((w, i) => <div key={w.id} className={cx('stack-dot', i === cur && 'active')} />)}</div>
          <span className="sr-only" aria-live="polite">Walk {cur + 1} of {walks.length}: {walks[cur].t}</span>
          <div className="swipe-hint" style={{ marginTop: 6 }}>← swipe to browse →</div>
        </div>

        <div className="nbhood-strip-section">
          <div className="stack-label" style={{ marginBottom: 10 }}>By neighbourhood</div>
          <div className="nbhood-strip">
            {neighbourhoods.map(nb => (
              <div className="nbhood-chip" key={nb?.slug} {...press(() => openNb(nb), `${nb.name} neighbourhood`)}>
                <div className="nbhood-chip-img" style={{ background: nb.bg }}>
                  <Photo slug={nb.slug} fallback={nb.emoji} />
                </div>
                <div className="nbhood-chip-name">{nb.name}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="reviews-section">
          <h2>What walkers say</h2>
          <div className="review-scroll"><Reviews list={reviews.slice(0, 4)} /></div>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── EXPLORE ───────── */
const filterGroups = {
  neighbourhood: ['Malleshwaram', 'Basavanagudi', 'Cubbon Park', 'MG Road'],
  duration: ['< 60 min', '60–90 min', '> 90 min'],
  price: ['Free', '< ₹200', '₹200+'],
  theme: ['Heritage', 'Culture', 'Nature', 'Colonial'],
}
const emptyFilters = { neighbourhood: [], duration: [], price: [], theme: [] }
function matches(w, q, f) {
  if (q && ![w.t, w.tag, w.theme].some(s => s.toLowerCase().includes(q))) return false
  if (f.neighbourhood.length && !f.neighbourhood.includes(w.tag)) return false
  if (f.theme.length && !f.theme.includes(w.theme)) return false
  if (f.price.length) {
    const p = w.price === 'Free' ? 0 : parseInt(w.price.replace('₹', ''))
    const ok = f.price.some(x => (x === 'Free' && w.price === 'Free') || (x === '< ₹200' && w.price !== 'Free' && p < 200) || (x === '₹200+' && w.price !== 'Free' && p >= 200))
    if (!ok) return false
  }
  if (f.duration.length) {
    const m = parseInt(w.duration)
    const ok = f.duration.some(d => (d === '< 60 min' && m < 60) || (d === '60–90 min' && m >= 60 && m <= 90) || (d === '> 90 min' && m > 90))
    if (!ok) return false
  }
  return true
}
function Explore({ go, openWalk }) {
  const [loading, setLoading] = useState(true)
  const [val, setVal] = useState('')
  const [q, setQ] = useState('')
  const [f, setF] = useState(emptyFilters)
  useEffect(() => { const t = setTimeout(() => setLoading(false), 600); return () => clearTimeout(t) }, [])
  useEffect(() => { const t = setTimeout(() => setQ(val.trim().toLowerCase()), 150); return () => clearTimeout(t) }, [val])
  const toggle = (g, o) => setF(p => ({ ...p, [g]: p[g].includes(o) ? p[g].filter(x => x !== o) : [...p[g], o] }))
  const clear = () => { setF(emptyFilters); setVal(''); setQ('') }
  const active = Object.values(f).some(a => a.length) || !!q
  const visible = walks.filter(w => matches(w, q, f))   // non-matching walks are removed, so results reflow
  return (
    <Phone tab="explore" go={go} caption="Explore / browse all walks">
      <div className="screen explore-screen">
        <div className="explore-band"><h1>All walks</h1></div>
        <div className="explore-search-wrap">
          <input className="explore-search-input" type="search" aria-label="Search walks and neighbourhoods" placeholder="Search walks, neighbourhoods…" value={val} onChange={e => setVal(e.target.value)} />
          <div className="explore-chips-wrap" role="group" aria-label="Filters">
            {Object.entries(filterGroups).flatMap(([g, opts], gi) => [
              gi > 0 && <span key={g + '-sep'} className="chip-sep" aria-hidden="true" />,
              ...opts.map(o => (
                <button key={g + o} type="button" aria-pressed={f[g].includes(o)} className={cx('explore-chip', f[g].includes(o) && 'active')} onClick={() => toggle(g, o)}>{o}</button>
              )),
            ])}
          </div>
          <div className="explore-count-row">
            <span className="explore-count" role="status" aria-live="polite">{loading ? 'Loading walks…' : `${visible.length} ${visible.length === 1 ? 'walk' : 'walks'}`}</span>
            {active && <button type="button" className="explore-clear" onClick={clear}>Clear all</button>}
          </div>
        </div>
        <div className="explore-grid">
          {loading ? [0, 1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 145, borderRadius: 10 }} />) : (
            <>
              {visible.map((w, i) => (
                <div key={w.id} className="explore-card stagger-item" role="button" tabIndex={0} style={{ animationDelay: i * 40 + 'ms' }}
                  onClick={() => openWalk(w)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openWalk(w))}>
                  <div className="explore-card-img" style={{ background: w.bg }}>
                    <Photo slug={w.neighbourhood} fallback={<div className="explore-card-emoji">{w.icon}</div>} />
                    <div className="explore-card-tag">{w.tag}</div>
                  </div>
                  <div className="explore-card-body">
                    <div className="explore-card-name">{w.t}</div>
                    <div className="explore-card-meta">{w.meta}</div>
                    <div className="explore-card-price">{w.price}</div>
                  </div>
                </div>
              ))}
              {!visible.length && (
                <div className="explore-empty empty-state" style={{ gridColumn: '1/-1' }}>
                  <div className="empty-icon"><Ic i={Search} size={34} /></div>
                  <div className="empty-title">No walks match</div>
                  <div className="empty-body">Try a different search or adjust your filters.</div>
                  <button className="btn-ghost empty-cta" onClick={clear} style={{ width: 'auto', padding: '9px 18px', fontSize: 13 }}>Clear filters</button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Phone>
  )
}

/* ───────── WALK DETAIL ───────── */
function WalkDetail({ walk: w, go, onStart }) {
  const reduced = useReducedMotion()
  const [scroll, setScroll] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [prog, setProg] = useState(0)
  const [booking, setBooking] = useState(false)
  const audioRef = useRef(null)
  const [dur, setDur] = useState(15)
  const realSample = LIVE && !!w.sampleUrl
  useEffect(() => () => { if (audioRef.current) audioRef.current.pause() }, [])
  useEffect(() => {
    if (!playing || realSample) return
    const t = setInterval(() => setProg(p => (p + 100 / 15 >= 100 ? 0 : p + 100 / 15)), 1000)
    return () => clearInterval(t)
  }, [playing])
  const toggle = () => {
    if (realSample) {
      if (!audioRef.current) {
        const a = new Audio(api.mediaUrl(w.sampleUrl))
        a.onended = () => { setPlaying(false); setProg(0) }
        a.ontimeupdate = () => setProg(a.duration ? (a.currentTime / a.duration) * 100 : 0)
        a.onloadedmetadata = () => setDur(Math.round(a.duration) || 15)
        a.onerror = () => setPlaying(false)
        audioRef.current = a
      }
      if (playing) { audioRef.current.pause(); setPlaying(false) }
      else audioRef.current.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
      return
    }
    if (playing) { setPlaying(false); setProg(0) } else setPlaying(true)
  }
  const elapsed = Math.round((prog / 100) * dur)
  const eq = [6, 11, 8, 14, 5]
  const walkReviews = reviews.filter(r => r.walkId === w.id)
  return (
    <Phone caption="Walk detail — parallax hero · audio sample" overlay={booking && <Sheet walk={w} onClose={() => setBooking(false)} onStart={onStart} />}>
      <div className="screen" onScroll={e => setScroll(e.currentTarget.scrollTop)}>
        <div className="detail-hero-wrap" style={{ background: w.bg }}>
          <div className="detail-hero-img" style={{ transform: reduced ? 'none' : `translateY(${scroll * 0.45}px)` }}>
            <Photo slug={w.neighbourhood} fallback={w.icon} />
          </div>
          <div className="detail-hero-overlay" />
          <button className="detail-back" aria-label="Back" onClick={() => go('explore')}><Ic i={ArrowLeft} size={20} /></button>
          <div className="detail-hero-content">
            <div className="detail-title">{w.t}</div>
            <div className="detail-subtitle">{w.tag} · {w.distance} · {w.duration}</div>
            <div className="detail-rating"><span className="stars" aria-hidden="true">{w.stars}</span><span>{w.reviewCount ? `${w.rating} (${w.reviewCount} reviews)` : 'No ratings yet'}</span></div>
          </div>
        </div>

        <div className="detail-section"><div className="detail-sect-label">Your itinerary</div></div>
        <div className="stop-carousel">
          {(w.stops || []).map((s, i) => (
            <div className="stop-card" key={i}>
              <div className="stop-card-emoji">{s.e}</div>
              <div className="stop-card-num">STOP {String(i + 1).padStart(2, '0')}</div>
              <div className="stop-card-name">{s.n}</div>
            </div>
          ))}
        </div>

        <div className="detail-section">
          <div className="detail-sect-label">Listen to a sample</div>
          <div className="audio-sample-card">
            <div className="audio-sample-title">{(w.sample || {}).title || 'Audio sample'}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button className="play-btn" aria-label={playing ? 'Pause sample' : 'Play sample'} onClick={toggle}>{playing ? <Ic i={Pause} size={20} /> : <Ic i={Play} size={20} />}</button>
              <div className={cx('equalizer', !playing && 'paused')}>{eq.map((h, i) => <div key={i} className="eq-bar" style={{ height: h }} />)}</div>
              <div style={{ flex: 1 }}>
                <div className="audio-prog"><div className="audio-prog-fill" style={{ width: prog + '%', animation: 'none' }} /></div>
                <div className="audio-times"><span>0:{String(elapsed).padStart(2, '0')}</span><span>0:{String(dur).padStart(2, '0')}</span></div>
              </div>
            </div>
          </div>
        </div>

        <div className="detail-section">
          <div className="detail-sect-label">Photos</div>
          <div className="gallery-strip">
            {[w.bg, '#B8A898', '#A28D6E', '#2E2520'].map((bg, i) => (
              <div className="gallery-thumb" key={i} style={{ background: bg }}>
                <Photo slug={w.neighbourhood} n={i} fallback={w.icon} />
              </div>
            ))}
          </div>
        </div>

        <div className="detail-section">
          <div className="detail-sect-label">What's included</div>
          <ul className="included-list">{w.included.map(t => <li className="included-item" key={t}><div className="included-check">✓</div>{t}</li>)}</ul>
        </div>

        <div className="detail-section">
          <div className="detail-sect-label">Fitness &amp; accessibility</div>
          <div className="tags-row">{w.tags.map(t => <span className="pill" key={t}>{t}</span>)}</div>
        </div>

        <div className="detail-section" style={{ marginBottom: 6 }}><div className="detail-sect-label">Reviews</div></div>
        {walkReviews.length
          ? <div className="review-scroll" style={{ paddingLeft: 16, paddingRight: 36, paddingBottom: 10 }}><Reviews list={walkReviews} /></div>
          : <div className="inline-empty">No reviews yet. Be the first to review this walk after you've walked it.</div>}

        <div className="detail-spacer" />
        <div className={cx('detail-sticky-bar', scroll > 150 && 'visible')}>
          <div><div className="detail-price-big">{w.price}</div><div className="detail-price-sub">One-time purchase</div></div>
          <button className="bookbtn" style={{ flexShrink: 0 }} onClick={() => setBooking(true)}>Get this walk</button>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── BOOKINGS ───────── */
function QR({ id }) {
  const hash = [...id].reduce((a, c) => a + c.charCodeAt(0), 0)
  const cells = []
  for (let r = 0; r < 7; r++) for (let c = 0; c < 7; c++) {
    const corner = (r < 3 && c < 3) || (r < 3 && c > 3) || (r > 3 && c < 3)
    if (corner || (hash * r + c * 7) % 3 === 0) cells.push(<rect key={r * 7 + c} x={c * 9 + 2} y={r * 9 + 2} width="8" height="8" fill="#2E2520" />)
  }
  const finder = (x, y) => <g key={x + '-' + y}><rect x={x} y={y} width="20" height="20" rx="2" fill="none" stroke="#2E2520" strokeWidth="2" /><rect x={x + 3} y={y + 3} width="14" height="14" fill="#2E2520" rx="1" /></g>
  return (
    <svg className="qr-svg" viewBox="0 0 65 65" fill="none">
      <rect width="65" height="65" fill="white" rx="4" />{cells}{finder(2, 2)}{finder(43, 2)}{finder(2, 43)}
    </svg>
  )
}
function Bookings({ go, startWalk }) {
  const [tab, setTab] = useState('upcoming')
  const [data, setData] = useState(bookingsData)
  const [open, setOpen] = useState({})
  const [collapsing, setCollapsing] = useState(null)
  const [cancelId, setCancelId] = useState(null)
  const refs = { upcoming: useRef(null), past: useRef(null) }
  const cancelRef = useRef(null)
  const [ul, setUl] = useState({ left: 0, width: 0 })
  useLayoutEffect(() => { const b = refs[tab].current; if (b) setUl({ left: b.offsetLeft, width: b.offsetWidth }) }, [tab])
  const [cancelErr, setCancelErr] = useState('')
  const confirm = async () => {
    const id = cancelId
    if (LIVE) {
      try { await api.purchases.cancel(id) } catch (e) { setCancelErr(friendlyError(e, "We couldn't cancel this booking.")); return }
    }
    setCancelErr(''); setCancelId(null); setCollapsing(id)
    setTimeout(() => { setData(d => ({ ...d, upcoming: d.upcoming.filter(b => b.id !== id) })); setCollapsing(null) }, 320)
  }
  const [moveErr, setMoveErr] = useState('')
  const moveHere = async b => {
    try { await api.purchases.rebindDevice(b.id); await hydrateUser(); setData({ upcoming: [...bookingsData.upcoming], past: [...bookingsData.past] }); setMoveErr('') }
    catch (e) { setMoveErr(friendlyError(e, "We couldn't move this walk to this device.")) }
  }
  const readyText = b => b.validUntil ? 'Valid until ' + b.validUntil : 'Ready to start any time'
  const list = data[tab]
  useDialog(cancelRef, !!cancelId, () => setCancelId(null))
  const cancelSheet = (
    <div className={cx('cancel-sheet-overlay', cancelId && 'show')} aria-hidden={!cancelId}>
          <div className="cancel-sheet" ref={cancelRef} role="dialog" aria-modal="true" aria-labelledby="cancel-title" aria-describedby="cancel-body" tabIndex={-1}>
            <div className="cancel-title" id="cancel-title">Cancel booking?</div>
            <div className="cancel-body" id="cancel-body">This will cancel your walk. You'll receive a full refund within 5–7 business days, as the walk hasn't started yet.</div>
            {cancelErr && <div className="pay-error" role="alert" style={{ marginBottom: 10 }}><span>{cancelErr}</span></div>}
            <div style={{ display: 'flex', gap: 9 }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => { setCancelId(null); setCancelErr('') }}>Keep it</button>
              <button className="btn-primary" style={{ flex: 1, background: 'var(--error)' }} onClick={confirm}>Yes, cancel</button>
            </div>
          </div>
        </div>
  )
  return (
    <Phone tab="bookings" go={go} caption="My bookings — ready to walk & completed" overlay={cancelSheet}>
      <div className="screen">
        <div className="bookings-hdr"><h1>My Bookings</h1></div>
        <div className="tabs-wrap" role="tablist" aria-label="Bookings">
          <button ref={refs.upcoming} role="tab" aria-selected={tab === 'upcoming'} className={cx('tab-btn', tab === 'upcoming' && 'active')} onClick={() => setTab('upcoming')}>Ready to walk</button>
          <button ref={refs.past} role="tab" aria-selected={tab === 'past'} className={cx('tab-btn', tab === 'past' && 'active')} onClick={() => setTab('past')}>Completed</button>
          <div className="tab-underline" style={ul} />
        </div>
        {moveErr && <div className="pay-error" role="alert" style={{ margin: '0 16px 8px' }}><span>{moveErr}</span></div>}
        <div className="tab-content">
          <div className="tab-pane active" key={tab} role="tabpanel">
            {!list.length ? (
              <div className="empty-state">
                <div className="empty-icon"><Ic i={Ticket} size={34} /></div>
                <div className="empty-title">{tab === 'upcoming' ? 'No walks ready' : 'No completed walks'}</div>
                <div className="empty-body">{tab === 'upcoming' ? 'Get a walk and your ticket will show up here, ready to start any time.' : 'Finish a walk to see it here.'}</div>
                {tab === 'upcoming' && <button className="btn-ghost empty-cta" style={{ width: 'auto', padding: '9px 18px', fontSize: 13 }} onClick={() => go('explore')}>Explore walks</button>}
              </div>
            ) : list.map(b => (
              <div key={b.id} className={cx('ticket-card', tab === 'past' && 'past', open[b.id] && 'expanded', collapsing === b.id && 'collapsing')}>
                <div className="ticket-top" {...press(() => setOpen(o => ({ ...o, [b.id]: !o[b.id] })))} aria-expanded={!!open[b.id]}>
                  <div className="ticket-thumb" style={{ background: b.bg }}>
                    <Photo slug={b.neighbourhood.toLowerCase().replace(/\s+/g, '-')} fallback={b.icon} />
                  </div>
                  <div className="ticket-info">
                    <div className="ticket-walk-name">{b.walkName}</div>
                    <div className="ticket-meta">{b.neighbourhood}</div>
                    <div className="ticket-date">{tab === 'upcoming' ? readyText(b) : `Walked ${b.walkedOn}`}</div>
                    <div className="ticket-tap-hint">Tap to {tab === 'upcoming' ? 'expand QR' : 'view details'}</div>
                  </div>
                  <div style={{ fontSize: 13, ...mono, fontWeight: 700 }}>{b.price}</div>
                </div>
                <div className="ticket-perf" />
                <div className="ticket-qr-section">
                  <div className="ticket-qr-inner">
                    <QR id={b.id} />
                    <div className="ticket-id">BOOKING ID<br /><strong>{b.ref || b.id}</strong><br />{tab === 'upcoming' ? readyText(b) : `Walked ${b.walkedOn}`}<br />{b.neighbourhood}</div>
                  </div>
                </div>
                <div className="ticket-actions">
                  {tab === 'upcoming' ? (
                    <>
                      {b.deviceStatus === 'other_device'
                        ? <button className="ticket-action-btn primary" onClick={() => moveHere(b)}>Use on this device</button>
                        : walks.some(w => w.t === b.walkName) && <button className="ticket-action-btn primary" onClick={() => startWalk(walks.find(w => w.t === b.walkName))}>{b.walkStatus === 'in_progress' ? 'Resume walk' : 'Start walk'}</button>}
                      <button className="ticket-action-btn danger" onClick={() => setCancelId(b.id)}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="ticket-action-btn primary" onClick={() => go('explore')}>More walks</button>
                      {!b.reviewed && <button className="ticket-action-btn">Leave review</button>}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── PASSPORT ───────── */
function Passport({ go, earned }) {
  const [flipped, setFlipped] = useState({})
  const collected = passportSlots.filter(s => s.collected).length
  return (
    <Phone tab="passport" go={go} caption="Passport — stamps & flip reveal">
      <div className="screen">
        <div className="passport-hdr">
          <h1>My Passport</h1>
          <div className="count">{collected} of {passportSlots.length} neighbourhoods collected</div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <div className="stamp-grid">
            {passportSlots.map((s, i) => {
              const just = earned && i === collected - 1
              return (
                <div key={s.slug} className={cx('stamp-slot stagger-item', just && 'just-earned', flipped[s.slug] && 'flipped')}
                  style={{ animationDelay: (just ? 50 : i * 40) + 'ms' }}
                  {...(s.collected
                    ? { ...press(() => setFlipped(f => ({ ...f, [s.slug]: !f[s.slug] })), `${s.name} stamp, collected on ${s.date} for ${s.walkName}. Tap to flip.`), 'aria-pressed': !!flipped[s.slug] }
                    : { role: 'img', 'aria-label': `${s.name} stamp, not yet collected` })}>
                  <div className="stamp-inner">
                    <div className={cx('stamp-face stamp-front', s.collected ? 'collected' : 'uncollected')}>
                      <div className="stamp-emoji">{s.emoji}</div>
                      <div className={cx('stamp-name', s.collected && 'collected')}>{s.name}</div>
                      {s.collected && <div style={{ fontSize: 11, color: 'var(--rust)', fontFamily: 'var(--font-label)', marginTop: 3 }}>✓ STAMPED</div>}
                    </div>
                    <div className="stamp-face stamp-back">
                      <div className="stamp-emoji">{s.emoji}</div>
                      {s.collected
                        ? <><div className="stamp-back-name">{s.walkName}</div><div className="stamp-back-date">{s.date}</div></>
                        : <div className="stamp-back-name" style={{ fontSize: 11, opacity: .6 }}>Not yet explored</div>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── NEIGHBOURHOOD ───────── */
function Neighbourhood({ nb, go, openWalk }) {
  const reduced = useReducedMotion()
  const [scroll, setScroll] = useState(0)
  const list = walks.filter(w => w.neighbourhood === nb.slug)
  return (
    <Phone caption="Neighbourhood hub — Malleshwaram">
      <div className="screen" onScroll={e => setScroll(e.currentTarget.scrollTop)}>
        <div className="nb-hero-wrap" style={{ background: nb.bg }}>
          <div className="nb-hero-img" style={{ transform: reduced ? 'none' : `translateY(${scroll * 0.45}px)` }}>
            <Photo slug={nb.slug} fallback={nb.emoji} />
          </div>
          <div className="nb-hero-overlay" />
          <button className="nb-back" aria-label="Back" onClick={() => go('home')}><Ic i={ArrowLeft} size={20} /></button>
          <div className="nb-hero-title"><h1>{nb.name}</h1><p>{nb.tagline}</p></div>
        </div>
        <div className="nb-context">{nb.description}</div>
        <div className="nb-walks-label">Walks in this neighbourhood</div>
        <div>
          {!list.length
            ? <div style={{ padding: 16, fontSize: 13, color: 'var(--text-soft)' }}>No walks yet in this neighbourhood — coming soon!</div>
            : list.map((w, i) => (
              <div key={w.id} className="nb-walk-row stagger-item" style={{ animationDelay: i * 60 + 'ms' }} {...press(() => openWalk(w), `${w.t}, ${w.meta}, ${w.price}`)}>
                <div className="nb-walk-thumb" style={{ background: w.bg }}>
                  <Photo slug={w.neighbourhood} fallback={w.icon} />
                </div>
                <div><div className="nb-walk-name">{w.t}</div><div className="nb-walk-meta">{w.meta}</div></div>
                <div className="nb-walk-price">{w.price}</div>
              </div>
            ))}
        </div>
      </div>
    </Phone>
  )
}

/* ───────── NOTIFICATIONS ───────── */
const TODAY = ['2h ago', '3h ago', 'Just now']
const NOTIF_ICON = { reminder: Bell, confirmed: CheckCircle2, new: MapIcon, review: Star }
function Notifications({ go }) {
  const [items, setItems] = useState(notificationsData.map(n => ({ ...n })))
  const [faded, setFaded] = useState(new Set())
  const [leaving, setLeaving] = useState(new Set())
  const [arriving, setArriving] = useState(null)
  const itemsRef = useRef(items)
  itemsRef.current = items
  const sim = useRef(100)
  const touchX = useRef(0)
  useEffect(() => { const t = setTimeout(() => { setFaded(new Set(itemsRef.current.map(n => n.id))); if (LIVE) api.notifications.markAllRead().catch(() => {}) }, 1500); return () => clearTimeout(t) }, [])
  const dismiss = id => {
    if (LIVE) api.notifications.dismiss(id).catch(() => {})
    setLeaving(s => new Set(s).add(id))
    setTimeout(() => setItems(l => l.filter(n => n.id !== id)), 350)
  }
  const simulate = () => {
    const id = ++sim.current
    setItems(l => [{ id, type: 'new', icon: '🗺️', title: 'New walk unlocked in Yelahanka', subtitle: 'Yelahanka Fort Trail · 2.8km · ₹279', time: 'Just now', unread: true }, ...l])
    setArriving(id)
    setTimeout(() => setArriving(null), 400)
  }
  const row = n => (
    <div key={n.id} className={cx('notif-row', leaving.has(n.id) && 'dismissing', arriving === n.id && 'new-arrival')}
      {...press(() => dismiss(n.id), `Dismiss notification: ${n.title}. ${n.subtitle}`)}
      onTouchStart={e => { touchX.current = e.touches[0].clientX }}
      onTouchEnd={e => { if (e.changedTouches[0].clientX - touchX.current > 60) dismiss(n.id) }}>
      <div className="notif-icon-wrap"><Ic i={NOTIF_ICON[n.type] || Bell} size={20} />{n.unread && <div className="notif-unread-dot" style={faded.has(n.id) ? { opacity: 0 } : undefined} />}</div>
      <div className="notif-info"><div className="notif-title">{n.title}</div><div className="notif-subtitle">{n.subtitle}</div></div>
      <div className="notif-time">{n.time}</div>
    </div>
  )
  const isToday = n => (n.today ?? TODAY.includes(n.time))
  const today = items.filter(isToday)
  const earlier = items.filter(n => !isToday(n))
  return (
    <Phone caption="Notifications — unread dots · swipe dismiss">
      <div className="screen">
        <div className="notif-hdr"><div className="back" {...press(() => go('home'))}>← Back</div><h1>Notifications</h1></div>
        <div className="notif-list">
          {!items.length && (
            <div className="empty-state">
              <div className="empty-icon"><Ic i={Bell} size={34} /></div>
              <div className="empty-title">You're all caught up</div>
              <div className="empty-body">Walk reminders, booking confirmations and new walks will show up here.</div>
            </div>
          )}
          {!!today.length && <><div className="notif-group-label">Today</div>{today.map(row)}</>}
          {!!earlier.length && <><div className="notif-group-label">Earlier</div>{earlier.map(row)}</>}
        </div>
        {!LIVE && <button className="notif-sim-btn" onClick={simulate}>+ Simulate new notification arriving</button>}
      </div>
    </Phone>
  )
}

/* ───────── ACTIVE WALK ───────── */
const fmtTime = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`
const rad = d => (d * Math.PI) / 180
const metres = ([a, b], [c, d]) => {
  const h = Math.sin(rad(c - a) / 2) ** 2 + Math.cos(rad(a)) * Math.cos(rad(c)) * Math.sin(rad(d - b) / 2) ** 2
  return 2 * 6371000 * Math.asin(Math.sqrt(h))
}
const fmtDist = m => (m < 1000 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1)} km`)
const SPEEDS = [1, 1.25, 1.5, 0.75]
const STORY_SECS = 220   // PLACEHOLDER: every stop's audio is 3:40 until real audio files exist

const pinIcon = (i, state) => L.divIcon({ className: `wmark ${state}`, html: `<span>${i + 1}</span>`, iconSize: [32, 32], iconAnchor: [16, 16] })

// Real map (Leaflet + OpenStreetMap tiles, no API key). Draws the route, numbered stops and, if allowed, the walker.
function WalkMap({ stops, cur, user, locOff }) {
  const reduced = useReducedMotion()
  const el = useRef(null)
  const map = useRef(null)
  const marks = useRef([])
  const me = useRef(null)
  const [tilesOk, setTilesOk] = useState(true)
  const pts = stops.map(s => s.coords)
  useEffect(() => {
    const m = L.map(el.current, { zoomControl: false, scrollWheelZoom: false, attributionControl: true, zoomSnap: 0.1, zoomDelta: 0.5, zoomAnimation: !reduced, fadeAnimation: !reduced, markerZoomAnimation: !reduced })
    map.current = m
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(m)
    let errs = 0
    tiles.on('tileerror', () => { if (++errs >= 3) setTilesOk(false) })
    tiles.on('tileload', () => { errs = 0; setTilesOk(true) })
    L.polyline(pts, { color: '#2E2520', weight: 8, opacity: .9, lineJoin: 'round' }).addTo(m)          // dark casing
    L.polyline(pts, { color: '#E8845F', weight: 4, opacity: 1, lineJoin: 'round' }).addTo(m)           // route
    marks.current = stops.map((s, i) => L.marker(s.coords, { icon: pinIcon(i, 'todo'), keyboard: false, interactive: false }).addTo(m))
    m.fitBounds(L.latLngBounds(pts), { padding: [30, 30] })
    // the container is sized by flex layout after mount: re-measure and re-fit whenever its size changes
    const ro = new ResizeObserver(() => { m.invalidateSize(); m.fitBounds(L.latLngBounds(pts), { padding: [30, 30], animate: false }) })
    ro.observe(el.current)
    return () => { ro.disconnect(); m.remove(); map.current = null; me.current = null }
  }, [])
  useEffect(() => { marks.current.forEach((mk, i) => mk.setIcon(pinIcon(i, i < cur ? 'done' : i === cur ? 'now' : 'todo'))) }, [cur])
  useEffect(() => {
    const m = map.current
    if (!m || !user) return
    if (!me.current) me.current = L.marker(user, { icon: L.divIcon({ className: 'wuser', html: '<i></i>', iconSize: [22, 22], iconAnchor: [11, 11] }), keyboard: false, interactive: false, zIndexOffset: 1000 }).addTo(m)
    else me.current.setLatLng(user)
  }, [user])
  const fit = () => map.current && map.current.fitBounds(L.latLngBounds(pts), { padding: [30, 30] })
  const locate = () => map.current && user && map.current.setView(user, 17)
  return (
    <div className="walk-map-live" role="region" aria-label="Walk map">
      <div ref={el} className="walk-map-canvas" />
      {locOff && <div className="map-chip" role="status"><MapPin size={13} aria-hidden="true" /> Location is off: showing the route only</div>}
      {!tilesOk && <div className="map-offline" role="status"><WifiOff size={13} aria-hidden="true" /> No map tiles (offline)</div>}
      <div className="map-btns">
        <button type="button" className="map-btn" aria-label="Fit whole route" onClick={fit}><Ic i={Maximize2} size={18} /></button>
        <button type="button" className="map-btn" aria-label="Centre on my location" disabled={!user} onClick={locate}><Ic i={Crosshair} size={18} /></button>
      </div>
    </div>
  )
}

function WalkPlayer({ walk: w, go, live }) {
  const stops = live ? live.stops : w.stops
  const [gps, setGps] = useState(false)
  const [cur, setCur] = useState(live ? Math.max(0, Math.min(live.session.stops_visited - 1, stops.length - 1)) : Math.min(1, stops.length - 1))
  const audioRef = useRef(null)
  const [dur, setDur] = useState(STORY_SECS)
  const [audioDone, setAudioDone] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [finErr, setFinErr] = useState('')
  const queueRef = useRef([])
  const curRef = useRef(cur)
  curRef.current = cur
  const queue = (type, stopId) => { if (live) queueRef.current.push({ id: uid(), stopId, type, at: new Date() }) }
  const flush = async () => {
    if (!live || !queueRef.current.length) return
    const batch = queueRef.current.splice(0)
    try { await api.sessions.sendEvents(live.session.id, batch) } catch (e) { queueRef.current.unshift(...batch); throw e }
  }
  const [user, setUser] = useState(null)
  const [loc, setLoc] = useState('pending')   // pending | ok | denied | unavailable
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const stop = stops[cur]
  const next = stops[cur + 1]
  const last = cur === stops.length - 1
  const total = live ? dur : STORY_SECS
  const ended = live ? audioDone : t >= STORY_SECS

  // live: audio for the current stop, arrival events, geofence, wake lock
  useEffect(() => {
    if (!live) return
    const a = audioRef.current
    a.src = live.audio[stop.id]
    a.playbackRate = speed
    setT(0); setAudioDone(false); setDur(STORY_SECS)
    queue('arrived', stop.id)
    a.play().catch(() => setPlaying(false))
  }, [cur])
  useEffect(() => {
    if (!live) return
    const tick = setInterval(() => { flush().catch(() => {}) }, 10000)
    const hide = () => { if (document.visibilityState === 'hidden') flush().catch(() => {}) }
    document.addEventListener('visibilitychange', hide)
    return () => { clearInterval(tick); document.removeEventListener('visibilitychange', hide); flush().catch(() => {}); if (audioRef.current) audioRef.current.pause() }
  }, [])
  useEffect(() => {
    if (!live || !navigator.wakeLock) return
    let lock = null
    const get = async () => { try { lock = await navigator.wakeLock.request('screen') } catch (_) {} }
    get()
    const vis = () => { if (document.visibilityState === 'visible') get() }
    document.addEventListener('visibilitychange', vis)
    return () => { document.removeEventListener('visibilitychange', vis); if (lock) lock.release().catch(() => {}) }
  }, [])
  const onPosition = c => {   // entering the next stop's trigger radius moves the walk on, in order
    if (!live) return
    const nxt = stops[curRef.current + 1]
    if (!nxt) return
    if (metres([c.latitude, c.longitude], nxt.coords) <= Math.max(nxt.radius || 30, 20) + Math.min(c.accuracy || 0, 25)) setCur(curRef.current + 1)
  }

  // walker's position (only if the browser/user allows it)
  useEffect(() => {
    if (!navigator.geolocation) { setLoc('unavailable'); return }
    const id = navigator.geolocation.watchPosition(
      p => { setUser([p.coords.latitude, p.coords.longitude]); setLoc('ok'); setGps(false); onPosition(p.coords) },
      e => { if (e.code === 1) setLoc('denied'); else setGps(true) },   // 1 = permission denied: stay quiet, the map just has no "you" dot
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 })
    return () => navigator.geolocation.clearWatch(id)
  }, [])
  // simulated audio clock (real audio files would replace this)
  useEffect(() => {
    if (live || !playing || ended) return
    const id = setInterval(() => setT(x => Math.min(STORY_SECS, x + 1)), 1000 / speed)
    return () => clearInterval(id)
  }, [playing, ended, speed])
  useEffect(() => { if (!live && ended) setPlaying(false) }, [ended])

  const seek = v => { if (live) { audioRef.current.currentTime = v; setT(v) } else setT(v) }
  const skip = d => { if (live) seek(Math.max(0, Math.min(dur, audioRef.current.currentTime + d))); else setT(x => Math.max(0, Math.min(STORY_SECS, x + d))) }
  const goTo = i => { setCur(i); setT(0); setPlaying(true) }
  const toggle = () => {
    if (live) {
      const a = audioRef.current
      if (ended) { a.currentTime = 0; setAudioDone(false) }
      if (a.paused || ended) a.play().catch(() => {}); else a.pause()
      return
    }
    if (ended) { setT(0); setPlaying(true) } else setPlaying(p => !p)
  }
  const cycleSpeed = () => setSpeed(v => { const n = SPEEDS[(SPEEDS.indexOf(v) + 1) % SPEEDS.length]; if (live && audioRef.current) audioRef.current.playbackRate = n; return n })
  const finish = async () => {
    if (!live) return go('complete')
    setFinishing(true); setFinErr('')
    try {
      await flush()
      await api.sessions.complete(live.session.id)
      lastWalk.summary = await api.sessions.summary(live.session.id)
      go('complete')
    } catch (e) { setFinErr(friendlyError(e, "We couldn't finish the walk. Check your connection and try again.")); setFinishing(false) }
  }
  const endEarly = () => {
    if (live && !window.confirm('End the walk now? It will be marked complete and cannot be walked again.')) return
    finish()
  }
  const toNext = next ? metres(user || stop.coords, next.coords) : 0

  return (
    <Phone caption="Active walk — GPS + audio (GPS banner demo)">
      <div className="screen walk-hc">
        {live && <audio ref={audioRef} preload="auto"
          onTimeUpdate={e => setT(e.currentTarget.currentTime)}
          onLoadedMetadata={e => setDur(e.currentTarget.duration || STORY_SECS)}
          onPlay={() => { setPlaying(true); queue('audio_started', stop.id) }}
          onPause={() => setPlaying(false)}
          onEnded={() => { setAudioDone(true); setPlaying(false); queue('audio_finished', stop.id) }} />}
        <div className={cx('gps-banner', gps && 'show')} role="status"><Ic i={WifiOff} size={15} /> Signal lost — we'll resume when you're back in range</div>
        <div className="walk-hdr"><span className="wname">{w.t}</span><span className="wpill">Stop {cur + 1} / {stops.length}</span></div>
        <WalkMap stops={stops} cur={cur} user={user} locOff={loc === 'denied' || loc === 'unavailable'} />
        <div className="walk-line-wrap">
          <div className="walk-line-track">
            {stops.map((_, i) => (
              <Fragment key={i}>
                {i > 0 && <div className="wl-line"><div className="wl-line-fill" style={{ width: i <= cur ? '100%' : '0%' }} /></div>}
                <div className="wl-stop"><div className={cx('wl-dot', i < cur && 'visited', i === cur && 'active')} /><div className={cx('wl-num', i < cur && 'visited', i === cur && 'active')}>{String(i + 1).padStart(2, '0')}</div></div>
              </Fragment>
            ))}
          </div>
        </div>
        <div className="audio-card">
          <div className="audio-stop-label">NOW PLAYING · STOP {String(cur + 1).padStart(2, '0')}</div>
          <div className="audio-stop-name">{stop.n}</div>
          <div className="audio-prog-wrap">
            <input className="audio-seek" type="range" min={0} max={Math.round(total)} step={1} value={Math.round(t)} aria-label="Seek audio" aria-valuetext={`${fmtTime(t)} of ${fmtTime(total)}`}
              style={{ '--pct': (t / total) * 100 + '%' }} onChange={e => seek(+e.target.value)} />
            <div className="audio-times"><span>{fmtTime(t)}</span><span>{fmtTime(total)}</span></div>
          </div>
          <div className="player-row">
            <button type="button" className="pl-btn speed" aria-label={`Playback speed ${speed} times. Change speed`} onClick={cycleSpeed}>{speed}×</button>
            <button type="button" className="pl-btn" aria-label="Back 15 seconds" onClick={() => skip(-15)}><Ic i={RotateCcw} size={26} /><b>15</b></button>
            <button type="button" className="play-btn big" aria-label={playing && !ended ? 'Pause' : ended ? 'Replay' : 'Play'} onClick={toggle}><Ic i={playing && !ended ? Pause : Play} size={30} /></button>
            <button type="button" className="pl-btn" aria-label="Forward 15 seconds" onClick={() => skip(15)}><Ic i={RotateCw} size={26} /><b>15</b></button>
            <span className="pl-btn ghost" aria-hidden="true" />
          </div>
        </div>
        <div className="next-stop-hint">
          {last ? (
            <>
              <div className="nsh-label">LAST STOP</div>
              <div className="nsh-name">You've reached the end of the route</div>
              <button type="button" className="next-btn" onClick={finish} disabled={finishing}>{finishing ? 'Finishing…' : 'Finish walk'} <Ic i={ChevronRight} size={18} /></button>
            </>
          ) : (
            <>
              <div className="nsh-label">UP NEXT · STOP {String(cur + 2).padStart(2, '0')}</div>
              <div className="nsh-name">{next.n}</div>
              <div className="nsh-dist">≈ {fmtDist(toNext)} {user ? 'from you' : 'from this stop'} · approximate</div>
              <button type="button" className="next-btn" onClick={() => goTo(cur + 1)}>Next stop <Ic i={ChevronRight} size={18} /></button>
            </>
          )}
        </div>
        {finErr && <div className="pay-error" role="alert" style={{ margin: '0 16px 8px' }}><span>{finErr}</span></div>}
        {!live && <button className="gps-demo-btn" onClick={() => setGps(g => !g)}>⚡ Demo: Toggle GPS lost banner</button>}
        <button className="end-walk-btn" onClick={endEarly} disabled={finishing}>End walk early</button>
      </div>
    </Phone>
  )
}

function Walk({ walk: w, go }) {
  const [st, setSt] = useState(LIVE ? { s: 'loading', msg: 'Preparing your walk…' } : { s: 'demo' })
  const [tryN, setTryN] = useState(0)
  useEffect(() => {
    if (!LIVE) return
    let dead = false
    setSt({ s: 'loading', msg: 'Preparing your walk…' })
    ;(async () => {
      try {
        const pkg = await api.tours.package(w.id)
        const stops = pkg.stops.map(x => ({ id: x.id, e: x.icon, n: x.name, d: x.blurb, coords: [x.lat, x.lng], radius: x.trigger_radius_m, audioUrl: x.audio_url }))
        const audio = await prepareAudio(stops, (i, n) => { if (!dead) setSt({ s: 'loading', msg: `Downloading audio… ${i} of ${n}` }) })
        const session = await api.sessions.start(w.id)
        if (!dead) setSt({ s: 'ready', live: { stops, audio, session } })
      } catch (e) { if (!dead) setSt({ s: 'error', e }) }
    })()
    return () => { dead = true }
  }, [w.id, tryN])
  if (st.s === 'demo') return <WalkPlayer walk={w} go={go} />
  if (st.s === 'ready') return <WalkPlayer walk={w} go={go} live={st.live} />
  const e = st.e
  const info = st.s === 'error' && (
    e && e.code === 'BOUND_TO_OTHER_DEVICE' ? ['This walk is on another device', 'Open My Bookings and choose "Use on this device" to move it here.', ['Go to bookings', () => go('bookings')]]
    : e && e.code === 'TOUR_NOT_OWNED' ? ['Get this walk first', 'You need to buy this walk before you can start it.', ['Back to walks', () => go('explore')]]
    : e && e.code === 'TOUR_ALREADY_COMPLETED' ? ["You've already walked this one", 'Each walk can be completed once. See your stamp in the passport.', ['Open passport', () => go('passport')]]
    : ["We couldn't start the walk", friendlyError(e), ['Try again', () => setTryN(n => n + 1)]])
  return (
    <Phone caption="Active walk">
      <div className="screen" style={{ display: 'grid', placeItems: 'center', textAlign: 'center', padding: 24 }}>
        {st.s === 'loading'
          ? <div role="status">{st.msg}</div>
          : <div className="empty-state"><div className="empty-title">{info[0]}</div><div className="empty-body">{info[1]}</div><button className="btn-ghost empty-cta" style={{ width: 'auto', padding: '9px 18px', fontSize: 13 }} onClick={info[2][1]}>{info[2][0]}</button><button className="back" style={{ marginTop: 10 }} onClick={() => go('home')}>Back to home</button></div>}
      </div>
    </Phone>
  )
}

/* ───────── COMPLETE ───────── */
function Complete({ walk: w, go, toPassport }) {
  const sm = LIVE ? lastWalk.summary : null
  const [liked, setLiked] = useState(!!(sm && sm.liked))
  const [myRating, setMyRating] = useState(sm ? sm.my_rating : null)
  const [commenting, setCommenting] = useState(false)
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const act = async fn => { try { await fn(); setNote('') } catch (e) { setNote(friendlyError(e)) } }
  const rate = n => act(async () => { await api.social.rate(w.id, n); setMyRating(n) })
  const toggleLike = () => act(async () => { if (liked) await api.social.unlike(w.id); else await api.social.like(w.id); setLiked(!liked) })
  const sendComment = () => act(async () => { if (!text.trim()) return; await api.social.comment(w.id, text.trim()); setText(''); setCommenting(false); setNote('Thanks for your comment.') })
  return (
    <Phone caption="Walk complete (→ passport with justEarned)">
      <div className="screen">
        <div className="complete-screen">
          <div className="complete-stamp"><div className="stamp-word">WALKED</div><div className="stamp-icon">✓</div></div>
          <div className="display" style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>Walk complete.</div>
          <div style={{ fontSize: 13, color: 'var(--text-soft)', lineHeight: 1.5, marginBottom: 18 }}>
            {w.t}<br />
            <span style={{ ...mono, fontSize: 11 }}>Tour locked · purchased once</span>
          </div>
          <div className="complete-stats">
            {(sm ? [[`${sm.stops_visited}/${sm.stop_count}`, 'Stops'], [`${sm.distance_km}km`, 'Walked'], [`${sm.duration_min}m`, 'Duration'], [sm.avg_rating == null ? '–' : Number(sm.avg_rating).toFixed(1) + ' ★', 'Avg rating']] : [[String(w.stops.length), 'Stops'], [w.distance.replace(' ', ''), 'Walked'], [w.duration.replace(' min', 'm'), 'Duration'], [w.rating + ' ★', 'Avg rating']]).map(([v, k]) => <div className="cstat" key={k}><div className="cv">{v}</div><div className="ck">{k}</div></div>)}
          </div>
          <div className="lc-row">
            <button className={cx('lc-btn', liked && 'liked')} onClick={LIVE ? toggleLike : () => setLiked(l => !l)}><Ic i={Heart} size={15} /> {liked ? 'Liked' : 'Like'}</button>
            <button className="lc-btn" onClick={() => LIVE && setCommenting(c => !c)}><Ic i={MessageCircle} size={15} /> Comment</button>
          </div>
          {LIVE && (
            <div style={{ marginBottom: 14 }}>
              <div role="radiogroup" aria-label="Rate this walk" style={{ display: 'flex', gap: 4, justifyContent: 'center', marginBottom: 8 }}>
                {[1, 2, 3, 4, 5].map(n => (
                  <button key={n} type="button" role="radio" aria-checked={myRating === n} aria-label={`${n} star${n > 1 ? 's' : ''}`} onClick={() => rate(n)}
                    style={{ background: 'none', border: 0, fontSize: 28, lineHeight: 1, minWidth: 44, minHeight: 44, cursor: 'pointer', color: myRating >= n ? 'var(--rust)' : 'var(--text-soft)' }}>{myRating >= n ? '★' : '☆'}</button>
                ))}
              </div>
              {commenting && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input className="field" aria-label="Your comment" placeholder="Share a thought about this walk" maxLength={500} value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendComment()} />
                  <button className="btn-primary" style={{ width: 'auto', padding: '0 16px' }} onClick={sendComment}>Send</button>
                </div>
              )}
              {note && <div className="pay-error" role="status" style={{ marginTop: 8 }}><span>{note}</span></div>}
            </div>
          )}
          <button className="btn-primary" onClick={() => toPassport(!sm || sm.stamp_earned)} style={{ marginBottom: 8 }}><Ic i={BookOpen} size={16} /> {!sm || sm.stamp_earned ? 'View your new stamp →' : 'View your passport →'}</button>
          <button className="btn-ghost" onClick={() => go('home')}>Back to home</button>
        </div>
      </div>
    </Phone>
  )
}

/* ───────── PROFILE ───────── */
function Profile({ go, toPassport }) {
  const [initial, setInitial] = useState(LIVE && profile.user ? ((profile.user.full_name || profile.user.email || '?')[0]).toUpperCase() : 'P')
  const [saveMsg, setSaveMsg] = useState('')
  const save = async patch => {
    if (!LIVE) return
    try { profile.user = await api.me.update(patch); setSaveMsg('Saved') } catch (e) { setSaveMsg(friendlyError(e, "We couldn't save that.")) }
  }
  const st = LIVE && profile.stats ? [[String(profile.stats.walks_completed), 'Walks'], [String(profile.stats.distance_km), 'km'], [String(profile.stats.reviews_count), 'Reviews']] : [['7', 'Walks'], ['14.2', 'km'], ['3', 'Reviews']]
  const entry = (icon, title, sub, onClick) => (
    <div className="profile-entry-row" {...press(onClick, sub ? `${title}, ${sub}` : title)}>
      <div className="sleft"><span className="sicon">{icon}</span><div><div className="stitle">{title}</div>{sub && <div className="ssub" style={{ fontSize: 11, color: 'var(--text-soft)' }}>{sub}</div>}</div></div>
      <span className="sarrow" style={{ fontSize: 14, color: 'var(--text-soft)' }}>›</span>
    </div>
  )
  return (
    <Phone tab="profile" go={go} caption="Profile (→ Passport entry)">
      <div className="screen">
        <div className="profile-hero"><h1>Your Profile</h1></div>
        <div style={{ position: 'relative' }}><div className="avatar-ring" role="img" aria-label={`Profile picture, initial ${initial}`}>{initial}<div className="avatar-edit"><Ic i={Pencil} size={13} /></div></div></div>
        <div className="profile-stats">
          {st.map(([v, k]) => <div className="pstat" key={k}><div className="pv">{v}</div><div className="pk">{k}</div></div>)}
        </div>
        <div className="pform">
          <Field label="Full name" placeholder="Priya Sharma" autoComplete="name" defaultValue={LIVE && profile.user ? profile.user.full_name || '' : undefined} onBlur={e => save({ fullName: e.target.value.trim() })} onChange={e => setInitial(e.target.value.trim()[0] ? e.target.value.trim()[0].toUpperCase() : '?')} />
          <Field label="Username" placeholder="@priya_walks" autoComplete="username" defaultValue={LIVE && profile.user && profile.user.username ? '@' + profile.user.username : undefined} onBlur={e => e.target.value.trim() && save({ username: e.target.value.trim() })} />
          <Field label="Email address" type="email" placeholder="priya@email.com" autoComplete="email" readOnly={LIVE} defaultValue={LIVE && profile.user ? profile.user.email : undefined} />
          {saveMsg && <div className="pay-error" role="status" style={{ marginTop: 8 }}><span>{saveMsg}</span></div>}
        </div>
        {entry(<Ic i={BookOpen} />, 'My Passport', `${passportSlots.filter(x => x.collected).length} of ${passportSlots.length} stamps collected`, () => toPassport(false))}
        {entry(<Ic i={Ticket} />, 'My Bookings', null, () => go('bookings'))}
        {entry(<Ic i={SettingsIcon} />, 'Settings', 'Privacy, location, legal', () => go('settings'))}
        <div className="tab-spacer" />
      </div>
    </Phone>
  )
}

/* ───────── SETTINGS ───────── */
function Toggle({ on: init, label, onChange }) {
  const [on, setOn] = useState(!!init)
  return <button type="button" role="switch" aria-checked={on} aria-label={label} className={cx('toggle', on && 'on')} onClick={() => { const n = !on; setOn(n); if (onChange) onChange(n) }} />
}
const Row = ({ icon, title, sub, danger, right, onClick, expanded }) => (
  <div className={cx('srow', danger && 'danger')} {...(onClick ? press(onClick, sub ? `${title}, ${sub}` : title) : {})} aria-expanded={expanded}>
    <div className="sleft"><span className="sicon">{icon}</span><div><div className="stitle">{title}</div>{sub && <div className="ssub">{sub}</div>}</div></div>
    {right || <span className="sarrow" style={danger ? { color: 'var(--error)' } : undefined}>›</span>}
  </div>
)
function Settings({ go }) {
  const [credits, setCredits] = useState(false)
  const [msg, setMsg] = useState('')
  const pref = patch => { if (LIVE) api.me.preferences(patch).then(u => { profile.user = u }).catch(e => setMsg(friendlyError(e))) }
  const signOut = async () => { try { if (LIVE) await api.auth.logout() } catch (_) {} clearUserData(); go('splash') }
  const exportData = async () => { if (!LIVE) return; try { downloadJson(await api.me.exportData(), 'nob-my-data.json'); setMsg('Your data was downloaded.') } catch (e) { setMsg(friendlyError(e)) } }
  const deleteAccount = async () => {
    if (!LIVE) return
    if (!window.confirm('Delete your account? This is permanent and cannot be undone.')) return
    try { await api.me.deleteAccount(); clearUserData(); go('splash') } catch (e) { setMsg(friendlyError(e)) }
  }
  return (
    <Phone caption="Settings">
      <div className="screen">
        <div className="settings-hero"><div className="back" {...press(() => go('profile'))}>← Profile</div><h1>Settings</h1></div>
        {msg && <div className="pay-error" role="status" style={{ margin: '0 16px 10px' }}><span>{msg}</span></div>}
        <div className="settings-section">
          <h2>Location</h2>
          <Row icon={<Ic i={MapPin} />} title="GPS tracking" sub="Required for audio triggers" right={<Toggle on label="GPS tracking" />} />
          <Row icon={<Ic i={Bell} />} title="Notifications" sub="Walk reminders & updates" right={<Toggle label="Notifications" on={LIVE ? !!(profile.user && profile.user.notifications_enabled) : false} onChange={n => pref({ notificationsEnabled: n })} />} />
        </div>
        <div className="settings-section" style={{ marginTop: 12 }}>
          <h2>Privacy &amp; Preferences</h2>
          <Row icon={<Ic i={BarChart3} />} title="Analytics sharing" sub="Help improve the app (opt-in)" right={<Toggle label="Analytics sharing" on={LIVE ? !!(profile.user && profile.user.analytics_opt_in) : false} onChange={n => pref({ analyticsOptIn: n })} />} />
          <Row icon={<Ic i={Download} />} title="Download my data" onClick={exportData} />
          <Row icon={<Ic i={Trash2} />} title="Delete my account" sub="Permanent — cannot be undone" danger onClick={deleteAccount} />
        </div>
        <div className="settings-section" style={{ marginTop: 12 }}>
          <h2>Legal</h2>
          <Row icon={<Ic i={FileText} />} title="Terms & conditions" />
          <Row icon={<Ic i={Lock} />} title="Privacy policy" />
          <Row icon={<Ic i={Wallet} />} title="Refund policy" sub="Full refund if walk not started" />
          <Row icon={<Ic i={Mail} />} title="Data grievance officer" sub="grievance@nob.app" />
          <Row icon={<Ic i={Info} />} title="About NoB" sub="Version 1.1.0" />
          <Row icon={<Ic i={Info} />} title="Photo credits" sub="Place photos come from Wikipedia" expanded={credits} onClick={() => setCredits(c => !c)}
            right={<span className="sarrow" aria-hidden="true">{credits ? '⌄' : '›'}</span>} />
          {credits && (
            <div className="credits">
              <p>Place photos are loaded from the Wikipedia articles below. They are openly licensed (Creative Commons or public domain); the author and licence of each photo are on its Wikipedia / Wikimedia Commons file page.</p>
              {neighbourhoods.map(nb => (
                <div key={nb?.slug} className="credits-group">
                  <b>{nb.name}</b>
                  <ul>{[...new Set(WIKI[nb.slug] || [])].map(t => <li key={t}><a href={`https://en.wikipedia.org/wiki/${encodeURIComponent(t)}`} target="_blank" rel="noopener noreferrer">{t.replace(/_/g, ' ')}</a></li>)}</ul>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="settings-section" style={{ marginTop: 12 }}>
          <h2>Account</h2>
          <Row icon={<Ic i={LogOut} />} title="Log out" danger onClick={signOut} />
        </div>
        <button className="explore-btn-big" style={{ marginTop: 16 }} onClick={() => go('profile')}>Back to Profile</button>
      </div>
    </Phone>
  )
}

/* ───────── APP / PROTOTYPE NAV ───────── */
const NAV = [
  ['splash', '🎧 Splash'], ['about', 'About'], ['signup', 'Sign Up'], ['login', 'Login'], ['location-prime', '📍 Location'], '|',
  ['home', 'Home'], ['explore', '🔍 Explore'], ['walk-detail', 'Walk Detail'], ['bookings', '🎟 Bookings'], ['passport', '📖 Passport'],
  ['neighbourhood', '🗺 Neighbourhood'], ['notifications', '🔔 Notifications'], '|',
  ['walk', 'Active Walk'], ['complete', 'Complete'], ['profile', 'Profile'], ['settings', 'Settings'],
]

const USER_PAGES = ['bookings', 'passport', 'notifications', 'profile', 'settings', 'walk', 'complete']

export default function App() {
  const [page, setPage] = useState('splash')
  const [walk, setWalk] = useState(walks[0])
  const [nb, setNb] = useState(neighbourhoods[0])
  const [earned, setEarned] = useState(false)
  const [boot, setBoot] = useState(LIVE ? 'loading' : 'ready')   // loading | ready | error
  const [notice, setNotice] = useState('')
  const loadAll = async () => {
    setBoot('loading')
    try {
      await hydrateCatalog()
      setWalk(walks[0]); setNb(neighbourhoods[0])
      if (api.isSignedIn()) { await hydrateUser().catch(() => {}); setPage('home') }
      setBoot('ready')
    } catch (e) { setBoot('error') }
  }
  useEffect(() => { if (LIVE) loadAll() }, [])
  useEffect(() => onSessionEnded(reason => {
    clearUserData()
    setNotice(reason === 'other_device' ? 'You were signed out because this account was signed in on another device.' : 'Your session has ended. Please sign in again.')
    setPage('login')
  }), [])
  const onAuthed = async () => { setNotice(''); await hydrateUser().catch(() => {}) }
  // on every screen change: set the page title and move focus to the new screen (for keyboard / screen-reader users)
  useEffect(() => {
    const label = (NAV.find(n => n[0] === page) || [page, page])[1].replace(/^[^A-Za-z]+/, '')
    document.title = `${label} · NoB`
    const el = document.querySelector('.stage .screen')
    if (el) { el.setAttribute('tabindex', '-1'); el.setAttribute('role', 'main'); el.setAttribute('aria-label', label); el.focus({ preventScroll: true }) }
  }, [page])
  const go = async p => {
    if (LIVE) {
      const signedIn = api.isSignedIn()
      if (USER_PAGES.includes(p) && !signedIn) { setNotice('Please sign in to continue.'); setPage('login'); return }
      if (signedIn && (USER_PAGES.includes(p) || p === 'home')) { try { await hydrateUser() } catch (_) {} }
    }
    if (p !== 'passport') setEarned(false)
    setPage(p)
  }
  const openWalk = w => { setWalk(w); setPage('walk-detail') }
  const openNb = n => { setNb(n); setPage('neighbourhood') }
  const startWalk = w => { setWalk(w); setPage('walk') }
  const toPassport = e => { setEarned(e); setPage('passport') }

  const screens = {
    splash: <Splash go={go} />,
    about: <About go={go} />,
    signup: <Signup go={go} onAuthed={onAuthed} />,
    login: <Login go={go} onAuthed={onAuthed} notice={notice} />,
    'location-prime': <LocationPrime go={go} />,
    home: <Home go={go} openNb={openNb} startWalk={startWalk} />,
    explore: <Explore go={go} openWalk={openWalk} />,
    'walk-detail': <WalkDetail key={walk?.id} walk={walk} go={go} onStart={() => startWalk(walk)} />,
    bookings: <Bookings go={go} startWalk={startWalk} />,
    passport: <Passport go={go} earned={earned} />,
    neighbourhood: <Neighbourhood key={nb?.slug} nb={nb} go={go} openWalk={openWalk} />,
    notifications: <Notifications go={go} />,
    walk: <Walk key={walk?.id} walk={walk} go={go} />,
    complete: <Complete walk={walk} go={go} toPassport={toPassport} />,
    profile: <Profile go={go} toPassport={toPassport} />,
    settings: <Settings go={go} />,
  }

  if (boot !== 'ready') {
    return (
      <div className="stage"><div className="phone-col"><div className="phone"><div className="screen" style={{ display: 'grid', placeItems: 'center', textAlign: 'center', padding: 24 }}>
        {boot === 'loading'
          ? <div role="status">Loading walks…</div>
          : <div className="empty-state"><div className="empty-title">Can't reach the server</div><div className="empty-body">Check your connection and try again.</div><button className="btn-ghost empty-cta" style={{ width: 'auto', padding: '9px 18px', fontSize: 13 }} onClick={loadAll}>Try again</button></div>}
      </div></div></div></div>
    )
  }

  return (
    <>
      {!LIVE && <nav className="nav-row" aria-label="Prototype screens">
        {NAV.map((n, i) => n === '|'
          ? <div className="nav-sep" key={i} />
          : <button key={n[0]} className={cx('navbtn', page === n[0] && 'active')} aria-current={page === n[0] ? 'page' : undefined} onClick={() => go(n[0])}>{n[1]}</button>)}
      </nav>}
      <div className="stage" key={page}>{screens[page]}</div>
    </>
  )
}
