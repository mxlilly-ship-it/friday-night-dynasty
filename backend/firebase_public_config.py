"""Public Firebase web config from server env (runtime — works when Vite build missed VITE_*)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

# Prefer FND_* on Railway (VITE_* may be build-only or easy to mis-format in RAW editor).
RUNTIME_ENV_KEYS = (
    "FND_FIREBASE_API_KEY",
    "FND_FIREBASE_AUTH_DOMAIN",
    "FND_FIREBASE_PROJECT_ID",
    "FND_FIREBASE_STORAGE_BUCKET",
    "FND_FIREBASE_MESSAGING_SENDER_ID",
    "FND_FIREBASE_APP_ID",
)

LEGACY_VITE_KEYS = (
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_STORAGE_BUCKET",
    "VITE_FIREBASE_MESSAGING_SENDER_ID",
    "VITE_FIREBASE_APP_ID",
)


def _env(*names: str) -> str:
    for name in names:
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return ""


def _config_from_json_blob() -> Dict[str, Any] | None:
    """Optional single variable: FIREBASE_WEB_CONFIG_JSON='{"apiKey":"...", ...}'"""
    raw = _env("FIREBASE_WEB_CONFIG_JSON", "FND_FIREBASE_WEB_CONFIG_JSON", "VITE_FIREBASE_WEB_CONFIG_JSON")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"FIREBASE_WEB_CONFIG_JSON is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("FIREBASE_WEB_CONFIG_JSON must be a JSON object")
    return data


def firebase_env_keys_in_process() -> List[str]:
    """Env var names in this container that look Firebase-related (for /health debugging)."""
    pat = re.compile(r"^(FIREBASE_|FND_FIREBASE_|VITE_FIREBASE_)", re.I)
    return sorted(k for k in os.environ if pat.match(k))


def firebase_env_status() -> Dict[str, bool]:
    """Which Firebase-related env keys are set (names only — for /health debugging)."""
    keys = [
        "FIREBASE_WEB_CONFIG_JSON",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        *RUNTIME_ENV_KEYS,
        *LEGACY_VITE_KEYS,
        "FND_FIREBASE_MEASUREMENT_ID",
        "VITE_FIREBASE_MEASUREMENT_ID",
    ]
    return {k: bool(os.environ.get(k, "").strip()) for k in keys}


def firebase_public_config() -> Dict[str, Any]:
    blob = _config_from_json_blob()
    if blob:
        api_key = str(blob.get("apiKey") or "").strip()
        auth_domain = str(blob.get("authDomain") or "").strip()
        project_id = str(blob.get("projectId") or "").strip()
        storage_bucket = str(blob.get("storageBucket") or "").strip()
        messaging_sender_id = str(blob.get("messagingSenderId") or "").strip()
        app_id = str(blob.get("appId") or "").strip()
        measurement_id = str(blob.get("measurementId") or "").strip()
    else:
        api_key = _env(
            "FND_FIREBASE_API_KEY",
            "VITE_FIREBASE_API_KEY",
            "FIREBASE_API_KEY",
        )
        auth_domain = _env(
            "FND_FIREBASE_AUTH_DOMAIN",
            "VITE_FIREBASE_AUTH_DOMAIN",
            "FIREBASE_AUTH_DOMAIN",
        )
        project_id = _env(
            "FND_FIREBASE_PROJECT_ID",
            "VITE_FIREBASE_PROJECT_ID",
            "FIREBASE_PROJECT_ID",
        )
        storage_bucket = _env(
            "FND_FIREBASE_STORAGE_BUCKET",
            "VITE_FIREBASE_STORAGE_BUCKET",
            "FIREBASE_STORAGE_BUCKET",
        )
        messaging_sender_id = _env(
            "FND_FIREBASE_MESSAGING_SENDER_ID",
            "VITE_FIREBASE_MESSAGING_SENDER_ID",
            "FIREBASE_MESSAGING_SENDER_ID",
        )
        app_id = _env(
            "FND_FIREBASE_APP_ID",
            "VITE_FIREBASE_APP_ID",
            "FIREBASE_APP_ID",
        )
        measurement_id = _env(
            "FND_FIREBASE_MEASUREMENT_ID",
            "VITE_FIREBASE_MEASUREMENT_ID",
            "FIREBASE_MEASUREMENT_ID",
        )

    missing: List[str] = []
    for label, val in (
        ("apiKey", api_key),
        ("authDomain", auth_domain),
        ("projectId", project_id),
        ("storageBucket", storage_bucket),
        ("messagingSenderId", messaging_sender_id),
        ("appId", app_id),
    ):
        if not val:
            missing.append(label)

    if missing:
        found = firebase_env_keys_in_process()
        hint = (
            "Easiest fix on Railway: add one variable FIREBASE_WEB_CONFIG_JSON with your Firebase "
            "web config as a single line of JSON, then redeploy. "
            "Or use FND_FIREBASE_API_KEY, FND_FIREBASE_AUTH_DOMAIN, etc. (one line each, no line breaks). "
            "If FIREBASE_SERVICE_ACCOUNT_JSON is set but nothing else appears in firebase_env_keys_in_process, "
            "your VITE_* entries may be mis-formatted in the Variables RAW editor."
        )
        if found:
            hint += f" Keys seen in container: {', '.join(found)}."
        else:
            hint += " No FIREBASE_/FND_FIREBASE_/VITE_FIREBASE_ keys seen in this container."
        raise ValueError(f"Missing Firebase env on server: {', '.join(missing)}. {hint}")

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
