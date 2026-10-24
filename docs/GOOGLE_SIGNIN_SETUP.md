# Turning on "Continue with Google"

The button is wired (frontend `GoogleBtn`, backend `POST /auth/google`). It stays a stub until you create a Google OAuth client and give its ID to both sides. The client ID is public (it is visible in the page); there is **no client secret** to store for this flow.

## 1. Create the client ID (about 10 minutes, needs a Google account)
1. Open https://console.cloud.google.com and create a project (e.g. "NoB").
2. APIs & Services → **OAuth consent screen** → User type **External** → fill app name, support email, developer email. Leave scopes at the defaults (email, profile, openid).
3. Keep the publishing status on **Testing** while developing and add your own Google accounts under **Test users** (only they can sign in; limit 100). Publish later, before launch.
4. APIs & Services → **Credentials** → Create credentials → **OAuth client ID** → type **Web application**.
5. **Authorized JavaScript origins** (no paths, no trailing slash, no redirect URIs needed):
   - `http://localhost:5173` (laptop, and an Android phone using `adb reverse`)
   - your real `https://` site address later
   Google rejects raw IP addresses, so use `localhost`.
6. Copy the **Client ID** (ends in `.apps.googleusercontent.com`).

## 2. Give it to the app
- `backend/.env`: `GOOGLE_CLIENT_ID=<the client id>` (the backend checks every Google token was issued for this ID)
- `frontend/.env`: `VITE_GOOGLE_CLIENT_ID=<the same client id>`

Restart both. The "Continue with Google" button should now be Google's own button.

## 3. Behaviour to know
- A Google sign-in creates the account on first use, or signs in the existing account with the same verified email (Google must report the email as verified).
- **Known gap:** accounts created through Google do not record Terms/Privacy acceptance (`terms_accepted_at` stays empty), unlike email sign-up. Decide with the founder/lawyer how to capture it before launch.
- The backend needs the `google-auth` package (now in `requirements.txt`; run `pip install -r requirements.txt` again).
- One active login per account still applies: signing in on a second device ends the first.
- It needs a network connection and the page origin must be exactly one of the authorized origins, otherwise the button shows an error or does not appear.
