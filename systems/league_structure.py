"""
League structure: classification + region scheduling pods, bounds, and playoff classification scope.

Teams with the same (classification, region) form one *scheduling pod*: they only play each
other in the regular season. At the end of the regular season, the best record in each pod
earns a regional title (``Team.regional_championships``). Playoffs are one bracket per
*classification*, seeded by overall standings across all regions in that class (state champion).
Region does not scope playoffs.

``league_structure`` on save state holds defaults and optional per-class/region team-count bounds.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from models.team import Team

logger = logging.getLogger(__name__)

# When region is omitted (legacy saves / data files), all teams share this pod label.
DEFAULT_REGION_KEY = "State"

STRUCTURE_VERSION = 1

# ---------------------------------------------------------------------------
# Region *names* are free-form strings on each team; use any label you like.
# Below are common presets for editors / UI (not enforced by the sim).
# ---------------------------------------------------------------------------

# Compass-style
REGION_PRESET_COMPASS: Tuple[str, ...] = ("North", "East", "South", "West")

# Letter pods (often 4 divisions)
REGION_PRESET_LETTERS: Tuple[str, ...] = ("A", "B", "C", "D")

# Numbered (with or without "Region " prefix — both work; keys must match team JSON exactly)
REGION_PRESET_NUMBERED: Tuple[str, ...] = ("Region 1", "Region 2", "Region 3", "Region 4")

# Short numeric labels (also valid)
REGION_PRESET_NUMBERED_SHORT: Tuple[str, ...] = ("1", "2", "3", "4")

REGION_NAME_PRESETS: Dict[str, Tuple[str, ...]] = {
    "compass": REGION_PRESET_COMPASS,
    "letters": REGION_PRESET_LETTERS,
    "numbered": REGION_PRESET_NUMBERED,
    "numbered_short": REGION_PRESET_NUMBERED_SHORT,
}

# Typical league-design targets for how many schools per pod (validation hints / UI).
# Any size is allowed if you set ``class_region_bounds`` accordingly; round-robin still uses 10 games/team.
# 8 is included for 32 teams ÷ 4 regions; 10 for 40 ÷ 4.
SUGGESTED_TEAMS_PER_REGION: Tuple[int, ...] = (5, 6, 8, 10, 12)

# Total teams in one *classification* when split evenly across four regions (editors / UI presets).
# 32 → 4×8 (fits 8-team playoff pod); 40 → 4×10.
SUGGESTED_CLASS_TOTAL_SIZES: Tuple[int, ...] = (32, 40)


def class_total_four_region_split(total: int) -> Optional[Tuple[int, int]]:
    """
    If ``total`` is divisible by 4, return (regions, teams_per_region). Else None.
    E.g. 32 → (4, 8), 40 → (4, 10).
    """
    t = int(total)
    if t <= 0 or t % 4 != 0:
        return None
    return (4, t // 4)


def exact_pod_bounds(team_count: int) -> Tuple[int, int]:
    """Return ``(min, max)`` both equal to ``team_count`` for strict per-region roster sizes."""
    n = max(0, int(team_count))
    return (n, n)


def merge_class_region_bounds(
    base: Dict[str, Any],
    classification: str,
    region_bounds: Dict[str, Tuple[int, int]],
) -> Dict[str, Any]:
    """
    Return a new ``league_structure`` dict with ``class_region_bounds[classification]`` merged.

    ``region_bounds`` maps region label -> (min_teams, max_teams), e.g.::

        {"North": (10, 10), "South": (10, 10), "East": (6, 6), "West": (6, 6)}
    """
    out = dict(base) if isinstance(base, dict) else default_league_structure()
    cr = dict(out.get("class_region_bounds") or {})
    inner = dict(cr.get(classification) or {})
    for reg, pair in region_bounds.items():
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            inner[str(reg)] = [int(pair[0]), int(pair[1])]
    cr[classification] = inner
    out["class_region_bounds"] = cr
    return out


def default_league_structure() -> Dict[str, Any]:
    """
    Default bounds for scheduling pods.

    - default_min_teams_per_pod: fewer teams → scheduling pod is invalid (cannot play 10 games).
    - default_max_teams_per_pod: soft cap for one round-robin pod (UI / validation).
      Set to 40 so pods up to 10 per region (40 total ÷ 4) or larger single-region tests do not warn.
    - class_region_bounds: optional overrides, shape:
        { "4A": { "North": [4, 12], "South": [4, 12] }, ... }
    """
    return {
        "version": STRUCTURE_VERSION,
        "default_min_teams_per_pod": 2,
        "default_max_teams_per_pod": 40,
        "class_region_bounds": {},
    }


def ensure_league_structure_in_state(state: Dict[str, Any]) -> None:
    """Mutates state to include ``league_structure`` when missing (migration-safe)."""
    ls = state.get("league_structure")
    if not isinstance(ls, dict):
        state["league_structure"] = default_league_structure()
        return
    base = default_league_structure()
    for k, v in base.items():
        ls.setdefault(k, v)
    # Older saves used default_max_teams_per_pod 24; bump so 10-team pods (40 ÷ 4 regions) validate.
    mx = ls.get("default_max_teams_per_pod")
    if mx == 24:
        ls["default_max_teams_per_pod"] = 40
    state["league_structure"] = ls


def scheduling_pod_key(classification: Optional[str], region: Optional[str]) -> Tuple[str, str]:
    c = (classification or "").strip() or "UNK"
    r = (region or "").strip() or DEFAULT_REGION_KEY
    return (c, r)


def classification_key(classification: Optional[str]) -> str:
    """Normalize classification for grouping (same class component as ``scheduling_pod_key``)."""
    return (classification or "").strip() or "UNK"


def teams_to_pods(teams: Dict[str, "Team"]) -> List[List[str]]:
    """
    Group team names by (classification, region). Pods are sorted by key, names sorted within pod.
    """
    buckets: Dict[Tuple[str, str], List[str]] = {}
    for name, t in teams.items():
        key = scheduling_pod_key(getattr(t, "classification", None), getattr(t, "region", None))
        buckets.setdefault(key, []).append(name)
    return [sorted(buckets[k]) for k in sorted(buckets.keys())]


def min_max_teams_for_pod(classification: str, region: str, structure: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    struct = structure if isinstance(structure, dict) else default_league_structure()
    dmin = int(struct.get("default_min_teams_per_pod", 2))
    dmax = int(struct.get("default_max_teams_per_pod", 40))
    cr = struct.get("class_region_bounds") or {}
    inner = cr.get(classification)
    if isinstance(inner, dict) and region in inner:
        pair = inner[region]
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return max(1, int(pair[0])), max(1, int(pair[1]))
    return dmin, dmax


def validate_scheduling_pods(
    pods: List[List[str]],
    teams: Dict[str, "Team"],
    structure: Optional[Dict[str, Any]],
) -> List[str]:
    """Return human-readable issues (empty list if OK)."""
    errors: List[str] = []
    for pod in pods:
        if len(pod) < 2:
            errors.append(f"Scheduling pod {pod!r} needs at least 2 teams.")
            continue
        t0 = teams[pod[0]]
        cls, reg = scheduling_pod_key(t0.classification, getattr(t0, "region", None))
        mn, mx = min_max_teams_for_pod(cls, reg, structure)
        if len(pod) < mn:
            errors.append(f"Pod ({cls}, {reg}) has {len(pod)} teams; minimum is {mn}.")
        if len(pod) > mx:
            errors.append(f"Pod ({cls}, {reg}) has {len(pod)} teams; maximum is {mx}.")
    return errors


def _region_index_map(regs_list: List[List[str]]) -> Dict[str, int]:
    return {name: ri for ri, lst in enumerate(regs_list) for name in lst}


def _count_cross_games(
    weeks: List[List[Tuple[str, str]]],
    reg_of: Dict[str, int],
) -> Dict[str, int]:
    from collections import Counter

    counts: Counter[str] = Counter()
    for wk in weeks:
        for home, away in wk:
            if reg_of.get(home) != reg_of.get(away):
                counts[home] += 1
                counts[away] += 1
    return counts


def _teams_playing_week(week: List[Tuple[str, str]]) -> set[str]:
    playing: set[str] = set()
    for home, away in week:
        playing.add(home)
        playing.add(away)
    return playing


def _pair_cross_week_pools(
    pool_a: List[str],
    pool_b: List[str],
    offset: int,
    used: set[str],
    ha_counts: Dict[str, Dict[str, int]],
) -> List[Tuple[str, str]]:
    from systems.schedule_system import pick_home_away

    avail_a = [t for t in pool_a if t not in used]
    avail_b = [t for t in pool_b if t not in used]
    n = min(len(avail_a), len(avail_b))
    games: List[Tuple[str, str]] = []
    for i in range(n):
        t1 = avail_a[i]
        t2 = avail_b[(i + offset) % len(avail_b)] if avail_b else avail_b[0]
        games.append(pick_home_away(t1, t2, ha_counts))
        used.add(t1)
        used.add(t2)
    return games


def _build_mixed_cross_weeks(
    regs_list: List[List[str]],
    ha_counts: Dict[str, Dict[str, int]],
    locks_fn,
    cross_target: int = 2,
) -> List[List[Tuple[str, str]]]:
    """Two cross-region weeks; gap-fill short teams before finishing BD pairings."""
    cross_weeks: List[List[Tuple[str, str]]] = []
    cross_so_far: Dict[str, int] = {t: 0 for lst in regs_list for t in lst}
    reg_of = _region_index_map(regs_list)

    def _gap_fill_week(week_games: List[Tuple[str, str]]) -> None:
        from systems.schedule_system import pick_home_away

        for _ in range(len(regs_list) * 4):
            short = sorted(
                [t for lst in regs_list for t in lst if cross_so_far.get(t, 0) < cross_target],
                key=lambda t: (cross_so_far.get(t, 0), t),
            )
            if not short:
                break
            team = short[0]
            playing = _teams_playing_week(week_games)
            if team in playing:
                continue
            my_reg = reg_of[team]
            placed = False
            for oreg, olist in enumerate(regs_list):
                if oreg == my_reg:
                    continue
                for opp in sorted(olist, key=lambda t: (cross_so_far.get(t, 0), t)):
                    if cross_so_far.get(opp, 0) >= cross_target or opp in playing:
                        continue
                    week_games.append(pick_home_away(team, opp, ha_counts))
                    cross_so_far[team] += 1
                    cross_so_far[opp] += 1
                    placed = True
                    break
                if placed:
                    break

    def _pair_regions(wk_idx: int, a: int, b: int, used: set[str], week_games: List[Tuple[str, str]]) -> None:
        locks = locks_fn(wk_idx, a, b)
        if locks:
            from systems.schedule_planning import pair_two_regions_with_locks

            paired = pair_two_regions_with_locks(
                regs_list[a], regs_list[b], wk_idx + a + b, locks, ha_counts
            )
            week_games.extend(paired)
            for home, away in paired:
                used.add(home)
                used.add(away)
                cross_so_far[home] += 1
                cross_so_far[away] += 1
            return
        need_a = [t for t in regs_list[a] if cross_so_far[t] < cross_target]
        need_b = [t for t in regs_list[b] if cross_so_far[t] < cross_target]
        need_a.sort(key=lambda t: (cross_so_far[t], t))
        need_b.sort(key=lambda t: (cross_so_far[t], t))
        max_sz = max(len(regs_list[a]), len(regs_list[b]), 1)
        paired = _pair_cross_week_pools(need_a, need_b, (wk_idx + a + b) % max_sz, used, ha_counts)
        week_games.extend(paired)
        for home, away in paired:
            cross_so_far[home] += 1
            cross_so_far[away] += 1

    # Week 9: AB + CD
    used_w9: set[str] = set()
    week9: List[Tuple[str, str]] = []
    _pair_regions(0, 0, 1, used_w9, week9)
    _pair_regions(0, 2, 3, used_w9, week9)
    _gap_fill_week(week9)
    cross_weeks.append(week9)

    # Week 10: AC, gap-fill, then BD
    used_w10: set[str] = set()
    week10: List[Tuple[str, str]] = []
    _pair_regions(1, 0, 2, used_w10, week10)
    _gap_fill_week(week10)
    used_w10 = _teams_playing_week(week10)
    _pair_regions(1, 1, 3, used_w10, week10)
    _gap_fill_week(week10)
    cross_weeks.append(week10)

    # Week 11: AD + BC when the class is large enough to need a third cross week (e.g. VA Class 2).
    total_teams = sum(len(lst) for lst in regs_list)
    if total_teams >= 48:
        used_w11: set[str] = set()
        week11: List[Tuple[str, str]] = []
        _pair_regions(2, 0, 3, used_w11, week11)
        _pair_regions(2, 1, 2, used_w11, week11)
        _gap_fill_week(week11)
        cross_weeks.append(week11)
    return cross_weeks


def _fill_cross_week_gaps(
    block: List[List[Tuple[str, str]]],
    regs_list: List[List[str]],
    ha_counts: Dict[str, Dict[str, int]],
    cross_target: int = 2,
    in_region_weeks: int = 8,
) -> None:
    """Add cross-region games on dedicated cross weeks for teams that were idle (uneven pods)."""
    from systems.schedule_system import pick_home_away

    reg_of = _region_index_map(regs_list)
    for wi in range(in_region_weeks, len(block)):
        week = block[wi]
        cross_counts = _count_cross_games(block, reg_of)
        short = sorted(
            [t for lst in regs_list for t in lst if cross_counts.get(t, 0) < cross_target],
            key=lambda t: (cross_counts.get(t, 0), t),
        )
        for team in short:
            if cross_counts.get(team, 0) >= cross_target:
                continue
            playing = _teams_playing_week(week)
            if team in playing:
                continue
            my_reg = reg_of[team]
            for oreg, olist in enumerate(regs_list):
                if oreg == my_reg:
                    continue
                for opp in sorted(olist):
                    if cross_counts.get(opp, 0) >= cross_target or opp in playing:
                        continue
                    game = pick_home_away(team, opp, ha_counts)
                    week.append(game)
                    cross_counts[team] += 1
                    cross_counts[opp] += 1
                    playing.add(team)
                    playing.add(opp)
                    break
                if cross_counts.get(team, 0) >= cross_target:
                    break


def _spillover_cross_into_in_region_weeks(
    block: List[List[Tuple[str, str]]],
    regs_list: List[List[str]],
    ha_counts: Dict[str, Dict[str, int]],
    cross_target: int = 2,
    in_region_weeks: int = 8,
) -> None:
    """Swap in-region games for cross-region when uneven pods left teams short on cross games."""
    from systems.schedule_system import pick_home_away

    reg_of = _region_index_map(regs_list)
    cross_counts = _count_cross_games(block, reg_of)
    in_region_counts: Dict[str, int] = {t: 0 for lst in regs_list for t in lst}
    for wi in range(min(in_region_weeks, len(block))):
        for home, away in block[wi]:
            if reg_of.get(home) == reg_of.get(away):
                in_region_counts[home] += 1
                in_region_counts[away] += 1

    def _playing(week: List[Tuple[str, str]]) -> set[str]:
        return _teams_playing_week(week)

    def _add_in_region_makeup(team: str, exclude_week: int) -> bool:
        """Give ``team`` one in-region game in a week they are idle."""
        my_reg = reg_of[team]
        pod = regs_list[my_reg]
        for wi in range(min(in_region_weeks, len(block))):
            if wi == exclude_week:
                continue
            playing = _playing(block[wi])
            if team in playing:
                continue
            candidates = [t for t in pod if t != team and t not in playing]
            if not candidates:
                continue
            opp = candidates[0]
            block[wi].append(pick_home_away(team, opp, ha_counts))
            in_region_counts[team] += 1
            in_region_counts[opp] += 1
            return True
        return False

    for wi in range(min(in_region_weeks, len(block))):
        week = block[wi]
        gi = 0
        while gi < len(week):
            home, away = week[gi]
            if reg_of.get(home) != reg_of.get(away):
                gi += 1
                continue
            swapped = False
            for team in (home, away):
                if cross_counts.get(team, 0) >= cross_target:
                    continue
                opp = away if team == home else home
                my_reg = reg_of[team]
                playing = _playing(week)
                for oreg, olist in enumerate(regs_list):
                    if oreg == my_reg:
                        continue
                    for cross_opp in sorted(olist):
                        if cross_counts.get(cross_opp, 0) >= cross_target:
                            continue
                        if cross_opp in playing:
                            continue
                        week[gi] = pick_home_away(team, cross_opp, ha_counts)
                        cross_counts[team] += 1
                        cross_counts[cross_opp] += 1
                        in_region_counts[team] -= 1
                        in_region_counts[opp] -= 1
                        if in_region_counts[opp] < 8:
                            _add_in_region_makeup(opp, wi)
                        swapped = True
                        break
                    if swapped:
                        break
                if swapped:
                    break
            gi += 1


def _snapshot_pod_game_counts(
    block: List[List[Tuple[str, str]]],
    regs_list: List[List[str]],
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    """Return (in_region, cross, total) game counts per team for one class block."""
    reg_of = _region_index_map(regs_list)
    all_teams = [t for lst in regs_list for t in lst]
    in_reg = {t: 0 for t in all_teams}
    cross = {t: 0 for t in all_teams}
    for week in block:
        for home, away in week:
            if reg_of.get(home) == reg_of.get(away):
                in_reg[home] += 1
                in_reg[away] += 1
            else:
                cross[home] += 1
                cross[away] += 1
    total = {t: in_reg[t] + cross[t] for t in all_teams}
    return in_reg, cross, total


def _embed_cross_on_bye_week(
    week_games: List[Tuple[str, str]],
    regs_list: List[List[str]],
    ha_counts: Dict[str, Dict[str, int]],
    cross_counts: Dict[str, int],
    cross_target: int = 2,
) -> None:
    """Use odd-pod bye weeks during in-region play for out-of-region games."""
    from systems.schedule_system import pick_home_away

    reg_of = _region_index_map(regs_list)
    playing = _teams_playing_week(week_games)
    for pod in regs_list:
        if len(pod) % 2 == 0:
            continue
        byes = [t for t in pod if t not in playing]
        if len(byes) != 1:
            continue
        team = byes[0]
        if cross_counts.get(team, 0) >= cross_target:
            continue
        my_reg = reg_of[team]
        for oreg, olist in enumerate(regs_list):
            if oreg == my_reg:
                continue
            for opp in sorted(olist, key=lambda t: (cross_counts.get(t, 0), t)):
                if opp in playing or cross_counts.get(opp, 0) >= cross_target:
                    continue
                week_games.append(pick_home_away(team, opp, ha_counts))
                cross_counts[team] += 1
                cross_counts[opp] += 1
                playing.add(team)
                playing.add(opp)
                break
            if cross_counts.get(team, 0) >= cross_target:
                break


def _ensure_mixed_template_ten_games(
    block: List[List[Tuple[str, str]]],
    regs_list: List[List[str]],
    ha_counts: Dict[str, Dict[str, int]],
    *,
    in_region_target: int = 8,
    cross_target: int = 2,
    total_target: int = 10,
    in_region_weeks: int = 8,
) -> None:
    """Guarantee 10-game seasons (8 in-region + 2 cross when possible) for uneven 4-region classes."""
    from systems.schedule_system import pick_home_away

    reg_of = _region_index_map(regs_list)
    all_teams = [t for lst in regs_list for t in lst]

    def try_add_cross(
        team: str,
        in_reg: Dict[str, int],
        cross: Dict[str, int],
        total: Dict[str, int],
    ) -> bool:
        if cross[team] >= cross_target or total[team] >= total_target:
            return False
        week_order = list(range(len(block)))
        week_order.sort(key=lambda wi: (0 if wi >= in_region_weeks else 1, wi))
        for wi in week_order:
            playing = _teams_playing_week(block[wi])
            if team in playing:
                continue
            my_reg = reg_of[team]
            opps = sorted(
                (
                    o
                    for o in all_teams
                    if reg_of[o] != my_reg and o not in playing and cross[o] < cross_target
                ),
                key=lambda o: (cross[o], o),
            )
            if not opps:
                opps = sorted(
                    (
                        o
                        for o in all_teams
                        if reg_of[o] != my_reg and o not in playing and total[o] < total_target
                    ),
                    key=lambda o: (cross[o], -in_reg[o], o),
                )
            if not opps:
                continue
            block[wi].append(pick_home_away(team, opps[0], ha_counts))
            return True
        return False

    def try_add_in_region(team: str, in_reg: Dict[str, int]) -> bool:
        my_reg = reg_of[team]
        pod = regs_list[my_reg]
        week_order = list(range(min(in_region_weeks, len(block)))) + list(
            range(min(in_region_weeks, len(block)), len(block))
        )
        for wi in week_order:
            playing = _teams_playing_week(block[wi])
            if team in playing:
                continue
            cands = [o for o in pod if o != team and o not in playing]
            if not cands:
                continue
            opp = min(cands, key=lambda o: in_reg[o])
            block[wi].append(pick_home_away(team, opp, ha_counts))
            return True
        return False

    def try_swap_in_for_cross(
        team: str,
        in_reg: Dict[str, int],
        cross: Dict[str, int],
        total: Dict[str, int],
    ) -> bool:
        my_reg = reg_of[team]
        for wi in range(min(in_region_weeks, len(block))):
            for gi, (home, away) in enumerate(block[wi]):
                if team not in (home, away):
                    continue
                if reg_of.get(home) != reg_of.get(away):
                    continue
                opp_in = away if home == team else home
                playing = _teams_playing_week(block[wi])
                for o in all_teams:
                    if reg_of[o] == my_reg or o in playing or o == team:
                        continue
                    if cross[o] >= cross_target and total[o] >= total_target:
                        continue
                    block[wi][gi] = pick_home_away(team, o, ha_counts)
                    in_reg[team] -= 1
                    in_reg[opp_in] -= 1
                    cross[team] += 1
                    cross[o] += 1
                    if in_reg[opp_in] < in_region_target:
                        try_add_in_region(opp_in, in_reg)
                    return True
        return False

    def try_swap_teammate_cross_for_in(team: str, in_reg: Dict[str, int], cross: Dict[str, int]) -> bool:
        """Convert a podmate's cross game into an in-region game for ``team`` (same week)."""
        my_reg = reg_of[team]
        pod = set(regs_list[my_reg])
        for wi in range(len(block)):
            playing = _teams_playing_week(block[wi])
            if team in playing:
                continue
            for gi, (home, away) in enumerate(block[wi]):
                if reg_of.get(home) == reg_of.get(away):
                    continue
                mate: Optional[str] = None
                cross_opp: Optional[str] = None
                if home in pod and home != team:
                    mate, cross_opp = home, away
                elif away in pod and away != team:
                    mate, cross_opp = away, home
                if not mate or not cross_opp:
                    continue
                block[wi][gi] = pick_home_away(team, mate, ha_counts)
                cross[mate] -= 1
                cross[cross_opp] -= 1
                in_reg[team] += 1
                in_reg[mate] += 1
                if cross[mate] < cross_target:
                    try_add_cross(mate, in_reg, cross, total)
                if cross[cross_opp] < cross_target:
                    try_add_cross(cross_opp, in_reg, cross, total)
                return True
        return False

    for _ in range(len(all_teams) * 40):
        in_reg, cross, total = _snapshot_pod_game_counts(block, regs_list)
        short = [t for t in all_teams if total[t] < total_target]
        if not short:
            break
        progressed_any = False
        for team in sorted(short, key=lambda t: (-(total_target - total[t]), cross[t], in_reg[t], t)):
            in_reg, cross, total = _snapshot_pod_game_counts(block, regs_list)
            if total[team] >= total_target:
                continue
            progressed = False
            if cross[team] < cross_target:
                progressed = try_add_cross(team, in_reg, cross, total)
                if not progressed:
                    progressed = try_swap_in_for_cross(team, in_reg, cross, total)
            if not progressed and in_reg[team] < in_region_target:
                progressed = try_add_in_region(team, in_reg)
            if not progressed and in_reg[team] < in_region_target:
                progressed = try_swap_teammate_cross_for_in(team, in_reg, cross)
            if not progressed:
                progressed = try_add_in_region(team, in_reg)
            if not progressed:
                progressed = try_add_cross(team, in_reg, cross, total)
            if progressed:
                progressed_any = True
        if not progressed_any:
            break


