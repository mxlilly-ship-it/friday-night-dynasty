"""
Awards system: Player of the Year, Offensive/Defensive POY, All-State 1st Team.
Uses PlayerSeasonStats from the completed season.
"""

from typing import Any, Dict, List, Optional

from systems.game_stats import PlayerSeasonStats


def _offensive_score(s: PlayerSeasonStats) -> tuple:
    """(total_yds, total_td) for offensive ranking."""
    total_yds = s.pass_yds + s.rush_yds + s.rec_yds
    total_td = s.pass_td + s.rush_td + s.rec_td
    return (total_yds, total_td)


def _defensive_score(s: PlayerSeasonStats) -> float:
    """Combined defensive impact: tackles + sacks*3 + INT*5."""
    return s.tackles + s.sacks * 3 + s.interceptions * 5


def _overall_score(s: PlayerSeasonStats) -> tuple:
    """For POY: combine offensive and defensive impact."""
    off_yds, off_td = _offensive_score(s)
    def_score = _defensive_score(s)
    return (off_yds + def_score * 2, off_td)


def _get_offensive_player_of_the_year(
    stats_map: Dict[int, PlayerSeasonStats],
) -> Optional[Dict[str, Any]]:
    """Best offensive player: total yards + TDs."""
    all_stats = [s for s in stats_map.values() if _offensive_score(s) != (0, 0)]
    if not all_stats:
        return None
    best = max(all_stats, key=_offensive_score)
    return {
        "name": best.player_name,
        "team": best.team_name,
        "pass_yds": best.pass_yds,
        "pass_td": best.pass_td,
        "rush_yds": best.rush_yds,
        "rush_td": best.rush_td,
        "rec": best.rec,
        "rec_yds": best.rec_yds,
        "rec_td": best.rec_td,
    }


def _get_defensive_player_of_the_year(
    stats_map: Dict[int, PlayerSeasonStats],
) -> Optional[Dict[str, Any]]:
    """Best defensive player: tackles + sacks*3 + INT*5."""
    all_stats = [s for s in stats_map.values() if _defensive_score(s) > 0]
    if not all_stats:
        return None
    best = max(all_stats, key=_defensive_score)
    return {
        "name": best.player_name,
        "team": best.team_name,
        "tackles": best.tackles,
        "sacks": best.sacks,
        "tfl": best.tfl,
        "interceptions": best.interceptions,
    }


def _get_player_of_the_year(
    stats_map: Dict[int, PlayerSeasonStats],
) -> Optional[Dict[str, Any]]:
    """Best overall player: combined offensive + defensive impact."""
    all_stats = list(stats_map.values())
    if not all_stats:
        return None
    best = max(all_stats, key=_overall_score)
    return {
        "name": best.player_name,
        "team": best.team_name,
        "pass_yds": best.pass_yds,
        "pass_td": best.pass_td,
        "rush_yds": best.rush_yds,
        "rush_td": best.rush_td,
        "rec_yds": best.rec_yds,
        "rec_td": best.rec_td,
        "tackles": best.tackles,
        "sacks": best.sacks,
        "interceptions": best.interceptions,
    }


def _infer_primary_position(s: PlayerSeasonStats) -> str:
    """Infer position from stats. Returns QB, RB, WR, DL, LB, or DB."""
    pass_impact = s.pass_yds + s.pass_td * 6 if s.att >= 10 else 0
    rush_impact = s.rush_yds + s.rush_td * 6
    rec_impact = s.rec_yds + s.rec_td * 6
    def_sacks = s.sacks
    def_tackles = s.tackles
    def_int = s.interceptions

    if pass_impact >= rush_impact and pass_impact >= rec_impact and s.att >= 20:
        return "QB"
    if rush_impact >= rec_impact:
        return "RB"
    if rec_impact > 0:
        return "WR"
    if def_sacks >= def_tackles * 0.3 and def_sacks >= def_int:
        return "DL"
    if def_int >= def_tackles * 0.5 and def_int > def_sacks:
        return "DB"
    return "LB"


