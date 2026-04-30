"""
Offseason manager: orchestrates the full offseason in 9 phases.
Order: Graduation -> Advance age/year -> Roster Trim -> Incoming freshmen
       -> Winter Phase 1 -> Winter Phase 2 -> Spring Ball -> Transfers (placeholder)
       -> 7 on 7 (placeholder) -> Training Results -> Schedule Release (placeholder)
       -> Play Selection -> Play Selection Results -> Reset season stats.
"""

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from systems.development_system import (
    remove_graduated_players,
    advance_age_and_year,
    add_incoming_freshmen,
    run_offseason_development,
    run_winter_phase_development,
    run_spring_ball_development,
)
from systems.play_selection import (
    run_play_selection_for_team,
    run_play_selection_results_for_team,
)

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team

# Phase names for logging/UI
OFFSEASON_PHASES = [
    "Winter Phase 1 (Training and Development)",
    "Winter Phase 2 (Training and Development)",
    "Spring Ball",
    "Transfers",
    "7 on 7 Tournaments",
    "Training Results",
    "Schedule Release",
    "Play Selection",
    "Play Selection Results",
]


def run_offseason_roster_turnover(
    team: "Team",
    *,
    league_history: Optional[Dict[str, Any]] = None,
    target_roster_size: Optional[int] = None,
    trim_roster_enabled: bool = True,
    add_freshmen: bool = True,
) -> Dict[str, Any]:
    """
    Graduation, age/year advance, optional roster trim, incoming freshmen.
    Used at year rollover before interactive offseason stages (winter/spring/etc.).
    """
    result: Dict[str, Any] = {
        "graduated": [],
        "graduated_count": 0,
        "quit": [],
        "quit_count": 0,
        "added": [],
        "added_count": 0,
    }
    graduated = remove_graduated_players(team)
    result["graduated"] = graduated
    result["graduated_count"] = len(graduated)

    advance_age_and_year(team)

    if trim_roster_enabled:
        quit_players = trim_roster(team)
        result["quit"] = quit_players
        result["quit_count"] = len(quit_players)

    if add_freshmen:
        added = add_incoming_freshmen(team, target_roster_size=target_roster_size, league_history=league_history)
        result["added"] = added
        result["added_count"] = len(added)

    return result


def trim_roster(
    team: "Team",
    base_quit_chance: float = 0.04,
    culture_modifier: float = 0.008,
    facilities_modifier: float = 0.004,
) -> List["Player"]:
    """
    Roster trimming: some players quit (underclassmen only).
    Higher culture and facilities reduce quit chance.
    Returns list of players who quit.
    """
    culture = getattr(team, "culture_grade", 5) or 5
    facilities = getattr(team, "facilities_grade", 5) or 5
    # Culture 10 -> -0.04, culture 1 -> +0.036; facilities similar
    quit_chance = base_quit_chance - (culture - 5) * culture_modifier - (facilities - 5) * facilities_modifier
    quit_chance = max(0.005, min(0.12, quit_chance))

    quit_players = []
    for player in list(team.roster):
        if random.random() < quit_chance:
            team.remove_player(player)
            quit_players.append(player)
    return quit_players


def reset_team_season_stats(team: "Team") -> None:
    """Reset team wins and losses for new season."""
    team.wins = 0
    team.losses = 0


def reset_standings(standings: Dict[str, Dict[str, Any]]) -> None:
    """Reset standings dict: wins, losses, points_for, points_against to 0."""
    for name, s in standings.items():
        s["wins"] = 0
        s["losses"] = 0
        s["points_for"] = 0
        s["points_against"] = 0


def reset_season_stats(season_stats: Dict[str, Dict[str, Any]]) -> None:
    """Reset season_stats dict (rush_yards, pass_yards, etc.) to 0."""
    for name, stats in season_stats.items():
        for key in stats:
            stats[key] = 0


