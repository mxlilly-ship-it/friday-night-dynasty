"""
Player development year-to-year and in-season.
Based on potential, facilities, coach development ability, growth_rate,
peak_age, late_bloomer / early_bloomer, and year in school.
Also handles senior removal (graduation) and advancing age/year for multi-season sims.
"""

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team

# Attributes that can improve with development (skill ratings; exclude meta/dev traits)
DEVELOPABLE_ATTRIBUTES = [
    "speed", "agility", "acceleration", "strength", "balance", "jumping",
    "stamina", "injury", "frame",
    "toughness", "effort", "football_iq", "coachability", "confidence",
    "discipline", "leadership", "composure",
    "throw_power", "throw_accuracy", "decisions", "catching",
    "run_blocking", "pass_blocking", "vision", "ball_security",
    "break_tackle", "elusiveness", "route_running", "coverage",
    "blitz", "pass_rush", "run_defense", "pursuit", "tackling", "block_shedding",
    "kick_power", "kick_accuracy",
]

# Winter Phase: physical development (strength vs speed/quickness)
WINTER_STRENGTH_ATTRS = ["strength"]
WINTER_SPEED_ATTRS = ["speed", "agility", "acceleration"]
WINTER_TRAINING_CATEGORIES = (
    "squat",
    "bench",
    "cleans",
    "cod",
    "speed",
    "plyometrics",
    "football_iq",
)
WINTER_SESSION_MODIFIERS = {
    "Winter 1": 0.75,
    "Winter 2": 1.0,
}
WINTER_PRIMARY_BASE_GAIN = 0.022
WINTER_SECONDARY_BASE_GAIN = 0.011

# Each category has a primary and secondary target attribute.
# "Injury resistance" maps to `injury` (higher is better), "Awareness" maps to `football_iq`.
WINTER_TRAINING_ATTRIBUTE_MAP: Dict[str, Dict[str, str]] = {
    "squat": {"primary": "strength", "secondary": "acceleration"},
    "bench": {"primary": "strength", "secondary": "injury"},
    "cleans": {"primary": "speed", "secondary": "agility"},
    "cod": {"primary": "agility", "secondary": "acceleration"},
    "speed": {"primary": "speed", "secondary": "jumping"},
    "plyometrics": {"primary": "jumping", "secondary": "agility"},
    "football_iq": {"primary": "football_iq", "secondary": "coachability"},
}

# Light positional influence for optional realism.
WINTER_POSITIONAL_TAGS: Dict[str, str] = {
    "QB": "qb",
    "RB": "skill",
    "WR": "skill",
    "TE": "trenches",
    "OL": "trenches",
    "DE": "trenches",
    "DT": "trenches",
    "LB": "hybrid",
    "CB": "skill",
    "S": "skill",
    "K": "special",
    "P": "special",
}
WINTER_CATEGORY_POSITIONAL_MODS: Dict[str, Dict[str, float]] = {
    "squat": {"trenches": 1.08},
    "bench": {"trenches": 1.08},
    "cleans": {"skill": 1.05},
    "cod": {"skill": 1.08},
    "speed": {"skill": 1.1},
    "plyometrics": {"skill": 1.08},
    "football_iq": {"qb": 1.1},
}

# Spring Ball focus options
SPRING_OFFENSE_FOCUS_OPTIONS = (
    "run_blocking",
    "pass_protection",
    "receiving",
    "pass_game",
    "run_game",
)
SPRING_DEFENSE_FOCUS_OPTIONS = (
    "run_defense",
    "pass_rush",
    "tackling",
    "pass_defense",
    "block_defeat",
)

# High school: year 9 = freshman, 10 = sophomore, 11 = junior, 12 = senior
SENIOR_YEAR = 12
FRESHMAN_YEAR = 9
GRADUATION_AGE = 18


def _get_player_year(player: "Player") -> int:
    """Return year in school (9-12). Infer from age if year not set."""
    if player.year is not None and 9 <= player.year <= 12:
        return player.year
    age = player.age if player.age is not None else 15
    # 14->9, 15->10, 16->11, 17-18->12
    return min(SENIOR_YEAR, FRESHMAN_YEAR + max(0, age - 14))


