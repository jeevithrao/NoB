"""Offline walk: start with no signal from the saved copy, finish offline, and sync when back online.
Needs the API on :8000 (mock payments, audio generated) and the frontend on :5173 with VITE_API_URL=http://localhost:8000.
    python3 frontend/e2e/offline_walk.py
"""
import json, random, time, urllib.request
from playwright.sync_api import sync_playwright

email = f"off_{int(time.time())}_{random.randint(0, 999)}@example.com"
API = 'http://localhost:8000'
def wait_text(pg, t, ms=15000): pg.wait_for_selector(f'text={t}', timeout=ms, state='attached')
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = br.new_context(**p.devices['Pixel 7'], geolocation={'latitude': 12.94, 'longitude': 77.57}, permissions=['geolocation'])
    pg = ctx.new_page(); pg.on('pageerror', lambda e: print('PAGEERR', str(e)[:300]))
    pg.goto('http://localhost:5173/'); pg.wait_for_selector('text=Loading walks…', state='detached', timeout=15000)
    pg.wait_for_timeout(6000); pg.click("text=Yes, I've got 'em all!"); pg.wait_for_timeout(2200); pg.click('text=Create an account'); pg.wait_for_timeout(900)
    pg.fill('input[autocomplete=name]', 'Offline Tester'); pg.fill('input[type=email]', email)
    pw = pg.query_selector_all('input[autocomplete=new-password]'); pw[0].fill('correct-horse-1'); pw[1].fill('correct-horse-1')
    pg.check('#consentTos'); pg.click('text=Create account → Enable location'); pg.wait_for_timeout(1500); pg.click('text=Not now'); pg.wait_for_timeout(1000)
    pg.click('text=Search walks'); pg.wait_for_timeout(1200); pg.click('text=Gandhi Bazaar Book Lanes'); pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('.screen').scrollTo(0, 400)"); pg.wait_for_timeout(500)
    pg.click('.detail-sticky-bar .bookbtn'); pg.wait_for_timeout(900); pg.click('.sheet .bookbtn'); pg.wait_for_timeout(700)
    pg.click('.pay-btn'); pg.wait_for_timeout(2500)
    pg.click('text=Take me to the start'); pg.wait_for_timeout(600); pg.click('text=Begin walk')
    pg.wait_for_selector('text=Testing only', timeout=20000); pg.click('text=Testing only')   # the start gate (dev build skip)
    pg.wait_for_timeout(6000); pg.screenshot(path='/tmp/off1.png'); print(pg.inner_text('body')[:300].replace('\n',' | ')); wait_text(pg, 'End walk early'); print('[online start] ok')
    pg.wait_for_timeout(1500)
    pg.click('.tabbar >> text=Bookings') if pg.query_selector('.tabbar') else None
    pkg = pg.evaluate("Object.keys(localStorage).filter(k => k.startsWith('nob.pkg.'))")
    print('[package saved]', len(pkg) == 1)
    # leave the walk (App state), then lose signal and start again
    pg.goto('http://localhost:5173/'); pg.wait_for_timeout(1500)
    ctx.set_offline(True)
    # SPA reload offline would fail the catalogue; so go online-load first, then drop signal:
    ctx.set_offline(False); pg.wait_for_selector('text=Loading walks…', state='detached', timeout=15000); pg.wait_for_timeout(3000)
    ctx.set_offline(True)
    pg.click('.tabbar >> text=Bookings'); pg.wait_for_timeout(1000)
    pg.click('text=Resume walk'); wait_text(pg, 'End walk early'); print('[offline start] ok')
    pg.once('dialog', lambda d: d.accept()); pg.click('text=End walk early')
    pg.wait_for_selector('text=Walk complete.', timeout=10000); print('[offline finish] ok')
    pend = pg.evaluate("localStorage.getItem('nob.pending')"); print('[pending stored]', bool(pend and json.loads(pend)['completed']))
    ctx.set_offline(False); pg.evaluate("window.dispatchEvent(new Event('online'))"); pg.wait_for_timeout(4000)
    print('[pending cleared]', pg.evaluate("localStorage.getItem('nob.pending')") is None)
    br.close()
