"""Multiplayer league email notifications (advance, reminders, lockout)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.email_notify import app_public_url, email_send_configured, send_email
from backend.storage.db import db

logger = logging.getLogger(__name__)

NOTIFICATION_WEEK_ADVANCED_MANUAL = "week_advanced_manual"
NOTIFICATION_WEEK_ADVANCED_AUTO = "week_advanced_auto"
NOTIFICATION_ADVANCE_REMINDER_24H = "advance_reminder_24h"
NOTIFICATION_ADVANCE_LOCKOUT = "advance_lockout"

DEFAULT_SETTINGS: Dict[str, bool] = {
    "email_week_advanced": True,
    "email_advance_reminder_24h": True,
    "email_advance_lockout": True,
}

_CRON_WINDOW_MINUTES = 20


def _now() -> int:
    return int(time.time())


def ensure_notification_settings(league_id: str) -> None:
    with db() as conn:
        row = conn.execute(
            "SELECT league_id FROM league_notification_settings WHERE league_id=?",
            (league_id,),
        ).fetchone()
        if row:
            return
        conn.execute(
            """
            INSERT INTO league_notification_settings (
              league_id, email_week_advanced, email_advance_reminder_24h,
              email_advance_lockout, updated_at
            ) VALUES (?,?,?,?,?)
            """,
            (league_id, 1, 1, 1, _now()),
        )


def get_notification_settings(league_id: str) -> Dict[str, bool]:
    ensure_notification_settings(league_id)
    with db() as conn:
        row = conn.execute(
            """
            SELECT email_week_advanced, email_advance_reminder_24h, email_advance_lockout
            FROM league_notification_settings WHERE league_id=?
            """,
            (league_id,),
        ).fetchone()
    if not row:
        return dict(DEFAULT_SETTINGS)
    return {
        "email_week_advanced": bool(row["email_week_advanced"]),
        "email_advance_reminder_24h": bool(row["email_advance_reminder_24h"]),
        "email_advance_lockout": bool(row["email_advance_lockout"]),
    }


def update_notification_settings(
    league_id: str,
    *,
    email_week_advanced: Optional[bool] = None,
    email_advance_reminder_24h: Optional[bool] = None,
    email_advance_lockout: Optional[bool] = None,
) -> Dict[str, bool]:
    ensure_notification_settings(league_id)
    current = get_notification_settings(league_id)
    if email_week_advanced is not None:
        current["email_week_advanced"] = bool(email_week_advanced)
    if email_advance_reminder_24h is not None:
        current["email_advance_reminder_24h"] = bool(email_advance_reminder_24h)
    if email_advance_lockout is not None:
        current["email_advance_lockout"] = bool(email_advance_lockout)
    with db() as conn:
        conn.execute(
            """
            UPDATE league_notification_settings
            SET email_week_advanced=?, email_advance_reminder_24h=?,
                email_advance_lockout=?, updated_at=?
            WHERE league_id=?
            """,
            (
                int(current["email_week_advanced"]),
                int(current["email_advance_reminder_24h"]),
                int(current["email_advance_lockout"]),
                _now(),
                league_id,
            ),
        )
    return current


def _user_email(user_id: str) -> str:
    from backend.services.multiplayer_service import _user_email as lookup

    return lookup(user_id)


def _assigned_coaches(league_id: str) -> List[Dict[str, str]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT m.user_id, m.team_name, u.email, u.username
            FROM league_members m
            LEFT JOIN users u ON u.id = m.user_id
            WHERE m.league_id=? AND m.status='active' AND m.team_name IS NOT NULL
              AND m.team_name != '' AND m.control_mode='human'
            ORDER BY m.joined_at ASC
            """,
            (league_id,),
        ).fetchall()
    out: List[Dict[str, str]] = []
    for row in rows:
        email = str(row["email"] or row["username"] or "").strip().lower()
        if not email or "@" not in email:
            continue
        out.append(
            {
                "user_id": str(row["user_id"]),
                "team_name": str(row["team_name"]),
                "email": email,
            }
        )
    return out


