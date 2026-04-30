"""
Regular-season regional titles: best record in each scheduling pod wins the region.

Pods match ``league_structure.scheduling_pod_key(classification, region)`` — the same
groups that play each other in the regular season. Ranking uses wins, then point
differential, then points for (then name), aligned with playoff seeding / rankings UI.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from systems.league_structure import scheduling_pod_key


def _standings_sort_tuple(team_name: str, standings: Dict[str, Dict[str, Any]]) -> Tuple[int, int, int, str]:
    s = standings.get(team_name) or {}
    w = int(s.get("wins", 0) or 0)
    pf = int(s.get("points_for", 0) or 0)
    pa = int(s.get("points_against", 0) or 0)
    diff = pf - pa
    # Higher wins / diff / pf first → negate for ascending sort
    return (-w, -diff, -pf, team_name)


def award_regular_season_regional_titles(state: Dict[str, Any]) -> List[str]:
    """
    Increment ``regional_championships`` on each pod's top regular-season team.

    Mutates team dicts in ``state["teams"]``. Uses ``state["standings"]``.
    Returns list of team names awarded (for logging).
    """
    teams_list = state.get("teams") or []
    standings = state.get("standings") or {}
    if not isinstance(teams_list, list) or not isinstance(standings, dict):
        return []

    pods: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    by_name: Dict[str, Dict[str, Any]] = {}
    for t in teams_list:
        if not isinstance(t, dict):
            continue
        n = t.get("name")
        if not n or not isinstance(n, str):
            continue
        by_name[n] = t
        key = scheduling_pod_key(t.get("classification"), t.get("region"))
        pods[key].append(n)

    winners: List[str] = []
    for _key, names in pods.items():
        in_st = [n for n in names if n in standings]
        if not in_st:
            continue
        in_st.sort(key=lambda nm: _standings_sort_tuple(nm, standings))
        champ = in_st[0]
        row = by_name.get(champ)
        if row is None:
            continue
        prev = int(row.get("regional_championships", 0) or 0)
        row["regional_championships"] = prev + 1
        winners.append(champ)
    return winners
