import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, model_validator

from backend.deps import require_entitled
from backend.services.league_service import save_dir_team_logo
from backend.services.multiplayer_service import (
    apply_league_coach_prep,
    apply_member_coach_setup,
    approve_join_request,
    assign_team_by_email,
    assign_team_to_member,
    build_commish_cross_region_planning,
    build_commish_dashboard,
    build_league_dashboard,
    commish_advance_league,
    create_admin_league,
    create_join_request,
    delete_admin_league,
    list_browsable_leagues,
    list_deleted_leagues_for_admin,
    permanently_delete_admin_league,
    reject_join_request,
    restore_admin_league,
    get_league_commish_game_bundle,
    get_league_game_bundle,
    account_identity_for_user,
    invite_user_to_league,
    is_platform_owner_user,
    list_league_chat_messages,
    list_leagues_for_user,
    lookup_user_by_email,
    post_league_chat_message,
    remove_league_member,
    reset_member_pin,
    resolve_commissioner_user_id,
    revoke_league_invite,
    save_commish_cross_region_picks,
    save_league_commish_game_state,
    save_league_game_state,
    submit_league_week,
    sync_pending_invites_for_user,
    unsubmit_league_week,
    update_league_settings,
    vacate_team_member,
    verify_team_pin,
    _load_league_row,
)
from backend.storage.db import db
from backend.storage.league_start_requests import create_league_start_request
from backend.support_notify import notify_league_start_request, support_notify_configured


router = APIRouter()

_LOGO_EXT = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpeg", ".webp": ".webp"}


class AdminCreateLeagueBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    user_team: Optional[str] = Field(None, min_length=1)
    coach_config: Dict[str, Any] = Field(default_factory=dict)
    start_year: Optional[int] = None
    teams_data: Optional[Dict[str, Any]] = None
    allow_user_coach_firing: bool = False
    transfers_disabled: bool = False
    commissioner_user_id: Optional[str] = None
    commissioner_email: Optional[str] = Field(None, min_length=3, max_length=200)
    timezone: str = "America/New_York"
    defer_commish_setup: bool = False

    @model_validator(mode="after")
    def _require_team_unless_deferred(self) -> "AdminCreateLeagueBody":
        if not self.defer_commish_setup and not str(self.user_team or "").strip():
            raise ValueError("user_team required")
        if self.defer_commish_setup and not (
            str(self.commissioner_email or "").strip() or str(self.commissioner_user_id or "").strip()
        ):
            raise ValueError("commissioner email required when the commissioner will finish setup")
        return self


class VerifyPinBody(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6)


class AssignTeamBody(BaseModel):
    user_id: str
    team_name: str
    pin: Optional[str] = None


class AssignByEmailBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    team_name: str
    pin: Optional[str] = None


class ResetPinBody(BaseModel):
    pin: Optional[str] = None


class CommishSettingsBody(BaseModel):
    advance_mode: Optional[str] = None
    advance_deadline_dow: Optional[int] = Field(None, ge=0, le=6)
    advance_deadline_time_local: Optional[str] = None
    submit_lockout_minutes: Optional[int] = Field(None, ge=0, le=120)
    timezone: Optional[str] = None
    email_week_advanced: Optional[bool] = None
    email_advance_reminder_24h: Optional[bool] = None
    email_advance_lockout: Optional[bool] = None


class CoachSetupBody(BaseModel):
    coach_config: Dict[str, Any]


class LeagueGameBody(BaseModel):
    state: Dict[str, Any]


class InviteBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)


class JoinRequestBody(BaseModel):
    message: Optional[str] = Field(None, max_length=500)


class ApproveJoinRequestBody(BaseModel):
    team_name: Optional[str] = None


class ChatMessageBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)
    team_name: Optional[str] = None


@router.get("/mine", response_model=Dict[str, Any])
def list_my_leagues_route(user=Depends(require_entitled)):
    from backend.platform_config import platform_owner_emails_configured

    user_id = user["user_id"]
    try:
        sync_pending_invites_for_user(user_id)
        leagues = list_leagues_for_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load leagues: {e}") from e
    identity = account_identity_for_user(user_id)
    account_email = identity.get("email") or identity.get("username") or ""
    return {
        "leagues": leagues,
        "is_platform_owner": is_platform_owner_user(user_id),
        "platform_owner_configured": platform_owner_emails_configured(),
        "account_email": account_email,
    }


