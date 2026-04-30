import json
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.routers import auth, saves, games, sim
from backend.spa_bundle import spa_dist_bundle_is_stale, spa_dist_dir, spa_frontend_dir, spa_ui_debug_meta
from systems.playbook_system import (
    DEFENSIVE_PLAYBOOK_FORMATIONS,
    OFFENSIVE_PLAYBOOK_FORMATIONS,
)


class _SpaNoCacheMiddleware(BaseHTTPMiddleware):
    """Avoid sticky cached index.js after `npm run build` (same host as API)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if os.environ.get("FND_ALLOW_SPA_CACHE", "").strip().lower() in ("1", "true", "yes"):
            return response
        path = request.url.path
        if path == "/" or path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Friday Night Dynasty API")

    @app.exception_handler(OSError)
    async def _oserror_handler(_request: Request, exc: OSError) -> JSONResponse:
        """Surface errno / winerror in API JSON so Windows file issues are diagnosable from the browser."""
        logging.exception("Unhandled OSError in request")
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "errno": exc.errno,
                "winerror": getattr(exc, "winerror", None),
                "filename": getattr(exc, "filename", None),
            },
        )

    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://127.0.0.1:8001,http://localhost:8001",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(_SpaNoCacheMiddleware)

    def _teams_json_path() -> str:
        """Resolve data/teams.json - try multiple locations for robustness."""
        candidates = []
        try:
            from systems.teams_loader import _default_path
            candidates.append(_default_path())
        except Exception:
            pass
        # Fallback: relative to this file (backend/app.py -> project_root/data/teams.json)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.abspath(os.path.join(app_dir, "..", "data", "teams.json")))
        candidates.append(os.path.join(os.getcwd(), "data", "teams.json"))
        for p in candidates:
            if p and os.path.isfile(p):
                return p
        return candidates[0] if candidates else "data/teams.json"

    def _playbooks_json_path() -> str:
        """Resolve data/playbooks.json - try multiple locations for robustness."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(app_dir, "..", "data", "playbooks.json")),
            os.path.join(os.getcwd(), "data", "playbooks.json"),
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                return p
        return candidates[0] if candidates else "data/playbooks.json"

    @app.get("/teams-data")
    def get_teams_data():
        """Teams from data/teams.json for new-save UI."""
        try:
            path = _teams_json_path()
            if not os.path.isfile(path):
                return {"_schema": "File not found", "teams": [], "_debug": {"path": path, "cwd": os.getcwd()}}
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"_schema": str(e), "teams": [], "_debug": {"cwd": os.getcwd()}}

    @app.get("/playbooks-data")
    def get_playbooks_data():
        """Offensive/defensive playbook options for coach setup UI."""
        try:
            return {
                "offense_playbooks": {
                    name: {"formations": list(formations)} for name, formations in OFFENSIVE_PLAYBOOK_FORMATIONS.items()
                },
                "defense_playbooks": {
                    name: {"formations": list(formations)} for name, formations in DEFENSIVE_PLAYBOOK_FORMATIONS.items()
                },
            }
        except Exception as e:
            return {"_schema": str(e), "offense_playbooks": {}, "defense_playbooks": {}, "_debug": {"cwd": os.getcwd()}}

    @app.get("/health")
    def health():
        """Quick check that API is running."""
        return {"ok": True}

    @app.get("/_fnd/ui-meta")
    def fnd_ui_meta():
        """Why the SPA may be blocked as stale — open in browser while debugging."""
        dist = spa_dist_dir()
        index_html = dist / "index.html"
        if not index_html.is_file():
            return {"error": "no dist/index.html", "dist": str(dist)}
        return spa_ui_debug_meta(index_html)

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(saves.router, prefix="/saves", tags=["saves"])
    app.include_router(games.router, prefix="/games", tags=["games"])
    app.include_router(sim.router, prefix="/sim", tags=["sim"])

    dist = spa_dist_dir()
    index_html = dist / "index.html"

    if index_html.is_file():
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa_assets")

        @app.get("/favicon.svg")
        def spa_favicon():
            p = dist / "favicon.svg"
            if p.is_file():
                return FileResponse(p)
            raise HTTPException(status_code=404)

        @app.get("/icons.svg")
        def spa_icons():
            p = dist / "icons.svg"
            if p.is_file():
                return FileResponse(p)
            raise HTTPException(status_code=404)

        @app.get("/fnd-landing.png")
        def spa_landing_image():
            p = dist / "fnd-landing.png"
            if p.is_file():
                return FileResponse(p)
            raise HTTPException(status_code=404)

        @app.get("/")
        def spa_index():
            """Serve the built React app from frontend/dist (no separate Vite process needed)."""
            if spa_dist_bundle_is_stale(index_html):
                body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rebuild frontend — Friday Night Dynasty</title>
  <style>
    body {{ font-family: system-ui, Segoe UI, sans-serif; background: #1e1b16; color: #1c1917; margin: 0; padding: 0; line-height: 1.5; }}
    .banner {{ background: #facc15; color: #422006; padding: 1rem 1.25rem; font-weight: 800; font-size: 1.1rem; }}
    .wrap {{ padding: 1.5rem 1.25rem 2rem; color: #e8eaef; max-width: 52rem; }}
    code, pre {{ background: #1a1d24; padding: 0.2em 0.45em; border-radius: 6px; font-size: 0.95rem; color: #e8eaef; }}
    pre {{ padding: 1rem; overflow: auto; }}
    a {{ color: #93c5fd; }}
    h1 {{ font-size: 1.25rem; margin-top: 0; color: #f8fafc; }}
  </style>
</head>
<body>
  <div class="banner">Friday Night Dynasty — action required (this is not the game UI)</div>
  <div class="wrap">
  <h1>Frontend bundle is out of date</h1>
  <p>
    The app at this address serves <strong>frontend/dist</strong>. Your <strong>frontend/src</strong> files
    (for example <code>TeamHomePage.tsx</code>) are <strong>newer</strong> than that build, so the browser
    will keep showing an <strong>old UI</strong> until you rebuild.
  </p>
  <p><strong>Fix (pick one):</strong></p>
  <ol>
    <li>
      <strong>Production bundle on this server:</strong> in a terminal where Node/npm work, run:
      <pre>cd { spa_frontend_dir().as_posix() }
npm run build</pre>
      Then reload this page with a hard refresh (Ctrl+Shift+R). API routes like <a href="/docs">/docs</a> still work.
    </li>
    <li>
      <strong>Dev UI:</strong> run <code>npm run dev</code> in <code>frontend/</code> and open
      <a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a> — that uses live source, not <code>dist</code>.
    </li>
    <li>
      <strong>Force the old bundle anyway:</strong> set environment variable <code>FND_IGNORE_STALE_SPA=1</code>
      and restart the API (not recommended if you expect UI fixes).
    </li>
  </ol>
  <p style="opacity:0.92;color:#94a3b8;font-size:0.88rem;margin-bottom:0">
    Debug: open <a href="/_fnd/ui-meta">/_fnd/ui-meta</a> for mtimes and stale flag.
  </p>
  </div>
</body>
</html>"""
                return HTMLResponse(content=body, headers={"Cache-Control": "no-store"})
            return FileResponse(index_html, headers={"Cache-Control": "no-cache, must-revalidate"})
    else:
        @app.get("/")
        def root_no_spa():
            return RedirectResponse(url="/docs")

    return app


app = create_app()

