"""
Offseason transfer system with two-stage flow:
1) Declare transfer portal entrants
2) Resolve destinations and move players
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from systems.coach_development import _goal_evaluation, _postseason_tier as _cd_postseason_tier

# Max portal candidates per team before the league-wide cap (not lifetime player cap).
TRANSFER_PORTAL_MAX_PER_TEAM = 2
# Max outgoing / incoming moves per team when resolving destinations.
TRANSFER_MOVES_MAX_OUT_PER_TEAM = 2
TRANSFER_MOVES_MAX_IN_PER_TEAM = 2
# League-wide portal size: ~50 entrants per 100 teams (typical total moves ~30–70 after resolution).
TRANSFER_PORTAL_LEAGUE_SHARE = 0.50


def _num(v: Any, default: float = 0.0) -> float:
    try:
        out = float(v)
        return out if out == out else default
    except Exception:
        return default


def _player_overall_proxy(p: Any) -> float:
    keys = [
        "speed",
        "agility",
        "acceleration",
        "strength",
        "football_iq",
        "coachability",
        "discipline",
        "confidence",
    ]
    vals = [_num(getattr(p, k, 50), 50) for k in keys]
    return sum(vals) / max(1, len(vals))


def _team_success_score(standings_row: Dict[str, Any]) -> float:
    w = _num(standings_row.get("wins", 0), 0)
    l = _num(standings_row.get("losses", 0), 0)
    g = max(1.0, w + l)
    win_pct = w / g
    # Better teams lower transfer risk.
    return (1.0 - win_pct) * 100.0


def _program_expectations_miss(
    team_name: str,
    standings_row: Dict[str, Any],
    team_obj: Any,
) -> float:
    """CPU / no-goal case: underperforming vs prestige raises transfer pressure (0–75)."""
    w = int(_num(standings_row.get("wins", 0), 0))
    l = int(_num(standings_row.get("losses", 0), 0))
    g = max(1, w + l)
    win_pct = w / float(g)
    prestige = float(_num(getattr(team_obj, "prestige", 5), 5))
    expected = 0.30 + (prestige / 15.0) * 0.38
    gap = max(0.0, expected - win_pct)
    return min(75.0, gap * 115.0)


def _user_goal_miss_pressure(
    team_name: str,
    standings_row: Dict[str, Any],
    standings: Dict[str, Any],
    season_goals: Optional[Dict[str, Any]],
    user_team: Optional[str],
    bracket_results: List[Dict[str, Any]],
    champion: str,
) -> float:
    """User team: missed win / stage goals add pressure (0–88)."""
    if not user_team or team_name != user_team:
        return 0.0
    if not isinstance(season_goals, dict):
        return 0.0
    has_goal = season_goals.get("win_goal") is not None or str(season_goals.get("stage_goal") or "").strip()
    if not has_goal:
        return 0.0
    w = int(_num(standings_row.get("wins", 0), 0))
    l = int(_num(standings_row.get("losses", 0), 0))
    tier = _cd_postseason_tier(team_name, standings, bracket_results, champion or "")
    achieved_rank = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(tier, 0)
    win_ok, stage_ok = _goal_evaluation(season_goals, w, l, achieved_rank)
    pressure = 0.0
    if not win_ok:
        pressure += 24.0
    if not stage_ok:
        pressure += 32.0
    return min(88.0, pressure)


def _expectations_pressure(
    team_name: str,
    standings_row: Dict[str, Any],
    team_obj: Any,
    standings: Dict[str, Any],
    season_goals: Optional[Dict[str, Any]],
    user_team: Optional[str],
    bracket_results: List[Dict[str, Any]],
    champion: str,
) -> float:
    g_user = _user_goal_miss_pressure(
        team_name, standings_row, standings, season_goals, user_team, bracket_results, champion
    )
    g_prog = _program_expectations_miss(team_name, standings_row, team_obj)
    return max(g_user, g_prog)


def _rising_star_upside_pressure(p_ovr: float, top_cut: float, prestige: float) -> float:
    """Elite players at lower-prestige programs are more likely to test the portal (0–40)."""
    if p_ovr < top_cut - 0.01:
        return 0.0
    gap = min(20.0, max(0.0, p_ovr - top_cut))
    under = max(0.0, 11.0 - float(prestige)) / 11.0
    return min(40.0, gap * under * 2.2)


def _playing_time_score(team: Any, p: Any) -> float:
    pos = str(getattr(p, "position", "") or "")
    name = str(getattr(p, "name", "") or "")
    if not pos or not name:
        return 65.0
    order = (getattr(team, "depth_chart_order", None) or {}).get(pos)
    if isinstance(order, list) and order:
        try:
            idx = [str(x) for x in order].index(name)
        except ValueError:
            idx = -1
        if idx == 0:
            return 8.0
        if idx == 1:
            return 48.0
        if idx == 2:
            return 68.0
        if idx >= 3:
            return 82.0
    return 70.0


def _culture_score(team: Any) -> float:
    cul = _num(getattr(team, "culture_grade", 5), 5)
    dis = _num(getattr(getattr(team, "coach", None), "culture", 5), 5)
    avg = (cul + dis) / 2.0
    # Lower culture -> higher transfer pressure.
    return max(0.0, min(100.0, (10.0 - avg) * 10.0))


def _region_neighbors(regions: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if not regions:
        return out
    for i, r in enumerate(regions):
        left = regions[(i - 1) % len(regions)]
        right = regions[(i + 1) % len(regions)]
        out[r] = [x for x in {left, right} if x != r]
    return out


def _proximity_opportunity_score(
    teams: Dict[str, Any],
    current_team_name: str,
    player_pos: str,
    current_region: str,
    neighbors: Dict[str, List[str]],
) -> float:
    score = 0.0
    nbs = set(neighbors.get(current_region, []))
    for tn, t in teams.items():
        if tn == current_team_name:
            continue
        reg = str(getattr(t, "region", "") or "")
        roster = list(getattr(t, "roster", []) or [])
        pos_count = sum(1 for rp in roster if str(getattr(rp, "position", "") or "") == player_pos)
        need = max(0.0, min(1.0, (5.0 - pos_count) / 5.0))
        if reg == current_region:
            score += need * 1.0
        elif reg in nbs:
            score += need * 0.6
        else:
            score += need * 0.2
    return max(0.0, min(100.0, score * 18.0))


def _distance_factor(origin_region: str, destination_region: str, neighbors: Dict[str, List[str]]) -> float:
    if destination_region == origin_region:
        return 1.0
    if destination_region in neighbors.get(origin_region, []):
        return 0.7
    return 0.4


def _playing_time_available(dest_team: Any, pos: str) -> float:
    roster = list(getattr(dest_team, "roster", []) or [])
    same_pos = sum(1 for p in roster if str(getattr(p, "position", "") or "") == pos)
    return max(0.0, min(100.0, (1.0 - min(1.0, same_pos / 5.0)) * 100.0))


def _dest_team_success(standings_row: Dict[str, Any]) -> float:
    w = _num(standings_row.get("wins", 0), 0)
    l = _num(standings_row.get("losses", 0), 0)
    g = max(1.0, w + l)
    return max(0.0, min(100.0, (w / g) * 100.0))


def _culture_fit(dest_team: Any) -> float:
    cul = _num(getattr(dest_team, "culture_grade", 5), 5)
    dis = _num(getattr(getattr(dest_team, "coach", None), "culture", 5), 5)
    return max(0.0, min(100.0, ((cul + dis) / 20.0) * 100.0))


def run_transfer_stage_1(
    teams: Dict[str, Any],
    standings: Dict[str, Any],
    *,
    current_year: int,
    season_goals: Optional[Dict[str, Any]] = None,
    user_team: Optional[str] = None,
    bracket_results: Optional[List[Dict[str, Any]]] = None,
    champion: Optional[str] = None,
) -> Dict[str, Any]:
    rng = random.Random(int(current_year) * 977 + len(teams))
    br = list(bracket_results or [])
    champ = str(champion or "")
    players_by_team: Dict[str, List[Any]] = {tn: list(getattr(t, "roster", []) or []) for tn, t in teams.items()}
    total_players = sum(len(v) for v in players_by_team.values())
    if total_players == 0:
        return {
            "year": int(current_year),
            "pool_pct": 0.0,
            "eligible_count": 0,
            "selected_count": 0,
            "entries": [],
            "summary": "No transfer activity.",
        }

    regions = sorted({str(getattr(t, "region", "") or "State") for t in teams.values()})
    neighbors = _region_neighbors(regions)
    out_candidates: List[Dict[str, Any]] = []

    for team_name, team in teams.items():
        roster = players_by_team.get(team_name, [])
        if not roster:
            continue
        sorted_ovr = sorted((_player_overall_proxy(p) for p in roster), reverse=True)
        top_cut_idx = max(0, int(len(sorted_ovr) * 0.15) - 1)
        top_cut = sorted_ovr[top_cut_idx] if sorted_ovr else 200.0
        srow = standings.get(team_name, {}) or {}
        prestige = float(_num(getattr(team, "prestige", 5), 5))
        expectations = _expectations_pressure(
            team_name, srow, team, standings, season_goals, user_team, br, champ
        )
        team_bucket: List[Dict[str, Any]] = []

        for p in roster:
            # Player.year is HS grade 9–12 for generated rosters (see player_generator).
            # Legacy saves may use 1–4 (seasons of eligibility); treat 3+ there as upperclass.
            year = int(_num(getattr(p, "year", 0), 0))
            if year >= 9:
                if year >= 12:
                    continue  # seniors: skip portal for this pass
            elif year >= 3:
                continue
            if int(_num(getattr(p, "transfer_count", 0), 0)) >= 1:
                continue

            pos = str(getattr(p, "position", "") or "")
            if not pos:
                continue
            p_ovr = _player_overall_proxy(p)
            playing_time = _playing_time_score(team, p)
            team_success = _team_success_score(srow)
            culture = _culture_score(team)
            region = str(getattr(team, "region", "") or "State")
            proximity = _proximity_opportunity_score(teams, team_name, pos, region, neighbors)
            variance = rng.uniform(0, 100)
            upside = _rising_star_upside_pressure(p_ovr, top_cut, prestige)

            score = (
                playing_time * 0.34
                + team_success * 0.16
                + culture * 0.14
                + proximity * 0.12
                + expectations * 0.12
                + variance * 0.09
                + upside * 0.03
            )
            # Slight boost so more players clear the portal gate.
            score += 4.0
            # Stars at marquee programs stick; elite players at weaker brands keep exit pressure via `upside`.
            if p_ovr >= top_cut and prestige >= 11:
                score *= 0.93
            elif p_ovr >= top_cut and prestige >= 7:
                score *= 0.97

            # Score gate: higher = more likely to enter portal.
            if score <= 42:
                continue
            raw = float(score)
            team_bucket.append(
                {
                    "player": str(getattr(p, "name", "Unknown")),
                    "team": team_name,
                    "from_team": team_name,
                    "position": pos,
                    "year": year,
                    "_sort": raw,
                    "region": region,
                }
            )

        team_bucket.sort(key=lambda x: -float(x["_sort"]))
        for row in team_bucket[:TRANSFER_PORTAL_MAX_PER_TEAM]:
            sc = float(row.pop("_sort"))
            out_candidates.append(
                {
                    "player": row["player"],
                    "team": row["team"],
                    "from_team": row["from_team"],
                    "position": row["position"],
                    "year": row["year"],
                    "score": round(sc, 1),
                    "priority": "high" if sc > 80 else "normal",
                    "region": row["region"],
                    "transfer_probability": round(min(0.97, max(0.35, sc / 100.0)) * 100, 1),
                }
            )

    # League-sized portal: ~50 entrants per 100 teams, min 1 when multi-team.
    n_teams = len(teams)
    cap = max(1, int(round(n_teams * TRANSFER_PORTAL_LEAGUE_SHARE))) if n_teams else 0
    effective_pool_pct = (cap / total_players * 100.0) if total_players else 0.0
    out_candidates.sort(key=lambda x: (-float(x["score"]), x["team"], x["player"]))
    selected = out_candidates[:cap]
    return {
        "year": int(current_year),
        "pool_pct": round(effective_pool_pct, 2),
        "eligible_count": len(out_candidates),
        "selected_count": len(selected),
        "entries": selected,
        "summary": (
            f"{len(selected)} players entered the transfer portal "
            f"({cap} league cap, up to {TRANSFER_PORTAL_MAX_PER_TEAM} entrants per team, "
            f"≈ {round(effective_pool_pct, 1)}% of league roster)."
        ),
    }


def run_transfer_stage_2(
    teams: Dict[str, Any],
    standings: Dict[str, Any],
    stage1_payload: Dict[str, Any],
    *,
    current_year: int,
) -> Dict[str, Any]:
    entries = list((stage1_payload or {}).get("entries") or [])
    if not entries:
        return {"year": int(current_year), "moved_count": 0, "blocked_count": 0, "entries": [], "summary": "No transfers resolved."}

    rng = random.Random(int(current_year) * 1283 + len(entries))
    regions = sorted({str(getattr(t, "region", "") or "State") for t in teams.values()})
    neighbors = _region_neighbors(regions)
    incoming_count: Dict[str, int] = {tn: 0 for tn in teams}
    outgoing_count: Dict[str, int] = {tn: 0 for tn in teams}
    moved: List[Dict[str, Any]] = []
    blocked = 0

    for row in entries:
        origin = str(row.get("team", ""))
        player_name = str(row.get("player", ""))
        pos = str(row.get("position", ""))
        origin_team = teams.get(origin)
        if not origin_team or outgoing_count.get(origin, 0) >= TRANSFER_MOVES_MAX_OUT_PER_TEAM:
            blocked += 1
            continue
        roster = list(getattr(origin_team, "roster", []) or [])
        player_obj = next((p for p in roster if str(getattr(p, "name", "")) == player_name), None)
        if not player_obj:
            blocked += 1
            continue
        if int(_num(getattr(player_obj, "transfer_count", 0), 0)) >= 1:
            blocked += 1
            continue

        origin_region = str(getattr(origin_team, "region", "") or "State")
        roll = rng.random()
        target_bucket = "same" if roll < 0.70 else "neighbor" if roll < 0.90 else "out"

        def _collect_candidates(bucket: str) -> List[Tuple[float, str, Any]]:
            acc: List[Tuple[float, str, Any]] = []
            for tn, t in teams.items():
                if tn == origin:
                    continue
                if incoming_count.get(tn, 0) >= TRANSFER_MOVES_MAX_IN_PER_TEAM:
                    continue
                dest_region = str(getattr(t, "region", "") or "State")
                if bucket != "any":
                    if bucket == "same" and dest_region != origin_region:
                        continue
                    if bucket == "neighbor" and dest_region not in neighbors.get(origin_region, []):
                        continue
                    if bucket == "out" and (
                        dest_region == origin_region or dest_region in neighbors.get(origin_region, [])
                    ):
                        continue

                pt = _playing_time_available(t, pos)
                succ = _dest_team_success(standings.get(tn, {}))
                fit = _culture_fit(t)
                dist = _distance_factor(origin_region, dest_region, neighbors) * 100.0
                school_fit = pt * 0.40 + succ * 0.20 + fit * 0.20 + dist * 0.20
                if succ >= 75 and _num(getattr(t, "prestige", 5), 5) >= 12:
                    school_fit -= 12
                acc.append((school_fit, tn, t))
            return acc

        candidates = _collect_candidates(target_bucket)
        # Single-region (or empty neighbor list) leagues often had no "neighbor"/"out" destinations.
        if not candidates:
            candidates = _collect_candidates("same")
        if not candidates:
            candidates = _collect_candidates("any")

        if not candidates:
            blocked += 1
            continue
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, dest_name, dest_team = candidates[0]
        try:
            origin_team.remove_player(player_obj)
            dest_team.add_player(player_obj)
            setattr(player_obj, "transfer_count", int(_num(getattr(player_obj, "transfer_count", 0), 0)) + 1)
            if not getattr(player_obj, "home_region", None):
                setattr(player_obj, "home_region", origin_region)
            outgoing_count[origin] = outgoing_count.get(origin, 0) + 1
            incoming_count[dest_name] = incoming_count.get(dest_name, 0) + 1
            moved.append(
                {
                    "player": player_name,
                    "from_team": origin,
                    "to_team": dest_name,
                    "position": pos,
                    "from_region": origin_region,
                    "to_region": str(getattr(dest_team, "region", "") or "State"),
                }
            )
        except Exception:
            blocked += 1
            continue

    return {
        "year": int(current_year),
        "moved_count": len(moved),
        "blocked_count": blocked,
        "entries": moved,
        "summary": f"{len(moved)} transfers finalized.",
    }

