"""
Recruiting system for incoming ninth-grade freshmen.
Controls quality of incoming players based on program attractiveness, coach recruiting,
community type (talent pipelines), prestige, recent success, and program stability.
Rare "golden generation" allows bad programs to occasionally land a great player.
"""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from models.community import CommunityType, get_community_rating
from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team


# Golden generation: bad program lands a great player (very rare)
GOLDEN_GENERATION_CHANCE = 0.005  # 0.5% per recruit for programs with low recruiting score


@dataclass
class RecruitingContext:
    """Computed recruiting context for a team when generating incoming freshmen."""
    talent_modifier: int = 0          # -8 to +10; added to potential
    attribute_modifier: int = 0       # small swing on current skills only (see compute_recruiting_context)
    golden_generation_roll: float = 0.0  # If random() < this, apply golden gen
    pipeline_bonus: Dict[str, int] = field(default_factory=dict)  # position -> bonus (0-6)


def get_recent_success(team: "Team", league_history: Optional[Dict[str, Any]] = None) -> float:
    """
    Score recent success from league history (0-1).
    Championships, runner-ups, wins over last 3 seasons.
    """
    if league_history is None:
        league_history = _load_league_history_safe()
    seasons = league_history.get("seasons", [])[-3:]  # Last 3 seasons
    if not seasons:
        return 0.5  # Neutral if no history
    score = 0.5
    for s in seasons:
        champ = s.get("state_champion", "")
        runner = s.get("runner_up", "")
        standings = {x["team"]: x for x in s.get("standings", [])}
        entry = standings.get(team.name, {})
        wins = entry.get("wins", 0)
        if champ == team.name:
            score += 0.15
        elif runner == team.name:
            score += 0.08
        if wins >= 3:
            score += 0.04
        elif wins >= 2:
            score += 0.02
    return min(1.0, score)


def get_program_stability(team: "Team") -> float:
    """
    Program stability score (0-1).
    Culture, facilities, community stability.
    """
    culture = getattr(team, "culture_grade", 5) or 5
    facilities = getattr(team, "facilities_grade", 5) or 5
    community = getattr(team, "community_type", None)
    stability = get_community_rating(community, "stability") if community else 5
    raw = (culture / 10.0) * 0.4 + (facilities / 10.0) * 0.3 + (stability / 10.0) * 0.3
    return min(1.0, raw)


