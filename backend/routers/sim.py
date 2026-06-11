from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from backend.services.league_service import (
    sim_week_state,
    advance_preseason_state,
    advance_offseason_state,
    sim_playoffs_state,
    sim_playoff_round_state,
    finish_season_state,
    start_coach_game_state,
    finish_coach_week_state,
    finish_coach_playoff_state,
    finish_coach_scrimmage_state,
    get_play_selection_from_state,
    get_play_learning_summary_from_state,
    get_coach_gameplan_v2_from_state,
    save_coach_gameplan_v2_in_state,
    update_depth_chart_in_state,
    patch_coach_inbox_state,
    _ensure_playoffs_migrated,
    _init_playoffs_multiclass,
    _ensure_all_eligible_playoff_brackets,
    _playoffs_global_completed,
)
from backend.http_errors import exception_detail
from backend.services.game_service import play_options, submit_play, sim_next_play, sim_to_half, sim_to_end
from backend.services.game_state import deserialize_game, get_teams_for_coach_game, serialize_game
from systems.save_system import team_from_dict
from systems.coach_email_system import ensure_coach_inbox


router = APIRouter()


class SimRequest(BaseModel):
    kind: str  # week-sim | preseason-advance | offseason-advance | playoffs-sim | playoffs-sim-round | season-finish
    state: Dict[str, Any]
    body: Optional[Dict[str, Any]] = None
    league_history: Optional[Dict[str, Any]] = None
    records: Optional[Dict[str, Any]] = None


class SimStateRequest(BaseModel):
    state: Dict[str, Any]


class SimCoachGameplanRequest(BaseModel):
    state: Dict[str, Any]
    offense: Optional[Dict[str, Any]] = None
    defense: Optional[Dict[str, Any]] = None
    fourth_down: Optional[Dict[str, Any]] = None
    add_offense_library: Optional[Dict[str, Any]] = None
    delete_offense_library_id: Optional[str] = None
    add_defense_library: Optional[Dict[str, Any]] = None
    delete_defense_library_id: Optional[str] = None


class SimDepthChartRequest(BaseModel):
    state: Dict[str, Any]
    depth_chart: Dict[str, Any]


class SimGameStartRequest(BaseModel):
    state: Dict[str, Any]
    context: str  # scrimmage | week | playoff
    scrimmage_index: Optional[int] = 0


class SimGameStepRequest(BaseModel):
    state: Dict[str, Any]
    game: Dict[str, Any]
    # Coach-playoff finalize (stateless/local): appended when playoffs complete so history/recaps sync.
    league_history: Optional[Dict[str, Any]] = None
    records: Optional[Dict[str, Any]] = None


class SimGamePlayRequest(BaseModel):
    state: Dict[str, Any]
    game: Dict[str, Any]
    offense_play_id: str
    defense_play_id: str


@router.post("", response_model=Dict[str, Any])
def sim_route(payload: SimRequest = Body(...)):
    try:
        kind = str(payload.kind or "").strip().lower()
        state = payload.state or {}
        body = payload.body or {}
        if str(state.get("season_phase") or "").strip().lower() in ("playoffs", "season_summary"):
            teams = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")}
            if teams:
                st = state.get("standings") or {
                    n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in teams
                }
                _ensure_playoffs_migrated(state, teams)
                if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
                    state["playoffs"] = _init_playoffs_multiclass(state, teams, st)
                _ensure_all_eligible_playoff_brackets(state, teams, st)
        if kind == "week-sim":
            out = sim_week_state(state)
            return {"state": out}
        if kind == "preseason-advance":
            out = advance_preseason_state(state, body)
            return {"state": out.get("state"), "phase_completed": out.get("phase_completed")}
        if kind == "offseason-advance":
            out = advance_offseason_state(state, body, league_history=payload.league_history)
            return {"state": out}
        if kind == "playoffs-sim":
            out = sim_playoffs_state(state)
            return {"state": out}
        if kind == "playoffs-sim-round":
            try:
                out = sim_playoff_round_state(state)
                return {"state": out}
            except ValueError as err:
                # Stateless/local: bracket already complete (e.g. user coach-played the final) but phase
                # still "playoffs" — mirror persisted sim_playoff_round and finalize into season_summary.
                if "Playoffs already complete" not in str(err):
                    raise
                hist = payload.league_history or {"seasons": []}
                records = payload.records or {}
                out = finish_season_state(state, hist, records, bulk_autopilot=False)
                return {
                    "state": out.get("state"),
                    "league_history": out.get("league_history"),
                    "records": out.get("records"),
                    "season_recaps": out.get("season_recaps"),
                    "champion": out.get("champion"),
                }
        if kind == "season-finish":
            hist = payload.league_history or {"seasons": []}
            records = payload.records or {}
            bulk_ap = bool((body or {}).get("bulk_autopilot"))
            begin_os = bool((body or {}).get("begin_offseason"))
            out = finish_season_state(
                state, hist, records, bulk_autopilot=bulk_ap, begin_offseason=begin_os
            )
            return {
                "state": out.get("state"),
                "league_history": out.get("league_history"),
                "records": out.get("records"),
                "season_recaps": out.get("season_recaps"),
                "champion": out.get("champion"),
            }
        raise ValueError(f"Unknown kind '{payload.kind}'")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/play-selection", response_model=Dict[str, Any])
