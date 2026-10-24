"""Go-to-start gate, street routing and the welcome screen.
Needs API :8000 (mock payments, audio generated) and the frontend (npm run dev) on :5173 with VITE_API_URL=http://localhost:8000.
The routing service is faked, so this proves our wiring, not the real OSM router.   python3 frontend/e2e/start_gate.py
"""
import json, random, subprocess, time
from playwright.sync_api import sync_playwright

START = (12.9455, 77.5718)           # Gandhi Bazaar Book Lanes, stop 1
FAR = (12.9600, 77.5900)
email = f"gate_{int(time.time())}_{random.randint(0, 999)}@example.com"
hits = []
def fake_router(route):
    hits.append(route.request.url)
    pts = [p.split(',') for p in route.request.url.split('/foot/')[1].split('?')[0].split(';')]
    line = [[float(a), float(b)] for a, b in pts]
    mid = [(line[0][0] + line[-1][0]) / 2 + 0.002, (line[0][1] + line[-1][1]) / 2]   # a bend, so it is visibly not straight
    line = [line[0], mid] + line[1:]
    route.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'},
                  body=json.dumps({'routes': [{'distance': 1500, 'geometry': {'coordinates': line}}]}))
def sessions():
    out = subprocess.run(['psql', '-h', 'localhost', '-p', '5433', '-U', 'ethnowalk_user', 'nob_dev', '-At', '-c',
        f"select count(*) from tour_sessions s join users u on u.id=s.user_id where u.email='{email}'"],
        env={'PGPASSWORD': 'ethnodb26', 'PATH': '/usr/bin:/bin'}, capture_output=True, text=True).stdout.strip()
    return int(out or 0)
def ok(label, cond): print(('PASS ' if cond else 'FAIL ') + label); assert cond, label

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = br.new_context(**p.devices['Pixel 7'], geolocation={'latitude': FAR[0], 'longitude': FAR[1]}, permissions=['geolocation'])
    pg = ctx.new_page(); pg.on('pageerror', lambda e: print('PAGEERR', str(e)[:200]))
    pg.route('https://routing.openstreetmap.de/**', fake_router)
    pg.goto('http://localhost:5173/'); pg.wait_for_selector('text=Loading walks…', state='detached', timeout=15000)
    pg.wait_for_timeout(6000); pg.click("text=Yes, I've got 'em all!"); pg.wait_for_timeout(2200)
    ok('first visit: intro leads to the Welcome screen with a Sign in option', pg.is_visible('text=I already have an account'))
    pg.click('text=Create an account'); pg.wait_for_timeout(900)
    pg.fill('input[autocomplete=name]', 'Gate Tester'); pg.fill('input[type=email]', email)
    pw = pg.query_selector_all('input[autocomplete=new-password]'); pw[0].fill('correct-horse-1'); pw[1].fill('correct-horse-1')
    pg.check('#consentTos'); pg.click('text=Create account → Enable location'); pg.wait_for_timeout(1500); pg.click('text=Not now'); pg.wait_for_timeout(1000)
    pg.click('text=Search walks'); pg.wait_for_timeout(1200); pg.click('text=Gandhi Bazaar Book Lanes'); pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('.screen').scrollTo(0, 400)"); pg.wait_for_timeout(500)
    pg.click('.detail-sticky-bar .bookbtn'); pg.wait_for_timeout(900); pg.click('.sheet .bookbtn'); pg.wait_for_timeout(700)
    pg.click('.pay-btn'); pg.wait_for_timeout(2500)
    pg.click('text=Take me to the start'); pg.wait_for_timeout(600); pg.click('text=Begin walk')
    pg.wait_for_selector('text=HEAD TO THE STARTING POINT', timeout=20000)
    ok('far away: shows the way to the start', True)
    ok('far away: no Start walk button', not pg.is_visible('button:has-text("Start walk")'))
    ok('far away: distance is shown', pg.is_visible('text=away'))
    ok('walk is NOT started on the server yet', sessions() == 0)
    pg.wait_for_timeout(1500)
    ok('street route requested from the router', len(hits) >= 1)
    paths = pg.evaluate("[...document.querySelectorAll('.leaflet-overlay-pane path')].map(p => (p.getAttribute('d')||'').split('L').length)")
    ok('route line follows the returned path (3 points: me, bend, start)', 3 in paths)
    pg.screenshot(path='/tmp/gate_far.png')
    ctx.set_geolocation({'latitude': START[0], 'longitude': START[1]}); pg.wait_for_timeout(2500)
    ok('at the start: arrival message', pg.is_visible("text=YOU'VE ARRIVED"))
    pg.screenshot(path='/tmp/gate_arrived.png')
    ok('at the start: Start walk button appears', pg.is_visible('button:has-text("Start walk")'))
    ok('still not started until tapped', sessions() == 0)
    pg.click('button:has-text("Start walk")'); pg.wait_for_selector('text=End walk early', state='attached', timeout=15000)
    ok('tapping Start begins the walk player', True)
    ok('session created on the server only now', sessions() == 1)
    pg.wait_for_timeout(2500)
    ok('whole-tour route requested for the walk map', len(hits) >= 2)
    pg.screenshot(path='/tmp/gate_walk.png')
    # returning visitor: logged out device lands on Welcome, not on the intro
    ctx2 = br.new_context(**p.devices['Pixel 7']); pg2 = ctx2.new_page()
    pg2.goto('http://localhost:5173/'); pg2.evaluate("localStorage.setItem('nob.seenIntro','1')"); pg2.reload()
    pg2.wait_for_selector('text=Loading walks…', state='detached', timeout=15000); pg2.wait_for_timeout(1500)
    ok('returning visitor sees Welcome with Sign in', pg2.is_visible('text=I already have an account'))
    pg2.click('text=I already have an account'); pg2.wait_for_timeout(800)
    ok('Sign in page opens', pg2.is_visible('text=Welcome back.'))
    br.close()
print('ALL PASSED')
