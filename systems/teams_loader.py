"""
Load teams from data/teams.json.
Single source of truth for league setup; add teams to the JSON file to expand the league.
"""

import json
import os
from typing import Any, Dict, List, Optional

from models.team import Team
from models.community import CommunityType
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

        team = Team(
            name=name,
            nickname=nickname,
            prestige=prestige,
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
