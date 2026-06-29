import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional

from backend.data_paths import saves_base_dir, sqlite_db_path
from systems.win_path_io import extended_abs_path, makedirs_with_path_fallback, windows_file_arg_error


def _db_path() -> str:
    return sqlite_db_path()


def _sqlite_db_candidates() -> List[str]:
    raw = os.path.abspath(_db_path())
    ext = extended_abs_path(raw)
    return [raw, ext] if ext != raw else [raw]


def _connect_sqlite() -> sqlite3.Connection:
    last: Optional[OSError] = None
    paths = _sqlite_db_candidates()
    for i, p in enumerate(paths):
        try:
            return sqlite3.connect(p, timeout=60)
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(paths) - 1:
                continue
            raise
    assert last is not None
    raise last


def init_db() -> None:
    db_dir = os.path.dirname(_db_path())
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(db_dir)))
    except OSError:
        os.makedirs(db_dir, exist_ok=True)
    saves_dir = saves_base_dir()
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(saves_dir)))
    except OSError:
        os.makedirs(saves_dir, exist_ok=True)
    with _connect_sqlite() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              username TEXT UNIQUE NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
              token TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saves (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              save_name TEXT NOT NULL,
              save_dir TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              UNIQUE(user_id, save_name),
              FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
              id TEXT PRIMARY KEY,
              save_id TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              state_json TEXT NOT NULL,
              FOREIGN KEY(save_id) REFERENCES saves(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_devices (
              user_id TEXT NOT NULL,
              device_id TEXT NOT NULL,
              label TEXT,
              created_at INTEGER NOT NULL,
              last_seen_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, device_id),
              FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _migrate_users_firebase(conn)
        _migrate_users_billing(conn)


def _migrate_users_billing(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "entitlement_active" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN entitlement_active INTEGER NOT NULL DEFAULT 0")
    if "purchased_at" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN purchased_at INTEGER")
    if "stripe_customer_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
          id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          stripe_checkout_session_id TEXT UNIQUE,
          stripe_payment_intent_id TEXT,
          amount_cents INTEGER,
          currency TEXT,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id)"
    )


def _migrate_users_firebase(conn: sqlite3.Connection) -> None:
    """Add firebase_uid / email columns for Firebase accounts (legacy dev users unchanged)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "firebase_uid" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN firebase_uid TEXT")
    if "email" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid) "
        "WHERE firebase_uid IS NOT NULL AND firebase_uid != ''"
    )


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = _connect_sqlite()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

