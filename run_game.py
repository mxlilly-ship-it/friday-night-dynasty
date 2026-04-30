"""
Start the game + API in one process.

Always run from the project root (this script cd's there automatically).
Open: http://127.0.0.1:8001/
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def _maybe_build_frontend_dist() -> None:
    """
    If frontend/dist is missing or older than frontend/src, run `npm run build` once.

    Opt out: set FND_SKIP_SPA_AUTO_BUILD=1
    Requires npm on PATH (Windows: npm.cmd is fine).
    """
    if os.environ.get("FND_SKIP_SPA_AUTO_BUILD", "").strip().lower() in ("1", "true", "yes"):
        return
    from backend.spa_bundle import spa_dist_index, spa_frontend_build_needed, spa_frontend_dir

    index = spa_dist_index()
    if not spa_frontend_build_needed(index):
        return
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    frontend = spa_frontend_dir()
    if not npm:
        print("  NOTE: frontend needs a production build (npm run build in frontend/).")
        print("        npm was not found in PATH — UI may not match latest source.")
        print("        Or use: npm run dev → http://127.0.0.1:5173  (live reload)")
        return
    print("  Building frontend bundle (npm run build) so the browser matches src …")
    try:
        r = subprocess.run(
            [npm, "run", "build"],
            cwd=str(frontend),
            shell=False,
            check=False,
        )
    except OSError as e:
        print(f"  NOTE: could not run npm build ({e}). UI may be out of date.")
        return
    if r.returncode != 0:
        print(f"  NOTE: npm run build exited with code {r.returncode}. UI may be out of date.")
    elif not index.is_file():
        print("  NOTE: dist/index.html still missing after build.")


def main() -> None:
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    _maybe_build_frontend_dist()

    port = int(os.environ.get("FND_PORT", "8001"))
    # Default 127.0.0.1: on Windows, binding 0.0.0.0 while another process holds 127.0.0.1:port
    # can leave two listeners; browsers to http://127.0.0.1/ may hit the wrong one.
    host = os.environ.get("FND_HOST", "127.0.0.1")

    import uvicorn

    print()
    print("  Friday Night Dynasty — server starting")
    print("  ----------------------------------------")
    print(f"  Game (browser):  http://127.0.0.1:{port}/")
    print(f"  API docs:        http://127.0.0.1:{port}/docs")
    print(f"  Health check:    http://127.0.0.1:{port}/health")
    print()
    print("  If the page will not load: use http:// not https://")
    print("  Prefer 127.0.0.1 over localhost (avoids IPv6 quirks).")
    print("  If port is busy, close other terminals running uvicorn or set FND_PORT=8002")
    print("  LAN access:      set FND_HOST=0.0.0.0 before starting")
    print("  UI bundle:       stale dist auto-builds via npm if on PATH (set FND_SKIP_SPA_AUTO_BUILD=1 to skip)")
    print("  Press Ctrl+C to stop.")
    print()

    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
