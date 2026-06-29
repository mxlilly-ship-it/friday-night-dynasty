from fastapi import Depends, Header, HTTPException

from backend.billing_config import billing_required
from backend.storage.auth import user_from_token
from backend.storage.billing import user_is_entitled


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
    """Logged-in user with an active one-time purchase (when billing is enabled)."""
    if not billing_required():
        return user
    if user_is_entitled(user["user_id"]):
        return user
    raise HTTPException(
        status_code=402,
        detail={
            "code": "PAYMENT_REQUIRED",
            "message": "Purchase required to play. Complete checkout to unlock your account.",
        },
    )

