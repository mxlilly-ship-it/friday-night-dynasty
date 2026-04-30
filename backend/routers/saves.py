import os
import inspect
import traceback
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
import json
from typing import Any, Dict, List, Optional

from backend.deps import require_user
from backend.services.league_service import (
    create_save,
    list_saves,
    get_save,
    delete_save,
    sim_week,
    finish_season,
    sim_playoffs,
    sim_playoff_round,
    advance_offseason,
    advance_preseason,
    get_play_selection_for_team,
    get_play_learning_summary,
    update_depth_chart,
    start_coach_game,
    finish_coach_scrimmage,
    finish_coach_week,
    finish_coach_playoff,
    get_playoff_game_text,
    get_week_game_text,
    get_team_logo_path,
    load_state,
    match_logo_filename_to_team,
    save_team_logo,
    get_coach_gameplan_v2,
    save_coach_gameplan_v2,
    get_team_history,
    get_coach_history,
    get_team_season_recap_text,
)
from systems.teams_loader import load_teams_from_json


router = APIRouter()


def _save_route_exception_detail(exc: BaseException) -> Any:
    """Broad except paths used to stringify errors; keep OSError fields for Windows path diagnosis."""
    caller = ""
    try:
        stk = inspect.stack()
        if len(stk) > 1:
            caller = str(stk[1].function or "")
    except Exception:
        caller = ""

    trace_location: Optional[str] = None
    try:
        tb = traceback.extract_tb(exc.__traceback__) if getattr(exc, "__traceback__", None) else []
        if tb:
            last = tb[-1]
            trace_location = f"{last.filename}:{last.lineno} in {last.name}"
    except Exception:
        trace_location = None

    ose: Optional[OSError] = None
    if isinstance(exc, OSError):
        ose = exc
    else:
        c = getattr(exc, "__cause__", None)
        if isinstance(c, OSError):
            ose = c
        else:
            ctx = getattr(exc, "__context__", None)
            if isinstance(ctx, OSError):
                ose = ctx
    if ose is not None:
        out: Dict[str, Any] = {
            "message": str(ose),
            "errno": ose.errno,
            "winerror": getattr(ose, "winerror", None),
            "filename": getattr(ose, "filename", None),
        }
        if caller:
            out["crash_at"] = caller
        if trace_location:
            out["trace_location"] = trace_location
        if not isinstance(exc, OSError):
            out["wrapper_type"] = type(exc).__name__
            out["wrapper_message"] = str(exc)
        return out
    out2: Dict[str, Any] = {"message": str(exc)}
    if caller:
        out2["crash_at"] = caller
    if trace_location:
        out2["trace_location"] = trace_location
    return out2


class CreateSaveRequest(BaseModel):
    save_name: str
    user_team: str
    coach_config: Dict[str, Any] = {}
    start_year: Optional[int] = None
    teams_data: Optional[Dict[str, Any]] = None


STAGE_GOAL_OPTIONS = ["Winning Season", "Playoffs", "Semifinal", "State Championship", "Title Winner"]


class AdvancePreseasonBody(BaseModel):
    """Optional playbook/game plan/depth chart/goals when advancing preseason stages."""
    offensive_playbook: Optional[str] = None
    defensive_playbook: Optional[str] = None
    game_plan: Optional[Dict[str, Any]] = None
    depth_chart: Optional[Dict[str, List[str]]] = None  # position -> [player names in order]
    position_changes: Optional[List[Dict[str, Any]]] = None  # [{ player_name, position, secondary_position? }]
    goals: Optional[Dict[str, Any]] = None  # { win_goal: int, stage_goal: str }


class AdvanceOffseasonBody(BaseModel):
    """Winter / spring focus when advancing interactive offseason stages."""
    winter_strength_pct: Optional[int] = None  # 0-100, strength vs speed/quickness
    winter_training_allocations: Optional[Dict[str, int]] = None
    winter_training_ack_results: Optional[bool] = None
    spring_offense_focus: Optional[str] = None  # run_blocking | pass_protection | receiving | pass_game | run_game
    spring_defense_focus: Optional[str] = None  # run_defense | pass_rush | tackling | pass_defense | block_defeat
    spring_ball_ack_results: Optional[bool] = None
    # Improvements stage (program grades)
    improve_facilities_grade: Optional[int] = None  # 1-10
    improve_culture_grade: Optional[int] = None  # 1-10
    improve_booster_support: Optional[int] = None  # 1-10
    # Coach development CP threshold allocations (skill -> allocated CP)
    coach_dev_allocations: Optional[Dict[str, Any]] = None