def compute_recruiting_score(
    team: "Team",
    league_history: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Compute recruiting score (0-100) for a program.
    Higher = better ability to attract talented freshmen.
    Factors: prestige, coach recruiting, community, recent success, stability.
    """
    prestige = getattr(team, "prestige", 5) or 5
    prestige_score = (prestige - 1) / 14.0 * 25  # 0-25

    coach = getattr(team, "coach", None)
    coach_recruit = getattr(coach, "recruiting", 5) if coach else 5
    coach_score = (coach_recruit - 1) / 9.0 * 20  # 0-20

    community = getattr(team, "community_type", None)
    talent = get_community_rating(community, "talent_pool") if community else 5
    exposure = get_community_rating(community, "exposure") if community else 5
    community_score = ((talent + exposure) / 2 - 1) / 9.0 * 20  # 0-20

    recent = get_recent_success(team, league_history)
    recent_score = recent * 15  # 0-15

    stability = get_program_stability(team)
    stability_score = stability * 20  # 0-20

    raw = prestige_score + coach_score + community_score + recent_score + stability_score
    return max(0, min(100, raw))


def get_talent_pipeline_bonuses(community_type: Optional[CommunityType]) -> Dict[str, int]:
    """
    Community-based talent pipelines: which positions tend to produce better players.
    Returns position -> bonus (0-6) for attribute/potential bumps.
    """
    if community_type is None:
        return {}
    pipelines: Dict[CommunityType, Dict[str, int]] = {
        CommunityType.RURAL: {"RB": 4, "LB": 3, "OL": 2, "TE": 2},
        CommunityType.URBAN: {"WR": 5, "CB": 4, "S": 3, "QB": 2},
        CommunityType.SUBURBAN: {"QB": 3, "WR": 2, "LB": 2},
        CommunityType.AFFLUENT: {"QB": 4, "WR": 3, "K": 3, "P": 2},
        CommunityType.BLUE_COLLAR: {"OL": 5, "DL": 4, "TE": 3, "LB": 2},  # DL = DE+DT
        CommunityType.FOOTBALL_FACTORY: {
            "QB": 2, "RB": 2, "WR": 2, "OL": 2, "TE": 2,
            "DE": 2, "DT": 2, "LB": 2, "CB": 2, "S": 2,
        },
    }
    base = pipelines.get(community_type, {})
    out: Dict[str, int] = {}
    for pos, bonus in base.items():
        if pos == "DL":
            out["DE"] = max(out.get("DE", 0), bonus)
            out["DT"] = max(out.get("DT", 0), bonus)
        else:
            out[pos] = max(out.get(pos, 0), bonus)
    return out


def compute_recruiting_context(
    team: "Team",
    league_history: Optional[Dict[str, Any]] = None,
) -> RecruitingContext:
    """
    Compute full recruiting context for a team.
    Used when generating each incoming freshman.
    """
    score = compute_recruiting_score(team, league_history)
    community = getattr(team, "community_type", None)

    # Talent modifier: score 0-100 -> -8 to +10
    talent_mod = int((score - 50) / 5)  # 50=0, 80=+6, 20=-6
    talent_mod = max(-8, min(10, talent_mod))

    # Current-skill modifier: keep small so freshmen stay raw; ceiling mostly lives in potential.
    attr_mod = max(-6, min(3, talent_mod // 4))

    # Golden generation: only for low-score programs, very rare
    golden_chance = 0.0
    if score < 45:
        golden_chance = GOLDEN_GENERATION_CHANCE * (1.0 - score / 45)

    pipeline = get_talent_pipeline_bonuses(community)

    return RecruitingContext(
        talent_modifier=talent_mod,
        attribute_modifier=attr_mod,
        golden_generation_roll=golden_chance,
        pipeline_bonus=pipeline,
    )


def apply_recruiting_modifiers(
    player: "Player",
    team: "Team",
    position: str,
    context: RecruitingContext,
) -> None:
    """
    Apply recruiting modifiers to a freshly generated player.
    Updates player in place (potential, attributes).
    """
    # Golden generation: bad program gets a star
    if context.golden_generation_roll > 0 and random.random() < context.golden_generation_roll:
        player.potential = min(RATING_ATTR_MAX, player.potential + random.randint(15, 25))
        for attr in ["speed", "agility", "strength", "football_iq"]:
            if hasattr(player, attr):
                v = getattr(player, attr)
                setattr(player, attr, min(RATING_ATTR_MAX, v + random.randint(4, 9)))

    # Normal modifiers
    player.potential = max(40, min(RATING_ATTR_MAX, player.potential + context.talent_modifier))

    # Pipeline bonus for this position
    pipe_bonus = context.pipeline_bonus.get(position, 0)
    if pipe_bonus > 0:
        player.potential = min(RATING_ATTR_MAX, player.potential + random.randint(0, pipe_bonus))

    # Attribute floor/boost from program quality
    if context.attribute_modifier != 0:
        skill_attrs = [
            "speed", "agility", "strength", "football_iq", "catching",
            "tackling", "throw_power", "run_blocking",
        ]
        for attr in skill_attrs:
            if hasattr(player, attr):
                v = getattr(player, attr)
                new_v = v + context.attribute_modifier
                new_v = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, new_v + random.randint(-2, 2)))
                setattr(player, attr, new_v)


# Attributes that define "how good they are now" — dampen for incoming freshmen only (not potential / dev traits).
_FRESHMAN_DAMPEN_ATTRS = (
    "speed", "agility", "acceleration", "strength", "balance", "jumping",
    "stamina", "injury", "frame",
    "toughness", "effort", "football_iq", "coachability", "confidence",
    "discipline", "leadership", "composure",
    "throw_power", "throw_accuracy", "decisions", "catching",
    "run_blocking", "pass_blocking", "vision", "ball_security",
    "break_tackle", "elusiveness", "route_running", "coverage",
    "blitz", "pass_rush", "run_defense", "pursuit", "tackling", "block_shedding",
    "kick_power", "kick_accuracy",
)


def _dampen_incoming_freshman_skills(player: "Player", recruiting_score: float = 50.0) -> None:
    """
    Compress current ratings toward a raw ninth-grader profile so few are varsity-ready.
    Top programs get a slightly higher ceiling; still almost nobody should play like a senior starter.
    Does not change potential, growth_rate, or bloomer traits.
    """
    anchor = 32
    # 0.40 (weak) .. 0.52 (elite recruiting) — keeps most overalls in the 30s–50s
    scale = 0.46 + (recruiting_score - 50.0) / 450.0
    scale = max(0.40, min(0.52, scale))
    cap = 72 + int(max(0.0, min(100.0, recruiting_score) - 50.0) / 12.0)
    cap = min(78, max(70, cap))
    for attr in _FRESHMAN_DAMPEN_ATTRS:
        if not hasattr(player, attr):
            continue
        v = int(getattr(player, attr))
        v = max(anchor, v)
        new_v = anchor + int((v - anchor) * scale)
        setattr(player, attr, max(22, min(cap, new_v)))


def _load_league_history_safe() -> Dict[str, Any]:
    """Load league history if available. Returns empty dict on failure."""
    try:
        from systems.league_history import load_league_history
        return load_league_history()
    except Exception:
        return {"seasons": []}


def generate_recruited_freshman(
    team: "Team",
    position: str,
    secondary_position: Optional[str] = None,
    has_kicking: bool = False,
    league_history: Optional[Dict[str, Any]] = None,
) -> "Player":
    """
    Generate one incoming freshman with recruiting modifiers applied.
    Replaces the need to call generate_player + manual modifier application.
    """
    from systems.player_generator import generate_player, TWO_WAY_PAIRS

    context = compute_recruiting_context(team, league_history)
    recruit_score = compute_recruiting_score(team, league_history)

    community = getattr(team, "community_type", None) or CommunityType.SUBURBAN
    prestige = getattr(team, "prestige", 5) or 5

    player = generate_player(
        position=position,
        community_type=community,
        secondary_position=secondary_position,
        has_kicking=has_kicking,
        team_prestige=prestige,
        classification=getattr(team, "classification", None),
        coach=getattr(team, "coach", None),
        age=14,
    )
    player.year = 9

    apply_recruiting_modifiers(player, team, position, context)
    _dampen_incoming_freshman_skills(player, recruiting_score=recruit_score)
    return player
