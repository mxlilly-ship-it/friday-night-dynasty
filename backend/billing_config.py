"""Stripe one-time purchase configuration (Railway env)."""

from __future__ import annotations

import os


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def stripe_price_id() -> str:
    return os.environ.get("STRIPE_PRICE_ID", "").strip()


def billing_checkout_configured() -> bool:
    return bool(stripe_secret_key() and stripe_price_id())


def billing_required() -> bool:
    """
    When True, game APIs require an active purchase.
    Defaults to True if Stripe checkout is configured, unless FND_BILLING_REQUIRED=0.
    """
    if not billing_checkout_configured():
        return False
    return _truthy("FND_BILLING_REQUIRED", default=True)


def billing_success_url(request_base: str) -> str:
    explicit = os.environ.get("FND_BILLING_SUCCESS_URL", "").strip()
    if explicit:
        return explicit
    base = request_base.rstrip("/")
    return f"{base}/?billing=success&session_id={{CHECKOUT_SESSION_ID}}"


def billing_cancel_url(request_base: str) -> str:
    explicit = os.environ.get("FND_BILLING_CANCEL_URL", "").strip()
    if explicit:
        return explicit
    base = request_base.rstrip("/")
    return f"{base}/?billing=cancelled"
