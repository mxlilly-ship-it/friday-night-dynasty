# Firebase keys and GitHub secret scanning

## Two different credentials

| Credential | Where it lives | Git? |
|------------|----------------|------|
| **Web API key** (`VITE_FIREBASE_API_KEY`) | Browser / Vite build | **Never** — use `frontend/.env` locally and Railway variables |
| **Service account JSON** (`FIREBASE_SERVICE_ACCOUNT_JSON`) | Railway only | **Never** — server env var only |

Firebase **web** API keys are not as sensitive as service account keys, but GitHub still flags them. Keep them out of the repo and **restrict** them in Google Cloud.

## If GitHub alerted on `AIzaSy...`

1. **Google Cloud Console** → [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials) (project `friday-night-dynasty`).
2. Open the leaked **API key** → **Application restrictions** → **HTTP referrers**:
   - `https://friday-night-dynasty-production.up.railway.app/*`
   - `http://localhost:*`
   - `http://127.0.0.1:*`
3. **API restrictions** → restrict to Firebase-related APIs (or “Firebase Authentication API” at minimum).
4. Optional but recommended: **Create credentials** → new API key → update Railway `VITE_FIREBASE_API_KEY` → **delete** the old key.
5. Close the GitHub secret alert as **revoked** / remediated.

The key may still exist in **git history** on public GitHub; rotation + restrictions limit abuse.

## Local dev

```bash
cp frontend/.env.example frontend/.env
# Fill VITE_FIREBASE_* from Firebase Console → Project settings → Your apps
```

## Railway (production)

Variables must be on the **same service** that runs the Dockerfile (your web app), not only at project level.

**Option A — six variables** (names must match exactly):

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_MEASUREMENT_ID` (optional)

**Option B — one JSON variable** (easier):

- `FIREBASE_WEB_CONFIG_JSON` = paste the whole web config object from Firebase Console as one line, e.g.  
  `{"apiKey":"AIza...","authDomain":"friday-night-dynasty.firebaseapp.com","projectId":"friday-night-dynasty",...}`

After saving variables, click **Redeploy**. Check:

- `https://<your-app>/health` → `firebase_env_set` should show `true` for each key you set
- `https://<your-app>/config/firebase.json` → should return JSON, not an error

Keep `FIREBASE_SERVICE_ACCOUNT_JSON` as a **separate** variable (server login only).
