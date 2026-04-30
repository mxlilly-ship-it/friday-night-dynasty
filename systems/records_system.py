"""
Record book: Team, Rushing, Passing, Receiving, Defense, and Game records.
Persisted to records.json. Updated after each season (and optionally after each game for game records).
"""

import json
import os
from typing import Any, Dict, List, Optional

from systems.game_stats import PlayerGameStats, PlayerSeasonStats
from systems.win_path_io import open_text_with_path_fallback, path_exists_any

RECORDS_PATH = "records.json"


def _default_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, RECORDS_PATH)


def _empty_records() -> Dict[str, Any]:
    return {
        "team": {
            "most_championships": None,
            "most_wins_season": None,
            "most_points_season": None,
        },
        "rushing": {
            "single_season_yards": None,
            "career_yards": None,
            "single_season_td": None,
        },
        "passing": {
            "single_season_yards": None,
            "career_yards": None,
            "single_season_td": None,
        },
        "receiving": {
            "single_season_yards": None,
            "career_yards": None,
            "single_season_td": None,
        },
        "defense": {
            "single_season_sacks": None,
            "career_sacks": None,
            "single_season_interceptions": None,
        },
        "game": {
            "most_passing_yards": None,
            "most_rushing_yards": None,
            "most_points": None,
        },
    }


def _record_entry(value: Any, holder: str, holder_team: str, season: int, **kwargs) -> Dict[str, Any]:
    return {"value": value, "holder": holder, "holder_team": holder_team, "season": season, **kwargs}


def _beats(current: Optional[Dict], new_value: Any, higher_is_better: bool = True) -> bool:
    if current is None:
        return True
    old = current.get("value", 0)
    if higher_is_better:
        return new_value > old
    return new_value < old  # e.g. fewest points allowed


def load_records(path: Optional[str] = None) -> Dict[str, Any]:
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    if not path_exists_any(plain):
        return _empty_records()
    with open_text_with_path_fallback(plain, "r") as f:
        data = json.load(f)
    empty = _empty_records()
    for k in empty:
        if k not in data:
            data[k] = empty[k]
    return data


def save_records(data: Dict[str, Any], path: Optional[str] = None) -> None:
    plain = os.path.abspath(os.path.normpath(path or _default_path()))
    with open_text_with_path_fallback(plain, "w") as f:
        json.dump(data, f, indent=2)


def _build_player_stats_list(stats_map: Dict[int, PlayerSeasonStats]) -> List[Dict[str, Any]]:
    """Flatten season stats to list of dicts for persistence."""
    return [
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
        for s in stats_map.values()
    ]


def _aggregate_career_stats(seasons_with_stats: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, int]]:
    """(name, team) -> career totals. Player identity = (name, team) per career."""
    career: Dict[tuple, Dict[str, int]] = {}
    for entry in seasons_with_stats:
        for p in entry.get("player_stats", []):
            key = (p["name"], p["team"])
            if key not in career:
                career[key] = {
                    "rush_yds": 0, "rush_td": 0,
                    "pass_yds": 0, "pass_td": 0, "comp": 0, "att": 0,
                    "rec_yds": 0, "rec_td": 0, "rec": 0,
                    "tackles": 0, "sacks": 0, "interceptions": 0,
                }
            for k in career[key]:
                career[key][k] += p.get(k, 0)
    return career


