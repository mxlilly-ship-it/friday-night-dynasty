"""Firebase Admin SDK — verify client ID tokens (Railway: FIREBASE_SERVICE_ACCOUNT_JSON)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

_initialized = False


def _parse_service_account_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if not text:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}") from e


def ensure_firebase_admin() -> None:
    global _initialized
    if _initialized:
        return
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_JSON is not set. Add your Firebase service account JSON on Railway."
        )
    cred = credentials.Certificate(_parse_service_account_json(raw))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _initialized = True


def verify_id_token(id_token: str) -> Dict[str, Any]:
    """Returns decoded Firebase token claims (uid, email, etc.)."""
    ensure_firebase_admin()
    token = str(id_token or "").strip()
    if not token:
        raise ValueError("id_token required")
    return firebase_auth.verify_id_token(token, check_revoked=False)


def email_from_claims(claims: Dict[str, Any]) -> str:
    email = claims.get("email")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return ""
