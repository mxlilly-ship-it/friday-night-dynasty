"""
League history: State Champion, Standings, Player of the Year, League Leaders per season.
Persisted to league_history.json.
"""

import json
import os
from typing import Any, Dict, List, Optional

from systems.game_stats import PlayerSeasonStats
from systems.win_path_io import open_text_with_path_fallback, path_exists_any

LEAGUE_HISTORY_PATH = "league_history.json"


def _default_path() -> str:
    """Path to league_history.json in project root."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, LEAGUE_HISTORY_PATH)


def load_league_history(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load league history from JSON. Returns dict with "seasons" list.
    Creates empty structure if file doesn't exist.
    """
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    if not path_exists_any(plain):
        return {"seasons": []}
    with open_text_with_path_fallback(plain, "r") as f:
        data = json.load(f)
    if "seasons" not in data:
        data["seasons"] = []
    return data


def save_league_history(data: Dict[str, Any], path: Optional[str] = None) -> None:
    """Write league history to JSON."""
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    with open_text_with_path_fallback(plain, "w") as f:
        json.dump(data, f, indent=2)


def _build_standings_list(
    team_names: List[str],
    standings: Dict[str, Dict[str, int]],
) -> List[Dict[str, Any]]:
    """Build ordered standings list for JSON."""
    sorted_names = sorted(
        team_names,
        key=lambda n: (
            -standings[n].get("wins", 0),
            -(standings[n].get("points_for", 0) - standings[n].get("points_against", 0)),
        ),
    )
    result = []
    for name in sorted_names:
        s = standings.get(name, {})
        pf = s.get("points_for", 0)
        pa = s.get("points_against", 0)
        result.append({
            "team": name,
            "wins": s.get("wins", 0),
            "losses": s.get("losses", 0),
            "points_for": pf,
            "points_against": pa,
            "point_diff": pf - pa,
        })
    return result