class StartCoachGameBody(BaseModel):
    """Start a coach-playable game (scrimmage, regular season, or playoff)."""
    context: str  # "scrimmage" | "week" | "playoff"
    scrimmage_index: Optional[int] = 0  # 0 or 1 for Scrimmage 1 or 2


@router.get("", response_model=List[Dict[str, Any]])
def list_saves_route(user=Depends(require_user)):
    return list_saves(user["user_id"])


@router.post("", response_model=Dict[str, Any])
def create_save_route(body: CreateSaveRequest, user=Depends(require_user)):
    try:
        return create_save(
            user["user_id"],
            body.save_name,
            body.user_team,
            body.coach_config,
            start_year=body.start_year,
            teams_data=body.teams_data,
        )
    except Exception as e:
        msg = str(e)
        if "UNIQUE constraint failed: saves.user_id, saves.save_name" in msg:
            # sqlite3 constraint is triggered when you reuse the same save_name for the same user
            raise HTTPException(
                status_code=409,
                detail="That save name already exists for your coach. Please choose a different save name.",
            )
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/meta/teams", response_model=List[Dict[str, Any]])
def list_teams_meta_route(user=Depends(require_user)):
    teams = load_teams_from_json()
    return [{"name": t.get("name", ""), "prestige": t.get("prestige", 5), "classification": t.get("classification")} for t in teams if t.get("name")]


