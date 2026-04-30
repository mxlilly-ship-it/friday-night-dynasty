"""
Dynamic team prestige system.

Prestige (1-15) increases from:
- Championships
- Playoff appearances
- Winning seasons
- Producing elite players (POY, league leaders)

Prestige decreases from:
- Losing seasons
- Long droughts (playoff, championship)
- Coach turnover (especially losing a legendary coach without a strong replacement)
"""

from typing import Any, Dict, List, Optional, Tuple

# --- Prestige delta weights ---
DELTA_CHAMPIONSHIP = 1.5
DELTA_RUNNER_UP = 0.5
DELTA_PLAYOFF_APPEARANCE = 0.25
DELTA_WINNING_SEASON = 0.15
DELTA_ELITE_POY = 0.35
DELTA_ELITE_LEAGUE_LEADER = 0.1
DELTA_ELITE_CAP = 0.6  # Max elite bonus per season

DELTA_LOSING_SEASON = -0.15
DELTA_PLAYOFF_DROUGHT_PER_YEAR = -0.2
DELTA_PLAYOFF_DROUGHT_THRESHOLD = 3
DELTA_PLAYOFF_DROUGHT_CAP = -0.6
DELTA_CHAMPIONSHIP_DROUGHT_PER_YEAR = -0.15
DELTA_CHAMPIONSHIP_DROUGHT_THRESHOLD = 5
DELTA_CHAMPIONSHIP_DROUGHT_CAP = -0.45
DELTA_COACH_TURNOVER_LEGENDARY_LOST = -0.4  # Per point of skill drop when old coach was 8+


def _get_playoff_teams(standings: List[Dict[str, Any]], top_n: int = 4) -> List[str]:
    """Return team names of top N by wins, then point differential."""
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
    """Years since team last satisfied predicate (e.g. made playoffs or won championship)."""
    for i, entry in enumerate(reversed(seasons)):
        if predicate(entry, team_name):
            return i
    return len(seasons)


def _count_elite_players_from_team(
    team_name: str,
    poy: Optional[Dict[str, Any]],
    league_leaders: Dict[str, List[Dict[str, Any]]],
) -> Tuple[int, bool]:
    """Return (count of league leaders from team, True if POY from team)."""
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
    """
    Penalty when a legendary coach (8+) leaves and replacement is worse.
    Returns negative delta (e.g. -0.4 per point of drop when old was 8+).
    """
    if old_skill < legendary_threshold:
        return 0.0
    drop = old_skill - new_skill
    if drop <= 0:
        return 0.0
    return max(-1.5, DELTA_COACH_TURNOVER_LEGENDARY_LOST * drop)


def compute_prestige_delta(
    team_name: str,
    team_prestige: int,
    seasons: List[Dict[str, Any]],
    latest: Dict[str, Any],
    coach_changes: Optional[Dict[str, Tuple[float, float]]] = None,
) -> float:
    """
    Compute prestige delta for one team based on latest season and history.

    - team_name: Team to evaluate
    - team_prestige: Current prestige (for reference; not used in delta)
    - seasons: Full list of season entries (newest last)
    - latest: Most recent season entry
    - coach_changes: Optional {team: (old_coach_skill, new_coach_skill)}

    Returns float delta (positive = gain, negative = loss).
    """
    delta = 0.0
    standings_list = latest.get("standings") or []
    champion = latest.get("state_champion") or ""
    runner_up = latest.get("runner_up") or ""
    poy = latest.get("player_of_the_year")
    league_leaders = latest.get("league_leaders") or {}

    # Standings as dict for wins
    standing_map = {s["team"]: s for s in standings_list}
    st = standing_map.get(team_name, {})
    wins = st.get("wins", 0)
    losses = st.get("losses", 0)
    games = wins + losses
    is_winning = games > 0 and wins > losses
    is_losing = games > 0 and losses > wins

    playoff_teams = _get_playoff_teams(standings_list, 8)
    made_playoffs = team_name in playoff_teams

    # --- Increases ---
    if team_name == champion:
        delta += DELTA_CHAMPIONSHIP
    elif team_name == runner_up:
        delta += DELTA_RUNNER_UP
    elif made_playoffs:
        delta += DELTA_PLAYOFF_APPEARANCE
    if is_winning:
        delta += DELTA_WINNING_SEASON

    elite_count, is_poy = _count_elite_players_from_team(team_name, poy, league_leaders)
    elite_bonus = 0.0
    if is_poy:
        elite_bonus += DELTA_ELITE_POY
    elite_bonus += min(elite_count, 3) * DELTA_ELITE_LEAGUE_LEADER  # Cap league leaders at 3
    delta += min(DELTA_ELITE_CAP, elite_bonus)

    # --- Decreases ---
    if is_losing:
        delta += DELTA_LOSING_SEASON

    # Playoff drought
    def made_playoffs_pred(entry: Dict, name: str) -> bool:
        playoff = _get_playoff_teams(entry.get("standings") or [], 8)
        return name in playoff

    years_since_playoff = _seasons_since_last(team_name, seasons, made_playoffs_pred)
    if years_since_playoff > DELTA_PLAYOFF_DROUGHT_THRESHOLD:
        excess = years_since_playoff - DELTA_PLAYOFF_DROUGHT_THRESHOLD
        drought_penalty = min(
            DELTA_PLAYOFF_DROUGHT_CAP,
            excess * DELTA_PLAYOFF_DROUGHT_PER_YEAR,
        )
        delta += drought_penalty

    # Championship drought
    def won_championship_pred(entry: Dict, name: str) -> bool:
        return (entry.get("state_champion") or "") == name

    years_since_champ = _seasons_since_last(team_name, seasons, won_championship_pred)
    if years_since_champ > DELTA_CHAMPIONSHIP_DROUGHT_THRESHOLD:
        excess = years_since_champ - DELTA_CHAMPIONSHIP_DROUGHT_THRESHOLD
        champ_drought_penalty = min(
            DELTA_CHAMPIONSHIP_DROUGHT_CAP,
            excess * DELTA_CHAMPIONSHIP_DROUGHT_PER_YEAR,
        )
        delta += champ_drought_penalty

    # Coach turnover
    if coach_changes and team_name in coach_changes:
        old_skill, new_skill = coach_changes[team_name]
        delta += _coach_turnover_penalty(old_skill, new_skill)

    return delta


def update_prestige(
    teams: Dict[str, Any],
    league_history: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
    coach_changes: Optional[Dict[str, Tuple[float, float]]] = None,
) -> None:
    """
    Update each team's prestige based on league history.

    - teams: Dict mapping team name -> Team object (with prestige, championships)
    - league_history: From load_league_history(). If None, loads from path.
    - path: Path to league_history.json (used if league_history is None)
    - coach_changes: Optional {team_name: (old_coach_skill, new_coach_skill)}
    """
    from systems.league_history import load_league_history

    data = league_history if league_history is not None else load_league_history(path)
    seasons = data.get("seasons") or []
    if not seasons:
        return

    latest = seasons[-1]
    for name, team in teams.items():
        prestige = getattr(team, "prestige", 5) or 5
        delta = compute_prestige_delta(
            name,
            prestige,
            seasons,
            latest,
            coach_changes=coach_changes,
        )
        new_prestige = max(1, min(15, round(prestige + delta)))
        team.prestige = new_prestige
        team._clamp_values()

    # Increment championships for state champion
    champion = latest.get("state_champion") or ""
    if champion and champion in teams:
        team = teams[champion]
        team.championships = getattr(team, "championships", 0) + 1
        team._clamp_values()


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
