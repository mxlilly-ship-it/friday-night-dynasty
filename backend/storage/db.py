import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional

from backend.data_paths import saves_base_dir, sqlite_db_path, leagues_base_dir
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
    leagues_dir = leagues_base_dir()
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(leagues_dir)))
    except OSError:
        os.makedirs(leagues_dir, exist_ok=True)
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
        _migrate_support_tickets(conn)
        _migrate_multiplayer_leagues(conn)
        _migrate_league_members_coach_setup(conn)


def _migrate_multiplayer_leagues(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leagues (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          save_dir TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_by_user_id TEXT NOT NULL,
          commissioner_user_id TEXT,
          timezone TEXT NOT NULL DEFAULT 'America/New_York',
          advance_mode TEXT NOT NULL DEFAULT 'manual',
          advance_deadline_dow INTEGER,
          advance_deadline_time_local TEXT,
          submit_lockout_minutes INTEGER NOT NULL DEFAULT 5,
          rules_json TEXT NOT NULL DEFAULT '{}',
          state_version INTEGER NOT NULL DEFAULT 0,
          sim_job_status TEXT NOT NULL DEFAULT 'idle',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          FOREIGN KEY(created_by_user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_members (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          team_name TEXT,
          role TEXT NOT NULL DEFAULT 'coach',
          status TEXT NOT NULL DEFAULT 'unassigned',
          control_mode TEXT NOT NULL DEFAULT 'human',
          pin_hash TEXT,
          pin_updated_at INTEGER,
          joined_at INTEGER NOT NULL,
          FOREIGN KEY(league_id) REFERENCES leagues(id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_members_league ON league_members(league_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_members_user ON league_members(user_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_invites (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          email TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          created_by_user_id TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          expires_at INTEGER,
          FOREIGN KEY(league_id) REFERENCES leagues(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_submit_status (
          league_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          team_name TEXT NOT NULL,
          stage_key TEXT NOT NULL,
          submitted_at INTEGER NOT NULL,
          PRIMARY KEY (league_id, user_id, team_name, stage_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_activity_log (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          actor_user_id TEXT,
          action TEXT NOT NULL,
          detail_json TEXT,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(league_id) REFERENCES leagues(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_activity_league ON league_activity_log(league_id, created_at DESC)"
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(leagues)").fetchall()}
    if "last_auto_advance_at" not in cols:
        conn.execute("ALTER TABLE leagues ADD COLUMN last_auto_advance_at INTEGER")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_chat_messages (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          team_name TEXT,
          display_name TEXT NOT NULL,
          body TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(league_id) REFERENCES leagues(id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_chat_league ON league_chat_messages(league_id, created_at DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_join_requests (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          message TEXT,
          created_at INTEGER NOT NULL,
          resolved_at INTEGER,
          resolved_by_user_id TEXT,
          FOREIGN KEY(league_id) REFERENCES leagues(id),
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_join_requests_league ON league_join_requests(league_id, status, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_join_requests_user ON league_join_requests(user_id, status)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_start_requests (
          id TEXT PRIMARY KEY,
          user_id TEXT,
          contact_email TEXT NOT NULL,
          league_type TEXT NOT NULL,
          estimated_players INTEGER NOT NULL,
          state TEXT NOT NULL,
          notes TEXT,
          file_name TEXT,
          file_path TEXT,
          created_at INTEGER NOT NULL,
          notified INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_start_requests_created ON league_start_requests(created_at DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_notification_settings (
          league_id TEXT PRIMARY KEY,
          email_week_advanced INTEGER NOT NULL DEFAULT 1,
          email_advance_reminder_24h INTEGER NOT NULL DEFAULT 1,
          email_advance_lockout INTEGER NOT NULL DEFAULT 1,
          updated_at INTEGER NOT NULL,
          FOREIGN KEY(league_id) REFERENCES leagues(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS league_email_log (
          id TEXT PRIMARY KEY,
          league_id TEXT NOT NULL,
          notification_type TEXT NOT NULL,
          stage_key TEXT NOT NULL,
          user_id TEXT NOT NULL,
          sent_at INTEGER NOT NULL,
          UNIQUE(league_id, notification_type, stage_key, user_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_league_email_log_league ON league_email_log(league_id, sent_at DESC)"
    )


def _migrate_league_members_coach_setup(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(league_members)").fetchall()}
    if "coach_setup_complete" not in cols:
        conn.execute(
            "ALTER TABLE league_members ADD COLUMN coach_setup_complete INTEGER NOT NULL DEFAULT 0"
        )
        conn.execute(
            """
            UPDATE league_members SET coach_setup_complete=1
            WHERE status='active' AND team_name IS NOT NULL AND team_name != ''
            """
        )


def _migrate_support_tickets(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_tickets (
          id TEXT PRIMARY KEY,
          user_id TEXT,
          contact_email TEXT NOT NULL,
          category TEXT NOT NULL,
          message TEXT NOT NULL,
          page_url TEXT,
          user_agent TEXT,
          created_at INTEGER NOT NULL,
          notified INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_support_tickets_created ON support_tickets(created_at DESC)"
    )


def _migrate_users_billing(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "entitlement_active" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN entitlement_active INTEGER NOT NULL DEFAULT 0")
    if "purchased_at" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN purchased_at INTEGER")
    if "stripe_customer_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    if "trial_completed" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN trial_completed INTEGER NOT NULL DEFAULT 0")
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

