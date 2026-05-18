"""
Dynamic team prestige via Team Points (TP).

Prestige 1–15 is derived from cumulative TP thresholds (widening bands).
Season results add/subtract TP; prestige changes only when crossing a band floor.
"""

from typing import Any, Dict, List, Optional, Tuple

# Minimum TP to be at each prestige level (index 0 = prestige 1, index 14 = prestige 15).
PRESTIGE_FLOORS: Tuple[float, ...] = (
    0.0,
    1.0,
    1.7,
    2.5,
    3.4,
    4.4,
    5.5,
    6.7,
    8.0,
    9.4,
    10.9,
    12.5,
    14.2,
    16.0,
    17.9,
)

PRESTIGE_MIN = 1
PRESTIGE_MAX = 15
START_BAND_POSITION = 0.70  # New saves begin ~70% through current prestige band.

# --- Team Points delta weights (per season / coaching pass) ---
TP_CHAMPIONSHIP = 0.18
TP_RUNNER_UP = 0.06
TP_PLAYOFF_APPEARANCE = 0.03
TP_WINNING_SEASON = 0.02
TP_PER_WIN = 0.01
TP_PER_LOSS = -0.01
TP_ELITE_POY = 0.04
TP_ELITE_LEAGUE_LEADER = 0.01
TP_ELITE_CAP = 0.07

TP_LOSING_SEASON = -0.02
TP_PLAYOFF_DROUGHT_PER_YEAR = -0.02
TP_PLAYOFF_DROUGHT_THRESHOLD = 3
TP_PLAYOFF_DROUGHT_CAP = -0.06
TP_CHAMPIONSHIP_DROUGHT_PER_YEAR = -0.015
TP_CHAMPIONSHIP_DROUGHT_THRESHOLD = 5
TP_CHAMPIONSHIP_DROUGHT_CAP = -0.045
TP_COACH_TURNOVER_LEGENDARY_LOST = -0.04


def clamp_team_points(tp: float) -> float:
    return max(0.0, float(tp))


def prestige_from_team_points(tp: float) -> int:
    """Map TP to displayed prestige 1–15."""
    value = clamp_team_points(tp)
    level = PRESTIGE_MIN
    for idx in range(len(PRESTIGE_FLOORS) - 1, -1, -1):
        if value >= PRESTIGE_FLOORS[idx]:
            level = idx + 1
            break
    return max(PRESTIGE_MIN, min(PRESTIGE_MAX, level))


def prestige_band_for_level(prestige: int) -> Tuple[float, float]:
    """Return (floor_inclusive, ceiling_exclusive) for prestige level."""
    p = max(PRESTIGE_MIN, min(PRESTIGE_MAX, int(prestige)))
    lo = PRESTIGE_FLOORS[p - 1]
    if p >= PRESTIGE_MAX:
        hi = lo + 2.0
    else:
        hi = PRESTIGE_FLOORS[p]
    return lo, hi


def default_team_points_for_prestige(prestige: int) -> float:
    """Starting TP when a save begins at integer prestige (~70% into band)."""
    p = max(PRESTIGE_MIN, min(PRESTIGE_MAX, int(prestige)))
    lo, hi = prestige_band_for_level(p)
    if p >= PRESTIGE_MAX:
        return round(lo + START_BAND_POSITION * 1.9, 2)
    return round(lo + START_BAND_POSITION * (hi - lo), 2)


def ensure_team_points_initialized(team: Any) -> None:
    """Backfill TP from prestige on legacy teams; sync prestige from TP."""
    raw = getattr(team, "team_points", None)
    if raw is None:
        prestige = int(getattr(team, "prestige", 5) or 5)
        team.team_points = default_team_points_for_prestige(prestige)
    else:
        team.team_points = clamp_team_points(float(raw))
    if getattr(team, "team_points_last_delta", None) is None:
        team.team_points_last_delta = 0.0
    team.prestige = prestige_from_team_points(team.team_points)


