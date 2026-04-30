import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional

from systems.win_path_io import extended_abs_path, makedirs_with_path_fallback, windows_file_arg_error


def _db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # backend/.. = project root
    root = os.path.dirname(base)
    return os.path.join(root, "backend", "dynasty.sqlite3")


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

