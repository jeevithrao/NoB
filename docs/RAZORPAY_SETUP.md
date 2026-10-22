# Razorpay test keys and webhook

Test mode moves no real money. Steps follow Razorpay's docs (checked 22 Oct 2026): https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/ and https://razorpay.com/docs/webhooks/setup-edit-payments/

## 1. Get test keys
1. Create a Razorpay account and log in to the Dashboard.
2. Switch the mode selector to **Test**.
3. **Account & Settings > Website and app settings > API Keys > Generate Key.** No website is needed for test keys.
4. The Dashboard shows the **Key ID** (`rzp_test_...`) and the **Key Secret** only once. Download and store the secret safely. If lost, regenerate and update every place that uses it.

## 2. Webhook secret
1. **Account & Settings > Website and app settings > Webhooks > Add New Webhook.**
2. URL: `https://<your public api domain>/webhooks/payment`. It must be public HTTPS: localhost is rejected, so use a tunnel (cloudflared/ngrok) while developing.
3. Secret: invent a long random value. It does not have to equal the API key secret. This is `RAZORPAY_WEBHOOK_SECRET`.
4. Events to tick: **payment.captured**, **order.paid**, **payment.failed** (the backend handles exactly these).
5. In test mode, Razorpay asks for the OTP `754081` when creating or editing a webhook.

## 3. Put them in the backend `.env`
```
MOCK_PAYMENTS=false
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxx
RAZORPAY_WEBHOOK_SECRET=the-secret-from-step-2
```
With `MOCK_PAYMENTS=false` the backend refuses to start unless all three are set.

## 4. Test payments
Use the test card and UPI details from Razorpay's own page (India section): https://razorpay.com/docs/payments/payments/test-card-upi-details/ . I could not open that page, and the card page I did open listed only US and international cards, so I do not quote numbers here. Use test mode only: test cards fail in live mode.

## What is built and tested
- Backend: order creation, checkout-signature verify, idempotent signed webhook, refunds (unit-tested with signatures).
- Frontend: the Pay button opens Razorpay Checkout, sends the result to `POST /purchases/{id}/verify`, handles cancel, decline, invalid signature, and a lost verify call (it polls, because the webhook completes the purchase).
- Both verified end to end against a **fake** Razorpay (`backend/scripts/fake_razorpay.py`, `frontend/e2e/payment_flow.py`). Not yet run against real Razorpay keys: that is the next test.

## Go-live (later)
Live keys need Razorpay's website/KYC verification (about 3 working days per their docs). Replace test keys with live keys everywhere, or customers see success with no money captured.
