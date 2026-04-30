import time
import uuid
from typing import Optional, Tuple

from backend.storage.db import db


def dev_login(username: str) -> Tuple[str, str]:
    """
    Create (or fetch) a user and return (user_id, bearer_token).
    Dev-only auth.
    """
    username = username.strip()
    if not username:
        raise ValueError("username required")
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if row:
            user_id = row["id"]
        else:
            user_id = str(uuid.uuid4())
            conn.execute("INSERT INTO users (id, username) VALUES (?,?)", (user_id, username))

        token = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO tokens (token, user_id, created_at) VALUES (?,?,?)",
            (token, user_id, int(time.time())),
        )
        return user_id, token


def user_from_token(token: str) -> Optional[Tuple[str, str]]:
    with db() as conn:
        row = conn.execute(
            "SELECT users.id as user_id, users.username as username FROM tokens JOIN users ON tokens.user_id=users.id WHERE tokens.token=?",
            (token,),
        ).fetchone()
        if not row:
            return None
        return row["user_id"], row["username"]