def migrate_team_dict_team_points(t: Dict[str, Any]) -> bool:
    """Migrate one serialized team dict; returns True if changed."""
    if not isinstance(t, dict):
        return False
    changed = False
    if t.get("team_points") is None:
        p = int(t.get("prestige", 5) or 5)
        t["team_points"] = default_team_points_for_prestige(p)
        changed = True
    if t.get("team_points_last_delta") is None:
        t["team_points_last_delta"] = 0.0
        changed = True
    tp = clamp_team_points(float(t.get("team_points", 0.0)))
    new_p = prestige_from_team_points(tp)
    if int(t.get("prestige", 0) or 0) != new_p:
        t["prestige"] = new_p
        changed = True
    t["team_points"] = round(tp, 2)
    return changed


def migrate_state_team_points_fields(state: Dict[str, Any]) -> bool:
    """Ensure all teams in save state have TP fields."""
    changed = False
    for t in state.get("teams") or []:
        if migrate_team_dict_team_points(t):
            changed = True
    return changed


def _get_playoff_teams(standings: List[Dict[str, Any]], top_n: int = 8) -> List[str]:
    sorted_standings = sorted(
        standings,
        key=lambda s: (-s.get("wins", 0), -s.get("point_diff", 0)),
    )
    return [s["team"] for s in sorted_standings[:top_n]]


def _seasons_since_last(
    team_name: str,
    seasons: List[Dict[str, Any]],
    predicate,
) -> int:
    for i, entry in enumerate(reversed(seasons)):
        if predicate(entry, team_name):
            return i
    return len(seasons)


def _count_elite_players_from_team(
    team_name: str,
    poy: Optional[Dict[str, Any]],
    league_leaders: Dict[str, List[Dict[str, Any]]],
) -> Tuple[int, bool]:
    count = 0
    is_poy = False
    if poy and poy.get("team") == team_name:
        is_poy = True
    for category_entries in (league_leaders or {}).values():
        for entry in category_entries or []:
            if entry.get("team") == team_name:
                count += 1
    return count, is_poy


def _coach_turnover_penalty(
    old_skill: float,
    new_skill: float,
    legendary_threshold: int = 8,
) -> float:
    if old_skill < legendary_threshold:
        return 0.0
    drop = old_skill - new_skill
    if drop <= 0:
        return 0.0
    return max(-0.15, TP_COACH_TURNOVER_LEGENDARY_LOST * drop)


def compute_team_points_delta(
    team_name: str,
    seasons: List[Dict[str, Any]],
    latest: Dict[str, Any],
    coach_changes: Optional[Dict[str, Tuple[float, float]]] = None,
    *,
    coach_turnover_only: bool = False,
) -> float:
    """Compute TP delta for one team (positive = gain)."""
    if coach_turnover_only:
        if not coach_changes or team_name not in coach_changes:
            return 0.0
        old_skill, new_skill = coach_changes[team_name]
        return _coach_turnover_penalty(old_skill, new_skill)

    delta = 0.0
    standings_list = latest.get("standings") or []
    champion = latest.get("state_champion") or ""
    runner_up = latest.get("runner_up") or ""
    poy = latest.get("player_of_the_year")
    league_leaders = latest.get("league_leaders") or {}

    standing_map = {s["team"]: s for s in standings_list}
    st = standing_map.get(team_name, {})
    wins = int(st.get("wins", 0) or 0)
    losses = int(st.get("losses", 0) or 0)
    games = wins + losses
    is_winning = games > 0 and wins > losses
    is_losing = games > 0 and losses > wins

    delta += wins * TP_PER_WIN + losses * TP_PER_LOSS

    playoff_teams = _get_playoff_teams(standings_list, 8)
    made_playoffs = team_name in playoff_teams

    if team_name == champion:
        delta += TP_CHAMPIONSHIP
    elif team_name == runner_up:
        delta += TP_RUNNER_UP
    elif made_playoffs:
        delta += TP_PLAYOFF_APPEARANCE
    if is_winning:
        delta += TP_WINNING_SEASON

    elite_count, is_poy = _count_elite_players_from_team(team_name, poy, league_leaders)
    elite_bonus = 0.0
    if is_poy:
        elite_bonus += TP_ELITE_POY
    elite_bonus += min(elite_count, 3) * TP_ELITE_LEAGUE_LEADER
    delta += min(TP_ELITE_CAP, elite_bonus)

    if is_losing:
        delta += TP_LOSING_SEASON

    def made_playoffs_pred(entry: Dict, name: str) -> bool:
        playoff = _get_playoff_teams(entry.get("standings") or [], 8)
        return name in playoff

    years_since_playoff = _seasons_since_last(team_name, seasons, made_playoffs_pred)
    if years_since_playoff > TP_PLAYOFF_DROUGHT_THRESHOLD:
        excess = years_since_playoff - TP_PLAYOFF_DROUGHT_THRESHOLD
        delta += min(TP_PLAYOFF_DROUGHT_CAP, excess * TP_PLAYOFF_DROUGHT_PER_YEAR)

    def won_championship_pred(entry: Dict, name: str) -> bool:
        return (entry.get("state_champion") or "") == name

    years_since_champ = _seasons_since_last(team_name, seasons, won_championship_pred)
    if years_since_champ > TP_CHAMPIONSHIP_DROUGHT_THRESHOLD:
        excess = years_since_champ - TP_CHAMPIONSHIP_DROUGHT_THRESHOLD
        delta += min(TP_CHAMPIONSHIP_DROUGHT_CAP, excess * TP_CHAMPIONSHIP_DROUGHT_PER_YEAR)

    if coach_changes and team_name in coach_changes:
        old_skill, new_skill = coach_changes[team_name]
        delta += _coach_turnover_penalty(old_skill, new_skill)

    return round(delta, 3)


