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
    _ensure_playoffs_migrated,
    _init_playoffs_multiclass,
    _ensure_all_eligible_playoff_brackets,
    _playoffs_global_completed,
)
from backend.services.game_service import play_options, submit_play, sim_next_play, sim_to_half, sim_to_end
from backend.services.game_state import deserialize_game, serialize_game
from systems.save_system import team_from_dict


router = APIRouter()


class SimRequest(BaseModel):
    kind: str  # week-sim | preseason-advance | offseason-advance | playoffs-sim | playoffs-sim-round | season-finish
    state: Dict[str, Any]
    body: Optional[Dict[str, Any]] = None
    league_history: Optional[Dict[str, Any]] = None
    records: Optional[Dict[str, Any]] = None


class SimGameStartRequest(BaseModel):
    state: Dict[str, Any]
    context: str  # scrimmage | week | playoff
    scrimmage_index: Optional[int] = 0


class SimGameStepRequest(BaseModel):
    state: Dict[str, Any]
    game: Dict[str, Any]


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
        if str(state.get("season_phase") or "").strip().lower() == "playoffs":
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
            playoffs = out.get("playoffs") if isinstance(out.get("playoffs"), dict) else {}
            if _playoffs_global_completed(playoffs):
                hist = payload.league_history or {"seasons": []}
                records = payload.records or {}
                fin = finish_season_state(out, hist, records)
                return {
                    "state": fin.get("state"),
                    "league_history": fin.get("league_history"),
                    "records": fin.get("records"),
                    "season_recaps": fin.get("season_recaps"),
                    "champion": fin.get("champion"),
                }
            return {"state": out}
        if kind == "playoffs-sim-round":
            out = sim_playoff_round_state(state)
            playoffs = out.get("playoffs") if isinstance(out.get("playoffs"), dict) else {}
            if _playoffs_global_completed(playoffs):
                hist = payload.league_history or {"seasons": []}
                records = payload.records or {}
                fin = finish_season_state(out, hist, records)
                return {
                    "state": fin.get("state"),
                    "league_history": fin.get("league_history"),
                    "records": fin.get("records"),
                    "season_recaps": fin.get("season_recaps"),
                    "champion": fin.get("champion"),
                }
            return {"state": out}
        if kind == "season-finish":
            hist = payload.league_history or {"seasons": []}
            records = payload.records or {}
            out = finish_season_state(state, hist, records)
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


@router.post("/game/start", response_model=Dict[str, Any])
def sim_game_start_route(payload: SimGameStartRequest = Body(...)):
    try:
        out = start_coach_game_state(payload.state, payload.context, payload.scrimmage_index)
        game = deserialize_game(out["game"])
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[out["home_team_name"]]
        away_team = teams[out["away_team_name"]]
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
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/options", response_model=Dict[str, Any])
def sim_game_options_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[getattr(game, "home_team_name", None)]
        away_team = teams[getattr(game, "away_team_name", None)]
        return {"options": play_options(game, home_team, away_team)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/play", response_model=Dict[str, Any])
def sim_game_play_route(payload: SimGamePlayRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[getattr(game, "home_team_name", None)]
        away_team = teams[getattr(game, "away_team_name", None)]
        out = submit_play(game, home_team, away_team, payload.offense_play_id, payload.defense_play_id)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/sim-next", response_model=Dict[str, Any])
def sim_game_sim_next_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[getattr(game, "home_team_name", None)]
        away_team = teams[getattr(game, "away_team_name", None)]
        out = sim_next_play(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/sim-to-half", response_model=Dict[str, Any])
def sim_game_sim_to_half_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[getattr(game, "home_team_name", None)]
        away_team = teams[getattr(game, "away_team_name", None)]
        out = sim_to_half(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/sim-to-end", response_model=Dict[str, Any])
def sim_game_sim_to_end_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        teams = {t["name"]: team_from_dict(t) for t in payload.state.get("teams", [])}
        home_team = teams[getattr(game, "home_team_name", None)]
        away_team = teams[getattr(game, "away_team_name", None)]
        out = sim_to_end(game, home_team, away_team)
        return {"game": serialize_game(game), **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/finish-week", response_model=Dict[str, Any])
def sim_game_finish_week_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        out = finish_coach_week_state(payload.state, game)
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/finish-playoff", response_model=Dict[str, Any])
def sim_game_finish_playoff_route(payload: SimGameStepRequest = Body(...)):
    try:
        game = deserialize_game(payload.game)
        out = finish_coach_playoff_state(payload.state, game)
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/game/finish-scrimmage", response_model=Dict[str, Any])
def sim_game_finish_scrimmage_route(payload: SimGameStepRequest = Body(...), scrimmage_stage: str = "Scrimmage 1"):
    try:
        game = deserialize_game(payload.game)
        out = finish_coach_scrimmage_state(payload.state, game, scrimmage_stage)
        return {"state": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

