"""Stripe Checkout — one-time purchase entitlement."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.billing_config import (
    billing_cancel_url,
    billing_checkout_configured,
    billing_required,
    billing_success_url,
    stripe_price_id,
    stripe_secret_key,
    stripe_webhook_secret,
)
from backend.deps import require_user
from backend.storage.billing import get_entitlement_status, grant_entitlement, revoke_entitlement_for_payment_intent, user_is_entitled
from backend.storage.db import db

router = APIRouter()
logger = logging.getLogger(__name__)


class BillingStatusResponse(BaseModel):
    billing_required: bool
    billing_configured: bool
    entitled: bool
    purchased_at: Optional[int] = None


class CreateCheckoutResponse(BaseModel):
    checkout_url: str


class ConfirmCheckoutResponse(BaseModel):
    entitled: bool
    purchased_at: Optional[int] = None


def _stripe_configure() -> None:
    key = stripe_secret_key()
    if not key:
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server.")
    stripe.api_key = key


def _request_base_url(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-proto") or "").strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip()
    if host:
        scheme = forwarded or request.url.scheme
        return f"{scheme}://{host}"
    return str(request.base_url).rstrip("/")


def _user_email(user_id: str) -> Optional[str]:
    with db() as conn:
        row = conn.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return None
    email = str(row["email"] or "").strip()
    return email or None


def _grant_from_checkout_session(session: Dict[str, Any]) -> bool:
    user_id = str(session.get("client_reference_id") or (session.get("metadata") or {}).get("user_id") or "").strip()
    if not user_id:
        logger.warning("Checkout session missing user_id metadata: %s", session.get("id"))
        return False
    if str(session.get("payment_status") or "") != "paid":
        return False
    if str(session.get("mode") or "") != "payment":
        return False

    amount_cents = None
    currency = None
    payment_intent_id = session.get("payment_intent")
    if isinstance(payment_intent_id, dict):
        payment_intent_id = payment_intent_id.get("id")
    amount_total = session.get("amount_total")
    if amount_total is not None:
        amount_cents = int(amount_total)
    currency = str(session.get("currency") or "") or None
    customer_id = session.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")

    return grant_entitlement(
        user_id,
        stripe_checkout_session_id=str(session.get("id") or ""),
        stripe_payment_intent_id=str(payment_intent_id) if payment_intent_id else None,
        stripe_customer_id=str(customer_id) if customer_id else None,
        amount_cents=amount_cents,
        currency=currency,
    )


@router.get("/status", response_model=BillingStatusResponse)
def billing_status_route(user=Depends(require_user)):
    entitled = user_is_entitled(user["user_id"])
    info = get_entitlement_status(user["user_id"])
    return BillingStatusResponse(
        billing_required=billing_required(),
        billing_configured=billing_checkout_configured(),
        entitled=entitled if billing_required() else True,
        purchased_at=info.get("purchased_at"),
    )


@router.post("/create-checkout-session", response_model=CreateCheckoutResponse)
def create_checkout_session_route(request: Request, user=Depends(require_user)):
    if not billing_checkout_configured():
        raise HTTPException(status_code=503, detail="Stripe checkout is not configured.")
    if user_is_entitled(user["user_id"]):
        raise HTTPException(status_code=400, detail="This account already has access.")

    base = _request_base_url(request)
    _stripe_configure()
    email = _user_email(user["user_id"])
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": stripe_price_id(), "quantity": 1}],
            success_url=billing_success_url(base),
            cancel_url=billing_cancel_url(base),
            client_reference_id=user["user_id"],
            metadata={"user_id": user["user_id"]},
            **({"customer_email": email} if email else {}),
        )
    except stripe.StripeError as e:
        logger.exception("Stripe checkout session create failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}") from e

    url = str(getattr(session, "url", None) or "").strip()
    if not url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL.")
    return CreateCheckoutResponse(checkout_url=url)


@router.get("/confirm", response_model=ConfirmCheckoutResponse)
def confirm_checkout_route(session_id: str = Query(..., min_length=8), user=Depends(require_user)):
    """Fallback if webhook is slow — verifies session with Stripe and grants access."""
    if not billing_checkout_configured():
        raise HTTPException(status_code=503, detail="Stripe checkout is not configured.")
    session_id = session_id.strip()
    _stripe_configure()
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}") from e

    meta = session.metadata or {}
    session_user = str(session.client_reference_id or meta.get("user_id") or "")
    if session_user != user["user_id"]:
        raise HTTPException(status_code=403, detail="Checkout session does not belong to this account.")

    _grant_from_checkout_session(
        {
            "id": session.id,
            "client_reference_id": session.client_reference_id,
            "metadata": dict(meta),
            "payment_status": session.payment_status,
            "mode": session.mode,
            "payment_intent": session.payment_intent,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "customer": session.customer,
        }
    )
    info = get_entitlement_status(user["user_id"])
    return ConfirmCheckoutResponse(
        entitled=bool(info.get("entitled")),
        purchased_at=info.get("purchased_at"),
    )


@router.post("/webhook")
async def stripe_webhook_route(request: Request):
    secret = stripe_webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured.")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {e}") from e
    except stripe.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {e}") from e

    event_type = str(event.get("type") or "")
    data_object = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        _grant_from_checkout_session(dict(data_object))
    elif event_type == "charge.refunded":
        pi = data_object.get("payment_intent")
        if pi:
            revoke_entitlement_for_payment_intent(str(pi))

    return {"received": True}
