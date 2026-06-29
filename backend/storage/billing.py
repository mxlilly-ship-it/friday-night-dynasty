"""One-time purchase entitlement (Stripe Checkout → SQLite)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from backend.storage.db import db

logger = logging.getLogger(__name__)


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
        return {"entitled": False, "purchased_at": None}
    return {
        "entitled": bool(int(row["entitlement_active"] or 0)),
        "purchased_at": int(row["purchased_at"]) if row["purchased_at"] else None,
        "stripe_customer_id": row["stripe_customer_id"] or None,
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
