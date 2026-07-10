"""
Persistent data directory for Railway / production.

Set FND_DATA_DIR to a mounted volume path (e.g. /data) so deploys do not wipe:
  - dynasty.sqlite3 (users, tokens, multiplayer league registry)
  - saves/ (single-player dynasty files)
  - leagues/ (multiplayer league_save.json folders)

Without a volume, every redeploy replaces the container filesystem with a fresh
copy from git — dynasties and multiplayer leagues disappear.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def project_root() -> str:
    return _PROJECT_ROOT


def data_root() -> str:
    """Root for all durable app data (DB + saves)."""
    raw = os.environ.get("FND_DATA_DIR", "").strip()
    if raw:
        return os.path.abspath(os.path.normpath(raw))
    return _PROJECT_ROOT


def sqlite_db_path() -> str:
    custom = os.environ.get("FND_DATA_DIR", "").strip()
    if custom:
        return os.path.join(data_root(), "dynasty.sqlite3")
    return os.path.join(_PROJECT_ROOT, "backend", "dynasty.sqlite3")


def saves_base_dir() -> str:
    return os.path.join(data_root(), "saves")


def leagues_base_dir() -> str:
    """Shared multiplayer league save folders."""
    return os.path.join(data_root(), "leagues")


def league_start_requests_dir() -> str:
    """Uploaded league files attached to start-league requests."""
    return os.path.join(data_root(), "league_start_requests")


def default_logos_dir() -> str:
    """Built-in crest images shipped with the league (data/logos/)."""
    return os.path.join(_PROJECT_ROOT, "data", "logos")


def default_logo_import_source() -> str | None:
    """
    Master folder for built-in crests (user's Game Logos folder).
    Override with data/game_logos_source.txt (one line, absolute path).
    """
    cfg = os.path.join(_PROJECT_ROOT, "data", "game_logos_source.txt")
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8") as f:
                line = f.read().strip()
            if line and os.path.isdir(line):
                return os.path.abspath(os.path.normpath(line))
        except OSError:
            pass
    desktop = os.path.join(os.path.expanduser("~"), "Desktop", "Game Logos (200 x 200 px)")
    if os.path.isdir(desktop):
        return os.path.abspath(desktop)
    return None


def persistence_configured() -> bool:
    return bool(os.environ.get("FND_DATA_DIR", "").strip())


def is_railway_runtime() -> bool:
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or os.environ.get("RAILWAY_SERVICE_ID")
    )


def warn_if_ephemeral_production_data() -> None:
    """Log loudly when a hosted deploy is not using a persistent volume."""
    if persistence_configured():
        return
    if not is_railway_runtime():
        return
    logger.warning(
        "FND_DATA_DIR is not set on Railway. Every git push / redeploy wipes "
        "dynasty.sqlite3, saves/, and leagues/. Mount a volume at /data and set "
        "FND_DATA_DIR=/data (see docs/RAILWAY_PERSISTENCE.md)."
    )


def persistence_health() -> dict:
    """Summary for /health — helps verify deploys keep data across pushes."""
    leagues_dir = leagues_base_dir()
    out = {
        "persistent_data": persistence_configured(),
        "data_root": data_root(),
        "sqlite_db": sqlite_db_path(),
        "sqlite_db_exists": os.path.isfile(sqlite_db_path()),
        "saves_dir": saves_base_dir(),
        "saves_dir_exists": os.path.isdir(saves_base_dir()),
        "leagues_dir": leagues_dir,
        "leagues_dir_exists": os.path.isdir(leagues_dir),
        "railway_runtime": is_railway_runtime(),
    }
    if not out["persistent_data"] and out["railway_runtime"]:
        out["warning"] = (
            "Data is ephemeral — mount a Railway volume at /data and set FND_DATA_DIR=/data "
            "or every deploy will reset multiplayer leagues and saves."
        )
    try:
        if out["sqlite_db_exists"]:
            from backend.storage.db import db

            with db() as conn:
                active = conn.execute(
                    "SELECT COUNT(*) FROM leagues WHERE status='active'"
                ).fetchone()[0]
                archived = conn.execute(
                    "SELECT COUNT(*) FROM leagues WHERE status='deleted'"
                ).fetchone()[0]
            out["active_leagues"] = int(active or 0)
            out["archived_leagues"] = int(archived or 0)
    except Exception:
        pass
    return out
