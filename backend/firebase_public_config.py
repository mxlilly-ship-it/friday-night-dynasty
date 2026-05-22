"""Public Firebase web config from server env (runtime — works when Vite build missed VITE_*)."""

from __future__ import annotations

import os
from typing import Any, Dict


def _env(*names: str) -> str:
    for name in names:
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return ""


def firebase_public_config() -> Dict[str, Any]:
    api_key = _env("VITE_FIREBASE_API_KEY", "FND_FIREBASE_API_KEY")
    auth_domain = _env("VITE_FIREBASE_AUTH_DOMAIN", "FND_FIREBASE_AUTH_DOMAIN")
    project_id = _env("VITE_FIREBASE_PROJECT_ID", "FND_FIREBASE_PROJECT_ID")
    storage_bucket = _env("VITE_FIREBASE_STORAGE_BUCKET", "FND_FIREBASE_STORAGE_BUCKET")
    messaging_sender_id = _env("VITE_FIREBASE_MESSAGING_SENDER_ID", "FND_FIREBASE_MESSAGING_SENDER_ID")
    app_id = _env("VITE_FIREBASE_APP_ID", "FND_FIREBASE_APP_ID")
    measurement_id = _env("VITE_FIREBASE_MEASUREMENT_ID", "FND_FIREBASE_MEASUREMENT_ID")

    missing = [
        label
        for label, val in (
            ("apiKey", api_key),
            ("authDomain", auth_domain),
            ("projectId", project_id),
            ("storageBucket", storage_bucket),
            ("messagingSenderId", messaging_sender_id),
            ("appId", app_id),
        )
        if not val
    ]
    if missing:
        raise ValueError(f"Missing Firebase env on server: {', '.join(missing)}")

    out: Dict[str, Any] = {
        "apiKey": api_key,
        "authDomain": auth_domain,
        "projectId": project_id,
        "storageBucket": storage_bucket,
        "messagingSenderId": messaging_sender_id,
        "appId": app_id,
    }
    if measurement_id:
        out["measurementId"] = measurement_id
    return out


def firebase_configured() -> bool:
    try:
        firebase_public_config()
        return True
    except ValueError:
        return False
