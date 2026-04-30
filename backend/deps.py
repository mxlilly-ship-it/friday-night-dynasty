from fastapi import Header, HTTPException

from backend.storage.auth import user_from_token


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

