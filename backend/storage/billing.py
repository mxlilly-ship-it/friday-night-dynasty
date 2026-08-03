"""One-time purchase entitlement (Stripe Checkout → SQLite)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.billing_config import billing_required
from backend.storage.db import db

logger = logging.getLogger(__name__)

PAYMENT_REQUIRED_MESSAGE = (
    "Purchase required to play Friday Night Dynasty. Complete checkout to unlock your account."
)

# Kept for older clients that still key off TRIAL_COMPLETE after schedule release.
TRIAL_COMPLETE_MESSAGE = PAYMENT_REQUIRED_MESSAGE


class TrialSeasonCompleteError(Exception):
    """Raised when a non-entitled user hits a paid-only action (legacy name)."""


def user_trial_completed(user_id: str) -> bool:
    """Legacy flag — no longer grants free play; retained for status/reporting."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    with db() as conn:
        row = conn.execute(
            "SELECT trial_completed FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        return bool(int(row["trial_completed"] or 0))


def mark_trial_completed(user_id: str) -> None:
    user_id = str(user_id or "").strip()
    if not user_id:
        return
    with db() as conn:
        conn.execute(
            "UPDATE users SET trial_completed=1 WHERE id=? AND trial_completed=0",
            (user_id,),
        )


def user_can_play(user_id: str) -> bool:
    """True when billing is off, or the user has purchased."""
    if not billing_required():
        return True
    return user_is_entitled(user_id)


def check_trial_before_year2_preseason(user_id: Optional[str]) -> None:
    """
    Safety gate before year-2 preseason.
    Purchase is required for all play when billing is on; this remains as a belt-and-suspenders check.
    """
    if not billing_required():
        return
    uid = str(user_id or "").strip()
    if not uid:
        raise TrialSeasonCompleteError(
            PAYMENT_REQUIRED_MESSAGE + " Sign in with your account to continue."
        )
    if user_is_entitled(uid):
        return
    mark_trial_completed(uid)
    raise TrialSeasonCompleteError(PAYMENT_REQUIRED_MESSAGE)


def trial_complete_http_detail(message: Optional[str] = None) -> Dict[str, Any]:
    return {
        "code": "PAYMENT_REQUIRED",
        "message": message or PAYMENT_REQUIRED_MESSAGE,
    }


def payment_required_http_detail(message: Optional[str] = None) -> Dict[str, Any]:
    return trial_complete_http_detail(message)


def user_is_entitled(user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    if not user_id:
        return False
    with db() as conn:
        row = conn.execute(
            "SELECT entitlement_active, purchased_at FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        return bool(int(row["entitlement_active"] or 0))


def get_entitlement_status(user_id: str) -> Dict[str, Any]:
    user_id = str(user_id or "").strip()
    with db() as conn:
        row = conn.execute(
            """
            SELECT entitlement_active, purchased_at, stripe_customer_id
            FROM users WHERE id=?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return {
            "entitled": False,
            "purchased_at": None,
            "trial_completed": False,
            "trial_available": False,
        }
    entitled = bool(int(row["entitlement_active"] or 0))
    trial_done = user_trial_completed(user_id)
    return {
        "entitled": entitled,
        "purchased_at": int(row["purchased_at"]) if row["purchased_at"] else None,
        "stripe_customer_id": row["stripe_customer_id"] or None,
        "trial_completed": trial_done,
        # Free season removed — purchase required when billing is enabled.
        "trial_available": False,
    }


def grant_entitlement(
    user_id: str,
    *,
    stripe_checkout_session_id: str,
    stripe_payment_intent_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    amount_cents: Optional[int] = None,
    currency: Optional[str] = None,
) -> bool:
    """
    Mark user entitled and record purchase. Returns False if session already processed.
    """
    user_id = str(user_id or "").strip()
    session_id = str(stripe_checkout_session_id or "").strip()
    if not user_id or not session_id:
        return False

    now = int(time.time())
    try:
        with db() as conn:
            existing = conn.execute(
                "SELECT user_id FROM purchases WHERE stripe_checkout_session_id=?",
                (session_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE users SET entitlement_active=1 WHERE id=?",
                    (existing["user_id"],),
                )
                return True

            user_row = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
            if not user_row:
                return False

            purchase_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO purchases (
                  id, user_id, stripe_checkout_session_id, stripe_payment_intent_id,
                  amount_cents, currency, status, created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    purchase_id,
                    user_id,
                    session_id,
                    stripe_payment_intent_id,
                    amount_cents,
                    currency,
                    "completed",
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE users
                SET entitlement_active=1,
                    purchased_at=COALESCE(purchased_at, ?),
                    stripe_customer_id=COALESCE(?, stripe_customer_id)
                WHERE id=?
                """,
                (now, stripe_customer_id, user_id),
            )
        return True
    except Exception:
        logger.exception("grant_entitlement failed for user %s session %s", user_id, session_id)
        return False


def revoke_entitlement_for_payment_intent(stripe_payment_intent_id: str) -> bool:
    """Refund handler — clears entitlement if this was the user's only completed purchase."""
    pi = str(stripe_payment_intent_id or "").strip()
    if not pi:
        return False
    with db() as conn:
        row = conn.execute(
            "SELECT user_id FROM purchases WHERE stripe_payment_intent_id=? AND status='completed'",
            (pi,),
        ).fetchone()
        if not row:
            return False
        user_id = row["user_id"]
        conn.execute(
            "UPDATE purchases SET status='refunded' WHERE stripe_payment_intent_id=?",
            (pi,),
        )
        other = conn.execute(
            """
            SELECT 1 FROM purchases
            WHERE user_id=? AND status='completed' LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not other:
            conn.execute(
                "UPDATE users SET entitlement_active=0 WHERE id=?",
                (user_id,),
            )
        return True
