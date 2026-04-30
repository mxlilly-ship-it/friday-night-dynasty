"""
Offseason transfer system with two-stage flow:
1) Declare transfer portal entrants
2) Resolve destinations and move players
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple


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
) -> Dict[str, Any]:
    rng = random.Random(int(current_year) * 977 + len(teams))
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
        out_count = 0

        for p in roster:
            year = int(_num(getattr(p, "year", 0), 0))
            if year >= 3:
                continue
            if int(_num(getattr(p, "transfer_count", 0), 0)) >= 1:
                continue

            pos = str(getattr(p, "position", "") or "")
            if not pos:
                continue
            p_ovr = _player_overall_proxy(p)
            playing_time = _playing_time_score(team, p)
            team_success = _team_success_score(standings.get(team_name, {}))
            culture = _culture_score(team)
            region = str(getattr(team, "region", "") or "State")
            proximity = _proximity_opportunity_score(teams, team_name, pos, region, neighbors)
            variance = rng.uniform(0, 100)

            score = (
                playing_time * 0.38
                + team_success * 0.20
                + culture * 0.18
                + proximity * 0.14
                + variance * 0.10
            )
            if p_ovr >= top_cut:
                score *= 0.82

            # Gate was 65; lowered so depth-chart starters and average backups still produce portal churn.
            if score <= 52:
                continue
            if out_count >= 8:
                continue
            out_count += 1
            out_candidates.append(
                {
                    "player": str(getattr(p, "name", "Unknown")),
                    "team": team_name,
                    "position": pos,
                    "year": year,
                    "score": round(float(score), 1),
                    "priority": "high" if score > 80 else "normal",
                    "region": region,
                    "transfer_probability": round(min(0.97, max(0.35, score / 100.0)) * 100, 1),
                }
            )

    cap_pct = rng.uniform(0.09, 0.16)
    cap = max(2, int(round(total_players * cap_pct)))
    out_candidates.sort(key=lambda x: (-float(x["score"]), x["team"], x["player"]))
    selected = out_candidates[:cap]
    return {
        "year": int(current_year),
        "pool_pct": round(cap_pct * 100.0, 2),
        "eligible_count": len(out_candidates),
        "selected_count": len(selected),
        "entries": selected,
        "summary": f"{len(selected)} players entered the transfer portal ({round(cap_pct * 100.0, 1)}% cap).",
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
        if not origin_team or outgoing_count.get(origin, 0) >= 8:
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
                if incoming_count.get(tn, 0) >= 8:
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

