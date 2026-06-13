"""
Load teams from data/teams.json.
Single source of truth for league setup; add teams to the JSON file to expand the league.

The same JSON also carries league-level metadata at the top (``state``,
``league_id``, ``email_pack``, ``playoff_system``) so a league's identity and
rules travel with its team list — see ``load_league_config_from_json`` and
``systems.league_metadata``.
"""

import json
import os
from typing import Any, Dict, List, Optional

from models.team import Team
from models.community import CommunityType
from systems.playoff_systems import DEFAULT_PLAYOFF_SYSTEM_ID
from systems.win_path_io import open_text_with_path_fallback, path_exists_any

TEAMS_JSON_PATH = "data/teams.json"

# Map JSON community strings to CommunityType
_COMMUNITY_MAP = {
    "rural": CommunityType.RURAL,
    "urban": CommunityType.URBAN,
    "suburban": CommunityType.SUBURBAN,
    "affluent": CommunityType.AFFLUENT,
    "blue-collar": CommunityType.BLUE_COLLAR,
    "blue_collar": CommunityType.BLUE_COLLAR,
    "football factory": CommunityType.FOOTBALL_FACTORY,
    "football_factory": CommunityType.FOOTBALL_FACTORY,
}


def parse_rivals_from_json(raw: Any) -> List[str]:
    """Parse optional rivals from teams.json or save dict (list of exact team names)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [p.strip() for p in raw.replace("·", ",").split(",") if p.strip()]
    return []


def league_team_static_lookup(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Team name -> static league JSON fields (stadium_name, rivals) for save backfill."""
    out: Dict[str, Dict[str, Any]] = {}
    for cfg in load_teams_from_json(path):
        if not isinstance(cfg, dict):
            continue
        name = str(cfg.get("name") or "").strip()
        if not name:
            continue
        entry: Dict[str, Any] = {}
        stadium = str(cfg.get("stadium_name") or "").strip()
        if stadium:
            entry["stadium_name"] = stadium
        rivals = parse_rivals_from_json(cfg.get("rivals"))
        if rivals:
            entry["rivals"] = rivals
        if entry:
            out[name] = entry
    return out


def enrich_save_teams_from_league_json(state: Dict[str, Any], path: Optional[str] = None) -> bool:
    """
    Backfill stadium_name and rivals from data/teams.json when missing on saved teams.
    Returns True if any team row was updated.
    """
    teams = state.get("teams")
    if not isinstance(teams, list):
        return False
    lookup = league_team_static_lookup(path)
    if not lookup:
        return False
    changed = False
    for t in teams:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "").strip()
        src = lookup.get(name)
        if not src:
            continue
        if not str(t.get("stadium_name") or "").strip() and src.get("stadium_name"):
            t["stadium_name"] = src["stadium_name"]
            changed = True
        rivals = t.get("rivals")
        if (not rivals or rivals == []) and src.get("rivals"):
            t["rivals"] = list(src["rivals"])
            changed = True
    return changed


def _default_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, TEAMS_JSON_PATH)


def _parse_community(value: Any) -> CommunityType:
    """Convert JSON community value to CommunityType."""
    if isinstance(value, CommunityType):
        return value
    s = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return _COMMUNITY_MAP.get(s, CommunityType.SUBURBAN)


def load_teams_from_json(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load team configs from teams.json. Returns list of team config dicts.
    Does NOT create Team objects or rosters; use build_teams_from_json for that.
    """
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    if not path_exists_any(plain):
        return []
    with open_text_with_path_fallback(plain, "r") as f:
        data = json.load(f)
    return data.get("teams", [])


def load_league_config_from_json(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the *full* league config (top-level dict) from a teams JSON file.

    Returned dict carries every top-level key declared in the JSON — including
    ``playoff_system`` — alongside the team rows. Returns an empty dict if the
    file is missing so callers can rely on ``.get(...)`` with defaults.

    Use this when you need league-level metadata such as the playoff system
    id; use ``load_teams_from_json`` when you only need the team rows.
    """
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    if not path_exists_any(plain):
        return {}
    with open_text_with_path_fallback(plain, "r") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def playoff_system_id_from_config(
    config: Optional[Dict[str, Any]],
    *,
    default: str = DEFAULT_PLAYOFF_SYSTEM_ID,
) -> str:
    """
    Extract the ``playoff_system`` id from a league config dict.

    Falls back to ``default`` when the field is missing/blank/non-string so
    legacy JSON files (and ad-hoc setups) still resolve to the WV system.
    """
    if not isinstance(config, dict):
        return default
    raw = config.get("playoff_system")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return default


def build_teams_from_json(
    path: Optional[str] = None,
    generate_roster: bool = True,
    two_way_chance: float = 0.55,
    assign_coaches: bool = True,
) -> Dict[str, Team]:
    """
    Load teams from teams.json, create Team objects, optionally generate rosters and assign coaches.
    Returns dict of team_name -> Team.
    """
    configs = load_teams_from_json(path)
    return build_teams_from_configs(
        configs,
        generate_roster=generate_roster,
        two_way_chance=two_way_chance,
        assign_coaches=assign_coaches,
    )


def build_teams_from_configs(
    configs: List[Dict[str, Any]],
    generate_roster: bool = True,
    two_way_chance: float = 0.55,
    assign_coaches: bool = True,
) -> Dict[str, Team]:
    """Create Team objects from already-loaded team config rows."""
    if not configs:
        return {}
    teams: Dict[str, Team] = {}
    for cfg in configs:
        name = cfg.get("name", "").strip()
        if not name:
            continue

        community = _parse_community(cfg.get("community", "suburban"))
        prestige = int(cfg.get("prestige", 5))
        nickname_raw = cfg.get("nickname", cfg.get("mascot"))
        nickname = str(nickname_raw).strip() if nickname_raw is not None and str(nickname_raw).strip() else None
        classification = cfg.get("classification") or ""
        region_raw = cfg.get("region")
        region = str(region_raw).strip() if region_raw is not None and str(region_raw).strip() else None
        culture_grade = int(cfg.get("culture_grade", cfg.get("culture", 5)))
        booster_support = int(cfg.get("booster_support", 5))
        enrollment = cfg.get("enrollment")
        facilities_grade = int(cfg.get("facilities_grade", 5))

        from systems.prestige_system import default_team_points_for_prestige, prestige_from_team_points

        start_tp = default_team_points_for_prestige(prestige)
        team = Team(
            name=name,
            nickname=nickname,
            stadium_name=str(cfg.get("stadium_name") or "").strip() or None,
            rivals=parse_rivals_from_json(cfg.get("rivals")),
            prestige=prestige_from_team_points(start_tp),
            team_points=start_tp,
            team_points_last_delta=0.0,
            community_type=community,
            classification=classification if classification else None,
            region=region,
            culture_grade=culture_grade,
            booster_support=booster_support,
            enrollment=int(enrollment) if enrollment is not None else None,
            facilities_grade=facilities_grade,
        )
        teams[name] = team

    if generate_roster:
        from systems.generate_team_roster import generate_team_roster
        for team in teams.values():
            generate_team_roster(team, two_way_chance=two_way_chance)

    if assign_coaches:
        from systems.coach_generator import assign_coaches_to_teams
        assign_coaches_to_teams(list(teams.values()))

    return teams
