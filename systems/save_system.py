"""
League save/load: one directory per save (saves/<name>/) with league_save.json (teams, current_year)
plus league_history.json and records.json in the same directory for history and records.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from models.team import Team
from models.player import Player
from models.coach import Coach
from models.community import CommunityType
from models.coach import OffensiveStyle, DefensiveStyle
from systems.playbook_system import normalize_coach_defensive_front, normalize_coach_offensive_playbook
from systems.win_path_io import isfile_any, makedirs_with_path_fallback, open_text_with_path_fallback

SAVES_DIR = "saves"
LEAGUE_SAVE_FILENAME = "league_save.json"
LEAGUE_HISTORY_FILENAME = "league_history.json"
RECORDS_FILENAME = "records.json"
SAVE_VERSION = 2


def _saves_base() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, SAVES_DIR)


def get_save_dir(save_name: str) -> str:
    """Return the full path to the save directory for this save name."""
    safe = "".join(c for c in save_name if c.isalnum() or c in " _-").strip() or "Untitled"
    return os.path.join(_saves_base(), safe)


def list_saves() -> List[str]:
    """List names of existing saves (directory names under saves/)."""
    base = _saves_base()
    if not os.path.isdir(base):
        return []
    names = []
    for entry in os.listdir(base):
        path = os.path.join(base, entry)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, LEAGUE_SAVE_FILENAME)):
            names.append(entry)
    return sorted(names)


# -------------------------
# Serialize / deserialize models
# -------------------------


def _num_from_save(d: Dict[str, Any], key: str, default: int) -> int:
    """
    Read an int rating from JSON. Keys present with null must not pass through as None —
    Player._clamp_ratings compares to ints and would raise TypeError.
    """
    if not isinstance(d, dict):
        return default
    v = d.get(key, default)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _optional_int_from_save(d: Dict[str, Any], key: str) -> Optional[int]:
    if not isinstance(d, dict) or key not in d:
        return None
    v = d[key]
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _optional_str_from_save(d: Dict[str, Any], key: str) -> Optional[str]:
    if not isinstance(d, dict) or key not in d:
        return None
    v = d[key]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def player_to_dict(p: Player) -> Dict[str, Any]:
    """Player to JSON-serializable dict."""
    return {
        "name": p.name,
        "speed": p.speed, "agility": p.agility, "acceleration": p.acceleration,
        "strength": p.strength, "balance": p.balance, "jumping": p.jumping,
        "stamina": p.stamina, "injury": p.injury, "frame": p.frame,
        "height": p.height, "weight": p.weight,
        "toughness": p.toughness, "effort": p.effort, "football_iq": p.football_iq,
        "coachability": p.coachability, "confidence": p.confidence,
        "discipline": p.discipline, "leadership": p.leadership, "composure": p.composure,
        "throw_power": p.throw_power, "throw_accuracy": p.throw_accuracy, "decisions": p.decisions,
        "catching": p.catching, "run_blocking": p.run_blocking, "pass_blocking": p.pass_blocking,
        "vision": p.vision, "ball_security": p.ball_security, "break_tackle": p.break_tackle,
        "elusiveness": p.elusiveness, "route_running": p.route_running,
        "coverage": p.coverage, "blitz": p.blitz, "pass_rush": p.pass_rush,
        "run_defense": p.run_defense, "pursuit": p.pursuit, "tackling": p.tackling,
        "block_shedding": p.block_shedding,
        "kick_power": p.kick_power, "kick_accuracy": p.kick_accuracy,
        "potential": p.potential, "growth_rate": p.growth_rate, "peak_age": p.peak_age,
        "consistency": p.consistency, "late_bloomer": p.late_bloomer, "early_bloomer": p.early_bloomer,
        "age": p.age, "position": p.position, "secondary_position": p.secondary_position,
        "year": p.year,
        "home_region": getattr(p, "home_region", None),
        "transfer_count": int(getattr(p, "transfer_count", 0) or 0),
    }


def player_from_dict(d: Dict[str, Any]) -> Player:
    """Dict to Player."""
    if not isinstance(d, dict):
        d = {}
    nm = d.get("name", "Unknown")
    if nm is None or (isinstance(nm, str) and not nm.strip()):
        nm = "Unknown"
    return Player(
        name=str(nm),
        speed=_num_from_save(d, "speed", 50),
        agility=_num_from_save(d, "agility", 50),
        acceleration=_num_from_save(d, "acceleration", 50),
        strength=_num_from_save(d, "strength", 50),
        balance=_num_from_save(d, "balance", 50),
        jumping=_num_from_save(d, "jumping", 50),
        stamina=_num_from_save(d, "stamina", 50),
        injury=_num_from_save(d, "injury", 50),
        frame=_num_from_save(d, "frame", 50),
        height=_num_from_save(d, "height", 70),
        weight=_num_from_save(d, "weight", 180),
        toughness=_num_from_save(d, "toughness", 50),
        effort=_num_from_save(d, "effort", 50),
        football_iq=_num_from_save(d, "football_iq", 50),
        coachability=_num_from_save(d, "coachability", 50),
        confidence=_num_from_save(d, "confidence", 50),
        discipline=_num_from_save(d, "discipline", 50),
        leadership=_num_from_save(d, "leadership", 50),
        composure=_num_from_save(d, "composure", 50),
        throw_power=_num_from_save(d, "throw_power", 50),
        throw_accuracy=_num_from_save(d, "throw_accuracy", 50),
        decisions=_num_from_save(d, "decisions", 50),
        catching=_num_from_save(d, "catching", 50),
        run_blocking=_num_from_save(d, "run_blocking", 50),
        pass_blocking=_num_from_save(d, "pass_blocking", 50),
        vision=_num_from_save(d, "vision", 50),
        ball_security=_num_from_save(d, "ball_security", 50),
        break_tackle=_num_from_save(d, "break_tackle", 50),
        elusiveness=_num_from_save(d, "elusiveness", 50),
        route_running=_num_from_save(d, "route_running", 50),
        coverage=_num_from_save(d, "coverage", 50),
        blitz=_num_from_save(d, "blitz", 50),
        pass_rush=_num_from_save(d, "pass_rush", 50),
        run_defense=_num_from_save(d, "run_defense", 50),
        pursuit=_num_from_save(d, "pursuit", 50),
        tackling=_num_from_save(d, "tackling", 50),
        block_shedding=_num_from_save(d, "block_shedding", 50),
        kick_power=_num_from_save(d, "kick_power", 50),
        kick_accuracy=_num_from_save(d, "kick_accuracy", 50),
        potential=_num_from_save(d, "potential", 50),
        growth_rate=_num_from_save(d, "growth_rate", 50),
        peak_age=_num_from_save(d, "peak_age", 16),
        consistency=_num_from_save(d, "consistency", 50),
        late_bloomer=_num_from_save(d, "late_bloomer", 50),
        early_bloomer=_num_from_save(d, "early_bloomer", 50),
        age=_optional_int_from_save(d, "age"),
        position=_optional_str_from_save(d, "position"),
        secondary_position=_optional_str_from_save(d, "secondary_position"),
        year=_optional_int_from_save(d, "year"),
        home_region=_optional_str_from_save(d, "home_region"),
        transfer_count=_num_from_save(d, "transfer_count", 0),
    )


def coach_to_dict(c: Coach) -> Dict[str, Any]:
    """Coach to JSON-serializable dict (enums as names)."""
    return {
        "name": c.name,
        "age": c.age,
        "preferred_schemes": c.preferred_schemes,
        "offensive_style": c.offensive_style.name,
        "defensive_style": c.defensive_style.name,
        "offensive_formation": c.offensive_formation,
        "defensive_formation": c.defensive_formation,
        "winter_strength_pct": c.winter_strength_pct,
        "spring_offense_focus": c.spring_offense_focus,
        "spring_defense_focus": c.spring_defense_focus,
        "playcalling": c.playcalling,
        "player_development": c.player_development,
        "community_outreach": c.community_outreach,
        "culture": c.culture,
        "recruiting": c.recruiting,
        "scheme_teach": c.scheme_teach,
        "years_at_school": c.years_at_school,
        "years_since_scheme_change": c.years_since_scheme_change,
        "last_preferred_playbook_change_year": getattr(c, "last_preferred_playbook_change_year", 0),
        "hot_seat": getattr(c, "hot_seat", 0),
    }


def coach_from_dict(d: Dict[str, Any]) -> Coach:
    """Dict to Coach."""
    off = d.get("offensive_style", "BALANCED")
    def_ = d.get("defensive_style", "BASE")
    try:
        off_style = OffensiveStyle[off] if isinstance(off, str) else off
    except KeyError:
        off_style = OffensiveStyle.BALANCED
    try:
        def_style = DefensiveStyle[def_] if isinstance(def_, str) else def_
    except KeyError:
        def_style = DefensiveStyle.BASE
    return Coach(
        name=d.get("name", "Unknown"),
        age=d.get("age", 35),
        preferred_schemes=d.get("preferred_schemes", {}),
        offensive_style=off_style,
        defensive_style=def_style,
        offensive_formation=normalize_coach_offensive_playbook(d.get("offensive_formation")),
        defensive_formation=normalize_coach_defensive_front(d.get("defensive_formation")),
        winter_strength_pct=d.get("winter_strength_pct", 50),
        spring_offense_focus=d.get("spring_offense_focus", "run_game"),
        spring_defense_focus=d.get("spring_defense_focus", "pass_defense"),
        playcalling=d.get("playcalling", 5),
        player_development=d.get("player_development", 5),
        community_outreach=d.get("community_outreach", 5),
        culture=d.get("culture", 5),
        recruiting=d.get("recruiting", 5),
        scheme_teach=d.get("scheme_teach", 5),
        years_at_school=d.get("years_at_school", 0),
        years_since_scheme_change=d.get("years_since_scheme_change", 0),
        last_preferred_playbook_change_year=int(d.get("last_preferred_playbook_change_year", 0) or 0),
        hot_seat=int(d.get("hot_seat", 0) or 0),
    )


def _community_from_value(value: Any) -> CommunityType:
    if isinstance(value, CommunityType):
        return value
    s = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    for ct in CommunityType:
        if ct.value.replace(" ", "_").replace("-", "_") == s or ct.name == s.upper():
            return ct
    return CommunityType.SUBURBAN


def team_to_dict(t: Team) -> Dict[str, Any]:
    """Team to JSON-serializable dict (roster and coach serialized)."""
    raw = {
        "name": t.name,
        "nickname": getattr(t, "nickname", None),
        "prestige": t.prestige,
        "team_points": round(float(getattr(t, "team_points", 0.0) or 0.0), 2),
        "team_points_last_delta": round(float(getattr(t, "team_points_last_delta", 0.0) or 0.0), 2),
        "community_type": t.community_type.value if hasattr(t.community_type, "value") else str(t.community_type),
        "enrollment": t.enrollment,
        "classification": t.classification,
        "region": getattr(t, "region", None),
        "wins": t.wins,
        "losses": t.losses,
        "regional_championships": t.regional_championships,
        "championships": t.championships,
        "facilities_grade": t.facilities_grade,
        "culture_grade": t.culture_grade,
        "booster_support": t.booster_support,
        "facilities_progress_pts": getattr(t, "facilities_progress_pts", 0),
        "culture_progress_pts": getattr(t, "culture_progress_pts", 0),
        "boosters_progress_pts": getattr(t, "boosters_progress_pts", 0),
        "roster": [player_to_dict(p) for p in t.roster],
        "coach": coach_to_dict(t.coach) if t.coach else None,
        "season_offensive_play_selection": t.season_offensive_play_selection,
        "season_defensive_play_selection": t.season_defensive_play_selection,
        "season_play_understanding_grade": t.season_play_understanding_grade,
        "sub_stamina_thresholds": t.sub_stamina_thresholds,
        "depth_chart_order": getattr(t, "depth_chart_order", None),
    }
    return raw


def team_from_dict(d: Dict[str, Any]) -> Team:
    """Dict to Team."""
    community = _community_from_value(d.get("community_type", "suburban"))
    roster_raw = d.get("roster", []) if isinstance(d, dict) else []
    roster_list = roster_raw if isinstance(roster_raw, list) else []
    roster = [player_from_dict(p) for p in roster_list if isinstance(p, dict)]
    coach = coach_from_dict(d["coach"]) if d.get("coach") else None
    t = Team(
        name=d.get("name", ""),
        nickname=d.get("nickname", d.get("mascot")),
        prestige=int(d.get("prestige", 5)),
        community_type=community,
        enrollment=d.get("enrollment"),
        classification=d.get("classification"),
        region=d.get("region"),
        wins=int(d.get("wins", 0)),
        losses=int(d.get("losses", 0)),
        regional_championships=int(d.get("regional_championships", 0)),
        championships=int(d.get("championships", 0)),
        facilities_grade=int(d.get("facilities_grade", 5)),
        culture_grade=int(d.get("culture_grade", 5)),
        booster_support=int(d.get("booster_support", 5)),
        facilities_progress_pts=int(d.get("facilities_progress_pts", 0) or 0),
        culture_progress_pts=int(d.get("culture_progress_pts", 0) or 0),
        boosters_progress_pts=int(d.get("boosters_progress_pts", 0) or 0),
        roster=roster,
        coach=coach,
        season_offensive_play_selection=d.get("season_offensive_play_selection"),
        season_defensive_play_selection=d.get("season_defensive_play_selection"),
        season_play_understanding_grade=d.get("season_play_understanding_grade"),
        sub_stamina_thresholds=d.get("sub_stamina_thresholds"),
        depth_chart_order=d.get("depth_chart_order"),
    )
    if d.get("team_points") is not None:
        try:
            t.team_points = float(d["team_points"])
        except (TypeError, ValueError):
            t.team_points = None
    try:
        t.team_points_last_delta = float(d.get("team_points_last_delta", 0.0) or 0.0)
    except (TypeError, ValueError):
        t.team_points_last_delta = 0.0
    from systems.prestige_system import ensure_team_points_initialized

    ensure_team_points_initialized(t)
    return t


# -------------------------
# League state (in-memory) and save file
# -------------------------

def build_league_state(
    teams: Dict[str, Team],
    current_year: int,
    save_name: str,
    *,
    user_team: Optional[str] = None,
    user_coach_name: Optional[str] = None,
    allow_user_coach_firing: bool = True,
    current_week: int = 1,
    season_phase: str = "regular",  # "regular" | "playoffs" | "season_summary" | "offseason" | "done"
    weeks: Optional[List[List[Dict[str, str]]]] = None,  # week -> [{home, away}]
    week_results: Optional[List[List[Dict[str, Any]]]] = None,  # week -> [{played, home_score, away_score, ot}]
    standings: Optional[Dict[str, Dict[str, int]]] = None,  # team -> {wins, losses, points_for, points_against}
    league_structure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the dict that gets written to league_save.json (teams + mid-season state)."""
    out: Dict[str, Any] = {
        "version": SAVE_VERSION,
        "save_name": save_name,
        "current_year": current_year,
        "user_team": user_team,
        "current_week": int(current_week),
        "season_phase": season_phase,
        "weeks": weeks or [],
        "week_results": week_results or [],
        "standings": standings or {},
        "teams": [team_to_dict(t) for t in teams.values()],
        "allow_user_coach_firing": bool(allow_user_coach_firing),
    }
    if user_coach_name is not None and str(user_coach_name).strip():
        out["user_coach_name"] = str(user_coach_name).strip()
    if league_structure is not None:
        out["league_structure"] = league_structure
    return out


