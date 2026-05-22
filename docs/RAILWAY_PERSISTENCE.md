# Railway: keep saves and logins across deploys

Every Railway redeploy replaces the container filesystem. Without persistent storage:

- `dynasty.sqlite3` is wiped → old browser tokens return **401** (“session expired”)
- `saves/` is wiped → dynasties disappear even after signing in again

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

- `/data/dynasty.sqlite3` — users, tokens, save index
- `/data/saves/<user_id>/<save_name>/` — dynasty files

## Verify

Open `https://<your-app>.up.railway.app/health` and check:

- `"persistent_data": true`
- `"sqlite_db_exists": true` after you have played at least once
- `"saves_dir_exists": true`

## After deploy (users)

- **Firebase login**: If still signed in to Firebase in the browser, the app should refresh the session automatically.
- **Otherwise**: Sign in again with email/password. Saves reappear if the volume still has your `saves/` folder.

## Coach-name / legacy accounts

If saves lived under a random user folder before stable IDs, sign in with the **same coach name** as in the save; the server can re-link dynasties from disk when `user_coach_name` in `league_save.json` matches.
