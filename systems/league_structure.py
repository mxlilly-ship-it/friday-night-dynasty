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
    from systems.schedule_system import build_weeks_10_game, build_weeks_10_game_for_pods

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

    def _pair_two_regions_week(a: List[str], b: List[str], offset: int) -> List[Tuple[str, str]]:
        n = min(len(a), len(b))
        games: List[Tuple[str, str]] = []
        for i in range(n):
            home = a[i]
            away = b[(i + offset) % n]
            if i % 2 == 1:
                home, away = away, home
            games.append((home, away))
        return games

    def _merge_class_blocks(blocks: List[List[List[Tuple[str, str]]]]) -> List[List[Tuple[str, str]]]:
        if not blocks:
            return []
        n_weeks = min(10, max(len(b) for b in blocks))
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
            block: List[List[Tuple[str, str]]] = []
            for wi in range(9):
                week_games: List[Tuple[str, str]] = []
                if wi < len(rr1):
                    week_games.extend(rr1[wi])
                if wi < len(rr2):
                    week_games.extend(rr2[wi])
                block.append(week_games)
            block.append(_pair_two_regions_week(r1_teams, r2_teams, offset=random.randrange(10)))
            class_blocks.append(block)
            continue

        # Rule template 2: 32 teams / 4 regions => 7 in-region + 3 out-of-region.
        if len(region_names) == 4 and total == 32 and all(s == 8 for s in sizes):
            handled_classes.add(cls)
            regs_list = [list(regs[r]) for r in region_names]
            rr_weeks = [build_weeks_10_game(lst) for lst in regs_list]
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
                    cross_games.extend(_pair_two_regions_week(regs_list[a], regs_list[b], offset=(wk_idx + a + b) % 8))
                block.append(cross_games)
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
        return base

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
    return _merge_class_blocks([custom, leftover])
