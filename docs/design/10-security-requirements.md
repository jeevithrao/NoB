# Security Requirements — v1

## Authentication & session management
- Passwords stored with bcrypt (already reflected in schema comment) — minimum 12 rounds.
- JWT access tokens short-lived (e.g. 1 hour) with refresh handled via the `auth_sessions` table, not long-lived client-stored secrets.
- Single active session enforcement (per Business Rules doc): a new login invalidates the prior `auth_sessions` row server-side — this must be checked on every authenticated request, not just at login time, so a kicked-out session actually stops working immediately.
- OTP codes: short expiry (e.g. 5–10 minutes), rate-limited attempts (e.g. max 5 tries) to prevent brute-forcing.

## Device binding
- `device_identifier` is client-generated and persisted locally, not derived from a hardware serial (privacy/App Store compliance) — treat it as a trust-on-first-use token, not a cryptographic guarantee. This is a deterrent against casual sharing, not a defense against a determined attacker rooting/jailbreaking a device — acceptable tradeoff for this product's threat level.

## Payment data
- No card/payment details ever touch our own servers or database — handled entirely by the gateway's SDK/hosted checkout. We only store `gateway_order_id`, `gateway_payment_id`, and amount.
- Webhook endpoint must verify the gateway's signature on every request — never trust an unsigned payment confirmation.

## Audio/content protection
- Signed URLs for audio files (time-limited) rather than permanent public links — prevents casual hotlinking/scraping of paid content, though full DRM is out of scope for v1.
- Downloaded audio stored in app-private local storage, not a public device folder.

## Transport & storage
- All API traffic over HTTPS/TLS — no exceptions.
- Standard encryption at rest for the database (managed Postgres provider default, or explicit disk encryption if self-hosted).

## Admin access
- Admin endpoints require `role = 'admin'`, checked server-side on every request.
- Recommend 2FA for admin accounts specifically, given they can issue refunds and reset licenses — this is a cheap safeguard against a single compromised admin credential.

## Input validation
- All user-submitted text (comments, profile "About Me") sanitized against injection/XSS before storage and before rendering in the app.

## What's explicitly out of scope for v1
- Full DRM/anti-piracy for audio files (signed URLs + device binding is the agreed-upon tradeoff, not bulletproof protection).
- Penetration testing / formal security audit — worth budgeting for before a wider public launch, not required to start building.
