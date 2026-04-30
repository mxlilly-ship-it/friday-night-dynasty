from fastapi import APIRouter
from pydantic import BaseModel

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

