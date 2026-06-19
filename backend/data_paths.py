"""
Persistent data directory for Railway / production.

Set FND_DATA_DIR to a mounted volume path (e.g. /data) so deploys do not wipe:
  - dynasty.sqlite3 (login tokens, save index)
  - saves/ (dynasty files)

Without a volume, every redeploy starts with an empty DB → browsers keep an old
token → "session expired" until users sign in again (and may not see saves if files were lost too).
"""

from __future__ import annotations

import os

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