def _get_player_age(player: "Player") -> int:
    """Return age (14-18)."""
    return player.age if player.age is not None else 15


def _age_curve_multiplier(player: "Player") -> float:
    """
    How much this player benefits from development based on age vs peak.
    early_bloomer (high) = peak earlier; late_bloomer (high) = peak later.
    Returns 0.3 to 1.0.
    """
    age = _get_player_age(player)
    peak = player.peak_age
    # Shift effective peak: early_bloomer pushes peak left, late_bloomer right
    shift = (player.late_bloomer - player.early_bloomer) / 100  # -1 to +1 in practice
    effective_peak = peak + shift * 2  # e.g. 16 + 1 = 17
    effective_peak = max(14, min(18, effective_peak))
    distance = abs(age - effective_peak)
    # 0 distance = 1.0, 2+ distance = 0.3
    mult = 1.0 - (distance * 0.25)
    return max(0.3, min(1.0, mult))


def _development_gain(
    player: "Player",
    team: "Team",
    attribute: str,
    is_offseason: bool = True,
) -> int:
    """
    Compute how much to add to one attribute this period.
    Room = potential - current (capped); gain scaled by facilities, coach, growth_rate, age curve.
    """
    current = getattr(player, attribute, 50)
    potential = player.potential
    room = max(0, potential - current)
    if room <= 0:
        return 0

    facilities = getattr(team, "facilities_grade", 5) or 5
    facility_factor = 0.6 + (facilities / 10) * 0.4  # 0.6 to 1.0

    coach_dev = 5
    if team.coach is not None:
        coach_dev = getattr(team.coach, "player_development", 5)
    coach_factor = 0.6 + (coach_dev / 10) * 0.4  # 0.6 to 1.0

    growth_factor = player.growth_rate / 100.0
    age_factor = _age_curve_multiplier(player)

    # Year bonus: underclassmen can have slightly higher ceiling (more growth left)
    year = _get_player_year(player)
    year_factor = 1.0 + (SENIOR_YEAR - year) * 0.02  # seniors 1.0, freshmen ~1.06

    base_gain = room * growth_factor * facility_factor * coach_factor * age_factor * year_factor
    if is_offseason:
        base_gain *= 2.0  # off-season is main development period
    # Random variance
    gain = int(base_gain * random.uniform(0.5, 1.5))
    return max(0, min(room, gain))


def develop_player(
    player: "Player",
    team: "Team",
    is_offseason: bool = True,
    attributes: Optional[List[str]] = None,
) -> int:
    """
    Apply development to one player. Updates attributes in place.
    Returns total points added across all attributes.
    """
    attrs = attributes or DEVELOPABLE_ATTRIBUTES
    total_gain = 0
    for attr in attrs:
        if not hasattr(player, attr):
            continue
        gain = _development_gain(player, team, attr, is_offseason=is_offseason)
        if gain > 0:
            current = getattr(player, attr, 50)
            new_val = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, current + gain))
            setattr(player, attr, new_val)
            total_gain += gain
    return total_gain


def _small_boost_cap(player: "Player", team: "Team", attr: str) -> int:
    """Room to grow for small boosts (capped so winter/spring stay small)."""
    current = getattr(player, attr, 50)
    room = max(0, player.potential - current)
    return min(room, 5)  # never add more than 5 in a single small phase


def _winter_efficiency(points: int) -> float:
    p = max(0, min(RATING_ATTR_MAX, int(points)))
    if p <= 10:
        return 0.10
    if p <= 20:
        return 0.40
    if p <= 39:
        return 0.75
    if p <= 60:
        return 1.00
    if p <= 75:
        return 0.80
    if p <= 90:
        return 0.50
    return 0.25


