from fastapi import Depends, Header, HTTPException

from backend.billing_config import billing_required
from backend.storage.auth import user_from_token
from backend.storage.billing import (
    payment_required_http_detail,
    trial_complete_http_detail,
    user_can_play,
    user_is_entitled,
    user_trial_completed,
)


def require_user(authorization: str = Header(default="")):
    """
    Very simple bearer auth:
      Authorization: Bearer <token>
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user = user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id, username = user
    return {"user_id": user_id, "username": username}


def require_entitled(user=Depends(require_user)):
    """Logged-in user with a purchase or an active free-season trial (when billing is enabled)."""
    if not billing_required():
        return user
    if user_can_play(user["user_id"]):
        return user
    if user_trial_completed(user["user_id"]):
        raise HTTPException(status_code=402, detail=trial_complete_http_detail())
    raise HTTPException(status_code=402, detail=payment_required_http_detail())


def require_purchased(user=Depends(require_user)):
    """Logged-in user with a completed purchase (multiplayer / paid-only routes)."""
    if not billing_required():
        return user
    if user_is_entitled(user["user_id"]):
        return user
    raise HTTPException(status_code=402, detail=payment_required_http_detail())


def optional_user(authorization: str = Header(default="")):
    """Bearer user when signed in; None when anonymous (support form)."""
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user = user_from_token(token)
    if not user:
        return None
    user_id, username = user
    return {"user_id": user_id, "username": username}