def save_league(
    save_name: str,
    teams: Dict[str, Team],
    current_year: int,
    *,
    user_team: Optional[str] = None,
    user_coach_name: Optional[str] = None,
    allow_user_coach_firing: bool = True,
    current_week: int = 1,
    season_phase: str = "regular",
    weeks: Optional[List[List[Dict[str, str]]]] = None,
    week_results: Optional[List[List[Dict[str, Any]]]] = None,
    standings: Optional[Dict[str, Dict[str, int]]] = None,
    league_structure: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Write league to save directory. Creates saves/<name>/ with league_save.json.
    Does NOT overwrite league_history.json or records.json (those are updated by append_season when you sim a season).
    Returns the save directory path.
    """
    save_dir = get_save_dir(save_name)
    makedirs_with_path_fallback(os.path.abspath(os.path.normpath(save_dir)))
    state = build_league_state(
        teams,
        current_year,
        save_name,
        user_team=user_team,
        user_coach_name=user_coach_name,
        allow_user_coach_firing=allow_user_coach_firing,
        current_week=current_week,
        season_phase=season_phase,
        weeks=weeks,
        week_results=week_results,
        standings=standings,
        league_structure=league_structure,
    )
    plain = os.path.abspath(os.path.join(os.path.normpath(save_dir), LEAGUE_SAVE_FILENAME))
    with open_text_with_path_fallback(plain, "w") as f:
        json.dump(state, f, indent=2)
    return save_dir


def load_league(save_name: str) -> Tuple[Dict[str, Team], int, str, Dict[str, Any]]:
    """
    Load league from save directory. Reads league_save.json and reconstructs Team objects.
    Returns (teams_dict, current_year, save_dir_path, state_dict).
    """
    save_dir = get_save_dir(save_name)
    plain = os.path.abspath(os.path.join(os.path.normpath(save_dir), LEAGUE_SAVE_FILENAME))
    if not isfile_any(plain):
        raise FileNotFoundError(f"Save not found: {plain}")
    with open_text_with_path_fallback(plain, "r") as f:
        state = json.load(f)
    version = state.get("version", 0)
    if version > SAVE_VERSION:
        raise ValueError(f"Save version {version} is newer than supported {SAVE_VERSION}")
    current_year = int(state.get("current_year", 1))
    teams_list = state.get("teams", [])
    teams = {}
    for t_dict in teams_list:
        t = team_from_dict(t_dict)
        teams[t.name] = t
    return teams, current_year, save_dir, state


def league_history_path(save_dir: str) -> str:
    """Path to league_history.json inside the save directory."""
    return os.path.join(save_dir, LEAGUE_HISTORY_FILENAME)


def records_path(save_dir: str) -> str:
    """Path to records.json inside the save directory."""
    return os.path.join(save_dir, RECORDS_FILENAME)


def ensure_save_has_history_and_records(save_dir: str) -> None:
    """
    If league_history.json doesn't exist in the save dir, write empty so append_season works.
    records.json is created on first append_season when load_records sees no file.
    """
    from systems.league_history import save_league_history

    hist_path = os.path.abspath(os.path.normpath(league_history_path(save_dir)))
    if not isfile_any(hist_path):
        save_league_history({"seasons": []}, hist_path)
