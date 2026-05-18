"""
School program progression: Culture, Facilities, and Boosters (grades 1–10).

Each pillar tracks progress points (0–3500) toward the next level. Level-up costs
are nonlinear; losses can demote levels with refund math into the progress bar.

Tunable constants drive game-by-game deltas, postseason awards, expectations, decay,
and offseason PP spend (same cost table as live progression).

This module is pure (no I/O) aside from optional RNG for variance.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

# --- Level-up costs: points needed to go FROM level L to L+1 (L = 1..9) ---
UPGRADE_COST_BY_LEVEL: Dict[int, int] = {
    1: 100,
    2: 300,
    3: 500,
    4: 800,
    5: 1200,
    6: 1500,
    7: 1900,
    8: 2400,
    9: 3000,
}

PROGRESS_CAP = 3500

# --- Regular season ---
WIN_BASE_POINTS = 100
LOSS_CLOSE_MARGIN = 8
LOSS_CLOSE_MULTIPLIER = 0.55
BLOWOUT_MARGINS = (10, 14, 21)
BLOWOUT_BONUSES = (10, 15, 20)

LOSS_VS_STRONGER = -40
LOSS_VS_EQUAL = -75
LOSS_VS_WEAKER = -120
STRENGTH_EPS = 3.0

# Optional variance per game (set GAME_VARIANCE = 0 to disable)
GAME_VARIANCE = 5

# --- Postseason lump sums (once per season, same delta to each pillar).
# Playoff game W/L already move pillars via ``run_playoff_game`` (same formula as the regular season). ---
POSTSEASON_PLAYOFF_APPEARANCE = 150
POSTSEASON_REGIONAL_TITLE = 400
POSTSEASON_STATE_RUNNER_UP = 700
POSTSEASON_STATE_CHAMPION = 1200

# --- Expectations (end of season): auto pillar adjustment + flex PP bank ---
EXPECTATION_MEETS_PILLAR_BONUS_MAX = 100
EXPECTATION_UNDER_MIN = -1000
EXPECTATION_UNDER_MAX = -300
EXPECTATION_EXCEED_MIN = 300
EXPECTATION_EXCEED_MAX = 800

# --- Decay (per season, subtracted from each pillar's progress points) ---
DECAY_TIER_1_4 = (0, 0)
DECAY_TIER_5_7 = (-200, -100)
DECAY_TIER_8_10 = (-500, -300)

# --- Goal miss extra sting (per pillar, added when goals fail) ---
GOAL_MISS_PILLAR_PENALTY = -80


def upgrade_cost(from_level: int) -> int:
    """Points to move from ``from_level`` to ``from_level`` + 1."""
    L = max(1, min(9, int(from_level)))
    return int(UPGRADE_COST_BY_LEVEL.get(L, 3000))


def total_upgrade_cost_between_levels(from_level: int, to_level: int) -> int:
    """Sum of costs for each step from ``from_level`` toward ``to_level`` (exclusive of to)."""
    a = max(1, min(10, int(from_level)))
    b = max(1, min(10, int(to_level)))
    if b <= a:
        return 0
    return sum(upgrade_cost(lv) for lv in range(a, b))


def pp_delta_for_level_change(from_level: int, to_level: int) -> int:
    """
    Offseason PP change for changing a single pillar's grade (negative = spend).
    Magnitude matches progression point costs (1 PP = 1 progression point).
    """
    a = max(1, min(10, int(from_level)))
    b = max(1, min(10, int(to_level)))
    if b > a:
        return -total_upgrade_cost_between_levels(a, b)
    if b < a:
        return total_upgrade_cost_between_levels(b, a)
    return 0


PILLAR_CUMULATIVE_PP_MAX = int(sum(upgrade_cost(k) for k in range(1, 10)))


def pillar_cumulative_pp_value(level: int, progress_pts: int) -> int:
    """
    Total PP-equivalent invested in one pillar from empty L1 up through ``progress_pts``
    toward the next level (same units as ``UPGRADE_COST_BY_LEVEL`` / offseason bank).
    """
    lv = max(1, min(10, int(level)))
    pts = clamp_progress_points(progress_pts)
    total = int(sum(upgrade_cost(k) for k in range(1, lv)))
    if lv < 10:
        cap = upgrade_cost(lv)
        total += int(min(max(0, pts), cap))
    return total


def pillar_state_from_cumulative_pp_value(target_value: int) -> Tuple[int, int]:
    """Inverse of ``pillar_cumulative_pp_value``: returns (grade, progress_pts) toward next level."""
    v = max(0, min(int(PILLAR_CUMULATIVE_PP_MAX), int(target_value)))
    lv = 1
    while lv < 10:
        need = upgrade_cost(lv)
        if v < need:
            return lv, int(v)
        v -= need
        lv += 1
    return 10, 0


def team_composite_strength(ratings: Dict[str, int]) -> float:
    off = float(ratings.get("offense", 50))
    defense = float(ratings.get("defense", 50))
    return (off + defense) / 2.0


def _loss_penalty_by_relative_strength(team_strength: float, opponent_strength: float) -> int:
    """Loser's strength vs winner's strength."""
    if opponent_strength > team_strength + STRENGTH_EPS:
        return LOSS_VS_STRONGER
    if team_strength > opponent_strength + STRENGTH_EPS:
        return LOSS_VS_WEAKER
    return LOSS_VS_EQUAL


def game_progression_delta(
    *,
    team_score: int,
    opp_score: int,
    team_strength: float,
    opp_strength: float,
    rng: Optional[random.Random] = None,
) -> int:
    """Single-pillar delta for one team after one game (apply to all three pillars)."""
    won = team_score > opp_score
    margin = abs(int(team_score) - int(opp_score))
    d = 0
    if won:
        d += WIN_BASE_POINTS
        if margin >= BLOWOUT_MARGINS[2]:
            d += BLOWOUT_BONUSES[2]
        elif margin >= BLOWOUT_MARGINS[1]:
            d += BLOWOUT_BONUSES[1]
        elif margin >= BLOWOUT_MARGINS[0]:
            d += BLOWOUT_BONUSES[0]
    else:
        base = _loss_penalty_by_relative_strength(team_strength, opp_strength)
        if margin <= LOSS_CLOSE_MARGIN:
            base = int(round(base * LOSS_CLOSE_MULTIPLIER))
        d += base
    if GAME_VARIANCE and rng is not None:
        d += rng.randint(-GAME_VARIANCE, GAME_VARIANCE)
    return d


def clamp_progress_points(raw: Any) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = 0
    return max(0, min(PROGRESS_CAP, v))


def apply_pillar_progress_delta(level: int, progress_pts: int, delta: int) -> Tuple[int, int]:
    """
    Apply ``delta`` to one pillar's progress bar, resolving level-ups and demotions.
    ``level`` is 1–10; ``progress_pts`` is clamped to [0, PROGRESS_CAP] after resolution.
    """
    lv = max(1, min(10, int(level)))
    pts = clamp_progress_points(progress_pts)
    pts += int(delta)
    # Demote while underwater
    while lv > 1 and pts < 0:
        pts += upgrade_cost(lv - 1)
        lv -= 1
    if lv == 1 and pts < 0:
        pts = 0
    # Promote while thresholds met
    while lv < 10 and pts >= upgrade_cost(lv):
        pts -= upgrade_cost(lv)
        lv += 1
    pts = clamp_progress_points(pts)
    return lv, pts


def apply_program_delta_to_team(team: Any, delta: int) -> None:
    """Mutate a ``Team`` instance: all three pillars move by the same ``delta``."""
    pairs = (
        ("facilities_grade", "facilities_progress_pts"),
        ("culture_grade", "culture_progress_pts"),
        ("booster_support", "boosters_progress_pts"),
    )
    for gk, pk in pairs:
        lv = max(1, min(10, int(getattr(team, gk, 5) or 5)))
        pt = clamp_progress_points(getattr(team, pk, 0))
        nlv, npt = apply_pillar_progress_delta(lv, pt, int(delta))
        setattr(team, gk, nlv)
        setattr(team, pk, npt)
    if hasattr(team, "_clamp_values"):
        team._clamp_values()


def apply_same_delta_to_team_pillars(team_row: Dict[str, Any], delta: int) -> None:
    """Mutate ``team_row`` dict: facilities / culture / boosters grades + progress points."""
    pairs = (
        ("facilities_grade", "facilities_progress_pts"),
        ("culture_grade", "culture_progress_pts"),
        ("booster_support", "boosters_progress_pts"),
    )
    for gk, pk in pairs:
        lv = max(1, min(10, int(team_row.get(gk, 5) or 5)))
        pt = clamp_progress_points(team_row.get(pk, 0))
        nlv, npt = apply_pillar_progress_delta(lv, pt, delta)
        team_row[gk] = nlv
        team_row[pk] = npt


def program_tier_from_grades(team_row: Dict[str, Any]) -> int:
    f = int(team_row.get("facilities_grade", 5) or 5)
    c = int(team_row.get("culture_grade", 5) or 5)
    b = int(team_row.get("booster_support", 5) or 5)
    return max(1, min(10, int(round((f + c + b) / 3.0))))


def _expected_wins_window(tier: int, games_played: int) -> Tuple[int, int]:
    g = max(1, int(games_played))
    half = g // 2
    if tier <= 3:
        return 2, min(4, g)
    if tier <= 5:
        lo = max(1, half - 1)
        hi = min(g, half + 1)
        return lo, hi
    if tier <= 7:
        return max(1, half), min(g, g - 1) if g > 1 else (1, 1)
    if tier <= 9:
        return max(half, 6) if g >= 10 else max(1, half), min(g, g)
    return max(half + 1, 7), g


def _postseason_rank(post_tier: str) -> int:
    return {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(
        str(post_tier or "none"), 0
    )


def expectation_adjustment(
    *,
    tier: int,
    wins: int,
    losses: int,
    post_tier: str,
    goal_fail_count: int,
    rng: Optional[random.Random] = None,
) -> Tuple[int, int, str]:
    """
    Returns (auto_pillar_delta_each, flex_pp_bank_add, label).

    ``auto_pillar_delta_each`` is applied to all three pillars (meets / underperform).
    ``flex_pp_bank_add`` is discretionary PP for the offseason (exceeds expectations only).
    """
    games = max(1, int(wins) + int(losses))
    lo, hi = _expected_wins_window(tier, games)
    w = int(wins)
    pr = _postseason_rank(post_tier)
    r = rng or random.Random()

    expected_pr = 0
    if tier >= 10:
        expected_pr = 4
    elif tier >= 8:
        expected_pr = 3
    elif tier >= 6:
        expected_pr = 2
    elif tier >= 4:
        expected_pr = 1

    exceeded_wins = w > hi
    missed_wins = w < lo
    exceeded_post = pr > expected_pr
    missed_post = expected_pr >= 2 and pr < expected_pr - 1

    goal_penalty_each = GOAL_MISS_PILLAR_PENALTY * int(goal_fail_count)

    if exceeded_wins or exceeded_post or (tier <= 3 and w >= hi):
        flex = r.randint(EXPECTATION_EXCEED_MIN, EXPECTATION_EXCEED_MAX)
        auto_each = r.randint(0, EXPECTATION_MEETS_PILLAR_BONUS_MAX)
        label = "exceeds"
    elif missed_wins or missed_post:
        flex = 0
        lo_u, hi_u = EXPECTATION_UNDER_MIN, EXPECTATION_UNDER_MAX
        if lo_u > hi_u:
            lo_u, hi_u = hi_u, lo_u
        auto_each = r.randint(lo_u, hi_u)
        label = "underperforms"
    else:
        flex = 0
        auto_each = r.randint(0, EXPECTATION_MEETS_PILLAR_BONUS_MAX)
        label = "meets"

    auto_each += goal_penalty_each
    return int(auto_each), int(max(0, flex)), label


def decay_points_for_tier(tier: int, rng: Optional[random.Random] = None) -> int:
    r = rng or random.Random()
    if tier <= 4:
        lo, hi = DECAY_TIER_1_4
    elif tier <= 7:
        lo, hi = DECAY_TIER_5_7
    else:
        lo, hi = DECAY_TIER_8_10
    if lo == hi == 0:
        return 0
    return -r.randint(-hi, -lo)


def count_season_goal_failures(
    wins: int,
    losses: int,
    post_tier: str,
    season_goals: Optional[Dict[str, Any]],
) -> int:
    """User season goals: 0–2 missed components (win target + stage target)."""
    goal_fail = 0
    if not isinstance(season_goals, dict):
        return 0
    try:
        win_goal = int(season_goals.get("win_goal")) if season_goals.get("win_goal") is not None else None
    except (TypeError, ValueError):
        win_goal = None
    stage_goal = str(season_goals.get("stage_goal") or "").strip() or None
    w = int(wins)
    if win_goal is not None and w < win_goal:
        goal_fail += 1
    achieved_rank = _postseason_rank(post_tier)
    goal_rank = None
    if stage_goal == "Winning Season":
        goal_rank = 0 if w >= int(losses) else 999
    elif stage_goal == "Playoffs":
        goal_rank = 1
    elif stage_goal == "Semifinal":
        goal_rank = 2
    elif stage_goal == "State Championship":
        goal_rank = 3
    elif stage_goal == "Title Winner":
        goal_rank = 4
    if goal_rank is not None:
        if goal_rank == 999:
            goal_fail += 1
        elif achieved_rank < goal_rank:
            goal_fail += 1
    return goal_fail


def postseason_progression_delta(
    *,
    team_name: str,
    champion: str,
    runner_up: str,
    bracket_results: List[Dict[str, Any]],
    regional_champs: List[str],
) -> int:
    """Single delta (applied to all pillars) for postseason awards."""
    d = 0
    made = any(
        isinstance(g, dict) and (g.get("home") == team_name or g.get("away") == team_name)
        for g in (bracket_results or [])
    )
    if made:
        d += POSTSEASON_PLAYOFF_APPEARANCE
    # Playoff wins use the same per-game formula as the regular season via
    # ``run_playoff_game`` / coach playoff finish (no duplicate +200 stack here).
    if team_name in (regional_champs or []):
        d += POSTSEASON_REGIONAL_TITLE
    if team_name == (champion or ""):
        d += POSTSEASON_STATE_CHAMPION
    elif team_name == (runner_up or ""):
        d += POSTSEASON_STATE_RUNNER_UP
    return d


def ensure_team_progression_defaults(team_row: Dict[str, Any]) -> None:
    for k in ("facilities_progress_pts", "culture_progress_pts", "boosters_progress_pts"):
        if k not in team_row:
            team_row[k] = 0
        else:
            team_row[k] = clamp_progress_points(team_row[k])


def season_end_progression_for_team(
    *,
    team_name: str,
    team_row: Dict[str, Any],
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    runner_up: str,
    regional_champs: List[str],
    post_tier: str,
    season_goals: Optional[Dict[str, Any]],
    apply_goal_penalties: bool,
    rng: Optional[random.Random] = None,
) -> Tuple[int, int, Dict[str, Any]]:
    """
    End-of-season pillar change (same delta applied to Culture, Facilities, Boosters).

    Returns ``(pillar_delta, flex_pp_bank, breakdown)``. Flex PP is offseason spend
    only when expectations are exceeded; pillar_delta includes postseason awards,
    expectation auto adjustment, decay, and optional goal penalties.
    """
    srow = (standings or {}).get(team_name) or {}
    wins = int(srow.get("wins", 0) or 0)
    losses = int(srow.get("losses", 0) or 0)
    tier = program_tier_from_grades(team_row)
    goal_fail = (
        count_season_goal_failures(wins, losses, post_tier, season_goals) if apply_goal_penalties else 0
    )

    post_delta = postseason_progression_delta(
        team_name=team_name,
        champion=champion,
        runner_up=runner_up,
        bracket_results=bracket_results,
        regional_champs=regional_champs,
    )
    auto_each, flex_pp, exp_label = expectation_adjustment(
        tier=tier,
        wins=wins,
        losses=losses,
        post_tier=post_tier,
        goal_fail_count=goal_fail,
        rng=rng,
    )
    decay = decay_points_for_tier(tier, rng=rng)
    pillar_delta = int(post_delta) + int(auto_each) + int(decay)

    breakdown = {
        "team": team_name,
        "wins": wins,
        "losses": losses,
        "program_tier": tier,
        "postseason_points_total": post_delta,
        "expectations_label": exp_label,
        "expectations_auto_each_pillar": auto_each,
        "expectations_flex_pp": flex_pp,
        "decay_each_pillar": decay,
        "goal_fail_count": goal_fail,
        "pillar_delta_each": pillar_delta,
        "postseason_tier": post_tier,
        "pp_total": flex_pp,
    }
    return pillar_delta, flex_pp, breakdown


def season_awards_breakdown(
    *,
    team_name: str,
    team_row: Dict[str, Any],
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    runner_up: str,
    regional_champs: List[str],
    season_goals: Optional[Dict[str, Any]],
    post_tier: str,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Build UI + bank fields (wrapper around ``season_end_progression_for_team``).
    """
    _, _, bd = season_end_progression_for_team(
        team_name=team_name,
        team_row=team_row,
        standings=standings,
        bracket_results=bracket_results,
        champion=champion,
        runner_up=runner_up,
        regional_champs=regional_champs,
        post_tier=post_tier,
        season_goals=season_goals,
        apply_goal_penalties=True,
        rng=rng,
    )
    return bd