def playoff_pool_team_names(state: Dict[str, Any], teams: Dict[str, "Team"]) -> List[str]:
    """
    Teams in the same playoff bracket as ``user_team``: same classification only (statewide).
    Region affects regular-season scheduling only. Falls back to all teams if user is missing.
    """
    user = state.get("user_team")
    if not user or user not in teams:
        return sorted(teams.keys())
    ut = teams[user]
    ck = classification_key(getattr(ut, "classification", None))
    pool = sorted(
        n for n, t in teams.items() if classification_key(getattr(t, "classification", None)) == ck
    )
    return pool if pool else sorted(teams.keys())


def build_regular_season_weeks(
    teams: Dict[str, "Team"],
    state: Optional[Dict[str, Any]] = None,
) -> List[List[Tuple[str, str]]]:
    """
    Build the regular season: independent circle round-robins inside each scheduling pod, merged per week.

    Each pod uses at most ``min(10, n-1)`` weeks (``n`` = pod size) so no two schools in the same pod
    play each other twice in one season.
    """
    from systems.schedule_system import (
        _ha_counts,
        build_weeks_10_game,
        build_weeks_10_game_for_pods,
        record_home_away,
        rebalance_home_away_weeks,
    )

    def _record_weeks_to_counts(weeks: List[List[Tuple[str, str]]], ha: Dict[str, Dict[str, int]]) -> None:
        for wk in weeks:
            for home, away in wk:
                record_home_away(home, away, ha)

    def _in_region_rr_weeks(regs_list: List[List[str]]) -> Tuple[List[List[List[Tuple[str, str]]]], Dict[str, Dict[str, int]]]:
        ha = _ha_counts()
        rr_weeks = []
        for lst in regs_list:
            rw = build_weeks_10_game(lst)
            _record_weeks_to_counts(rw, ha)
            rr_weeks.append(rw)
        return rr_weeks, ha

    def _teams_in_week(week: List[Tuple[str, str]]) -> set[str]:
        playing: set[str] = set()
        for home, away in week:
            playing.add(home)
            playing.add(away)
        return playing

    def _bye_team_in_week(pod: List[str], week: List[Tuple[str, str]]) -> Optional[str]:
        """Single bye team in an odd-sized pod week, if any."""
        playing = _teams_in_week(week)
        byes = [t for t in pod if t not in playing]
        if len(byes) == 1:
            return byes[0]
        return None

    def _by_class_and_region() -> Dict[str, Dict[str, List[str]]]:
        out: Dict[str, Dict[str, List[str]]] = {}
        for name, t in teams.items():
            cls = classification_key(getattr(t, "classification", None))
            reg = (getattr(t, "region", None) or DEFAULT_REGION_KEY).strip() or DEFAULT_REGION_KEY
            out.setdefault(cls, {}).setdefault(reg, []).append(name)
        for cls in out:
            for reg in out[cls]:
                random.shuffle(out[cls][reg])
        return out

    def _pair_two_regions_week(
        a: List[str],
        b: List[str],
        offset: int,
        locks: Optional[List[Tuple[str, str]]] = None,
        ha_counts: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[Tuple[str, str]]:
        from systems.schedule_planning import pair_two_regions_with_locks
        from systems.schedule_system import pick_home_away, record_home_away

        if locks:
            return pair_two_regions_with_locks(a, b, offset, locks, ha_counts)
        n = min(len(a), len(b))
        games: List[Tuple[str, str]] = []
        for i in range(n):
            t1 = a[i]
            t2 = b[(i + offset) % n]
            if ha_counts is not None:
                games.append(pick_home_away(t1, t2, ha_counts))
            else:
                home, away = t1, t2
                if i % 2 == 1:
                    home, away = away, home
                games.append((home, away))
        return games

    def _cross_locks(cls: str, reg_a: str, reg_b: str, slot_index: int) -> List[Tuple[str, str]]:
        from systems.schedule_planning import locks_for_cross_week

        return locks_for_cross_week(teams, state, cls, reg_a, reg_b, slot_index)

    def _locked_cross_games(state_obj: Optional[Dict[str, Any]]) -> set[Tuple[str, str]]:
        """Oriented (home, away) edges from all cross-region schedule picks."""
        from systems.schedule_planning import cross_region_pick_team_names, lock_for_pick, parse_stored_pick

        locked: set[Tuple[str, str]] = set()
        if not state_obj:
            return locked
        picks_raw = state_obj.get("cross_region_picks") or {}
        if not isinstance(picks_raw, dict):
            return locked
        for team_name in cross_region_pick_team_names(state_obj):
            user_picks = picks_raw.get(team_name)
            if not isinstance(user_picks, dict):
                continue
            for key, raw in user_picks.items():
                pick = parse_stored_pick(raw)
                if not pick.opponent:
                    continue
                try:
                    si = int(key)
                except (TypeError, ValueError):
                    continue
                try:
                    locked.add(
                        lock_for_pick(
                            teams,
                            team_name,
                            si,
                            pick.opponent,
                            user_home=pick.user_home,
                        )
                    )
                except ValueError:
                    continue
        return locked

    def _finalize_weeks(weeks: List[List[Tuple[str, str]]]) -> List[List[Tuple[str, str]]]:
        return rebalance_home_away_weeks(weeks, locked=_locked_cross_games(state))

    def _merge_class_blocks(blocks: List[List[List[Tuple[str, str]]]]) -> List[List[Tuple[str, str]]]:
        if not blocks:
            return []
        n_weeks = max(len(b) for b in blocks)
        out: List[List[Tuple[str, str]]] = [[] for _ in range(n_weeks)]
        for b in blocks:
            for wi in range(n_weeks):
                if wi < len(b):
                    out[wi].extend(b[wi])
        return out

    grouped = _by_class_and_region()
    class_blocks: List[List[List[Tuple[str, str]]]] = []
    handled_classes: set[str] = set()

    for cls, regs in grouped.items():
        region_names = sorted(regs.keys())
        total = sum(len(v) for v in regs.values())
        sizes = [len(regs[r]) for r in region_names]

        # Rule template 1: 20 teams / 2 regions => 9 in-region + 1 out-of-region.
        if len(region_names) == 2 and total == 20 and all(s == 10 for s in sizes):
            handled_classes.add(cls)
            r1, r2 = region_names[0], region_names[1]
            r1_teams = list(regs[r1])
            r2_teams = list(regs[r2])
            rr1 = build_weeks_10_game(r1_teams)
            rr2 = build_weeks_10_game(r2_teams)
            ha = _ha_counts()
            _record_weeks_to_counts(rr1, ha)
            _record_weeks_to_counts(rr2, ha)
            block: List[List[Tuple[str, str]]] = []
            for wi in range(9):
                week_games: List[Tuple[str, str]] = []
                if wi < len(rr1):
                    week_games.extend(rr1[wi])
                if wi < len(rr2):
                    week_games.extend(rr2[wi])
                block.append(week_games)
            block.append(
                _pair_two_regions_week(
                    r1_teams,
                    r2_teams,
                    offset=random.randrange(10),
                    locks=_cross_locks(cls, r1, r2, 0),
                    ha_counts=ha,
                )
            )
            class_blocks.append(block)
            continue

        # Rule template 2: 32 teams / 4 regions => 7 in-region + 3 out-of-region.
        if len(region_names) == 4 and total == 32 and all(s == 8 for s in sizes):
            handled_classes.add(cls)
            regs_list = [list(regs[r]) for r in region_names]
            rr_weeks, ha = _in_region_rr_weeks(regs_list)
            block = []
            for wi in range(7):
                week_games: List[Tuple[str, str]] = []
                for rw in rr_weeks:
                    if wi < len(rw):
                        week_games.extend(rw[wi])
                block.append(week_games)

            # Three cross-region weeks (round-robin between the four regions).
            pair_weeks = [
                ((0, 1), (2, 3)),
                ((0, 2), (1, 3)),
                ((0, 3), (1, 2)),
            ]
            for wk_idx, pairs in enumerate(pair_weeks):
                cross_games: List[Tuple[str, str]] = []
                for a, b in pairs:
                    cross_games.extend(
                        _pair_two_regions_week(
                            regs_list[a],
                            regs_list[b],
                            offset=(wk_idx + a + b) % 8,
                            locks=_cross_locks(cls, region_names[a], region_names[b], wk_idx),
                            ha_counts=ha,
                        )
                    )
                block.append(cross_games)
            class_blocks.append(block)
            continue

        # Rule template 3: 40 teams / 4 regions × 10 => 9 in-region + 1 out-of-region.
        if len(region_names) == 4 and total == 40 and all(s == 10 for s in sizes):
            handled_classes.add(cls)
            regs_list = [list(regs[r]) for r in region_names]
            rr_weeks, ha = _in_region_rr_weeks(regs_list)
            block = []
            for wi in range(9):
                week_games: List[Tuple[str, str]] = []
                for rw in rr_weeks:
                    if wi < len(rw):
                        week_games.extend(rw[wi])
                block.append(week_games)
            cross_games: List[Tuple[str, str]] = []
            cross_games.extend(
                _pair_two_regions_week(
                    regs_list[0],
                    regs_list[1],
                    offset=random.randrange(10),
                    locks=_cross_locks(cls, region_names[0], region_names[1], 0),
                    ha_counts=ha,
                )
            )
            cross_games.extend(
                _pair_two_regions_week(
                    regs_list[2],
                    regs_list[3],
                    offset=random.randrange(10),
                    locks=_cross_locks(cls, region_names[2], region_names[3], 0),
                    ha_counts=ha,
                )
            )
            block.append(cross_games)
            class_blocks.append(block)
            continue

        # Rule template 4: 28 teams / 4 regions × 7 => 6 in-region + 4 cross = 10 games in 10 weeks.
        # One cross game per team lands on their in-region bye week; the other three are full cross weeks.
        if len(region_names) == 4 and total == 28 and all(s == 7 for s in sizes):
            handled_classes.add(cls)
            regs_list = [list(regs[r]) for r in region_names]
            from systems.schedule_planning import align_4x7_slot0_bye_weeks, locks_for_bye_teams

            rr_weeks = [build_weeks_10_game(lst) for lst in regs_list]
            align_4x7_slot0_bye_weeks(regs_list, rr_weeks, teams, state, cls)
            ha = _ha_counts()
            for rw in rr_weeks:
                _record_weeks_to_counts(rw, ha)
            block = []
            for wi in range(7):
                week_games: List[Tuple[str, str]] = []
                for ri, rw in enumerate(rr_weeks):
                    if wi < len(rw):
                        week_games.extend(rw[wi])
                # Slot 0: cross-region games for teams on their in-region bye this week.
                for a, b in ((0, 1), (2, 3)):
                    pod_a, pod_b = regs_list[a], regs_list[b]
                    week_a = rr_weeks[a][wi] if wi < len(rr_weeks[a]) else []
                    week_b = rr_weeks[b][wi] if wi < len(rr_weeks[b]) else []
                    bye_a = _bye_team_in_week(pod_a, week_a)
                    bye_b = _bye_team_in_week(pod_b, week_b)
                    if bye_a and bye_b:
                        slot0_locks = locks_for_bye_teams(
                            _cross_locks(cls, region_names[a], region_names[b], 0),
                            bye_a,
                            bye_b,
                        )
                        week_games.extend(
                            _pair_two_regions_week(
                                [bye_a],
                                [bye_b],
                                offset=0,
                                locks=slot0_locks,
                                ha_counts=ha,
                            )
                        )
                block.append(week_games)

            pair_weeks = [
                ((0, 2), (1, 3)),
                ((0, 3), (1, 2)),
                ((0, 1), (2, 3)),
            ]
            for wk_idx, pairs in enumerate(pair_weeks):
                slot_idx = wk_idx + 1
                cross_games: List[Tuple[str, str]] = []
                for a, b in pairs:
                    cross_games.extend(
                        _pair_two_regions_week(
                            regs_list[a],
                            regs_list[b],
                            offset=(slot_idx + a + b) % 7,
                            locks=_cross_locks(cls, region_names[a], region_names[b], slot_idx),
                            ha_counts=ha,
                        )
                    )
                block.append(cross_games)
            class_blocks.append(block)
            continue

        # Rule template 5: 4 regions (mixed pod sizes) => up to 8 in-region weeks + 2 cross.
        # Virginia Div 1/2, Ohio D5-style leagues with uneven regional counts.
        exact_four_region = (
            (total == 32 and all(s == 8 for s in sizes))
            or (total == 40 and all(s == 10 for s in sizes))
            or (total == 28 and all(s == 7 for s in sizes))
        )
        if len(region_names) == 4 and total >= 16 and not exact_four_region:
            handled_classes.add(cls)
            regs_list = [list(regs[r]) for r in region_names]
            rr_weeks: List[List[List[Tuple[str, str]]]] = []
            ha = _ha_counts()
            in_region_rounds = 8
            for lst in regs_list:
                rw = build_weeks_10_game(lst, max_rounds=in_region_rounds)
                _record_weeks_to_counts(rw, ha)
                rr_weeks.append(rw)
            block = []
            in_weeks = min(in_region_rounds, max((len(rw) for rw in rr_weeks), default=0))
            cross_counts: Dict[str, int] = {t: 0 for lst in regs_list for t in lst}
            for wi in range(in_weeks):
                week_games: List[Tuple[str, str]] = []
                for rw in rr_weeks:
                    if wi < len(rw):
                        week_games.extend(rw[wi])
                _embed_cross_on_bye_week(week_games, regs_list, ha, cross_counts)
                block.append(week_games)

            def _locks(wk_idx: int, a: int, b: int) -> List[Tuple[str, str]]:
                return _cross_locks(cls, region_names[a], region_names[b], wk_idx)

            block.extend(_build_mixed_cross_weeks(regs_list, ha, _locks))
            _fill_cross_week_gaps(block, regs_list, ha, in_region_weeks=in_weeks)
            _ensure_mixed_template_ten_games(
                block, regs_list, ha, in_region_weeks=in_weeks
            )
            class_blocks.append(block)
            continue

    if class_blocks:
        custom = _merge_class_blocks(class_blocks)
    else:
        custom = []

    structure = (state or {}).get("league_structure") if isinstance((state or {}).get("league_structure"), dict) else None
    pods = teams_to_pods(teams)
    issues = validate_scheduling_pods(pods, teams, structure)
    if issues:
        logger.warning("League structure: %s", " | ".join(issues))
    base = build_weeks_10_game_for_pods(pods)

    if not handled_classes:
        return _finalize_weeks(base)

    # Keep existing behavior for classes not covered by the explicit templates (e.g. 24-team classes).
    leftover_pods: List[List[str]] = []
    for pod in pods:
        if not pod:
            continue
        t0 = teams.get(pod[0])
        cls = classification_key(getattr(t0, "classification", None)) if t0 else "UNK"
        if cls in handled_classes:
            continue
        leftover_pods.append(pod)
    leftover = build_weeks_10_game_for_pods(leftover_pods)
    return _finalize_weeks(_merge_class_blocks([custom, leftover]))
