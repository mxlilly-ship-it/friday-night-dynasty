# Railway: keep saves and multiplayer leagues across deploys

Every Railway **git push / redeploy** replaces the container filesystem. Without persistent storage:

- `dynasty.sqlite3` is wiped or reset → multiplayer leagues vanish from the list
- `leagues/` is wiped → league save files are lost even if the DB row still existed
- `saves/` is wiped → single-player dynasties disappear

This is **not** caused by archiving logic — the server is starting with a fresh (or git-baked) database.

## Fix (required for production)

1. In Railway → your service → **Volumes** → **Add Volume**
   - Mount path: `/data`
   - Size: start with 1–5 GB

2. In **Variables**, add:

   ```
   FND_DATA_DIR=/data
   ```

3. Redeploy once.

The API stores:

- `/data/dynasty.sqlite3` — users, tokens, **multiplayer league registry** (active + archived)
- `/data/saves/<user_id>/<save_name>/` — single-player dynasty files
- `/data/leagues/<league_id>/` — multiplayer `league_save.json` and history

## Verify after deploy

Open `https://<your-app>.up.railway.app/health` and check:

| Field | Expected |
|-------|----------|
| `"persistent_data": true` | Volume + env var configured |
| `"data_root": "/data"` | Not `/app` |
| `"sqlite_db": "/data/dynasty.sqlite3"` | Not `.../backend/dynasty.sqlite3` |
| `"leagues_dir_exists": true` | After creating a test league |
| `"active_leagues"` | Increases when you create leagues |
| `"warning"` | **Should be absent** |

If `"persistent_data": false` or you see a `"warning"` field, **every push will wipe test leagues**.

## After deploy (users)

- **Firebase login**: If still signed in to Firebase in the browser, the app should refresh the session automatically.
- **Otherwise**: Sign in again with email/password.

## Coach-name / legacy accounts

If saves lived under a random user folder before stable IDs, sign in with the **same coach name** as in the save; the server can re-link dynasties from disk when `user_coach_name` in `league_save.json` matches.

## Do not commit local database files

`backend/dynasty.sqlite3` must **not** be in git. If it is tracked, each Docker build bakes an old DB into the image and production can look like leagues were “deleted” or reset on deploy.