def normalize_winter_training_allocations(raw: Optional[dict]) -> Dict[str, int]:
    """Normalize arbitrary input to valid 7-category, 100-point winter allocations."""
    values: Dict[str, int] = {}
    src = raw if isinstance(raw, dict) else {}
    for cat in WINTER_TRAINING_CATEGORIES:
        try:
            values[cat] = max(0, int(src.get(cat, 0)))
        except (TypeError, ValueError):
            values[cat] = 0
    total = sum(values.values())
    if total <= 0:
        # Default balanced profile (close to optimal bell-curve band).
        return {
            "squat": 15,
            "bench": 15,
            "cleans": 15,
            "cod": 15,
            "speed": 15,
            "plyometrics": 15,
            "football_iq": 10,
        }
    if total == 100:
        return values
    # Scale to exactly 100 while preserving distribution.
    scaled = {k: int((v / total) * 100) for k, v in values.items()}
    diff = 100 - sum(scaled.values())
    order = sorted(WINTER_TRAINING_CATEGORIES, key=lambda c: values[c], reverse=True)
    i = 0
    while diff != 0 and order:
        key = order[i % len(order)]
        if diff > 0:
            scaled[key] += 1
            diff -= 1
        elif scaled[key] > 0:
            scaled[key] -= 1
            diff += 1
        i += 1
        if i > 1000:
            break
    return scaled


