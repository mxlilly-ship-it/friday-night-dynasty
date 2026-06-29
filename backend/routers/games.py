from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

from backend.deps import require_entitled
from backend.services.game_service import (
    get_game,
    game_state_dict,
    play_options,
    submit_play,
    save_game,
    sim_next_play,
    sim_to_half,
    sim_to_end,
)
from backend.services.game_state import get_teams_for_coach_game
from backend.services.league_service import attach_user_coach_gameplan_v2_from_save_state, get_save


router = APIRouter()


class PlayRequest(BaseModel):
    offense_play_id: str
    defense_play_id: str


@router.get("/{game_id}", response_model=Dict[str, Any])
def get_game_route(game_id: str, user=Depends(require_entitled)):
    try:
        game = get_game(game_id)
        return {"game_id": game_id, "state": game_state_dict(game)}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{game_id}/options", response_model=Dict[str, Any])
def options_route(game_id: str, save_id: str, user=Depends(require_entitled)):
    try:
        save = get_save(user["user_id"], save_id)
        state = save["state"]
        game = get_game(game_id)
        home_team, away_team = get_teams_for_coach_game(state, game)
        attach_user_coach_gameplan_v2_from_save_state(
            state, home_team, away_team, getattr(game, "user_team_name", None)
        )
        return {"game_id": game_id, "options": play_options(game, home_team, away_team), "user_team_name": getattr(game, "user_team_name", None)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/play", response_model=Dict[str, Any])
def play_route(game_id: str, save_id: str, body: PlayRequest, user=Depends(require_entitled)):
    try:
        save = get_save(user["user_id"], save_id)
        state = save["state"]
        game = get_game(game_id)
        home_team, away_team = get_teams_for_coach_game(state, game)
        attach_user_coach_gameplan_v2_from_save_state(
            state, home_team, away_team, getattr(game, "user_team_name", None)
        )
        out = submit_play(game, home_team, away_team, body.offense_play_id, body.defense_play_id)
        save_game(game_id, game)
        return {"game_id": game_id, **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/sim-next", response_model=Dict[str, Any])
def sim_next_route(game_id: str, save_id: str, user=Depends(require_entitled)):
    try:
        save = get_save(user["user_id"], save_id)
        state = save["state"]
        game = get_game(game_id)
        home_team, away_team = get_teams_for_coach_game(state, game)
        attach_user_coach_gameplan_v2_from_save_state(
            state, home_team, away_team, getattr(game, "user_team_name", None)
        )
        out = sim_next_play(game, home_team, away_team)
        save_game(game_id, game)
        return {"game_id": game_id, **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/sim-to-half", response_model=Dict[str, Any])
def sim_to_half_route(game_id: str, save_id: str, user=Depends(require_entitled)):
    try:
        save = get_save(user["user_id"], save_id)
        state = save["state"]
        game = get_game(game_id)
        home_team, away_team = get_teams_for_coach_game(state, game)
        attach_user_coach_gameplan_v2_from_save_state(
            state, home_team, away_team, getattr(game, "user_team_name", None)
        )
        out = sim_to_half(game, home_team, away_team)
        save_game(game_id, game)
        return {"game_id": game_id, **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/sim-to-end", response_model=Dict[str, Any])
def sim_to_end_route(game_id: str, save_id: str, user=Depends(require_entitled)):
    try:
        save = get_save(user["user_id"], save_id)
        state = save["state"]
        game = get_game(game_id)
        home_team, away_team = get_teams_for_coach_game(state, game)
        attach_user_coach_gameplan_v2_from_save_state(
            state, home_team, away_team, getattr(game, "user_team_name", None)
        )
        out = sim_to_end(game, home_team, away_team)
        save_game(game_id, game)
        return {"game_id": game_id, **out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