def sim_play_selection_route(payload: SimStateRequest = Body(...)):
    """Preseason play selection UI for browser/local saves (no auth)."""
    try:
        return get_play_selection_from_state(payload.state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/play-learning-summary", response_model=Dict[str, Any])
def sim_play_learning_summary_route(payload: SimStateRequest = Body(...)):
    """Play selection results screen for browser/local saves (no auth)."""
    try:
        return get_play_learning_summary_from_state(payload.state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/depth-chart", response_model=Dict[str, Any])
def sim_depth_chart_route(payload: SimDepthChartRequest = Body(...)):
    """Save depth chart order for browser/local saves (no auth)."""
    try:
        dc = payload.depth_chart if isinstance(payload.depth_chart, dict) else {}
        state = update_depth_chart_in_state(payload.state, dc)
        return {"state": state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/coach-gameplan", response_model=Dict[str, Any])
def sim_coach_gameplan_route(payload: SimCoachGameplanRequest = Body(...)):
    """OFF/DEF coach gameplan (v2) for browser/local saves (no auth)."""
    try:
        if (
            payload.offense is not None
            or payload.defense is not None
            or payload.fourth_down is not None
            or payload.add_offense_library is not None
            or payload.delete_offense_library_id is not None
            or payload.add_defense_library is not None
            or payload.delete_defense_library_id is not None
        ):
            result = save_coach_gameplan_v2_in_state(
                payload.state,
                offense=payload.offense,
                defense=payload.defense,
                fourth_down=payload.fourth_down,
                add_offense_library=payload.add_offense_library,
                delete_offense_library_id=payload.delete_offense_library_id,
                add_defense_library=payload.add_defense_library,
                delete_defense_library_id=payload.delete_defense_library_id,
            )
        else:
            result = get_coach_gameplan_v2_from_state(payload.state)
        return {**result, "state": payload.state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/start", response_model=Dict[str, Any])
def sim_game_start_route(payload: SimGameStartRequest = Body(...)):
    try:
        out = start_coach_game_state(payload.state, payload.context, payload.scrimmage_index)
        game = deserialize_game(out["game"])
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        options = play_options(game, home_team, away_team)
        return {
            "home_team_name": out["home_team_name"],
            "away_team_name": out["away_team_name"],
            "user_team_name": out["user_team_name"],
            "game": serialize_game(game),
            "state": out["state"],
            "options": options,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not start coach game"))


@router.post("/game/options", response_model=Dict[str, Any])
def sim_game_options_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        return {"options": play_options(game, home_team, away_team), "game": serialize_game(game)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not load play options"))


@router.post("/game/play", response_model=Dict[str, Any])
def sim_game_play_route(payload: SimGamePlayRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        out = submit_play(game, home_team, away_team, payload.offense_play_id, payload.defense_play_id)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Play failed"))


@router.post("/game/sim-next", response_model=Dict[str, Any])
def sim_game_sim_next_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        out = sim_next_play(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Simulation failed"))


@router.post("/game/sim-to-half", response_model=Dict[str, Any])
def sim_game_sim_to_half_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        out = sim_to_half(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Simulation failed"))


@router.post("/game/sim-to-end", response_model=Dict[str, Any])
def sim_game_sim_to_end_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        home_team, away_team = get_teams_for_coach_game(payload.state, game)
        out = sim_to_end(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Simulation failed"))


@router.post("/game/finish-week", response_model=Dict[str, Any])
def sim_game_finish_week_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        out = finish_coach_week_state(payload.state, game)
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not finish week"))


@router.post("/game/finish-playoff", response_model=Dict[str, Any])
def sim_game_finish_playoff_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        out_state = finish_coach_playoff_state(payload.state, game)
        playoffs = out_state.get("playoffs") if isinstance(out_state.get("playoffs"), dict) else {}
        if playoffs and _playoffs_global_completed(playoffs):
            hist = payload.league_history if isinstance(payload.league_history, dict) else {"seasons": []}
            records_raw = payload.records if isinstance(payload.records, dict) else {}
            fin = finish_season_state(out_state, hist, records_raw, bulk_autopilot=False)
            return {
                "state": fin.get("state"),
                "league_history": fin.get("league_history"),
                "records": fin.get("records"),
                "season_recaps": fin.get("season_recaps"),
                "champion": fin.get("champion"),
            }
        return {"state": out_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not finish playoff game"))


@router.post("/game/finish-scrimmage", response_model=Dict[str, Any])
def sim_game_finish_scrimmage_route(payload: SimGameStepRequest = Body(...), scrimmage_stage: str = "Scrimmage 1"):
    try:
        game = deserialize_game(payload.game)
        out = finish_coach_scrimmage_state(payload.state, game, scrimmage_stage)
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not finish scrimmage"))


@router.post("/hydrate-inbox", response_model=Dict[str, Any])
def sim_hydrate_inbox_route(payload: SimStateRequest = Body(...)):
    """Ensure coach_inbox + starter mail exists for browser/local saves on load."""
    try:
        state = payload.state or {}
        ensure_coach_inbox(state)
        return {"state": state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Could not hydrate inbox"))


class SimCoachInboxPatchBody(BaseModel):
    state: Dict[str, Any]
    mark_read: Optional[list] = None
    choose: Optional[Dict[str, str]] = None
    delete: Optional[list] = None


@router.patch("/coach-inbox", response_model=Dict[str, Any])
def sim_patch_coach_inbox_route(body: SimCoachInboxPatchBody = Body(...)):
    """Mark read / resolve choice / delete for browser/local saves."""
    try:
        out = patch_coach_inbox_state(
            body.state or {},
            mark_read=body.mark_read,
            choose=body.choose,
            delete=body.delete,
        )
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e, "Inbox update failed"))