def _get_all_state_first_team(
    stats_map: Dict[int, PlayerSeasonStats],
) -> List[Dict[str, Any]]:
    """All-State 1st Team: QB(1), RB(2), WR(2), DL(2), LB(2), DB(2)."""
    all_stats = list(stats_map.values())
    if not all_stats:
        return []

    by_pos: Dict[str, List[PlayerSeasonStats]] = {}
    for s in all_stats:
        pos = _infer_primary_position(s)
        by_pos.setdefault(pos, []).append(s)

    result: List[Dict[str, Any]] = []
    used_keys: set = set()

    def pick(positions: List[str], key_fn, count: int) -> None:
        candidates = []
        for pos in positions:
            for s in by_pos.get(pos, []):
                key = (s.player_name, s.team_name)
                if key not in used_keys:
                    val = key_fn(s)
                    candidates.append((val if isinstance(val, (int, float)) else val[0], s))
        candidates.sort(key=lambda x: -x[0])
        for _, s in candidates[:count]:
            used_keys.add((s.player_name, s.team_name))
            result.append({
                "position": _infer_primary_position(s),
                "name": s.player_name,
                "team": s.team_name,
                "stats": {
                    "pass_yds": s.pass_yds,
                    "rush_yds": s.rush_yds,
                    "rec_yds": s.rec_yds,
                    "tackles": s.tackles,
                    "sacks": s.sacks,
                    "interceptions": s.interceptions,
                },
            })

    pick(["QB"], lambda s: s.pass_yds, 1)
    pick(["RB"], lambda s: s.rush_yds, 2)
    pick(["WR"], lambda s: s.rec_yds, 2)
    pick(["DL"], lambda s: s.sacks, 2)
    pick(["LB"], lambda s: s.tackles, 2)
    pick(["DB"], lambda s: s.interceptions, 2)

    return result


def compute_awards(
    season_player_stats: Dict[int, PlayerSeasonStats],
) -> Dict[str, Any]:
    """Compute all awards for a season."""
    return {
        "player_of_the_year": _get_player_of_the_year(season_player_stats),
        "offensive_player_of_the_year": _get_offensive_player_of_the_year(season_player_stats),
        "defensive_player_of_the_year": _get_defensive_player_of_the_year(season_player_stats),
        "all_state_first_team": _get_all_state_first_team(season_player_stats),
    }


def format_awards_text(awards: Dict[str, Any]) -> List[str]:
    """Format awards as readable text lines."""
    lines = []
    lines.append("AWARDS")
    lines.append("-" * 50)

    poy = awards.get("player_of_the_year")
    lines.append(f"Player of the Year: {poy['name']} ({poy['team']})" if poy else "Player of the Year: (none)")

    opoy = awards.get("offensive_player_of_the_year")
    if opoy:
        yds = opoy.get("pass_yds", 0) + opoy.get("rush_yds", 0) + opoy.get("rec_yds", 0)
        lines.append(f"Offensive Player of the Year: {opoy['name']} ({opoy['team']}) - {yds} total yds")
    else:
        lines.append("Offensive Player of the Year: (none)")

    dpoy = awards.get("defensive_player_of_the_year")
    if dpoy:
        parts = [f"{dpoy['tackles']} tack"] if dpoy.get("tackles") else []
        if dpoy.get("sacks"):
            parts.append(f"{dpoy['sacks']} sack")
        if dpoy.get("interceptions"):
            parts.append(f"{dpoy['interceptions']} INT")
        line = f"Defensive Player of the Year: {dpoy['name']} ({dpoy['team']})"
        if parts:
            line += " - " + ", ".join(parts)
        lines.append(line)
    else:
        lines.append("Defensive Player of the Year: (none)")

    lines.append("")
    lines.append("All-State 1st Team")
    lines.append("-" * 30)
    for entry in awards.get("all_state_first_team", []):
        pos = entry.get("position", "?")
        name = entry.get("name", "?")
        team = entry.get("team", "?")
        s = entry.get("stats", {})
        if pos in ("QB", "RB", "WR"):
            yds = s.get("pass_yds", 0) + s.get("rush_yds", 0) + s.get("rec_yds", 0)
            ext = f" - {yds} yds" if yds else ""
        else:
            t, sa, i = s.get("tackles", 0), s.get("sacks", 0), s.get("interceptions", 0)
            ext = f" - {t} tack, {sa} sack, {i} INT" if (t or sa or i) else ""
        lines.append(f"  {pos}: {name} ({team}){ext}")

    return lines
