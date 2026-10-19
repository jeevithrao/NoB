# Non-Functional Requirements (NFR) — v1

## Location / GPS
- GPS polling interval during an active walk: 3–5 seconds (foreground only for v1 — no background triggering required, simplifies permissions).
- Minimum trigger radius floor: 20m, regardless of what a content admin sets on a stop, to reduce false triggers from GPS drift in dense urban areas.
- Location permission requested with a clear rationale screen before the OS prompt — required for app store review, not just good UX.

## Offline capability
- A downloaded tour (audio + stop/route data) must function with zero network connectivity from "Start Walk" to "Walk Complete."
- Session progress events queue locally and sync opportunistically — no user-facing failure if sync is delayed.
- Target offline storage per tour: reasonable audio compression (e.g. 64–96kbps mono voice) to keep a typical 2km/10-stop tour under ~50MB — exact target to confirm once real audio files exist.

## Performance
- Home Feed initial load: under 2 seconds on 4G.
- Audio trigger latency (crossing into radius → playback start): under 1 second, since this is the core "magic" of the product.
- App cold start to Splash-interactive: under 3 seconds.

## Reliability
- Payment webhook processing must be idempotent (a retried webhook must not double-credit a purchase).
- Session sync must be idempotent (see API spec — dedupe by `client_event_id`).

## Battery
- Continuous GPS polling during a walk is inherently battery-intensive — budget for this in the UI (e.g. a visible "walk in progress" indicator, no misleading "background-only" claims) rather than trying to hide the cost.

## Device support
- Target: iOS 15+ and Android 10+ (adjust based on actual dev/testing capacity — this is a starting assumption, not a hard constraint from product).

## Concurrency (early-stage target, not enterprise-scale)
- Design for hundreds of concurrent active walks at launch, not thousands — right-size backend infra accordingly rather than over-engineering for scale that doesn't exist yet.

## Data integrity
- Money stored as integer paise (already in schema) — never floating point.
- A purchase's `bound_device_id` and a tour session's `completed` flag are the two fields enforcing the entire licensing model — these need the highest test coverage of anything in the app.
