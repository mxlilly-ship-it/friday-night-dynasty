"""Multiplayer league start requests from players."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Dict, Optional

from backend.data_paths import league_start_requests_dir
from backend.storage.db import db

LEAGUE_TYPES = frozenset({"default", "custom", "help"})

_LEAGUE_TYPE_LABELS = {
    "default": "Built-in default teams (112 schools)",
    "custom": "Custom teams file (.json)",
    "help": "Not sure yet / need help choosing",
}


def _now() -> int:
    return int(time.time())


def _safe_filename(name: str) -> str:
    base = os.path.basename(str(name or "").strip())
    base = re.sub(r"[^\w.\- ]+", "_", base).strip("._ ")
    return base[:120] or "league.json"


def create_league_start_request(
    *,
    league_type: str,
    estimated_players: int,
    state: str,
    contact_email: str,
    user_id: Optional[str] = None,
    notes: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
) -> Dict[str, Any]:
    league_type = str(league_type or "").strip().lower()
    if league_type not in LEAGUE_TYPES:
        raise ValueError("Invalid league type")
    estimated_players = int(estimated_players)
    if estimated_players < 2 or estimated_players > 120:
        raise ValueError("Estimated players must be between 2 and 120")
    state = str(state or "").strip()
    if len(state) < 2:
        raise ValueError("State is required")
    contact_email = str(contact_email or "").strip().lower()
    if not contact_email or "@" not in contact_email:
        raise ValueError("A valid contact email is required")
    clean_notes = (notes or "").strip()[:2000] or None

    saved_name: Optional[str] = None
    saved_path: Optional[str] = None
    if league_type == "custom":
        if not file_bytes:
            raise ValueError("Upload your custom teams .json file")
        if len(file_bytes) > 8 * 1024 * 1024:
            raise ValueError("League file must be 8 MB or smaller")
        try:
            json.loads(file_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("League file must be valid UTF-8 JSON") from e
    elif file_bytes:
        if len(file_bytes) > 8 * 1024 * 1024:
            raise ValueError("League file must be 8 MB or smaller")
        try:
            json.loads(file_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("League file must be valid UTF-8 JSON") from e

    request_id = str(uuid.uuid4())
    now = _now()
    if file_bytes:
        safe_name = _safe_filename(file_name or "teams.json")
        if not safe_name.lower().endswith(".json"):
            safe_name = f"{safe_name}.json"
        dest_dir = league_start_requests_dir()
        os.makedirs(dest_dir, exist_ok=True)
        saved_path = os.path.join(dest_dir, f"{request_id}_{safe_name}")
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
        saved_name = safe_name

    with db() as conn:
        conn.execute(
            """
            INSERT INTO league_start_requests (
              id, user_id, contact_email, league_type, estimated_players, state,
              notes, file_name, file_path, created_at, notified
            ) VALUES (?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                request_id,
                user_id,
                contact_email,
                league_type,
                estimated_players,
                state,
                clean_notes,
                saved_name,
                saved_path,
                now,
            ),
        )

    return {
        "request_id": request_id,
        "created_at": now,
        "contact_email": contact_email,
        "league_type": league_type,
        "league_type_label": _LEAGUE_TYPE_LABELS.get(league_type, league_type),
        "estimated_players": estimated_players,
        "state": state,
        "notes": clean_notes,
        "file_name": saved_name,
        "file_path": saved_path,
        "user_id": user_id,
    }