def _already_sent(league_id: str, notification_type: str, stage_key: str, user_id: str) -> bool:
    with db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM league_email_log
            WHERE league_id=? AND notification_type=? AND stage_key=? AND user_id=?
            """,
            (league_id, notification_type, stage_key, user_id),
        ).fetchone()
    return bool(row)


def _log_sent(league_id: str, notification_type: str, stage_key: str, user_id: str) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO league_email_log (
              id, league_id, notification_type, stage_key, user_id, sent_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), league_id, notification_type, stage_key, user_id, _now()),
        )


def _send_to_coach(
    *,
    to_email: str,
    subject: str,
    body: str,
    league_id: str,
    notification_type: str,
    stage_key: str,
    user_id: str,
) -> bool:
    if _already_sent(league_id, notification_type, stage_key, user_id):
        return False
    if not email_send_configured():
        logger.info(
            "League email not sent (%s) — Resend not configured",
            notification_type,
        )
        return False
    ok = send_email(to_email=to_email, subject=subject, text=body)
    if ok:
        _log_sent(league_id, notification_type, stage_key, user_id)
    return ok


def _format_deadline_local(deadline: datetime) -> str:
    try:
        return deadline.strftime("%A %I:%M %p %Z").replace(" 0", " ")
    except Exception:
        return deadline.isoformat()


def _stage_label_from_key(stage_key: str) -> str:
    if stage_key.startswith("regular:week:"):
        try:
            wk = int(stage_key.rsplit(":", 1)[-1])
            return f"Week {wk}"
        except ValueError:
            pass
    return stage_key.replace(":", " — ")


def notify_week_advanced(
    league_id: str,
    *,
    advance_source: str,
    action_label: str,
    completed_stage_key: str,
    league_name: str,
) -> int:
    """Email assigned coaches that the league advanced. Returns count sent."""
    settings = get_notification_settings(league_id)
    if not settings.get("email_week_advanced"):
        return 0
    auto = str(advance_source or "manual").lower() == "auto"
    notification_type = NOTIFICATION_WEEK_ADVANCED_AUTO if auto else NOTIFICATION_WEEK_ADVANCED_MANUAL
    app_url = app_public_url()
    if auto:
        subject = f"{league_name} — League auto-advanced"
        intro = (
            f"Your league \"{league_name}\" auto-advanced at the scheduled deadline.\n"
            f"{action_label}."
        )
    else:
        subject = f"{league_name} — {action_label}"
        intro = (
            f"Your commissioner advanced \"{league_name}\".\n"
            f"{action_label}."
        )
    body_template = "\n".join(
        [
            intro,
            "",
            "Results are in. Open Friday Night Dynasty to review scores, standings, and prep for what's next.",
            "",
            f"Play here: {app_url}",
        ]
    )
    sent = 0
    for coach in _assigned_coaches(league_id):
        if _send_to_coach(
            to_email=coach["email"],
            subject=subject,
            body=body_template,
            league_id=league_id,
            notification_type=notification_type,
            stage_key=completed_stage_key,
            user_id=coach["user_id"],
        ):
            sent += 1
    return sent


def _next_advance_deadline(league_row: Dict[str, Any]) -> Optional[datetime]:
    from backend.services.multiplayer_service import _advance_countdown_iso

    iso = _advance_countdown_iso(league_row)
    if not iso:
        return None
    try:
        deadline = datetime.fromisoformat(iso)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=ZoneInfo("UTC"))
        return deadline
    except Exception:
        return None


def _in_cron_window(target: datetime, now: datetime) -> bool:
    """True if now is within [_CRON_WINDOW_MINUTES] after target."""
    delta = (now - target).total_seconds()
    return 0 <= delta < _CRON_WINDOW_MINUTES * 60


def _process_league_scheduled_notifications(league_row: Dict[str, Any]) -> Dict[str, int]:
    from backend.services.multiplayer_service import (
        _load_state,
        _stage_key_from_state,
        _submitted_teams,
        try_auto_advance_league,
    )

    stats = {"reminders": 0, "lockouts": 0, "auto_advances": 0}
    league_id = str(league_row["id"])
    if str(league_row.get("status") or "") != "active":
        return stats
    if str(league_row.get("advance_mode") or "manual").lower() != "auto":
        return stats

    settings = get_notification_settings(league_id)
    deadline = _next_advance_deadline(league_row)
    if deadline is None:
        return stats

    now = datetime.now(deadline.tzinfo)
    save_dir = str(league_row.get("save_dir") or "")
    try:
        state = _load_state(save_dir)
    except Exception:
        return stats

    stage_key = _stage_key_from_state(state)
    submitted = _submitted_teams(league_id, stage_key)
    league_name = str(league_row.get("name") or "League")
    stage_label = _stage_label_from_key(stage_key)
    app_url = app_public_url()
    deadline_text = _format_deadline_local(deadline)
    lockout_minutes = int(league_row.get("submit_lockout_minutes") or 5)

    coaches = _assigned_coaches(league_id)
    unsubmitted = [c for c in coaches if c["team_name"] not in submitted]

    if settings.get("email_advance_reminder_24h") and unsubmitted:
        # Interval schedules shorter than 48h can't meaningfully use a 24h-before reminder.
        interval_hours = None
        try:
            raw_iv = league_row.get("advance_interval_hours")
            interval_hours = int(raw_iv) if raw_iv is not None else None
        except (TypeError, ValueError):
            interval_hours = None
        if interval_hours is None or interval_hours >= 48:
            reminder_target = deadline - timedelta(hours=24)
            if _in_cron_window(reminder_target, now):
                subject = f"{league_name} — Submit by {deadline_text}"
                for coach in unsubmitted:
                    body = "\n".join(
                        [
                            f"You have not submitted for {stage_label} in \"{league_name}\".",
                            "",
                            f"The league auto-advances in about 24 hours ({deadline_text}).",
                            "Complete your prep and submit before the deadline.",
                            "",
                            f"Play here: {app_url}",
                        ]
                    )
                    if _send_to_coach(
                        to_email=coach["email"],
                        subject=subject,
                        body=body,
                        league_id=league_id,
                        notification_type=NOTIFICATION_ADVANCE_REMINDER_24H,
                        stage_key=stage_key,
                        user_id=coach["user_id"],
                    ):
                        stats["reminders"] += 1

    if settings.get("email_advance_lockout") and unsubmitted:
        lockout_start = deadline - timedelta(minutes=lockout_minutes)
        if _in_cron_window(lockout_start, now):
            subject = f"{league_name} — Submit now (lockout started)"
            for coach in unsubmitted:
                body = "\n".join(
                    [
                        f"Submit lockout has started for {stage_label} in \"{league_name}\".",
                        "",
                        f"You can no longer unsubmit. The league auto-advances at {deadline_text}.",
                        "",
                        f"Play here: {app_url}",
                    ]
                )
                if _send_to_coach(
                    to_email=coach["email"],
                    subject=subject,
                    body=body,
                    league_id=league_id,
                    notification_type=NOTIFICATION_ADVANCE_LOCKOUT,
                    stage_key=stage_key,
                    user_id=coach["user_id"],
                ):
                    stats["lockouts"] += 1

    if try_auto_advance_league(league_id):
        stats["auto_advances"] += 1

    return stats


def run_notification_tick() -> Dict[str, Any]:
    """Cron entry: deadline reminders, lockouts, and auto-advance for all auto leagues."""
    if not email_send_configured():
        return {
            "ok": True,
            "email_configured": False,
            "leagues_checked": 0,
            "reminders": 0,
            "lockouts": 0,
            "auto_advances": 0,
        }

    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, name, save_dir, status, advance_mode, advance_deadline_dow,
                   advance_deadline_time_local, advance_interval_hours, advance_cycle_anchor_at,
                   submit_lockout_minutes, timezone,
                   commissioner_user_id, last_auto_advance_at
            FROM leagues
            WHERE status='active' AND lower(advance_mode)='auto'
            """
        ).fetchall()

    totals = {"leagues_checked": len(rows), "reminders": 0, "lockouts": 0, "auto_advances": 0}
    for row in rows:
        try:
            stats = _process_league_scheduled_notifications(dict(row))
            totals["reminders"] += stats["reminders"]
            totals["lockouts"] += stats["lockouts"]
            totals["auto_advances"] += stats["auto_advances"]
        except Exception:
            logger.exception("Notification tick failed for league %s", row["id"])
    totals["ok"] = True
    return totals