def build_ai_winter_training_allocations(team: "Team") -> Dict[str, int]:
    """
    AI allocation target:
    mostly balanced (40-60 inefficient guard) with light coach/style identity.
    """
    base = {
        "squat": random.randint(12, 18),
        "bench": random.randint(10, 16),
        "cleans": random.randint(10, 16),
        "cod": random.randint(10, 16),
        "speed": random.randint(10, 16),
        "plyometrics": random.randint(10, 16),
        "football_iq": random.randint(8, 14),
    }
    coach = getattr(team, "coach", None)
    if coach is not None:
        dev = int(getattr(coach, "player_development", 5) or 5)
        style_name = str(getattr(getattr(coach, "offensive_style", None), "name", "BALANCED") or "BALANCED").upper()
        # Philosophy bias: run-heavy staffs trend toward weight room; pass-heavy toward speed/movement.
        if style_name == "HEAVY_RUN":
            base["squat"] += 8
            base["bench"] += 6
            base["cleans"] += 2
            base["speed"] -= 2
        elif style_name == "LEAN_RUN":
            base["squat"] += 5
            base["bench"] += 3
            base["speed"] -= 1
        elif style_name == "HEAVY_PASS":
            base["speed"] += 8
            base["cod"] += 6
            base["cleans"] += 4
            base["squat"] -= 2
            base["bench"] -= 2
        elif style_name == "LEAN_PASS":
            base["speed"] += 5
            base["cod"] += 4
            base["cleans"] += 2
            base["squat"] -= 1

        if dev >= 7:
            base["football_iq"] += 2
            base["cod"] += 1
        if int(getattr(coach, "playcalling", 5) or 5) >= 7:
            base["football_iq"] += 2

        # Stronger coaches self-scout and redirect part of winter work to weak areas.
        adapt_skill = (
            int(getattr(coach, "player_development", 5) or 5)
            + int(getattr(coach, "scheme_teach", 5) or 5)
            + int(getattr(coach, "playcalling", 5) or 5)
        )
        if adapt_skill >= 19:
            roster = list(getattr(team, "roster", []) or [])
            if roster:
                def _avg(attr: str) -> float:
                    vals = [float(getattr(p, attr, 50)) for p in roster]
                    return (sum(vals) / len(vals)) if vals else 50.0

                # Category quality scores: lower score = bigger weakness.
                cat_scores = {
                    "squat": (_avg("strength") * 0.7) + (_avg("run_blocking") * 0.3),
                    "bench": (_avg("strength") * 0.6) + (_avg("injury") * 0.4),
                    "cleans": (_avg("speed") * 0.6) + (_avg("agility") * 0.4),
                    "cod": (_avg("agility") * 0.55) + (_avg("acceleration") * 0.45),
                    "speed": (_avg("speed") * 0.7) + (_avg("acceleration") * 0.3),
                    "plyometrics": (_avg("jumping") * 0.6) + (_avg("agility") * 0.4),
                    "football_iq": (_avg("football_iq") * 0.65) + (_avg("coachability") * 0.35),
                }
                # Redirect more aggressively for elite development staffs.
                shift_budget = 4 if adapt_skill < 23 else 7
                weakest = sorted(cat_scores.items(), key=lambda kv: kv[1])[:3]
                strongest = sorted(cat_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
                w_idx = 0
                s_idx = 0
                while shift_budget > 0 and weakest and strongest:
                    w_cat = weakest[w_idx % len(weakest)][0]
                    s_cat = strongest[s_idx % len(strongest)][0]
                    if w_cat == s_cat:
                        s_idx += 1
                        continue
                    if base.get(s_cat, 0) > 6:
                        base[s_cat] -= 1
                        base[w_cat] = base.get(w_cat, 0) + 1
                        shift_budget -= 1
                    else:
                        s_idx += 1
                    w_idx += 1
    return normalize_winter_training_allocations(base)


def _winter_feedback_messages(allocations: Dict[str, int]) -> List[str]:
    msgs: List[str] = []
    for cat in WINTER_TRAINING_CATEGORIES:
        pts = int(allocations.get(cat, 0))
        eff = _winter_efficiency(pts)
        label = cat.replace("_", " ").title()
        if 40 <= pts <= 60:
            msgs.append(f"Your balanced focus on {label} is maximizing player development.")
        elif pts >= 76:
            msgs.append(f"Overloading {label} drills is reducing efficiency.")
        elif pts <= 10:
            msgs.append(f"Minimal investment in {label} is limiting gains in that area.")
    if sum(1 for c in WINTER_TRAINING_CATEGORIES if 40 <= int(allocations.get(c, 0)) <= 60) >= 2:
        msgs.append("Your staff is building a reputation for explosive, balanced winter training.")
    if not msgs:
        msgs.append("Winter sessions delivered modest progress across multiple groups.")
    # Keep results concise.
    return msgs[:4]


def run_winter_training_session(
    team: "Team",
    allocations: Optional[Dict[str, int]],
    stage_name: str,
) -> Dict[str, Any]:
    """
    Winter 1 / Winter 2 controlled gains with bell-curve efficiency and 100-point allocations.
    Returns a UI-ready results payload and applies ratings in-place.
    """
    alloc = normalize_winter_training_allocations(allocations)
    session_modifier = WINTER_SESSION_MODIFIERS.get(str(stage_name), 1.0)
    facilities = int(getattr(team, "facilities_grade", 5) or 5)
    coach = getattr(team, "coach", None)
    coach_dev = int(getattr(coach, "player_development", 5) or 5) if coach else 5
    team_scale = (0.92 + (facilities - 5) * 0.015) * (0.92 + (coach_dev - 5) * 0.015)
    team_scale = max(0.78, min(1.18, team_scale))
    # Guardrails so Winter sessions stay meaningful but clearly below full offseason development.
    session_player_cap = 2 if str(stage_name) == "Winter 1" else 3
    team_total_cap = max(22, int(len(getattr(team, "roster", []) or []) * (0.65 if str(stage_name) == "Winter 1" else 0.9)))
    team_points_applied = 0

    player_rows: List[Dict[str, Any]] = []
    key_events: List[Dict[str, Any]] = []
    category_totals = {c: 0.0 for c in WINTER_TRAINING_CATEGORIES}

    for player in list(team.roster):
        p_name = str(getattr(player, "name", "Player"))
        p_pos = str(getattr(player, "position", "") or "")
        p_tag = WINTER_POSITIONAL_TAGS.get(p_pos, "hybrid")
        per_attr_gain: Dict[str, float] = {}
        player_total = 0.0
        age_scalar = 0.75 + (_age_curve_multiplier(player) * 0.35)
        growth_scalar = 0.75 + (max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(getattr(player, "growth_rate", 50)))) / 100.0) * 0.5
        for cat in WINTER_TRAINING_CATEGORIES:
            if team_points_applied >= team_total_cap:
                break
            pts = int(alloc.get(cat, 0))
            eff = _winter_efficiency(pts)
            mapping = WINTER_TRAINING_ATTRIBUTE_MAP[cat]
            pos_mod = WINTER_CATEGORY_POSITIONAL_MODS.get(cat, {}).get(p_tag, 1.0)
            primary_raw = pts * eff * session_modifier * WINTER_PRIMARY_BASE_GAIN * team_scale * pos_mod
            secondary_raw = pts * eff * session_modifier * WINTER_SECONDARY_BASE_GAIN * team_scale * pos_mod
            for attr, raw in ((mapping["primary"], primary_raw), (mapping["secondary"], secondary_raw)):
                if not hasattr(player, attr):
                    continue
                cur = int(getattr(player, attr, 50))
                room = max(0, int(getattr(player, "potential", 50)) - cur)
                if room <= 0:
                    continue
                if player_total >= session_player_cap:
                    continue
                room_scalar = max(0.15, min(1.0, room / 14.0))
                # Tie Winter to long-term development profile to avoid overcooking players over years.
                gain_float = raw * age_scalar * growth_scalar * room_scalar * random.uniform(0.88, 1.12)
                base = int(gain_float)
                frac = max(0.0, min(1.0, gain_float - base))
                roll = base + (1 if random.random() < frac else 0)
                if gain_float > 1.6 and random.random() < 0.10:
                    roll += 1
                roll = max(0, min(2, roll))
                gain = min(room, roll)
                if gain <= 0:
                    continue
                if player_total + gain > session_player_cap:
                    gain = max(0, int(session_player_cap - player_total))
                if gain <= 0:
                    continue
                if team_points_applied + gain > team_total_cap:
                    gain = max(0, int(team_total_cap - team_points_applied))
                if gain <= 0:
                    continue
                setattr(player, attr, max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, cur + gain)))
                per_attr_gain[attr] = per_attr_gain.get(attr, 0.0) + float(gain)
                player_total += float(gain)
                team_points_applied += int(gain)
                category_totals[cat] += float(gain)
                key_events.append({
                    "player_name": p_name,
                    "position": p_pos,
                    "attribute": attr,
                    "delta": int(gain),
                    "category": cat,
                })
        if player_total > 0:
            player_rows.append(
                {
                    "player_name": p_name,
                    "position": p_pos,
                    "total_delta": round(player_total, 2),
                    "attribute_deltas": {k: int(v) for k, v in per_attr_gain.items()},
                }
            )

    key_events.sort(key=lambda r: (-int(r["delta"]), str(r["player_name"]), str(r["attribute"])))
    notable = key_events[:5]
    total_points = int(sum(int(r.get("delta", 0)) for r in key_events))
    if total_points >= 52:
        summary = "Excellent Winter Session"
    elif total_points >= 28:
        summary = "Solid Winter Session"
    else:
        summary = "Minor Winter Progress"

    efficiency_rows = [
        {
            "category": cat,
            "points": int(alloc.get(cat, 0)),
            "efficiency": round(_winter_efficiency(int(alloc.get(cat, 0))), 2),
            "gains": round(float(category_totals.get(cat, 0.0)), 1),
        }
        for cat in WINTER_TRAINING_CATEGORIES
    ]

    return {
        "stage": str(stage_name),
        "allocations": alloc,
        "summary": summary,
        "total_points": total_points,
        "team_total_cap": team_total_cap,
        "efficiency_rows": efficiency_rows,
        "notable_players": notable,
        "feedback": _winter_feedback_messages(alloc),
        "player_rows": player_rows[:30],
    }


