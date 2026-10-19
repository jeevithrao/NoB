# Definition of Done — v1

A feature/ticket is **Done** only when all of the following are true:

## Functionality
- [ ] Matches the relevant Feature Specification / PRD requirement exactly — deviations were discussed and approved, not silently decided by the developer.
- [ ] Works fully offline where required (walk playback, session progress) — tested with airplane mode on, not just "should work."
- [ ] Handles the documented edge cases (interrupted walk resume, device-binding conflict, payment failure/retry, out-of-order stop arrival).

## Data & security
- [ ] Server-side validation exists for every rule that matters (license consumption, device binding, role checks) — not just enforced client-side.
- [ ] No sensitive data (passwords, payment details) logged or stored in plaintext.

## Testing
- [ ] Manually tested on at least one real iOS and one real Android device (simulators don't reliably reflect GPS behavior).
- [ ] The specific "walk end-to-end" success criterion from the PRD passes: purchase → download → walk → complete, fully offline during the walk portion.

## Code & review
- [ ] Code reviewed by at least one other person before merge.
- [ ] No hardcoded secrets/API keys committed.

## Documentation
- [ ] Any new API endpoint is added to the API Specification doc.
- [ ] Any new business rule or edge-case decision made during implementation is written back into the Business Rules doc — this project's docs should stay a living reference, not go stale the moment coding starts.

## Ready for the next stage
- [ ] Deployed and verified on staging before being considered ready for production release.