def update_records_from_season(
    records: Dict[str, Any],
    league_history: Dict[str, Any],
    new_season_index: int,
    season_player_stats: Dict[int, PlayerSeasonStats],
    standings: Dict[str, Dict[str, int]],
) -> Dict[str, Any]:
    """
    Update records using the newly completed season.
    Mutates records in place. Call after append_season.
    """
    seasons = league_history.get("seasons", [])
    if not seasons or new_season_index < 0 or new_season_index >= len(seasons):
        return records

    season_entry = seasons[new_season_index]
    seq = season_entry.get("season", new_season_index + 1)
    # player_stats should already be in season_entry from append_season

    # --- Team records ---
    champ = season_entry.get("state_champion") or ""
    standings_list = season_entry.get("standings", [])
    for st in standings_list:
        team = st.get("team", "")
        wins = st.get("wins", 0)
        pf = st.get("points_for", 0)
        pa = st.get("points_against", 0)

        if wins > 0:
            r = records["team"]["most_wins_season"]
            if _beats(r, wins):
                records["team"]["most_wins_season"] = _record_entry(wins, team, team, seq)

        if pf > 0:
            r = records["team"]["most_points_season"]
            if _beats(r, pf):
                records["team"]["most_points_season"] = _record_entry(pf, team, team, seq)

    # Championships
    if champ:
        champ_count = sum(1 for s in seasons if (s.get("state_champion") or "") == champ)
        r = records["team"]["most_championships"]
        if _beats(r, champ_count):
            records["team"]["most_championships"] = _record_entry(
                champ_count, champ, champ, seq, detail="all-time"
            )

    # --- Player single-season records ---
    for s in season_player_stats.values():
        if s.rush_yds > 0:
            r = records["rushing"]["single_season_yards"]
            if _beats(r, s.rush_yds):
                records["rushing"]["single_season_yards"] = _record_entry(
                    s.rush_yds, s.player_name, s.team_name, seq
                )
        if s.rush_td > 0:
            r = records["rushing"]["single_season_td"]
            if _beats(r, s.rush_td):
                records["rushing"]["single_season_td"] = _record_entry(
                    s.rush_td, s.player_name, s.team_name, seq
                )
        if s.pass_yds > 0:
            r = records["passing"]["single_season_yards"]
            if _beats(r, s.pass_yds):
                records["passing"]["single_season_yards"] = _record_entry(
                    s.pass_yds, s.player_name, s.team_name, seq
                )
        if s.pass_td > 0:
            r = records["passing"]["single_season_td"]
            if _beats(r, s.pass_td):
                records["passing"]["single_season_td"] = _record_entry(
                    s.pass_td, s.player_name, s.team_name, seq
                )
        if s.rec_yds > 0:
            r = records["receiving"]["single_season_yards"]
            if _beats(r, s.rec_yds):
                records["receiving"]["single_season_yards"] = _record_entry(
                    s.rec_yds, s.player_name, s.team_name, seq
                )
        if s.rec_td > 0:
            r = records["receiving"]["single_season_td"]
            if _beats(r, s.rec_td):
                records["receiving"]["single_season_td"] = _record_entry(
                    s.rec_td, s.player_name, s.team_name, seq
                )
        if s.sacks > 0:
            r = records["defense"]["single_season_sacks"]
            if _beats(r, s.sacks):
                records["defense"]["single_season_sacks"] = _record_entry(
                    s.sacks, s.player_name, s.team_name, seq
                )
        if s.interceptions > 0:
            r = records["defense"]["single_season_interceptions"]
            if _beats(r, s.interceptions):
                records["defense"]["single_season_interceptions"] = _record_entry(
                    s.interceptions, s.player_name, s.team_name, seq
                )

    # --- Career records (recompute from all seasons with player_stats) ---
    seasons_with_stats = [s for s in seasons if "player_stats" in s]
    career = _aggregate_career_stats(seasons_with_stats)

    for (name, team), stats in career.items():
        ry = stats["rush_yds"]
        if ry > 0:
            r = records["rushing"]["career_yards"]
            if _beats(r, ry):
                records["rushing"]["career_yards"] = _record_entry(ry, name, team, seq, detail="career")
        py = stats["pass_yds"]
        if py > 0:
            r = records["passing"]["career_yards"]
            if _beats(r, py):
                records["passing"]["career_yards"] = _record_entry(py, name, team, seq, detail="career")
        recy = stats["rec_yds"]
        if recy > 0:
            r = records["receiving"]["career_yards"]
            if _beats(r, recy):
                records["receiving"]["career_yards"] = _record_entry(recy, name, team, seq, detail="career")
        sacks = stats["sacks"]
        if sacks > 0:
            r = records["defense"]["career_sacks"]
            if _beats(r, sacks):
                records["defense"]["career_sacks"] = _record_entry(sacks, name, team, seq, detail="career")

    return records


