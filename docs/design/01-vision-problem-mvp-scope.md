# Neighbourhoods of Bangalore — Foundational Docs
*Vision · Problem Statement · Target Customer · MVP Scope · Out-of-Scope*

---

## 1. Vision Document

**Product name:** Neighbourhoods of Bangalore

**One-line pitch:** A mobile app that turns any walk in Bangalore into a guided, GPS-triggered audio story — no guide, no group, no fixed schedule, just you, your headphones, and the history under your feet.

**Vision statement:**
Every neighbourhood in Bangalore has stories most residents and visitors never hear — who built a lane, why a market exists where it does, what a temple's carvings mean. Neighbourhoods of Bangalore makes that hidden layer of the city audible and walkable, one purchased tour at a time, starting with Bangalore and designed to expand to any city with a story to tell.

**Why now:**
- Smartphone GPS accuracy and offline map/audio caching are now reliable enough to trigger narration precisely on a walking route without a live guide.
- Self-guided, on-demand audio tours (à la VoiceMap/Detour) have proven the format works; there's no strong player doing this specifically for Bangalore/Indian neighbourhoods.
- Rising interest in "slow travel" / local discovery among both residents and domestic tourists.

**Guiding principles:**
- Depth over breadth — a small number of richly produced tours beats many shallow ones.
- The walk is the product — audio timing and GPS trigger accuracy matter as much as the writing.
- Works without a data connection — because the whole point is walking around outdoors.

---

## 2. Problem Statement

**The problem:** People walking through Bangalore's neighbourhoods — whether lifelong residents, new movers, or visiting tourists — have no easy way to learn the detailed history, context, and significance of the specific streets and landmarks they're passing, in the moment they're passing them.

**Who has this problem:**
- Curious residents who've lived somewhere for years but never learned its backstory.
- New movers to a neighbourhood who want to feel oriented and connected, not just informed.
- Tourists/visitors who want more than a listicle — a real, walkable narrative.

**Why existing options fall short:**
- Guided walking tours require booking, a fixed group, and a fixed time.
- Blogs/Google results give text you'd have to read while distracted, not narration timed to your location.
- Generic audio guide apps (museum-style) aren't built for outdoor, multi-km neighbourhood walks with real GPS triggering.

**Cost of not solving it:** People stay disconnected from the place they live in or visit; local history and neighbourhood identity stays undiscovered and unmonetized for the people who could tell those stories.

---

## 3. Target Customer / ICP

**Primary persona: "The Curious Wanderer"**
- Lives in or is visiting Bangalore.
- Enjoys walking, is curious about local history/culture, likely already uses things like museum audio guides, walking tour apps, or long-form podcasts.
- Comfortable paying a small one-time fee (₹) for a well-produced experience — this is a "nice weekend/evening activity" purchase, not a utility.
- Owns a smartphone with GPS and is willing to walk 1–3 km with headphones in.

**Explicitly not (for now):** Large tour groups, corporate/institutional tour buyers, non-walking audiences (e.g. people wanting to view content without physically visiting).

---

## 4. MVP Scope (In)

1. **Browse tours** — list of available Bangalore neighbourhood tours, filterable/viewable on a stylised map showing nearby available walks.
2. **Tour detail page** — description, distance, duration, price, cover image.
3. **Purchase flow** — one-time, per-tour purchase (Razorpay/Stripe-style gateway), unlocks that tour permanently for the user.
4. **Offline download** — once purchased, user can download the tour's audio + route data for fully offline use during the walk.
5. **Route navigation** — shows the route from the user's current location to the tour's starting point.
6. **Live guided walk** — once the walk starts, GPS tracks the user's position; audio auto-plays when the user enters a stop's trigger radius, in order.
7. **Session tracking** — records stops visited and whether the tour was completed (for the user's own history, e.g. "continue where you left off").
8. **Basic account** — sign up/sign in (email or Google), simple profile.
9. **Saved/bookmarked tours** — wishlist of tours not yet purchased.
10. **Post-walk reaction** — user can leave a comment/like on a tour (lightweight, not a social feed).

## 5. Out-of-Scope (v1 — explicitly not building yet)

- Multi-city support (Bangalore only for now).
- Subscription/bundle pricing (strictly one-time per-tour purchase for v1).
- DMs or following between users — no social network layer.
- User-generated tours (all tours are produced/curated by the team, not uploaded by residents).
- Ads (explicitly deferred to post-MVP).
- Admin CMS beyond the minimum needed to publish a tour (full-featured tour-authoring tool is a later investment).
- Real-time multiplayer/group walks.
- Business/vendor listings ("Business Plans" feature — monetization model undecided, deferred entirely).
- Any payment methods beyond a single gateway integration.

---

*Next docs to draft: User Flow / Sitemap, Feature Specification (GPS-trigger + purchase + offline sync), Business Rules, updated Database ERD.*