def run_winter_phase_development(team: "Team") -> None:
    """
    Winter Phase 1 or 2: small physical development based on coach allocation.
    Coach winter_strength_pct (0-100) = % toward strength; remainder = speed/quickness.
    Small natural boosts only (0-2 per attribute per phase).
    """
    coach = team.coach
    strength_pct = max(0, min(100, int(getattr(coach, "winter_strength_pct", 50) if coach else 50)))
    alloc = {
        "squat": int(round(strength_pct * 0.35)),
        "bench": int(round(strength_pct * 0.25)),
        "cleans": int(round((100 - strength_pct) * 0.3)),
        "cod": int(round((100 - strength_pct) * 0.2)),
        "speed": int(round((100 - strength_pct) * 0.25)),
        "plyometrics": int(round((100 - strength_pct) * 0.15)),
        "football_iq": 0,
    }
    run_winter_training_session(team, normalize_winter_training_allocations(alloc), "Winter 1")


def _spring_focus_attr_weights() -> dict:
    return {
        "run_blocking": {
            "OL": [("run_blocking", 1.0), ("strength", 0.35)],
            "TE": [("run_blocking", 0.7), ("strength", 0.35)],
            "RB": [("run_blocking", 0.35), ("strength", 0.2)],
        },
        "pass_protection": {
            "OL": [("pass_blocking", 1.0), ("football_iq", 0.25)],
            "TE": [("pass_blocking", 0.65), ("football_iq", 0.2)],
            "RB": [("pass_blocking", 0.35), ("football_iq", 0.15)],
        },
        "receiving": {
            "WR": [("catching", 0.95), ("route_running", 0.75)],
            "TE": [("catching", 0.75), ("route_running", 0.45)],
            "RB": [("catching", 0.4), ("route_running", 0.25)],
        },
        "pass_game": {
            "QB": [("throw_accuracy", 1.0), ("decisions", 0.65)],
            "WR": [("route_running", 0.85), ("catching", 0.75)],
            "TE": [("route_running", 0.45), ("catching", 0.45)],
        },
        "run_game": {
            "RB": [("vision", 0.9), ("break_tackle", 0.8)],
            "OL": [("run_blocking", 0.7), ("strength", 0.3)],
            "TE": [("run_blocking", 0.45), ("vision", 0.2)],
            "QB": [("decisions", 0.25)],
        },
        "run_defense": {
            "DT": [("run_defense", 1.0), ("block_shedding", 0.6)],
            "DE": [("run_defense", 0.75), ("block_shedding", 0.4)],
            "LB": [("run_defense", 0.7), ("pursuit", 0.45)],
            "S": [("run_defense", 0.25), ("tackling", 0.3)],
        },
        "pass_rush": {
            "DE": [("pass_rush", 1.0), ("blitz", 0.5)],
            "DT": [("pass_rush", 0.6), ("block_shedding", 0.35)],
            "LB": [("pass_rush", 0.75), ("blitz", 0.55)],
        },
        "tackling": {
            "DE": [("tackling", 0.55)],
            "DT": [("tackling", 0.55)],
            "LB": [("tackling", 0.8), ("pursuit", 0.35)],
            "CB": [("tackling", 0.55)],
            "S": [("tackling", 0.75), ("pursuit", 0.25)],
        },
        "pass_defense": {
            "CB": [("coverage", 1.0), ("football_iq", 0.35)],
            "S": [("coverage", 0.9), ("football_iq", 0.4)],
            "LB": [("coverage", 0.35), ("football_iq", 0.2)],
        },
        "block_defeat": {
            "DE": [("block_shedding", 1.0), ("run_defense", 0.35)],
            "DT": [("block_shedding", 1.0), ("run_defense", 0.45)],
            "LB": [("block_shedding", 0.65), ("blitz", 0.35)],
        },
    }


