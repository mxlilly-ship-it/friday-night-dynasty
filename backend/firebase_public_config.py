"""Public Firebase web config from server env (runtime — works when Vite build missed VITE_*)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# Env names to set on Railway (service that runs the Docker app).
REQUIRED_ENV_KEYS = (
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
    raw = _env("FIREBASE_WEB_CONFIG_JSON", "VITE_FIREBASE_WEB_CONFIG_JSON")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"FIREBASE_WEB_CONFIG_JSON is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("FIREBASE_WEB_CONFIG_JSON must be a JSON object")
    return data


def firebase_env_status() -> Dict[str, bool]:
    """Which Firebase-related env keys are set (names only — for /health debugging)."""
    keys = list(REQUIRED_ENV_KEYS) + [
        "VITE_FIREBASE_MEASUREMENT_ID",
        "FIREBASE_WEB_CONFIG_JSON",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
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
        api_key = _env("VITE_FIREBASE_API_KEY", "FND_FIREBASE_API_KEY", "FIREBASE_API_KEY")
        auth_domain = _env(
            "VITE_FIREBASE_AUTH_DOMAIN",
            "FND_FIREBASE_AUTH_DOMAIN",
            "FIREBASE_AUTH_DOMAIN",
        )
        project_id = _env("VITE_FIREBASE_PROJECT_ID", "FND_FIREBASE_PROJECT_ID", "FIREBASE_PROJECT_ID")
        storage_bucket = _env(
            "VITE_FIREBASE_STORAGE_BUCKET",
            "FND_FIREBASE_STORAGE_BUCKET",
            "FIREBASE_STORAGE_BUCKET",
        )
        messaging_sender_id = _env(
            "VITE_FIREBASE_MESSAGING_SENDER_ID",
            "FND_FIREBASE_MESSAGING_SENDER_ID",
            "FIREBASE_MESSAGING_SENDER_ID",
        )
        app_id = _env("VITE_FIREBASE_APP_ID", "FND_FIREBASE_APP_ID", "FIREBASE_APP_ID")
        measurement_id = _env(
            "VITE_FIREBASE_MEASUREMENT_ID",
            "FND_FIREBASE_MEASUREMENT_ID",
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
        unset = [k for k in REQUIRED_ENV_KEYS if not os.environ.get(k, "").strip()]
        hint = (
            "Set these on the **same Railway service** that deploys this app (Variables tab), "
            "then redeploy: "
            + ", ".join(REQUIRED_ENV_KEYS)
            + ". Or set one variable FIREBASE_WEB_CONFIG_JSON with your Firebase web config JSON."
        )
        if unset:
            hint += f" Currently unset: {', '.join(unset)}."
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