@router.get("/browse", response_model=Dict[str, Any])
def browse_leagues_route(user=Depends(require_entitled)):
    try:
        leagues = list_browsable_leagues(user["user_id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load leagues: {e}") from e
    return {"leagues": leagues}


@router.post("/start-requests", response_model=Dict[str, Any])
async def league_start_request_route(
    league_type: str = Form(...),
    estimated_players: int = Form(...),
    state: str = Form(...),
    contact_email: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    league_file: Optional[UploadFile] = File(None),
    user=Depends(require_entitled),
):
    from backend.services.multiplayer_service import account_identity_for_user

    user_id = user["user_id"]
    email = (contact_email or "").strip().lower()
    if not email:
        identity = account_identity_for_user(user_id)
        email = str(identity.get("email") or identity.get("username") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid contact email is required.")

    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    if league_file and league_file.filename:
        file_name = league_file.filename
        file_bytes = await league_file.read()

    try:
        request = create_league_start_request(
            league_type=league_type,
            estimated_players=estimated_players,
            state=state,
            contact_email=email,
            user_id=user_id,
            notes=notes,
            file_bytes=file_bytes,
            file_name=file_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    notified = notify_league_start_request(request)
    if notified:
        with db() as conn:
            conn.execute(
                "UPDATE league_start_requests SET notified=1 WHERE id=?",
                (request["request_id"],),
            )

    if notified or support_notify_configured():
        hint = "Request sent. We'll email you at {email} to follow up.".format(email=email)
    else:
        hint = (
            f"Request received (ID {request['request_id'][:8]}). "
            f"We'll follow up at {email}."
        )
    return {
        "ok": True,
        "request_id": request["request_id"],
        "email_sent": notified,
        "message": hint,
    }


@router.get("/{league_id}/schools", response_model=Dict[str, Any])
def league_schools_route(league_id: str, user=Depends(require_entitled)):
    from backend.services.multiplayer_service import league_schools_for_user

    try:
        schools = league_schools_for_user(league_id, user["user_id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"teams": schools}


class CoachPrepBody(BaseModel):
    prep: Dict[str, Any] = Field(default_factory=dict)


@router.post("/{league_id}/coach-prep", response_model=Dict[str, Any])
def coach_prep_route(
    league_id: str,
    team_name: str,
    body: CoachPrepBody,
    user=Depends(require_entitled),
):
    try:
        return apply_league_coach_prep(league_id, user["user_id"], team_name, body.prep)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{league_id}/commish/dashboard", response_model=Dict[str, Any])
def commish_dashboard_route(league_id: str, user=Depends(require_entitled)):
    try:
        return build_commish_dashboard(league_id, user["user_id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{league_id}/commish/settings", response_model=Dict[str, Any])
def commish_settings_route(
    league_id: str,
    body: CommishSettingsBody,
    user=Depends(require_entitled),
):
    try:
        return update_league_settings(
            league_id,
            user["user_id"],
            advance_mode=body.advance_mode,
            advance_deadline_dow=body.advance_deadline_dow,
            advance_deadline_time_local=body.advance_deadline_time_local,
            submit_lockout_minutes=body.submit_lockout_minutes,
            timezone=body.timezone,
            email_week_advanced=body.email_week_advanced,
            email_advance_reminder_24h=body.email_advance_reminder_24h,
            email_advance_lockout=body.email_advance_lockout,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class CommishSimWeekBody(BaseModel):
  cross_region_picks: Optional[List[Dict[str, Any]]] = None


class CommishCrossRegionPicksBody(BaseModel):
    cross_region_picks: List[Dict[str, Any]]


@router.get("/{league_id}/commish/cross-region-planning", response_model=Dict[str, Any])
def commish_cross_region_planning_route(league_id: str, user=Depends(require_entitled)):
    try:
        return build_commish_cross_region_planning(league_id, user["user_id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{league_id}/commish/cross-region-picks", response_model=Dict[str, Any])
def commish_cross_region_picks_route(
    league_id: str,
    team_name: str,
    body: CommishCrossRegionPicksBody,
    user=Depends(require_entitled),
):
    try:
        return save_commish_cross_region_picks(
            league_id,
            user["user_id"],
            team_name,
            body.cross_region_picks,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/commish/sim-week", response_model=Dict[str, Any])
def commish_sim_week_route(
    league_id: str,
    body: Optional[CommishSimWeekBody] = Body(None),
    user=Depends(require_entitled),
):
    try:
        picks = body.cross_region_picks if body else None
        return commish_advance_league(league_id, user["user_id"], cross_region_picks=picks)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not advance league: {e}") from e


@router.get("/{league_id}/commish/game", response_model=Dict[str, Any])
def league_commish_game_route(league_id: str, user=Depends(require_entitled)):
    try:
        return get_league_commish_game_bundle(league_id, user["user_id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{league_id}/commish/game", response_model=Dict[str, Any])
def league_commish_game_save_route(
    league_id: str,
    body: LeagueGameBody,
    user=Depends(require_entitled),
):
    try:
        return save_league_commish_game_state(league_id, user["user_id"], body.state)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{league_id}/game", response_model=Dict[str, Any])
def league_game_route(
    league_id: str,
    team_name: str,
    user=Depends(require_entitled),
):
    try:
        return get_league_game_bundle(league_id, user["user_id"], team_name)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{league_id}/game", response_model=Dict[str, Any])
def league_game_save_route(
    league_id: str,
    team_name: str,
    body: LeagueGameBody,
    user=Depends(require_entitled),
):
    try:
        return save_league_game_state(league_id, user["user_id"], team_name, body.state)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{league_id}/dashboard", response_model=Dict[str, Any])
def league_dashboard_route(
    league_id: str,
    team_name: Optional[str] = None,
    user=Depends(require_entitled),
):
    try:
        return build_league_dashboard(league_id, user["user_id"], acting_team_name=team_name)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{league_id}/chat", response_model=Dict[str, Any])
def league_chat_list_route(league_id: str, user=Depends(require_entitled)):
    try:
        messages = list_league_chat_messages(league_id, user["user_id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"messages": messages, "chat_enabled": True}


@router.post("/{league_id}/chat", response_model=Dict[str, Any])
def league_chat_post_route(
    league_id: str,
    body: ChatMessageBody,
    user=Depends(require_entitled),
):
    try:
        return post_league_chat_message(
            league_id,
            user["user_id"],
            body.body,
            team_name=body.team_name,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/submit", response_model=Dict[str, Any])
def submit_week_route(
    league_id: str,
    team_name: str,
    user=Depends(require_entitled),
):
    try:
        return submit_league_week(league_id, user["user_id"], team_name)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{league_id}/submit", response_model=Dict[str, Any])
def unsubmit_week_route(
    league_id: str,
    team_name: str,
    user=Depends(require_entitled),
):
    try:
        return unsubmit_league_week(league_id, user["user_id"], team_name)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/teams/{team_name}/verify-pin", response_model=Dict[str, Any])
def verify_pin_route(
    league_id: str,
    team_name: str,
    body: VerifyPinBody,
    user=Depends(require_entitled),
):
    ok = verify_team_pin(league_id, user["user_id"], team_name, body.pin)
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    return {"ok": True, "league_id": league_id, "team_name": team_name}


@router.post("/{league_id}/teams/{team_name}/coach-setup", response_model=Dict[str, Any])
def coach_setup_route(
    league_id: str,
    team_name: str,
    body: CoachSetupBody,
    user=Depends(require_entitled),
):
    try:
        return apply_member_coach_setup(
            league_id,
            user["user_id"],
            team_name,
            body.coach_config,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/logos/{team_name}", response_model=Dict[str, Any])
async def upload_league_logo_route(
    league_id: str,
    team_name: str,
    logo: UploadFile = File(...),
    user=Depends(require_entitled),
):
    if not is_platform_owner_user(user["user_id"]):
        league_row = _load_league_row(league_id)
        if not league_row:
            raise HTTPException(status_code=404, detail="league not found")
        if str(league_row.get("commissioner_user_id") or "") != user["user_id"]:
            raise HTTPException(status_code=403, detail="commissioner only")
    league_row = _load_league_row(league_id)
    if not league_row:
        raise HTTPException(status_code=404, detail="league not found")
    save_dir = str(league_row.get("save_dir") or "")
    if not save_dir:
        raise HTTPException(status_code=500, detail="league save missing")
    raw_name = logo.filename or ""
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in _LOGO_EXT:
        raise HTTPException(status_code=400, detail="Unsupported logo type")
    data = await logo.read()
    try:
        path = save_dir_team_logo(save_dir, team_name, data, ext)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "team_name": team_name, "path": path}


@router.get("/admin/users/lookup", response_model=Dict[str, Any])
def admin_lookup_user_route(email: str, user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    found = lookup_user_by_email(email)
    if not found:
        raise HTTPException(status_code=404, detail="No account found for that email")
    return found


@router.post("/admin/leagues", response_model=Dict[str, Any])
def admin_create_league_route(body: AdminCreateLeagueBody, user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    try:
        return create_admin_league(
            user["user_id"],
            name=body.name,
            user_team=str(body.user_team or "").strip(),
            coach_config=body.coach_config,
            start_year=body.start_year,
            teams_data=body.teams_data,
            allow_user_coach_firing=body.allow_user_coach_firing,
            transfers_disabled=body.transfers_disabled,
            commissioner_user_id=body.commissioner_user_id,
            commissioner_email=body.commissioner_email,
            timezone=body.timezone,
            defer_commish_setup=body.defer_commish_setup,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/admin/leagues/{league_id}", response_model=Dict[str, Any])
def admin_delete_league_route(league_id: str, user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    try:
        return delete_admin_league(user["user_id"], league_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/admin/leagues/deleted", response_model=Dict[str, Any])
def admin_list_deleted_leagues_route(user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    try:
        return {"leagues": list_deleted_leagues_for_admin(user["user_id"])}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/admin/leagues/{league_id}/restore", response_model=Dict[str, Any])
def admin_restore_league_route(league_id: str, user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    try:
        return restore_admin_league(user["user_id"], league_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/admin/leagues/{league_id}/permanent", response_model=Dict[str, Any])
def admin_permanent_delete_league_route(league_id: str, user=Depends(require_entitled)):
    if not is_platform_owner_user(user["user_id"]):
        raise HTTPException(status_code=403, detail="Platform owner only")
    try:
        return permanently_delete_admin_league(user["user_id"], league_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/invites", response_model=Dict[str, Any])
def invite_to_league_route(league_id: str, body: InviteBody, user=Depends(require_entitled)):
    try:
        return invite_user_to_league(league_id, user["user_id"], body.email)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/join-requests", response_model=Dict[str, Any])
def create_join_request_route(
    league_id: str,
    body: JoinRequestBody,
    user=Depends(require_entitled),
):
    try:
        return create_join_request(league_id, user["user_id"], message=body.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/join-requests/{request_id}/approve", response_model=Dict[str, Any])
def approve_join_request_route(
    league_id: str,
    request_id: str,
    body: ApproveJoinRequestBody,
    user=Depends(require_entitled),
):
    try:
        return approve_join_request(
            league_id,
            user["user_id"],
            request_id,
            team_name=body.team_name,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{league_id}/join-requests/{request_id}", response_model=Dict[str, Any])
def reject_join_request_route(
    league_id: str,
    request_id: str,
    user=Depends(require_entitled),
):
    try:
        return reject_join_request(league_id, user["user_id"], request_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/members/assign", response_model=Dict[str, Any])
def assign_team_route(league_id: str, body: AssignTeamBody, user=Depends(require_entitled)):
    try:
        return assign_team_to_member(
            league_id,
            user["user_id"],
            body.user_id,
            body.team_name,
            pin=body.pin,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/members/assign-by-email", response_model=Dict[str, Any])
def assign_team_by_email_route(league_id: str, body: AssignByEmailBody, user=Depends(require_entitled)):
    try:
        return assign_team_by_email(
            league_id,
            user["user_id"],
            body.email,
            body.team_name,
            pin=body.pin,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/members/{target_user_id}/reset-pin", response_model=Dict[str, Any])
def reset_pin_route(
    league_id: str,
    target_user_id: str,
    body: ResetPinBody,
    user=Depends(require_entitled),
):
    try:
        return reset_member_pin(
            league_id,
            user["user_id"],
            target_user_id,
            pin=body.pin,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{league_id}/members/{target_user_id}/vacate", response_model=Dict[str, Any])
def vacate_team_route(league_id: str, target_user_id: str, user=Depends(require_entitled)):
    try:
        return vacate_team_member(league_id, user["user_id"], target_user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{league_id}/members/{target_user_id}", response_model=Dict[str, Any])
def remove_member_route(league_id: str, target_user_id: str, user=Depends(require_entitled)):
    try:
        return remove_league_member(league_id, user["user_id"], target_user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{league_id}/invites/{invite_id}", response_model=Dict[str, Any])
def revoke_invite_route(league_id: str, invite_id: str, user=Depends(require_entitled)):
    try:
        return revoke_league_invite(league_id, user["user_id"], invite_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