def _spring_gain_roll(weight: float, scale: float, room_cap: int) -> int:
    """Small spring-ball gain distribution: mostly 0/1, some 2, rare 3."""
    if room_cap <= 0:
        return 0
    chance = min(0.92, 0.22 * scale * max(0.2, weight))
    if random.random() > chance:
        return 0
    r = random.random()
    if r < 0.70:
        gain = 1
    elif r < 0.93:
        gain = 2
    else:
        gain = 3
    return min(room_cap, gain)


def _grade_spring_summary(total_points: int) -> str:
    if total_points >= 34:
        return "Excellent Spring"
    if total_points >= 18:
        return "Solid Spring"
    return "Minor Improvement"


def _group_avg_delta(rows: List[dict], position: str, attr: str) -> float:
    vals = [float(r["delta"]) for r in rows if r.get("position") == position and r.get("attribute") == attr]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 1)


def run_spring_ball_development(team: "Team") -> dict:
    """
    Spring Ball: targeted small improvements based on one offensive and one defensive focus.
    Returns a results payload for UI.
    """
    coach = team.coach
    off_focus = getattr(coach, "spring_offense_focus", "run_game") if coach else "run_game"
    def_focus = getattr(coach, "spring_defense_focus", "pass_defense") if coach else "pass_defense"
    if off_focus not in SPRING_OFFENSE_FOCUS_OPTIONS:
        off_focus = "run_game"
    if def_focus not in SPRING_DEFENSE_FOCUS_OPTIONS:
        def_focus = "pass_defense"

    facilities = getattr(team, "facilities_grade", 5) or 5
    coach_dev = getattr(coach, "player_development", 5) if coach else 5
    scale = (0.65 + facilities / 30.0) * (0.65 + coach_dev / 30.0)

    focus_weights = _spring_focus_attr_weights()
    focused_rows: List[dict] = []
    all_deltas: List[dict] = []
    ovr_pop_players: List[str] = []

    for player in list(team.roster):
        player_name = getattr(player, "name", "Player")
        pos_candidates = [str(getattr(player, "position", "") or "")]
        sec = str(getattr(player, "secondary_position", "") or "")
        if sec:
            pos_candidates.append(sec)
        before_ovr_proxy = sum(int(getattr(player, a, 50)) for a in ("speed", "strength", "football_iq", "tackling", "coverage", "throw_accuracy")) / 6.0
        player_gain = 0

        for focus in (off_focus, def_focus):
            mapping = focus_weights.get(focus, {})
            for pos in pos_candidates:
                for attr, weight in mapping.get(pos, []):
                    if not hasattr(player, attr):
                        continue
                    cur = int(getattr(player, attr, 50))
                    room_cap = min(max(0, int(getattr(player, "potential", 50)) - cur), 3)
                    gain = _spring_gain_roll(weight, scale, room_cap)
                    if gain <= 0:
                        continue
                    setattr(player, attr, max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, cur + gain)))
                    row = {
                        "player_name": player_name,
                        "position": pos,
                        "attribute": attr,
                        "delta": gain,
                        "focus": focus,
                    }
                    focused_rows.append(row)
                    all_deltas.append(row)
                    player_gain += gain

        # Very rare tiny overall bump marker (reporting only, not a direct stat boost)
        if player_gain > 0 and random.random() < 0.03:
            ovr_pop_players.append(player_name)

        after_ovr_proxy = sum(int(getattr(player, a, 50)) for a in ("speed", "strength", "football_iq", "tackling", "coverage", "throw_accuracy")) / 6.0
        if after_ovr_proxy > before_ovr_proxy and random.random() < 0.04:
            ovr_pop_players.append(player_name)

    focused_rows.sort(key=lambda r: (-int(r["delta"]), str(r["player_name"]), str(r["attribute"])))
    notable = focused_rows[:5]
    total_points = sum(int(r["delta"]) for r in all_deltas)

    position_group_changes = [
        {"label": "OL Run Block Avg", "delta": _group_avg_delta(all_deltas, "OL", "run_blocking")},
        {"label": "QB Throw Accuracy Avg", "delta": _group_avg_delta(all_deltas, "QB", "throw_accuracy")},
        {"label": "WR Route Running Avg", "delta": _group_avg_delta(all_deltas, "WR", "route_running")},
        {"label": "CB Coverage Avg", "delta": _group_avg_delta(all_deltas, "CB", "coverage")},
        {"label": "LB Tackling Avg", "delta": _group_avg_delta(all_deltas, "LB", "tackling")},
    ]

    neutral_feedback: List[str] = []
    if _group_avg_delta(all_deltas, "WR", "route_running") <= 0 and _group_avg_delta(all_deltas, "WR", "catching") <= 0:
        neutral_feedback.append("Limited improvement in WR group")
    if _group_avg_delta(all_deltas, "CB", "coverage") <= 0 and _group_avg_delta(all_deltas, "S", "coverage") <= 0:
        neutral_feedback.append("Minimal defensive progress this spring")
    if not neutral_feedback:
        neutral_feedback.append("Most groups saw at least minor progress this spring")

    return {
        "offensive_focus": off_focus,
        "defensive_focus": def_focus,
        "summary": _grade_spring_summary(total_points),
        "total_points": total_points,
        "position_group_changes": position_group_changes,
        "notable_players": notable,
        "overall_pop_players": sorted(set(ovr_pop_players))[:3],
        "neutral_feedback": neutral_feedback[:3],
    }


