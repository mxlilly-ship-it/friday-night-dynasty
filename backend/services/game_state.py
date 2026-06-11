import json
from typing import Any, Dict, Optional, Tuple

from engine.game_engine import Game


def _resolve_coach_matchup_names(state: Dict[str, Any], game: Game) -> Optional[Tuple[str, str]]:
    """Infer home/away team names from save state when the serialized game lost them."""
    user_team = getattr(game, "user_team_name", None) or state.get("user_team")
    if not user_team:
        return None

    phase = str(state.get("season_phase") or "").strip().lower()
    if phase == "playoffs":
        from backend.services.league_service import resolve_playoff_coach_matchup

        m = resolve_playoff_coach_matchup(state, str(user_team))
        if m:
            return m[0], m[1]

    if phase == "preseason":
        for slot in state.get("preseason_scrimmage_opponents") or []:
            if not isinstance(slot, dict):
                continue
            opp = slot.get("opponent")
            if not opp:
                continue
            user_home = slot.get("user_home", True)
            if user_home:
                return str(user_team), str(opp)
            return str(opp), str(user_team)

    week_idx = int(state.get("current_week", 1)) - 1
    weeks = state.get("weeks") or []
    if 0 <= week_idx < len(weeks):
        for g in weeks[week_idx] or []:
            if not isinstance(g, dict):
                continue
            home_name, away_name = g.get("home"), g.get("away")
            if home_name == user_team or away_name == user_team:
                return home_name, away_name
    return None


def get_teams_for_coach_game(save_state: Dict[str, Any], game: Game) -> Tuple[Any, Any]:
    """Resolve home/away Team objects for coach play; repair missing names on ``game``."""
    from systems.save_system import team_from_dict

    teams = {
        t["name"]: team_from_dict(t)
        for t in save_state.get("teams") or []
        if isinstance(t, dict) and t.get("name")
    }
    home_name = getattr(game, "home_team_name", None) or None
    away_name = getattr(game, "away_team_name", None) or None
    if not home_name or not away_name:
        resolved = _resolve_coach_matchup_names(save_state, game)
        if resolved:
            home_name, away_name = resolved

    if not home_name or not away_name:
        raise ValueError(
            "Coach game is missing home/away team names — close this screen and tap Play game again."
        )
    if home_name not in teams:
        raise ValueError(f"Home team {home_name!r} not found in save")
    if away_name not in teams:
        raise ValueError(f"Away team {away_name!r} not found in save")

    game.home_team_name = home_name
    game.away_team_name = away_name
    return teams[home_name], teams[away_name]


def serialize_game(game: Game) -> Dict[str, Any]:
    # Game is a regular class; its state lives in __dict__.
    return dict(game.__dict__)


def deserialize_game(data: Dict[str, Any]) -> Game:
    game = Game()
    for k, v in data.items():
        setattr(game, k, v)
    return game


def dumps_game(game: Game) -> str:
    return json.dumps(serialize_game(game))


def loads_game(s: str) -> Game:
    return deserialize_game(json.loads(s))

