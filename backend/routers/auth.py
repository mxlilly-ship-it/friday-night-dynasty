from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.deps import require_user
from backend.storage.auth import dev_login


router = APIRouter()


class DevLoginRequest(BaseModel):
    username: str


class DevLoginResponse(BaseModel):
    user_id: str
    token: str


@router.post("/dev-login", response_model=DevLoginResponse)
def dev_login_route(body: DevLoginRequest):
    user_id, token = dev_login(body.username)
    return DevLoginResponse(user_id=user_id, token=token)


@router.get("/session")
def session_route(user=Depends(require_user)):
    """Validate bearer token (browser calls after deploy / DB reset)."""
    return {"user_id": user["user_id"], "username": user["username"]}