def run_offseason(
    team: "Team",
    develop: bool = True,
    add_freshmen: bool = True,
    trim_roster_enabled: bool = True,
    reset_team_stats: bool = True,
    standings: Optional[Dict[str, Dict[str, Any]]] = None,
    season_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    target_roster_size: Optional[int] = None,
    league_history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run full offseason for one team.

    Pre-phases: Graduation -> Advance age/year -> Roster trim -> Incoming freshmen.

    Then 9 phases:
    1. Winter Phase 1 (Training and Development) - physical, coach strength/speed split
    2. Winter Phase 2 (Training and Development) - same
    3. Spring Ball - skill focus (offense run/pass/balanced, defense run_stop/pass_defense/balanced)
    4. Transfers - placeholder
    5. 7 on 7 Tournaments - placeholder
    6. Training Results - full offseason growth
    7. Schedule Release - placeholder (schedule built at season start)
    8. Play Selection - coach picks plays per category (100% per category); locked for season
    9. Play Selection Results - player understanding grade (A+ to F-) from scheme_teach + roster iq/coachability

    Returns dict with graduated_count, quit_count, added_count, phases_run, play_selection, play_selection_results, etc.
    """
    result: Dict[str, Any] = {
        "graduated": [],
        "graduated_count": 0,
        "quit": [],
        "quit_count": 0,
        "added": [],
        "added_count": 0,
        "phases_run": [],
        "developed": False,
        "play_selection": None,
        "play_selection_results": None,
    }

    # Pre-phases: roster turnover
    roster = run_offseason_roster_turnover(
        team,
        league_history=league_history,
        target_roster_size=target_roster_size,
        trim_roster_enabled=trim_roster_enabled,
        add_freshmen=add_freshmen,
    )
    result["graduated"] = roster["graduated"]
    result["graduated_count"] = roster["graduated_count"]
    result["quit"] = roster["quit"]
    result["quit_count"] = roster["quit_count"]
    result["added"] = roster["added"]
    result["added_count"] = roster["added_count"]

    # 7 offseason phases
    # 1. Winter Phase 1 (Training and Development)
    run_winter_phase_development(team)
    result["phases_run"].append(OFFSEASON_PHASES[0])

    # 2. Winter Phase 2 (Training and Development)
    run_winter_phase_development(team)
    result["phases_run"].append(OFFSEASON_PHASES[1])

    # 3. Spring Ball
    run_spring_ball_development(team)
    result["phases_run"].append(OFFSEASON_PHASES[2])

    # 4. Transfers (placeholder)
    result["phases_run"].append(OFFSEASON_PHASES[3])

    # 5. 7 on 7 Tournaments (placeholder)
    result["phases_run"].append(OFFSEASON_PHASES[4])

    # 6. Training Results (full offseason growth)
    if develop:
        run_offseason_development(team)
        result["developed"] = True
    result["phases_run"].append(OFFSEASON_PHASES[5])

    # 7. Schedule Release (placeholder - schedule built when season starts)
    result["phases_run"].append(OFFSEASON_PHASES[6])

    # 8. Play Selection (coach picks plays per category; locked for season)
    try:
        result["play_selection"] = run_play_selection_for_team(team)
    except Exception:  # no playbook or no coach - leave selection None
        result["play_selection"] = {}
    result["phases_run"].append(OFFSEASON_PHASES[7])

    # 9. Play Selection Results (player understanding grade A+ to F-)
    try:
        result["play_selection_results"] = run_play_selection_results_for_team(team)
    except Exception:
        result["play_selection_results"] = {}
    result["phases_run"].append(OFFSEASON_PHASES[8])

    # Reset season stats
    if reset_team_stats:
        reset_team_season_stats(team)
    if standings is not None:
        reset_standings(standings)
    if season_stats is not None:
        reset_season_stats(season_stats)

    return result


def run_offseason_all_teams(
    teams: List["Team"],
    standings: Optional[Dict[str, Dict[str, Any]]] = None,
    season_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    develop: bool = True,
    add_freshmen: bool = True,
    trim_roster_enabled: bool = True,
    reset_team_stats: bool = True,
    league_history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Run offseason for all teams. Resets standings and season_stats once (shared).
    Returns dict of team_name -> result for each team.
    """
    if standings is not None:
        reset_standings(standings)
    if season_stats is not None:
        reset_season_stats(season_stats)
    results = {}
    for team in teams:
        results[team.name] = run_offseason(
            team,
            develop=develop,
            add_freshmen=add_freshmen,
            trim_roster_enabled=trim_roster_enabled,
            reset_team_stats=reset_team_stats,
            standings=None,
            season_stats=None,
            league_history=league_history,
        )
    return results
