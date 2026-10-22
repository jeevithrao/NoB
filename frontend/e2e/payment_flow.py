"""Browser test of the Razorpay Checkout path against a FAKE Razorpay API and a stubbed checkout.js.

Needs: fake_razorpay.py on :9000, the API on :8000 started with RAZORPAY_API_BASE=http://localhost:9000/v1,
RAZORPAY_KEY_ID=rzp_test_fake RAZORPAY_KEY_SECRET=fakesecret RAZORPAY_WEBHOOK_SECRET=fakewebhook MOCK_PAYMENTS=false,
and the frontend on :5173 with VITE_API_URL=http://localhost:8000.   python3 frontend/e2e/payment_flow.py
It proves our wiring; it does not talk to real Razorpay.
"""
import random, time
from playwright.sync_api import sync_playwright

STUB = """
window.Razorpay = function (o) {
  this.o = o; this.h = {};
  this.on = (ev, fn) => { this.h[ev] = fn };
  this.open = async () => {
    const mode = window.__rzpMode || 'ok';
    if (mode === 'dismiss') return setTimeout(() => o.modal.ondismiss(), 50);
    if (mode === 'fail') return setTimeout(() => this.h['payment.failed']({ error: { description: 'Card declined (stub)' } }), 50);
    const pay = 'pay_STUB' + Math.random().toString(16).slice(2, 8);
    const key = await crypto.subtle.importKey('raw', new TextEncoder().encode('fakesecret'), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const sig = Array.from(new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(o.order_id + '|' + pay)))).map(b => b.toString(16).padStart(2, '0')).join('');
    setTimeout(() => o.handler({ razorpay_order_id: o.order_id, razorpay_payment_id: pay, razorpay_signature: mode === 'badsig' ? 'deadbeef' : sig }), 50);
  };
};
"""
email = f"pay_{int(time.time())}_{random.randint(0, 999)}@example.com"
def show(pg, l, n=200): print(f'[{l}]', pg.inner_text('.sheet')[-n:].replace('\n', ' | '))
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_context(**p.devices['Pixel 7']).new_page()
    pg.route('https://checkout.razorpay.com/v1/checkout.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=STUB))
    pg.goto('http://localhost:5173/'); pg.wait_for_selector('text=Loading walks…', state='detached', timeout=15000)
    pg.wait_for_timeout(6000); pg.click("text=Yes, I've got 'em all!"); pg.wait_for_timeout(900)
    pg.fill('input[autocomplete=name]', 'Pay Tester'); pg.fill('input[type=email]', email)
    pw = pg.query_selector_all('input[autocomplete=new-password]'); pw[0].fill('correct-horse-1'); pw[1].fill('correct-horse-1')
    pg.check('#consentTos'); pg.click('text=Create account → Enable location'); pg.wait_for_timeout(1500); pg.click('text=Not now'); pg.wait_for_timeout(1000)
    pg.click('text=Search walks'); pg.wait_for_timeout(1200); pg.click('text=Gandhi Bazaar Book Lanes'); pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('.screen').scrollTo(0, 400)"); pg.wait_for_timeout(500)
    pg.click('.detail-sticky-bar .bookbtn'); pg.wait_for_timeout(900); pg.click('.sheet .bookbtn'); pg.wait_for_timeout(700)
    for mode in ['dismiss', 'fail', 'badsig']:
        pg.evaluate(f"window.__rzpMode='{mode}'"); pg.click('.pay-btn'); pg.wait_for_timeout(1800); show(pg, mode)
    pg.evaluate("window.__rzpMode='ok'"); pg.click('.pay-btn'); pg.wait_for_timeout(2500); show(pg, 'success', 160)
    pg.click('text=Take me to the start'); pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
    pg.click('.detail-back'); pg.wait_for_timeout(800); pg.click('.tabbar >> text=Bookings'); pg.wait_for_timeout(1000)
    print('[bookings]', pg.inner_text('body')[:170].replace('\n', ' | '))
    br.close()
