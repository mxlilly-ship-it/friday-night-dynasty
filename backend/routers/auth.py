from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.deps import require_user
from backend.firebase_verify import email_from_claims, verify_id_token
from backend.storage.auth import (
    MAX_DEVICES_PER_USER,
    DeviceLimitError,
    dev_login,
    firebase_login,
    list_user_devices,
    remove_device,
    remove_device_for_firebase_uid,
)


router = APIRouter()


class DevLoginRequest(BaseModel):
    username: str


class DevLoginResponse(BaseModel):
    user_id: str
    token: str


class FirebaseAuthRequest(BaseModel):
    id_token: str = Field(..., min_length=10)
    device_id: str = Field(..., min_length=8, max_length=128)
    device_label: str | None = Field(default=None, max_length=120)


class FirebaseAuthResponse(BaseModel):
    user_id: str
    token: str
    username: str
    email: str = ""


class DeviceRow(BaseModel):
    device_id: str
    label: str | None = None
    created_at: int
    last_seen_at: int


@router.post("/dev-login", response_model=DevLoginResponse)
def dev_login_route(body: DevLoginRequest):
    user_id, token = dev_login(body.username)
    return DevLoginResponse(user_id=user_id, token=token)


@router.post("/firebase", response_model=FirebaseAuthResponse)
def firebase_auth_route(body: FirebaseAuthRequest):
    """
    Exchange a Firebase ID token (after client sign-in/sign-up) for an app session token.
    Enforces at most MAX_DEVICES_PER_USER distinct device_id values per account.
    """
    try:
        claims = verify_id_token(body.id_token)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {e}") from e

    uid = str(claims.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Firebase token missing uid")
    email = email_from_claims(claims)

    try:
        user_id, token, username = firebase_login(
            uid,
            email,
            body.device_id.strip(),
            body.device_label,
        )
    except DeviceLimitError as e:
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    f"This account is already on {MAX_DEVICES_PER_USER} devices. "
                    "Remove one below (from another device or browser), then try again."
                ),
                "devices": e.devices,
                "max_devices": MAX_DEVICES_PER_USER,
            },
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return FirebaseAuthResponse(
        user_id=user_id,
        token=token,
        username=username,
        email=email,
    )


@router.get("/session")
def session_route(user=Depends(require_user)):
    """Validate bearer token (browser calls after deploy / DB reset)."""
    return {"user_id": user["user_id"], "username": user["username"]}


@router.get("/devices", response_model=list[DeviceRow])
def list_devices_route(user=Depends(require_user)):
    return list_user_devices(user["user_id"])


class FirebaseRemoveDeviceRequest(BaseModel):
    id_token: str = Field(..., min_length=10)
    device_id: str = Field(..., min_length=8, max_length=128)


@router.post("/firebase/remove-device")
def firebase_remove_device_route(body: FirebaseRemoveDeviceRequest):
    """Remove a registered device using Firebase proof (for device-limit screen before session exists)."""
    try:
        claims = verify_id_token(body.id_token)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {e}") from e
    uid = str(claims.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Firebase token missing uid")
    if not remove_device_for_firebase_uid(uid, body.device_id.strip()):
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}


@router.delete("/devices/{device_id}")
def delete_device_route(device_id: str, user=Depends(require_user)):
    if not remove_device(user["user_id"], device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}
