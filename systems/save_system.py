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
    return Player(
        name=d.get("name", "Unknown"),
        speed=d.get("speed", 50), agility=d.get("agility", 50), acceleration=d.get("acceleration", 50),
        strength=d.get("strength", 50), balance=d.get("balance", 50), jumping=d.get("jumping", 50),
        stamina=d.get("stamina", 50), injury=d.get("injury", 50), frame=d.get("frame", 50),
        height=d.get("height", 70), weight=d.get("weight", 180),
        toughness=d.get("toughness", 50), effort=d.get("effort", 50), football_iq=d.get("football_iq", 50),
        coachability=d.get("coachability", 50), confidence=d.get("confidence", 50),
        discipline=d.get("discipline", 50), leadership=d.get("leadership", 50), composure=d.get("composure", 50),
        throw_power=d.get("throw_power", 50), throw_accuracy=d.get("throw_accuracy", 50), decisions=d.get("decisions", 50),
        catching=d.get("catching", 50), run_blocking=d.get("run_blocking", 50), pass_blocking=d.get("pass_blocking", 50),
        vision=d.get("vision", 50), ball_security=d.get("ball_security", 50), break_tackle=d.get("break_tackle", 50),
        elusiveness=d.get("elusiveness", 50), route_running=d.get("route_running", 50),
        coverage=d.get("coverage", 50), blitz=d.get("blitz", 50), pass_rush=d.get("pass_rush", 50),
        run_defense=d.get("run_defense", 50), pursuit=d.get("pursuit", 50), tackling=d.get("tackling", 50),
        block_shedding=d.get("block_shedding", 50),
        kick_power=d.get("kick_power", 50), kick_accuracy=d.get("kick_accuracy", 50),
        potential=d.get("potential", 50), growth_rate=d.get("growth_rate", 50), peak_age=d.get("peak_age", 16),
        consistency=d.get("consistency", 50), late_bloomer=d.get("late_bloomer", 50), early_bloomer=d.get("early_bloomer", 50),
        age=d.get("age"), position=d.get("position"), secondary_position=d.get("secondary_position"),
        year=d.get("year"),
        home_region=d.get("home_region"),
        transfer_count=int(d.get("transfer_count", 0) or 0),
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
    roster = [player_from_dict(p) for p in d.get("roster", [])]
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
        roster=roster,
        coach=coach,
        season_offensive_play_selection=d.get("season_offensive_play_selection"),
        season_defensive_play_selection=d.get("season_defensive_play_selection"),
        season_play_understanding_grade=d.get("season_play_understanding_grade"),
        sub_stamina_thresholds=d.get("sub_stamina_thresholds"),
        depth_chart_order=d.get("depth_chart_order"),
    )
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
    current_week: int = 1,
    season_phase: str = "regular",  # "regular" | "playoffs" | "offseason" | "done"
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
    }
    if league_structure is not None:
        out["league_structure"] = league_structure
    return out


def save_league(
    save_name: str,
    teams: Dict[str, Team],
    current_year: int,
    *,
    user_team: Optional[str] = None,
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
