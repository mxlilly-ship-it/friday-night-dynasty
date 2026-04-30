# Run Friday Night Dynasty locally

You need **two terminals** open — API first, then the web UI.

## 1) API (FastAPI) — port **8000**

In **PowerShell**, from this folder (`Friday Night Dynasty`):

```powershell
cd "C:\Users\mxlil\Desktop\Friday Night Dynasty"
pip install -r backend\requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Leave this window open. You should see: `Uvicorn running on http://127.0.0.1:8000`

**Check:** open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — if it loads, the API is up.

## 2) Frontend (Vite) — port **5173**

Open a **second** PowerShell window:

```powershell
cd "C:\Users\mxlil\Desktop\Friday Night Dynasty\frontend"
npm install
npm run dev
```

**Check:** open [http://localhost:5173](http://localhost:5173) (or the URL Vite prints).

While developing, the UI calls **`/api/...`** on the same host as Vite; Vite **proxies** those requests to `http://127.0.0.1:8000`. You still must have the API running (step 1).

## If something still won’t connect

| Problem | What to try |
|--------|-------------|
| Browser says “can’t reach” for **5173** | Frontend isn’t running — run `npm run dev` in `frontend`. |
| Game loads but login/saves fail | API isn’t running — start uvicorn on **8000**. |
| `python` / `pip` not found | Install [Python 3](https://www.python.org/downloads/) and check “Add to PATH”. |
| Port already in use | Close the other app using 8000 or 5173, or change port (see Vite/API docs). |
| Wrong address | Use **http** not **https** for local dev. |

- **Dev (`npm run dev`):** requests go to `/api` → proxied to the API on port 8000.
- **Production build:** set `VITE_API_BASE` when building, or it defaults to `http://127.0.0.1:8000` (see `frontend/src/App.tsx`).