def update_records_from_game(
    records: Dict[str, Any],
    game_stats: Dict[int, PlayerGameStats],
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    season_num: int = 0,
) -> Dict[str, Any]:
    """
    Update game records from one game's stats.
    Call after each game (before merging into season).
    """
    for gs in game_stats.values():
        if gs.pass_yds > 0:
            r = records["game"]["most_passing_yards"]
            if _beats(r, gs.pass_yds):
                records["game"]["most_passing_yards"] = _record_entry(
                    gs.pass_yds, gs.player_name, gs.team_name, season_num, detail="single game"
                )
        if gs.rush_yds > 0:
            r = records["game"]["most_rushing_yards"]
            if _beats(r, gs.rush_yds):
                records["game"]["most_rushing_yards"] = _record_entry(
                    gs.rush_yds, gs.player_name, gs.team_name, season_num, detail="single game"
                )

    max_pts = max(home_score, away_score)
    if max_pts > 0:
        r = records["game"]["most_points"]
        if _beats(r, max_pts):
            team = home_team if home_score >= away_score else away_team
            records["game"]["most_points"] = _record_entry(
                max_pts, team, team, season_num, detail="single game"
            )

    return records


def format_records_text(records: Dict[str, Any]) -> List[str]:
    """Format record book as readable text."""
    lines = []
    lines.append("RECORD BOOK")
    lines.append("=" * 50)

    def fmt(r: Optional[Dict], label: str) -> str:
        if not r:
            return f"  {label}: (no record)"
        v = r.get("value", "?")
        h = r.get("holder", "?")
        t = r.get("holder_team", "")
        s = r.get("season", "?")
        tail = f" ({t})" if t and t != h else ""
        return f"  {label}: {v} - {h}{tail} (Season {s})"

    lines.append("")
    lines.append("Team")
    lines.append("-" * 30)
    lines.append(fmt(records["team"]["most_championships"], "Most Championships"))
    lines.append(fmt(records["team"]["most_wins_season"], "Most Wins (Season)"))
    lines.append(fmt(records["team"]["most_points_season"], "Most Points (Season)"))

    lines.append("")
    lines.append("Rushing")
    lines.append("-" * 30)
    lines.append(fmt(records["rushing"]["single_season_yards"], "Single Season Yards"))
    lines.append(fmt(records["rushing"]["career_yards"], "Career Yards"))
    lines.append(fmt(records["rushing"]["single_season_td"], "Single Season TD"))

    lines.append("")
    lines.append("Passing")
    lines.append("-" * 30)
    lines.append(fmt(records["passing"]["single_season_yards"], "Single Season Yards"))
    lines.append(fmt(records["passing"]["career_yards"], "Career Yards"))
    lines.append(fmt(records["passing"]["single_season_td"], "Single Season TD"))

    lines.append("")
    lines.append("Receiving")
    lines.append("-" * 30)
    lines.append(fmt(records["receiving"]["single_season_yards"], "Single Season Yards"))
    lines.append(fmt(records["receiving"]["career_yards"], "Career Yards"))
    lines.append(fmt(records["receiving"]["single_season_td"], "Single Season TD"))

    lines.append("")
    lines.append("Defense")
    lines.append("-" * 30)
    lines.append(fmt(records["defense"]["single_season_sacks"], "Single Season Sacks"))
    lines.append(fmt(records["defense"]["career_sacks"], "Career Sacks"))
    lines.append(fmt(records["defense"]["single_season_interceptions"], "Single Season INT"))

    lines.append("")
    lines.append("Game")
    lines.append("-" * 30)
    lines.append(fmt(records["game"]["most_passing_yards"], "Most Passing Yards (Game)"))
    lines.append(fmt(records["game"]["most_rushing_yards"], "Most Rushing Yards (Game)"))
    lines.append(fmt(records["game"]["most_points"], "Most Points (Game)"))

    return lines