def run_offseason_development(team: "Team") -> None:
    """Training Results: full offseason development for every player (main growth period)."""
    for player in list(team.roster):
        develop_player(player, team, is_offseason=True)


def in_season_development(team: "Team", games_played: int = 1) -> None:
    """
    Small in-season development (e.g. call after each game or weekly).
    games_played: number of games to account for (smaller gains per game).
    """
    for player in list(team.roster):
        develop_player(player, team, is_offseason=False)
    # Scale down: we already use is_offseason=False which is 0.5x; could further reduce per game
    # For now one call per "in_season_development" - caller can call every N games with small effect


def remove_graduated_players(team: "Team") -> List["Player"]:
    """
    Remove seniors who have completed their eligibility (year == 12 or age >= 18).
    Returns list of removed players.
    """
    removed = []
    for player in list(team.roster):
        year = _get_player_year(player)
        age = _get_player_age(player)
        if year >= SENIOR_YEAR or age >= GRADUATION_AGE:
            team.remove_player(player)
            removed.append(player)
    return removed


def advance_age_and_year(team: "Team") -> None:
    """
    Advance every remaining player: age += 1, year += 1 (cap year at 12).
    Call after remove_graduated_players so only returning players are advanced.
    """
    for player in team.roster:
        player.age = (_get_player_age(player) + 1)
        y = _get_player_year(player)
        player.year = min(SENIOR_YEAR, y + 1)


