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