def _pick_player_of_the_year(
    season_stats_map: Dict[int, PlayerSeasonStats],
    teams_dict: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick Player of the Year: player with highest total yards (pass + rush + rec)
    plus TDs as tiebreaker. Returns dict with name, team, and key stats.
    """
    all_stats = list(season_stats_map.values())
    if not all_stats:
        return None

    def impact(s: PlayerSeasonStats) -> tuple:
        total_yds = s.pass_yds + s.rush_yds + s.rec_yds
        total_td = s.pass_td + s.rush_td + s.rec_td
        return (total_yds, total_td)

    best = max(all_stats, key=impact)
    if impact(best) == (0, 0):
        # No offensive production - pick top defensive player (tackles + sacks*2 + INT*3)
        def_def = [s for s in all_stats if s.tackles > 0 or s.sacks > 0 or s.interceptions > 0]
        if not def_def:
            return None
        best = max(def_def, key=lambda s: s.tackles + s.sacks * 2 + s.interceptions * 3)

    return {
        "name": best.player_name,
        "team": best.team_name,
        "pass_yds": best.pass_yds,
        "pass_td": best.pass_td,
        "comp": best.comp,
        "att": best.att,
        "rush_yds": best.rush_yds,
        "rush_td": best.rush_td,
        "rec": best.rec,
        "rec_yds": best.rec_yds,
        "rec_td": best.rec_td,
        "tackles": best.tackles,
        "sacks": best.sacks,
        "interceptions": best.interceptions,
    }


def _build_league_leaders(
    season_stats_map: Dict[int, PlayerSeasonStats],
    top_n: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """Build league leaders dict for JSON."""
    all_stats = list(season_stats_map.values())
    result: Dict[str, List[Dict[str, Any]]] = {}

    # Passing yards
    pass_yds = [s for s in all_stats if s.att > 0]
    pass_yds.sort(key=lambda s: -s.pass_yds)
    result["passing_yards"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.pass_yds, "detail": f"{s.comp}/{s.att}, {s.pass_td} TD, {s.int_thrown} INT"}
        for s in pass_yds[:top_n]
    ]

    # Passing TD
    pass_td_list = sorted(pass_yds, key=lambda s: -s.pass_td)
    result["passing_td"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.pass_td}
        for s in pass_td_list[:top_n]
    ]

    # Rushing yards
    rush_yds = [s for s in all_stats if s.rush_yds != 0 or s.rush_td > 0]
    rush_yds.sort(key=lambda s: (-s.rush_yds, -s.rush_td))
    result["rushing_yards"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.rush_yds, "detail": f"{s.rush_td} TD"}
        for s in rush_yds[:top_n]
    ]

    # Receiving yards
    rec_stats = [s for s in all_stats if s.rec > 0 or s.rec_yds != 0 or s.rec_td > 0]
    rec_stats.sort(key=lambda s: (-s.rec_yds, -s.rec))
    result["receiving_yards"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.rec_yds, "detail": f"{s.rec} rec, {s.rec_td} TD"}
        for s in rec_stats[:top_n]
    ]

    # Tackles
    defs = [s for s in all_stats if s.tackles > 0]
    defs.sort(key=lambda s: -s.tackles)
    result["tackles"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.tackles}
        for s in defs[:top_n]
    ]

    # Sacks
    sack_list = [s for s in all_stats if s.sacks > 0]
    sack_list.sort(key=lambda s: -s.sacks)
    result["sacks"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.sacks}
        for s in sack_list[:top_n]
    ]

    # Interceptions
    int_list = [s for s in all_stats if s.interceptions > 0]
    int_list.sort(key=lambda s: -s.interceptions)
    result["interceptions"] = [
        {"name": s.player_name, "team": s.team_name, "value": s.interceptions}
        for s in int_list[:top_n]
    ]

    return result


def append_season(
    champion: str,
    runner_up: str,
    team_names: List[str],
    standings: Dict[str, Dict[str, int]],
    season_player_stats: Dict[int, PlayerSeasonStats],
    season_number: Optional[int] = None,
    year: Optional[int] = None,
    bracket_results: Optional[List[Dict[str, Any]]] = None,
    team_coaches: Optional[Dict[str, str]] = None,
    team_recap_files: Optional[Dict[str, str]] = None,
    path: Optional[str] = None,
    save_dir: Optional[str] = None,
) -> None:
    """
    Append one season to league history.

    - champion: State champion team name
    - runner_up: Runner-up (championship loser)
    - team_names: List of all team names
    - standings: {team_name: {wins, losses, points_for, points_against}}
    - season_player_stats: player_id -> PlayerSeasonStats
    - season_number: 1-based (default: len(seasons)+1)
    - year: calendar year (optional)
    - path: optional full path to league_history.json (legacy)
    - save_dir: if set, league_history and records are read/written under this directory (for per-save play)
    """
    hist_path = path
    rec_path = None
    if save_dir:
        hist_path = os.path.join(save_dir, "league_history.json")
        rec_path = os.path.join(save_dir, "records.json")
    data = load_league_history(hist_path)
    seasons = data["seasons"]
    seq = season_number if season_number is not None else len(seasons) + 1

    poy = _pick_player_of_the_year(season_player_stats)
    leaders = _build_league_leaders(season_player_stats, top_n=5)

    from systems.awards_system import compute_awards

    awards = compute_awards(season_player_stats)
    player_stats_list = [
        {
            "name": s.player_name,
            "team": s.team_name,
            "pass_yds": s.pass_yds,
            "pass_td": s.pass_td,
            "comp": s.comp,
            "att": s.att,
            "rush_yds": s.rush_yds,
            "rush_td": s.rush_td,
            "rec": s.rec,
            "rec_yds": s.rec_yds,
            "rec_td": s.rec_td,
            "tackles": s.tackles,
            "sacks": s.sacks,
            "interceptions": s.interceptions,
        }
        for s in season_player_stats.values()
    ]

    standings_list = _build_standings_list(team_names, standings)
    if team_coaches:
        for row in standings_list:
            tn = row.get("team")
            if tn in team_coaches:
                row["coach"] = team_coaches.get(tn) or ""

    entry = {
        "season": seq,
        "year": year,
        "state_champion": champion,
        "runner_up": runner_up,
        "standings": standings_list,
        "playoffs": {"bracket_results": bracket_results or []},
        "player_of_the_year": poy,
        "league_leaders": leaders,
        "awards": awards,
        "player_stats": player_stats_list,
        "team_recaps": team_recap_files or {},
    }

    seasons.append(entry)
    save_league_history(data, hist_path)

    # Update record book
    from systems.records_system import load_records, save_records, update_records_from_season
    rec = load_records(rec_path)
    update_records_from_season(rec, data, len(seasons) - 1, season_player_stats, standings)
    save_records(rec, rec_path)


def append_season_in_memory(
    league_history: Dict[str, Any],
    records: Dict[str, Any],
    *,
    champion: str,
    runner_up: str,
    team_names: List[str],
    standings: Dict[str, Dict[str, int]],
    season_player_stats: Dict[int, PlayerSeasonStats],
    season_number: Optional[int] = None,
    year: Optional[int] = None,
    bracket_results: Optional[List[Dict[str, Any]]] = None,
    team_coaches: Optional[Dict[str, str]] = None,
    team_recap_files: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Stateless version of append_season:
    - Mutates/returns league_history and records in-memory (no file I/O).
    """
    if "seasons" not in league_history or not isinstance(league_history.get("seasons"), list):
        league_history["seasons"] = []
    seasons = league_history["seasons"]
    seq = season_number if season_number is not None else len(seasons) + 1

    poy = _pick_player_of_the_year(season_player_stats)
    leaders = _build_league_leaders(season_player_stats, top_n=5)

    from systems.awards_system import compute_awards

    awards = compute_awards(season_player_stats)
    player_stats_list = [
        {
            "name": s.player_name,
            "team": s.team_name,
            "pass_yds": s.pass_yds,
            "pass_td": s.pass_td,
            "comp": s.comp,
            "att": s.att,
            "rush_yds": s.rush_yds,
            "rush_td": s.rush_td,
            "rec": s.rec,
            "rec_yds": s.rec_yds,
            "rec_td": s.rec_td,
            "tackles": s.tackles,
            "sacks": s.sacks,
            "interceptions": s.interceptions,
        }
        for s in season_player_stats.values()
    ]

    standings_list = _build_standings_list(team_names, standings)
    if team_coaches:
        for row in standings_list:
            tn = row.get("team")
            if tn in team_coaches:
                row["coach"] = team_coaches.get(tn) or ""

    entry = {
        "season": seq,
        "year": year,
        "state_champion": champion,
        "runner_up": runner_up,
        "standings": standings_list,
        "playoffs": {"bracket_results": bracket_results or []},
        "player_of_the_year": poy,
        "league_leaders": leaders,
        "awards": awards,
        "player_stats": player_stats_list,
        "team_recaps": team_recap_files or {},
    }
    seasons.append(entry)

    from systems.records_system import update_records_from_season

    # Ensure records has expected shape if caller passed {}
    if not records or not isinstance(records, dict):
        from systems.records_system import load_records

        records = load_records(path=None)
    update_records_from_season(records, league_history, len(seasons) - 1, season_player_stats, standings)
    return {"league_history": league_history, "records": records}