def add_incoming_freshmen(
    team: "Team",
    target_roster_size: Optional[int] = None,
    community_type=None,
    two_way_chance: float = 0.55,
    kicking_chance: float = 0.12,
    league_history: Optional[dict] = None,
) -> List["Player"]:
    """
    Add new freshmen (age 14, year 9) to fill roster toward target size.
    Uses recruiting system: prestige, coach recruiting, community, recent success,
    stability, and talent pipelines control quality. Rare golden generation for bad programs.
    Returns list of added players.
    """
    from systems.recruiting_system import generate_recruited_freshman
    from systems.generate_team_roster import calculate_roster_size, _scale_position_counts
    from systems.player_generator import TWO_WAY_PAIRS

    if target_roster_size is None:
        target_roster_size = calculate_roster_size(team)
    current = len(team.roster)
    need = max(0, target_roster_size - current)
    if need == 0:
        return []

    # Build position list in proportion to target roster (so we add balanced positions)
    position_counts = _scale_position_counts(target_roster_size)
    positions_expanded = [p for p, c in position_counts.items() for _ in range(c)]
    random.shuffle(positions_expanded)
    added: List["Player"] = []
    for i in range(need):
        pos = positions_expanded[i % len(positions_expanded)]
        sec = None
        if random.random() < two_way_chance and pos in TWO_WAY_PAIRS and TWO_WAY_PAIRS[pos]:
            sec = random.choice(TWO_WAY_PAIRS[pos])
        kick = random.random() < kicking_chance or pos in ("K", "P")
        player = generate_recruited_freshman(
            team=team,
            position=pos,
            secondary_position=sec,
            has_kicking=kick,
            league_history=league_history,
        )
        team.add_player(player)
        added.append(player)
    return added


def run_full_offseason(
    team: "Team",
    develop: bool = True,
    add_freshmen: bool = True,
    target_roster_size: Optional[int] = None,
) -> dict:
    """
    Run full offseason: remove graduated, advance age/year, develop, add freshmen.
    Returns dict with removed_count, added_count, developed=True.
    """
    removed = remove_graduated_players(team)
    advance_age_and_year(team)
    if develop:
        run_offseason_development(team)
    added = []
    if add_freshmen:
        added = add_incoming_freshmen(team, target_roster_size=target_roster_size)
    return {
        "removed_count": len(removed),
        "removed_players": removed,
        "added_count": len(added),
        "added_players": added,
        "developed": develop,
    }