@router.get("/meta/teams-data", response_model=Dict[str, Any])
def teams_json_file_route():
    """Full contents of data/teams.json (schema + teams array) for new-save UI. No auth so teams load before login."""
    from systems.teams_loader import _default_path

    path = _default_path()
    if not os.path.isfile(path):
        return {"_schema": "", "teams": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# `/logos/bulk` MUST be registered before `/logos/{team_name}` or "bulk" is captured as a team name
# and the wrong handler runs (expects `logo` instead of `logos`).
@router.post("/logos/bulk", response_model=Dict[str, Any])
async def bulk_upload_team_logos_route(
    save_id: str = Query(..., description="Save ID used to resolve valid team names"),
    logos: List[UploadFile] = File(...),
    user=Depends(require_user),
):
    try:
        state, _save_dir = load_state(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load save: {e}")
    valid_teams = [str(t.get("name", "")).strip() for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
    imported: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for item in logos or []:
        raw_name = str(item.filename or "").strip()
        if not raw_name:
            skipped.append({"file": "(unnamed)", "reason": "Missing file name"})
            continue
        stem, ext = os.path.splitext(raw_name)
        ext = ext.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            skipped.append({"file": raw_name, "reason": "Unsupported file type"})
            continue
        team_name = match_logo_filename_to_team(valid_teams, stem)
        if not team_name:
            skipped.append({"file": raw_name, "reason": "No matching team name found"})
            continue
        data = await item.read()
        try:
            save_team_logo(user["user_id"], team_name, data, ext)
            imported.append({"file": raw_name, "team_name": team_name})
        except ValueError as e:
            skipped.append({"file": raw_name, "reason": str(e)})
    return {
        "ok": True,
        "total": len(logos or []),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }


@router.post("/logos/{team_name}", response_model=Dict[str, Any])
async def upload_team_logo_route(team_name: str, logo: UploadFile = File(...), user=Depends(require_user)):
    name = (team_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing team name")
    filename = str(logo.filename or "").lower()
    ext = os.path.splitext(filename)[1]
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, and WEBP are supported.")
    data = await logo.read()
    try:
        save_team_logo(user["user_id"], name, data, ext)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    return {"ok": True, "team_name": name}


@router.get("/logos/{team_name}")
def get_team_logo_route(team_name: str, user=Depends(require_user)):
    name = (team_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing team name")
    path = get_team_logo_path(user["user_id"], name)
    if not path:
        raise HTTPException(status_code=404, detail="Logo not found")
    media_type = "image/png"
    low = path.lower()
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif low.endswith(".webp"):
        media_type = "image/webp"
    return FileResponse(path, media_type=media_type)


@router.get("/{save_id}/play-selection", response_model=Dict[str, Any])
def get_play_selection_route(save_id: str, user=Depends(require_user)):
    """Play selection with names for game plan UI (preseason stage 2)."""
    try:
        return get_play_selection_for_team(user["user_id"], save_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() or "load save" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/play-learning-summary", response_model=Dict[str, Any])
def get_play_learning_summary_route(save_id: str, user=Depends(require_user)):
    """Offensive/defensive percent learned + overall grade (Play Selection Results screen)."""
    return get_play_learning_summary(user["user_id"], save_id)


class UpdateDepthChartBody(BaseModel):
    depth_chart: Dict[str, List[str]]  # position -> [player names in order]


class CoachGameplanV2Body(BaseModel):
    offense: Optional[Dict[str, Any]] = None
    defense: Optional[Dict[str, Any]] = None
    fourth_down: Optional[Dict[str, Any]] = None


@router.get("/{save_id}/coach-gameplan", response_model=Dict[str, Any])
def get_coach_gameplan_v2_route(save_id: str, user=Depends(require_user)):
    """Get OFF+DEF coach gameplan (v2) for the user's next game."""
    try:
        return get_coach_gameplan_v2(user["user_id"], save_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.put("/{save_id}/coach-gameplan", response_model=Dict[str, Any])
def save_coach_gameplan_v2_route(save_id: str, body: CoachGameplanV2Body, user=Depends(require_user)):
    """Save OFF and/or DEF coach gameplan (v2) for the user's next game."""
    try:
        return save_coach_gameplan_v2(
            user["user_id"],
            save_id,
            offense=body.offense,
            defense=body.defense,
            fourth_down=body.fourth_down,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.put("/{save_id}/depth-chart", response_model=Dict[str, Any])
def update_depth_chart_route(save_id: str, body: UpdateDepthChartBody, user=Depends(require_user)):
    """Save depth chart order (from Team menu or preseason). Returns updated save state."""
    state = update_depth_chart(user["user_id"], save_id, body.depth_chart)
    return {"state": state}


@router.get("/{save_id}/team-history", response_model=Dict[str, Any])
def get_team_history_route(
    save_id: str,
    team_name: str = Query("", description="Team to view (defaults to user team)"),
    user=Depends(require_user),
):
    """Team History table for the selected team."""
    try:
        return get_team_history(user["user_id"], save_id, team_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/coach-history", response_model=Dict[str, Any])
def get_coach_history_route(
    save_id: str,
    coach_name: str = Query(..., description="Coach display name to match (case-insensitive)"),
    user=Depends(require_user),
):
    """Coach History: one row per season/team where this coach name appears in saved standings."""
    try:
        return get_coach_history(user["user_id"], save_id, coach_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/team-history/recap.txt")
def download_team_season_recap_route(
    save_id: str,
    team_name: str = Query(...),
    year: int = Query(...),
    user=Depends(require_user),
):
    """Download a season recap .txt for a team/year (if available)."""
    try:
        text = get_team_season_recap_text(user["user_id"], save_id, team_name, year)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    filename = f"{team_name}_Year_{year}_recap.txt".replace(" ", "_")
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{save_id}", response_model=Dict[str, Any])
def get_save_route(save_id: str, user=Depends(require_user)):
    try:
        return get_save(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{save_id}")
def delete_save_route(save_id: str, user=Depends(require_user)):
    """Delete a save/dynasty. Cannot be undone."""
    try:
        delete_save(user["user_id"], save_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/week/sim", response_model=Dict[str, Any])
def sim_week_route(save_id: str, user=Depends(require_user)):
    try:
        return sim_week(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/season/finish", response_model=Dict[str, Any])
def finish_season_route(save_id: str, user=Depends(require_user)):
    try:
        return finish_season(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/playoffs/sim", response_model=Dict[str, Any])
def sim_playoffs_route(save_id: str, user=Depends(require_user)):
    """Simulate the full 8-team playoff bracket in one shot (only if no playoff games played yet)."""
    try:
        return sim_playoffs(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/playoffs/sim-round", response_model=Dict[str, Any])
def sim_playoff_round_route(save_id: str, user=Depends(require_user)):
    """Simulate the next playoff round (quarterfinals, semifinals, or championship)."""
    try:
        return sim_playoff_round(user["user_id"], save_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/offseason/advance", response_model=Dict[str, Any])
def advance_offseason_route(save_id: str, body: Optional[AdvanceOffseasonBody] = Body(None), user=Depends(require_user)):
    try:
        payload = body.model_dump(exclude_none=True) if body else {}
        return advance_offseason(user["user_id"], save_id, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/preseason/advance", response_model=Dict[str, Any])
def advance_preseason_route(save_id: str, body: Optional[AdvancePreseasonBody] = Body(None), user=Depends(require_user)):
    try:
        playbook = body.model_dump(exclude_none=True) if body else {}
        return advance_preseason(user["user_id"], save_id, playbook)
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/start-coach-game", response_model=Dict[str, Any])
def start_coach_game_route(save_id: str, body: StartCoachGameBody, user=Depends(require_user)):
    """Start a coach-playable game. For scrimmage: uses preseason_scrimmage_opponents."""
    try:
        return start_coach_game(user["user_id"], save_id, body.context, body.scrimmage_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/games/{game_id}/finish-scrimmage", response_model=Dict[str, Any])
def finish_coach_scrimmage_route(save_id: str, game_id: str, user=Depends(require_user), scrimmage_stage: str = Query("Scrimmage 1", description="Scrimmage 1 or Scrimmage 2")):
    """Record coach-played scrimmage result and advance preseason."""
    try:
        return finish_coach_scrimmage(user["user_id"], save_id, game_id, scrimmage_stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/games/{game_id}/finish-week", response_model=Dict[str, Any])
def finish_coach_week_route(save_id: str, game_id: str, user=Depends(require_user)):
    """Record coach-played regular-season game and update standings. Week advances via /week/sim."""
    try:
        return finish_coach_week(user["user_id"], save_id, game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.post("/{save_id}/games/{game_id}/finish-playoff", response_model=Dict[str, Any])
def finish_coach_playoff_route(save_id: str, game_id: str, user=Depends(require_user)):
    """Record coach-played playoff game. Other games in the round: Continue (sim-round)."""
    try:
        return finish_coach_playoff(user["user_id"], save_id, game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/weeks/{week_num}/games/{game_index}/box-score.txt")
def week_game_box_score_txt_route(save_id: str, week_num: int, game_index: int, user=Depends(require_user)):
    try:
        filename, text = get_week_game_text(user["user_id"], save_id, week_num, game_index, kind="box-score")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content=text, media_type="text/plain; charset=utf-8", headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/weeks/{week_num}/games/{game_index}/game-log.txt")
def week_game_log_txt_route(save_id: str, week_num: int, game_index: int, user=Depends(require_user)):
    try:
        filename, text = get_week_game_text(user["user_id"], save_id, week_num, game_index, kind="game-log")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content=text, media_type="text/plain; charset=utf-8", headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))


@router.get("/{save_id}/playoffs/game-text.txt")
def playoff_game_text_txt_route(
    save_id: str,
    round: str = Query(..., description="Quarterfinal | Semifinal | Championship"),
    home: str = Query(..., description="Home team name"),
    away: str = Query(..., description="Away team name"),
    kind: str = Query(..., description="box-score | game-log"),
    classification: Optional[str] = Query(None, description="Optional class bracket (e.g. 3A) when multiple"),
    user=Depends(require_user),
):
    """Download playoff box score / game log for a played game."""
    try:
        filename, text = get_playoff_game_text(
            user["user_id"], save_id, round, home, away, kind=kind, classification=classification
        )
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content=text, media_type="text/plain; charset=utf-8", headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=_save_route_exception_detail(e))