def apply_team_points_delta(team: Any, delta: float, *, accumulate_last_delta: bool = False) -> None:
    """Apply TP change and sync prestige."""
    ensure_team_points_initialized(team)
    before = float(team.team_points)
    after = clamp_team_points(before + float(delta))
    team.team_points = round(after, 2)
    team.prestige = prestige_from_team_points(team.team_points)
    d = round(float(delta), 2)
    if accumulate_last_delta:
        team.team_points_last_delta = round(float(getattr(team, "team_points_last_delta", 0.0) or 0.0) + d, 2)
    else:
        team.team_points_last_delta = d
    if hasattr(team, "_clamp_values"):
        team._clamp_values()


def update_prestige(
    teams: Dict[str, Any],
    league_history: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
    coach_changes: Optional[Dict[str, Tuple[float, float]]] = None,
    *,
    coach_turnover_only: bool = False,
) -> None:
    """
    Update each team's Team Points and derived prestige from league history.

    - coach_turnover_only: only coaching-move TP (carousel III); accumulates last_delta.
    - Otherwise: full season TP; sets last_delta for the prestige report.
    """
    from systems.league_history import load_league_history

    if coach_turnover_only:
        if not coach_changes:
            return
        for name, team in teams.items():
            if name not in coach_changes:
                continue
            ensure_team_points_initialized(team)
            old_skill, new_skill = coach_changes[name]
            delta = _coach_turnover_penalty(old_skill, new_skill)
            apply_team_points_delta(team, delta, accumulate_last_delta=True)
        return

    data = league_history if league_history is not None else load_league_history(path)
    seasons = data.get("seasons") or []
    if not seasons:
        return

    latest = seasons[-1]
    for name, team in teams.items():
        ensure_team_points_initialized(team)
        delta = compute_team_points_delta(
            name,
            seasons,
            latest,
            coach_changes=coach_changes,
        )
        apply_team_points_delta(team, delta, accumulate_last_delta=False)


# Backward-compatible alias for imports expecting prestige deltas.
compute_prestige_delta = compute_team_points_delta


def get_coach_skill_sum(coach: Any) -> float:
    """Return a single skill number for coach (1-10 scale). Used for turnover penalty."""
    if coach is None:
        return 3.0
    skills = [
        getattr(coach, "playcalling", 5),
        getattr(coach, "player_development", 5),
        getattr(coach, "recruiting", 5),
        getattr(coach, "culture", 5),
    ]
    return sum(skills) / len(skills) if skills else 5.0
