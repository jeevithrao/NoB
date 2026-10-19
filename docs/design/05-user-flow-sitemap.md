# User Flow / Sitemap — Neighbourhoods of Bangalore v1

## 1. Full Sitemap (all screens)

**Onboarding / Auth**
- Splash
- Sign Up
- Sign In
- OTP Verification
- Welcome / "Glad you're here!" (post sign-up success)

**Core**
- Home Feed
- Map (Places on the Map)
- Tour Detail
- Purchase / Checkout
- Download / Offline Prep
- Route-to-Start (navigation to tour start point)
- Active Walk (live GPS-triggered playback)
- Walk Complete (summary + like/comment prompt)
- Profile (view/edit)
- Profile Creation (first-time setup)
- Settings
  - About the App
  - Privacy & Preferences
  - Help
  - (Business Plans entry — hidden in v1, per PRD open question)

**Supporting / states**
- Empty state (no tours nearby, no saved tours)
- Loading/skeleton state (home feed)
- Error state (payment failed, GPS unavailable, download failed)

---

## 2. Primary User Flow (first-time user, happy path)

```
Splash
  └─(tap "Explore Bangalore")─▶ Map
       └─(tap "Discover More")─▶ Home Feed
            └─(tap a tour card)─▶ Tour Detail
                 └─(not signed in)─▶ Sign Up
                      └─▶ OTP Verification ─▶ Welcome ("Glad you're here!")
                           └─(tap "Start Exploring")─▶ Profile Creation
                                └─(tap "Register/Save")─▶ Home Feed
                                     └─(tap same tour again)─▶ Tour Detail
                                          └─(tap "Purchase")─▶ Purchase/Checkout
                                               └─(payment success)─▶ Download/Offline Prep
                                                    └─(download complete)─▶ Route-to-Start
                                                         └─(arrived at start)─▶ Active Walk
                                                              └─(final stop reached)─▶ Walk Complete
                                                                   └─(optional)─▶ like/comment
                                                                   └─▶ back to Home Feed
```

## 3. Returning user flow

```
Splash ─(already signed in, skip auth)─▶ Home Feed
```

## 4. Returning to an in-progress (interrupted) walk

```
Home Feed / Profile ─(tour shows "Continue")─▶ Route-to-Start or directly Active Walk
     (resumes tour_sessions row where completed = FALSE, stops_visited preserved)
```

## 5. Sign-in flow (existing user)

```
Splash ─(tap "Explore Bangalore")─▶ Map/Home ─(tap profile/account icon)─▶ Sign In
     └─(tap "Continue")─▶ Home Feed
     └─(tap "Forgot password?")─▶ Password Reset (out of scope detail — flag if needed)
     └─(tap "Don't have an account? Sign Up")─▶ Sign Up
```

## 6. Purchase flow detail (screen-level, not API-level — see Feature Spec for that)

```
Tour Detail ─(tap "Purchase")─▶ Purchase/Checkout
     ├─(payment success)─▶ Download/Offline Prep ─▶ Route-to-Start
     └─(payment failed)─▶ Error state ─(retry)─▶ Purchase/Checkout
                                     ─(cancel)─▶ Tour Detail
```

## 7. Edge case: already-completed tour

```
Home Feed / Tour Detail (tour marked "Completed", locked)
     └─(tap)─▶ Tour Detail shows locked state + past summary, no "Start Walk" option
     (per Business Rules: no replay without new purchase)
```

## 8. Edge case: second device login

```
User logs in on Device B while active on Device A
     └─▶ Device A's session invalidated (single active session enforced)
     └─▶ Device B can sign in normally, but must re-download any tours
          it wants offline (bound to Device A previously)
```

## 9. Navigation shell

- **Bottom tab bar (persistent on core screens):** Home · Map · Profile · Settings
- **Active Walk screen is full-screen, no tab bar** — user shouldn't navigate away mid-walk without an explicit exit confirmation ("Are you sure you want to end this walk early?").
- **Back arrow (top-left)** on all secondary screens (Tour Detail, About, Settings sub-pages).

---

## 10. Screens still needing a UI (not in the original Lovable mockups)

These are implied by the flow above but weren't in the initial screen set — flagging so design can produce them before dev starts:

- Purchase/Checkout screen
- Download/Offline Prep screen (progress indicator)
- Route-to-Start screen (map + directions to tour start)
- Active Walk screen (live playback UI, progress through stops, "End Walk" control)
- Walk Complete / summary screen
- Error states (payment failed, GPS unavailable/permission denied, download failed)
- "Continue" state on Home Feed / Profile for in-progress tours
- Locked/completed state on Tour Detail
