"""Platform owner (admin) configuration for multiplayer leagues."""

from __future__ import annotations

import os

from backend.data_paths import project_root


def _load_local_env_file() -> None:
    """Load project-root `.env` into os.environ (only keys not already set)."""
    path = os.path.join(project_root(), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


_load_local_env_file()


def platform_owner_emails() -> set[str]:
    raw = os.environ.get("FND_PLATFORM_OWNER_EMAILS", "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def platform_owner_emails_configured() -> bool:
    return bool(platform_owner_emails())


def is_platform_owner_email(email: str | None) -> bool:
    if not email:
        return False
    owners = platform_owner_emails()
    if not owners:
        return False
    return email.strip().lower() in owners
