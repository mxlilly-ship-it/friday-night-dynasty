"""
Recruiting system for incoming ninth-grade freshmen.
Controls quality of incoming players based on program attractiveness, coach recruiting,
community type (talent pipelines), prestige, recent success, and program stability.
Golden-generation rolls mostly juice potential; varsity-ready frosh outliers are driven by rare overall bands.
"""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from models.community import CommunityType, get_community_rating
from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team


# Golden generation: bad program lands unusually high-ceiling freshmen (potential-heavy; stays raw physically)
GOLDEN_GENERATION_CHANCE = 0.005  # 0.5% per recruit when recruiting_score is low enough

# Stochastic overall ceiling (applied after dampening): ~once per ten league-years at ~1.2k freshmen/year
GENERATIONAL_HS_FRESHMAN_CHANCE = 1.0 / 12000.0


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

    # Current-skill modifier stays tiny — development carries long-term upside.
    attr_mod = max(-7, min(2, talent_mod // 5))

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
    # Golden generation: bad program steals a developmental gem (mostly upside, not varsity-ready bodies)
    if context.golden_generation_roll > 0 and random.random() < context.golden_generation_roll:
        player.potential = min(RATING_ATTR_MAX, player.potential + random.randint(15, 26))
        for attr in ["speed", "agility", "strength", "football_iq"]:
            if hasattr(player, attr):
                v = getattr(player, attr)
                setattr(player, attr, min(RATING_ATTR_MAX, v + random.randint(1, 3)))

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


# Attributes that meaningfully move `calculate_player_overall` when nudged (trim/boost).
_OVERALL_LEVER_ATTRS: Dict[str, Tuple[str, ...]] = {
    "QB": ("throw_power", "throw_accuracy", "decisions", "football_iq", "speed", "agility", "elusiveness"),
    "RB": ("speed", "agility", "acceleration", "vision", "break_tackle", "ball_security", "catching", "strength"),
    "WR": ("speed", "agility", "acceleration", "catching", "route_running", "ball_security", "vision"),
    "OL": ("run_blocking", "pass_blocking", "strength", "agility", "balance"),
    "TE": ("catching", "run_blocking", "strength", "speed", "route_running", "vision"),
    "DE": ("pass_rush", "run_defense", "block_shedding", "strength", "speed", "tackling"),
    "DT": ("strength", "run_defense", "block_shedding", "pass_rush", "tackling"),
    "LB": ("tackling", "pursuit", "coverage", "run_defense", "speed", "strength"),
    "CB": ("coverage", "speed", "agility", "acceleration", "tackling"),
    "S": ("coverage", "tackling", "speed", "agility", "football_iq", "pursuit"),
    "K": ("kick_power", "kick_accuracy"),
    "P": ("kick_power", "kick_accuracy"),
}

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
    Compress ninth-grade current ratings toward JV / freshman-ball — most overalls stay under ~45 after trim.
    Top programs widen slightly; varsity-starting freshmen are scarce and handled via overall cap rolls.
    Does not change potential, growth_rate, or bloomer traits.
    """
    # JV / ninth-grade readiness. Scale + cap are intentionally tight so most freshmen
    # land 30-50 OVR; only the rare overall-band tier (and Winter/Spring development on top
    # of those) can ever push a freshman past the mid-60s.
    anchor = 30
    scale = 0.32 + (recruiting_score - 50.0) / 280.0
    scale = max(0.27, min(0.42, scale))
    recruit = max(0.0, min(100.0, recruiting_score))
    cap = max(42, min(54, int(41 + recruit / 8.5)))
    for attr in _FRESHMAN_DAMPEN_ATTRS:
        if not hasattr(player, attr):
            continue
        v = int(getattr(player, attr))
        v = max(anchor, v)
        new_v = anchor + int(round((v - anchor) * scale))
        setattr(player, attr, max(RATING_ATTR_MIN, min(cap, new_v)))


def _incoming_freshman_overall_band(team: "Team") -> Tuple[Optional[int], int]:
    """
    (optional_floor, ceiling) tier for freshmen overall.
    Most draws only set a ceiling (floor None) — raw JV bodies stay low.
    Rare tiers also set a floor so standouts can crack JV+/varsity bands occasionally.

    Distribution targets (per league per offseason, ~2k freshmen):
      - ~80%   land 10-50 (raw JV bodies, the clear majority)
      - ~15-18% land in the 50-60s ("better ones" — fringe varsity / JV+ talent)
      - ~1-2%  touch the low 60s; only a true outlier above 70 via the
               generational unicorn roll (≈1 per league per decade)
    Above 75 should always feel like a special talent, not a "tier-2 freshman".
    """
    comm = getattr(team, "community_type", None)
    ff = aff = False
    if comm == CommunityType.FOOTBALL_FACTORY:
        ff = True
    elif comm == CommunityType.AFFLUENT:
        aff = True

    r = random.random()
    geo = random.randint(0, 4) if ff else (random.randint(0, 2) if aff else 0)

    # Ultra-rare unicorn — the only path that can cross 75 OVR (≈1 per league per decade).
    if r < GENERATIONAL_HS_FRESHMAN_CHANCE:
        floor = random.randint(70, 74) + min(geo // 3, 2)
        ceil = min(80, floor + random.randint(2, 6))
        if ceil <= floor:
            ceil = floor + random.randint(2, 4)
        return floor, ceil

    # "Headline" frosh — best in their class for the year. Deliberately rare: ~0.30%.
    # ~5-7 across a full league per offseason; tops out in the low 70s.
    if r < 0.003:
        floor = random.randint(60, 65) + min(geo // 2, 2)
        ceil = min(72, floor + random.randint(3, 7))
        if ceil <= floor + 2:
            ceil = floor + random.randint(3, 6)
        return floor, ceil

    # JV+ tier — clearly above-average, lands mid-50s to low 60s. ~1.7% incremental.
    if r < 0.020:
        floor = random.randint(52, 58) + min(geo // 2, 2)
        ceil = min(64, floor + random.randint(3, 8))
        if ceil <= floor + 2:
            ceil = floor + random.randint(3, 6)
        return max(RATING_ATTR_MIN + 12, floor), ceil

    # "Better ones" — the meaningful 50-60s tier the user described. ~13% incremental.
    if r < 0.150:
        floor = random.randint(44, 51) + min(geo // 2, 2)
        spread = random.randint(4, random.randint(6, 10))
        ceil = min(60, floor + spread)
        if ceil <= floor + 4:
            ceil = floor + random.randint(4, 8)
        return max(RATING_ATTR_MIN + 10, floor), ceil

    # Clear majority stay developmental (10-50 overall dominates).
    if r < 0.93:
        return None, min(50, random.randint(28, 46) + min(geo + 2, 5))
    # Slightly broader tail for the long-shot "might catch on by JV" frosh.
    return None, min(54, random.randint(32, 50) + min(geo + 2, 5))


def _freshman_boost_attr_ceiling(lo: Optional[int]) -> int:
    """Per-attribute ceiling used by the OVR-band boost loop.

    Tighter than RATING_ATTR_MAX so the boost loop can't quietly push individual
    attrs into the 80s/90s when nudging a frosh up to a tier floor.
    """
    if lo is None:
        return 56
    if lo >= 70:
        # Unicorn: a couple of premier attrs can sit in the high 70s/low 80s,
        # but most still cluster lower so OVR caps where the band says.
        return 80
    if lo >= 58:
        return 70
    if lo >= 50:
        return 64
    return 58


def _apply_incoming_freshman_overall_band(player: "Player", lo: Optional[int], hi: int) -> None:
    """Trim down above hi; if lo is set, raise positional overall toward the band floor efficiently."""
    from systems.team_ratings import calculate_player_overall

    pos = str(getattr(player, "position", "") or "")
    base = _OVERALL_LEVER_ATTRS.get(pos, ())
    pool = [a for a in base if hasattr(player, a)]
    if not pool:
        pool = [a for a in _FRESHMAN_DAMPEN_ATTRS if hasattr(player, a)]
    if not pool:
        return

    ceil_attr = _freshman_boost_attr_ceiling(lo)
    stall = 0
    step_down = 0
    cur = calculate_player_overall(player)

    while cur > hi and step_down < 320:
        step_down += 1
        attr = random.choice(pool)
        v = int(getattr(player, attr))
        if v > RATING_ATTR_MIN + 1:
            setattr(player, attr, v - 1)
            stall = 0
        else:
            stall += 1
            if stall > 140:
                break
        prev = cur
        cur = calculate_player_overall(player)
        if cur == prev and step_down > 200:
            break

    if lo is None:
        return

    target_lo = max(RATING_ATTR_MIN + 11, lo)
    cur = calculate_player_overall(player)
    stall = 0
    step_up = 0
    while cur < target_lo and step_up < 420:
        step_up += 1
        attr = random.choice(pool)
        v = int(getattr(player, attr))
        gap = target_lo - cur
        bump = 1 + (1 if gap > 10 else 0) + (1 if gap > 18 else 0)
        bump = min(bump, max(1, ceil_attr - v))
        if bump > 0 and v < ceil_attr:
            setattr(player, attr, min(ceil_attr, v + bump))
            stall = 0
        else:
            stall += 1
            if stall > 120:
                break
        prev = cur
        cur = calculate_player_overall(player)
        if cur == prev and step_up > 160:
            break


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
    band = _incoming_freshman_overall_band(team)
    _apply_incoming_freshman_overall_band(player, band[0], band[1])
    return player
