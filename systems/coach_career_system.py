"""
Coach career system: retirement, hiring/firing, promotion to better schools,
and scheme changes (every 3 years).

Runs during the offseason, after the season ends and before roster operations.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from models.coach import Coach, OffensiveStyle, DefensiveStyle
from systems.coach_generator import generate_coach_for_team, get_program_attractiveness
from systems.prestige_system import get_coach_skill_sum
from systems.playbook_system import (
    DEFENSIVE_BASE_VALUES,
    OFFENSIVE_PLAYBOOK_VALUES,
    normalize_coach_defensive_front,
    normalize_coach_offensive_playbook,
)
from systems.preferred_playbook import coach_may_change_preferred_playbooks, coach_record_preferred_playbook_change

# --- Retirement ---
RETIREMENT_AGE_FORCED = 75
RETIREMENT_CHANCE_65 = 0.12
RETIREMENT_CHANCE_68 = 0.24
RETIREMENT_CHANCE_70 = 0.42
RETIREMENT_CHANCE_72 = 0.62

# --- Firing ---
FIRING_LOSING_STREAK_THRESHOLD = 3   # Consecutive losing seasons
FIRING_PLAYOFF_DROUGHT_THRESHOLD = 4  # Years without playoffs
FIRING_CHANCE_PER_STRESS = 0.33      # Chance to fire when threshold met

# --- Promotion ---
PROMOTION_SUCCESS_MIN_WINS = 5       # Consider coach "successful" with 5+ wins recently
PROMOTION_CHAMPION_BONUS = 2         # Championships make coach very attractive
PROMOTION_PLAYOFF_BONUS = 1
PROMOTION_ACCEPT_BASE = 0.6          # Base chance to accept offer from better school

# --- Scheme change ---
SCHEME_CHANGE_YEARS = 3
SCHEME_CHANGE_CHANCE = 0.35


def _retirement_chance(age: int) -> float:
    """Probability coach retires this offseason."""
    if age >= RETIREMENT_AGE_FORCED:
        return 1.0
    if age >= 72:
        return RETIREMENT_CHANCE_72
    if age >= 70:
        return RETIREMENT_CHANCE_70
    if age >= 68:
        return RETIREMENT_CHANCE_68
    if age >= 65:
        return RETIREMENT_CHANCE_65
    return 0.0


def _get_playoff_teams(standings: List[Dict[str, Any]], top_n: int = 4) -> List[str]:
    """Top N teams by wins, then point differential."""
    sorted_standings = sorted(
        standings,
        key=lambda s: (-s.get("wins", 0), -s.get("point_diff", 0)),
    )
    return [s["team"] for s in sorted_standings[:top_n]]


def _coach_success_score(
    team_name: str,
    seasons: List[Dict[str, Any]],
    lookback: int = 3,
) -> float:
    """
    Score how successful a coach has been recently (higher = more successful).
    Used for promotion attractiveness.
    """
    if not seasons:
        return 0.0
    recent = seasons[-lookback:]
    score = 0.0
    for entry in recent:
        champion = entry.get("state_champion") or ""
        runner_up = entry.get("runner_up") or ""
        playoff = _get_playoff_teams(entry.get("standings") or [], 8)
        standing_map = {s["team"]: s for s in entry.get("standings") or []}
        st = standing_map.get(team_name, {})
        wins = st.get("wins", 0)
        losses = st.get("losses", 0)
        if team_name == champion:
            score += 10 + PROMOTION_CHAMPION_BONUS
        elif team_name == runner_up:
            score += 6 + PROMOTION_PLAYOFF_BONUS
        elif team_name in playoff:
            score += 4 + PROMOTION_PLAYOFF_BONUS
        elif wins + losses > 0 and wins > losses:
            score += 2
        elif wins >= PROMOTION_SUCCESS_MIN_WINS:
            score += 1
    return score


def _consecutive_losing_seasons(team_name: str, seasons: List[Dict[str, Any]]) -> int:
    """Count consecutive losing seasons at end of history."""
    count = 0
    for entry in reversed(seasons):
        standing_map = {s["team"]: s for s in entry.get("standings") or []}
        st = standing_map.get(team_name, {})
        wins = st.get("wins", 0)
        losses = st.get("losses", 0)
        if wins + losses == 0:
            break
        if losses > wins:
            count += 1
        else:
            break
    return count


def _seasons_since_playoff(team_name: str, seasons: List[Dict[str, Any]]) -> int:
    """Years since team last made playoffs."""
    for i, entry in enumerate(reversed(seasons)):
        playoff = _get_playoff_teams(entry.get("standings") or [], 8)
        if team_name in playoff:
            return i
    return len(seasons)


def _should_fire(
    team_name: str,
    team_prestige: int,
    seasons: List[Dict[str, Any]],
    fire_chance_override: Optional[float] = None,
) -> bool:
    """
    Decide if a team fires its coach. Higher prestige = higher expectations.
    """
    if not seasons:
        return False
    losing_streak = _consecutive_losing_seasons(team_name, seasons)
    playoff_drought = _seasons_since_playoff(team_name, seasons)
    stress = 0
    if losing_streak >= FIRING_LOSING_STREAK_THRESHOLD:
        stress += 1 + (losing_streak - FIRING_LOSING_STREAK_THRESHOLD)
    if playoff_drought >= FIRING_PLAYOFF_DROUGHT_THRESHOLD:
        stress += 1 + (playoff_drought - FIRING_PLAYOFF_DROUGHT_THRESHOLD) // 2
    if stress == 0:
        return False
    # Higher prestige teams more likely to fire when underperforming
    prestige_mod = 1.0 + (team_prestige - 5) * 0.05  # 5 prestige = 1.0, 10 = 1.25
    chance = min(0.85, FIRING_CHANCE_PER_STRESS * stress * prestige_mod)
    if fire_chance_override is not None:
        chance = fire_chance_override
    return random.random() < chance


def _consider_scheme_change(coach: Coach) -> bool:
    """Whether coach changes scheme (offensive or defensive style) this year."""
    years = getattr(coach, "years_since_scheme_change", 0)
    return years >= SCHEME_CHANGE_YEARS and random.random() < SCHEME_CHANGE_CHANCE


def _apply_scheme_change(coach: Coach, current_year: int) -> Dict[str, Any]:
    """
    Randomly change one of: offensive style, defensive style,
    offensive formation (playbook), or defensive formation (playbook).
    Returns dict of what changed for the event (old/new keys).
    """
    changes: Dict[str, Any] = {}
    old_off_style = coach.offensive_style
    old_def_style = coach.defensive_style
    old_off_form = getattr(coach, "offensive_formation", "Spread")
    old_def_form = getattr(coach, "defensive_formation", "4-3")

    options: List[str] = []
    if [s for s in OffensiveStyle if s != coach.offensive_style]:
        options.append("offensive_style")
    if [s for s in DefensiveStyle if s != coach.defensive_style]:
        options.append("defensive_style")
    cur_off_pb = normalize_coach_offensive_playbook(old_off_form)
    if [x for x in OFFENSIVE_PLAYBOOK_VALUES if x != cur_off_pb]:
        options.append("offensive_formation")
    cur_def_base = normalize_coach_defensive_front(old_def_form)
    if [x for x in DEFENSIVE_BASE_VALUES if x != cur_def_base]:
        options.append("defensive_formation")

    if not coach_may_change_preferred_playbooks(coach, int(current_year)):
        options = [o for o in options if o not in ("offensive_formation", "defensive_formation")]

    if not options:
        coach.years_since_scheme_change = 0
        return changes

    choice = random.choice(options)
    if choice == "offensive_style":
        styles = [s for s in OffensiveStyle if s != coach.offensive_style]
        coach.offensive_style = random.choice(styles)
        changes["old_offensive_style"] = old_off_style.value
        changes["new_offensive_style"] = coach.offensive_style.value
    elif choice == "defensive_style":
        styles = [s for s in DefensiveStyle if s != coach.defensive_style]
        coach.defensive_style = random.choice(styles)
        changes["old_defensive_style"] = old_def_style.value
        changes["new_defensive_style"] = coach.defensive_style.value
    elif choice == "offensive_formation":
        cur = normalize_coach_offensive_playbook(old_off_form)
        forms = [x for x in OFFENSIVE_PLAYBOOK_VALUES if x != cur]
        if not forms:
            coach.years_since_scheme_change = 0
            return changes
        coach.offensive_formation = random.choice(forms)
        changes["old_offensive_formation"] = old_off_form
        changes["new_offensive_formation"] = coach.offensive_formation
        coach_record_preferred_playbook_change(coach, int(current_year))
    else:
        cur = normalize_coach_defensive_front(old_def_form)
        forms = [x for x in DEFENSIVE_BASE_VALUES if x != cur]
        if not forms:
            coach.years_since_scheme_change = 0
            return changes
        coach.defensive_formation = random.choice(forms)
        changes["old_defensive_formation"] = old_def_form
        changes["new_defensive_formation"] = coach.defensive_formation
        coach_record_preferred_playbook_change(coach, int(current_year))

    coach.years_since_scheme_change = 0
    return changes


def run_coach_career_phase(
    teams: Dict[str, Any],
    league_history: Optional[Dict[str, Any]] = None,
    standings: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    current_year: int = 1,
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[float, float]]]:
    """
    Run the full coach career phase in one shot (scripts / legacy callers).
    Dynasty saves use phased coaching carousel during the offseason instead.
    """
    from systems.coach_carousel import run_carousel_full

    return run_carousel_full(teams, league_history, standings, current_year=current_year)
