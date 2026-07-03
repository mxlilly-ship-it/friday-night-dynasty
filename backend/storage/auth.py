import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.storage.db import db

MAX_DEVICES_PER_USER = 3
# Stable namespace for dev coach-name accounts (same username → same user_id after redeploy).
_DEV_USER_NS = uuid.UUID("f7e3b2c4-9a1d-4f5e-8c6d-2b1a0e9f3d7c")


def stable_dev_user_id(username: str) -> str:
    """Deterministic user id from coach/username so saves/ folder survives DB resets when volume persists."""
    key = username.strip().lower()
    if not key:
        raise ValueError("username required")
    return str(uuid.uuid5(_DEV_USER_NS, key))


class DeviceLimitError(Exception):
    """User already has MAX_DEVICES_PER_USER registered devices."""

    def __init__(self, devices: List[Dict[str, Any]]):
        self.devices = devices
        super().__init__(f"Device limit reached ({MAX_DEVICES_PER_USER} devices)")


def dev_login(username: str) -> Tuple[str, str]:
    """
    Create (or fetch) a user and return (user_id, bearer_token).
    Dev-only auth.
    """
    username = username.strip()
    if not username:
        raise ValueError("username required")
    with db() as conn:
        user_id = stable_dev_user_id(username)
        row = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            legacy = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if legacy and legacy["id"] != user_id:
                old_id = legacy["id"]
                conn.execute("UPDATE saves SET user_id=? WHERE user_id=?", (user_id, old_id))
                conn.execute("UPDATE user_devices SET user_id=? WHERE user_id=?", (user_id, old_id))
                conn.execute("UPDATE tokens SET user_id=? WHERE user_id=?", (user_id, old_id))
                conn.execute("DELETE FROM users WHERE id=?", (old_id,))
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, email) VALUES (?,?,?)",
                (user_id, username, username if "@" in username else None),
            )
            if "@" in username:
                conn.execute(
                    "UPDATE users SET email=? WHERE id=? AND (email IS NULL OR email='')",
                    (username, user_id),
                )

        token = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO tokens (token, user_id, created_at) VALUES (?,?,?)",
            (token, user_id, int(time.time())),
        )
        return user_id, token


def _issue_token(conn, user_id: str) -> str:
    token = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO tokens (token, user_id, created_at) VALUES (?,?,?)",
        (token, user_id, int(time.time())),
    )
    return token


def _upsert_firebase_user(conn, firebase_uid: str, email: str) -> Tuple[str, str]:
    """Return (user_id, display_username)."""
    row = conn.execute(
        "SELECT id, username FROM users WHERE firebase_uid=?",
        (firebase_uid,),
    ).fetchone()
    display = email or firebase_uid
    if row:
        user_id = row["id"]
        if user_id != firebase_uid:
            old_id = user_id
            conn.execute("UPDATE saves SET user_id=? WHERE user_id=?", (firebase_uid, old_id))
            conn.execute("UPDATE user_devices SET user_id=? WHERE user_id=?", (firebase_uid, old_id))
            conn.execute("UPDATE tokens SET user_id=? WHERE user_id=?", (firebase_uid, old_id))
            conn.execute("DELETE FROM users WHERE id=?", (old_id,))
            user_id = firebase_uid
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, firebase_uid, email) VALUES (?,?,?,?)",
                (user_id, display, firebase_uid, email or None),
            )
        elif email:
            conn.execute("UPDATE users SET email=?, username=? WHERE id=?", (email, display, user_id))
        return user_id, display

    # Use Firebase uid as primary key so save paths stay stable across DB resets.
    user_id = firebase_uid
    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, firebase_uid, email) VALUES (?,?,?,?)",
        (user_id, display, firebase_uid, email or None),
    )
    return user_id, display


def _list_devices(conn, user_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT device_id, label, created_at, last_seen_at
        FROM user_devices
        WHERE user_id=?
        ORDER BY last_seen_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        {
            "device_id": r["device_id"],
            "label": r["label"],
            "created_at": int(r["created_at"]),
            "last_seen_at": int(r["last_seen_at"]),
        }
        for r in rows
    ]


def register_device(conn, user_id: str, device_id: str, label: Optional[str] = None) -> None:
    """Register or refresh a device. Raises DeviceLimitError if over cap."""
    device_id = str(device_id or "").strip()
    if not device_id:
        raise ValueError("device_id required")
    now = int(time.time())
    existing = conn.execute(
        "SELECT 1 FROM user_devices WHERE user_id=? AND device_id=?",
        (user_id, device_id),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE user_devices SET last_seen_at=?, label=COALESCE(?, label) WHERE user_id=? AND device_id=?",
            (now, label, user_id, device_id),
        )
        return

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM user_devices WHERE user_id=?",
        (user_id,),
    ).fetchone()["c"]
    if int(count) >= MAX_DEVICES_PER_USER:
        raise DeviceLimitError(_list_devices(conn, user_id))

    conn.execute(
        """
        INSERT INTO user_devices (user_id, device_id, label, created_at, last_seen_at)
        VALUES (?,?,?,?,?)
        """,
        (user_id, device_id, label, now, now),
    )


def remove_device_for_firebase_uid(firebase_uid: str, device_id: str) -> bool:
    """Remove a device row for a Firebase account (no app session required)."""
    firebase_uid = str(firebase_uid or "").strip()
    device_id = str(device_id or "").strip()
    if not firebase_uid or not device_id:
        raise ValueError("firebase uid and device_id required")
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE firebase_uid=?", (firebase_uid,)).fetchone()
        if not row:
            return False
        cur = conn.execute(
            "DELETE FROM user_devices WHERE user_id=? AND device_id=?",
            (row["id"], device_id),
        )
        return cur.rowcount > 0


def remove_device(user_id: str, device_id: str) -> bool:
    device_id = str(device_id or "").strip()
    if not device_id:
        raise ValueError("device_id required")
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM user_devices WHERE user_id=? AND device_id=?",
            (user_id, device_id),
        )
        return cur.rowcount > 0


def list_user_devices(user_id: str) -> List[Dict[str, Any]]:
    with db() as conn:
        return _list_devices(conn, user_id)


def firebase_login(
    firebase_uid: str,
    email: str,
    device_id: str,
    device_label: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Verify Firebase user, enforce device cap, issue app bearer token.
    Returns (user_id, token, username_for_display).
    """
    firebase_uid = str(firebase_uid or "").strip()
    if not firebase_uid:
        raise ValueError("firebase uid required")
    with db() as conn:
        user_id, username = _upsert_firebase_user(conn, firebase_uid, email)
        register_device(conn, user_id, device_id, device_label)
        token = _issue_token(conn, user_id)
        return user_id, token, username


def user_from_token(token: str) -> Optional[Tuple[str, str]]:
    with db() as conn:
        row = conn.execute(
            "SELECT users.id as user_id, users.username as username FROM tokens JOIN users ON tokens.user_id=users.id WHERE tokens.token=?",
            (token,),
        ).fetchone()
        if not row:
            return None
        return row["user_id"], row["username"]
