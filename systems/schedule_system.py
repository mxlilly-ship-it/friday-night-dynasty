"""
Schedule system: regular season as circle round-robin (up to 10 rounds) with shuffled order.

Each team plays at most one game per round. A full single round-robin has ``n - 1`` rounds
(``n`` = team count after adding a bye slot if odd). Running more than ``n - 1`` rounds repeats
the same opponent pairings, so we cap rounds at ``min(10, n - 1)``.

Home/away is assigned to keep each team near a 5-5 / 4-6 / 6-4 split (not 7-3 or 3-7).
"""

import random
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

# Max |home - away| allowed after balancing (4-6, 5-5, 6-4 for a 10-game season).
DEFAULT_MAX_HOME_AWAY_DIFF = 2


def _ha_counts() -> DefaultDict[str, Dict[str, int]]:
    return defaultdict(lambda: {"h": 0, "a": 0})


def _home_away_imbalance(counts: Dict[str, Dict[str, int]], team: str) -> int:
    c = counts[team]
    return int(c["h"]) - int(c["a"])


def pick_home_away(
    t1: str,
    t2: str,
    counts: Dict[str, Dict[str, int]],
) -> Tuple[str, str]:
    """Pick home/away for a matchup; mutates ``counts``."""
    i1 = _home_away_imbalance(counts, t1)
    i2 = _home_away_imbalance(counts, t2)
    if i1 < i2:
        home, away = t1, t2
    elif i2 < i1:
        home, away = t2, t1
    else:
        home, away = (t1, t2) if t1 <= t2 else (t2, t1)
    counts[home]["h"] += 1
    counts[away]["a"] += 1
    return home, away


def record_home_away(
    home: str,
    away: str,
    counts: Dict[str, Dict[str, int]],
) -> None:
    counts[home]["h"] += 1
    counts[away]["a"] += 1


def _schedule_imbalance_cost(counts: Dict[str, Dict[str, int]]) -> int:
    return sum(abs(_home_away_imbalance(counts, team)) for team in counts)


def rebalance_home_away_weeks(
    weeks: List[List[Tuple[str, str]]],
    *,
    max_diff: int = DEFAULT_MAX_HOME_AWAY_DIFF,
    locked: Optional[Set[Tuple[str, str]]] = None,
) -> List[List[Tuple[str, str]]]:
    """
    Flip home/away on individual games so no team exceeds ``max_diff`` home/away gap when possible.

    ``locked`` holds oriented (home, away) tuples that must not be flipped (e.g. user cross-region picks).
    """
    if not weeks:
        return weeks
    locked = locked or set()
    out: List[List[Tuple[str, str]]] = [[(h, a) for h, a in wk] for wk in weeks]

    def counts_from_schedule() -> DefaultDict[str, Dict[str, int]]:
        c = _ha_counts()
        for wk in out:
            for home, away in wk:
                record_home_away(home, away, c)
        return c

    max_passes = max(50, sum(len(wk) for wk in out) * 4)
    for _ in range(max_passes):
        counts = counts_from_schedule()
        if all(abs(_home_away_imbalance(counts, t)) <= max_diff for t in counts):
            break
        improved = False
        for wi, wk in enumerate(out):
            for gi, (home, away) in enumerate(wk):
                if (home, away) in locked:
                    continue
                ih = _home_away_imbalance(counts, home)
                ia = _home_away_imbalance(counts, away)
                before = abs(ih) + abs(ia)
                after = abs(ih - 1) + abs(ia + 1)
                if after < before:
                    out[wi][gi] = (away, home)
                    counts[home]["h"] -= 1
                    counts[home]["a"] += 1
                    counts[away]["a"] -= 1
                    counts[away]["h"] += 1
                    improved = True
        if not improved:
            break

    return out


def _circle_rr_num_rounds(n_after_parity: int) -> int:
    """Rounds without repeating any matchup in circle round-robin; capped at 10."""
    if n_after_parity < 2:
        return 0
    return min(10, n_after_parity - 1)


def build_schedule_10_game(team_names: List[str], seed: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    Build a regular-season game list (home, away) using circle round-robin.

    Length is ``num_rounds * (n/2)`` matchups (excluding bye games), with
    ``num_rounds = min(10, n - 1)`` so no team faces the same opponent twice in the season.
    """
    if seed is not None:
        random.seed(seed)
    teams = list(team_names)
    random.shuffle(teams)
    n = len(teams)
    if n < 2:
        return []

    # Ensure even number for round-robin (add bye if odd)
    if n % 2:
        teams = teams + [None]
        n += 1

    num_rounds = _circle_rr_num_rounds(n)
    fixed = teams[0]
    others = teams[1 : n]
    schedule: List[Tuple[str, str]] = []
    ha = _ha_counts()

    for r in range(num_rounds):
        rotated = [others[(i - r) % (n - 1)] for i in range(n - 1)]
        order = [fixed] + rotated
        for i in range(n // 2):
            t1, t2 = order[i], order[n - 1 - i]
            if t1 is not None and t2 is not None:
                schedule.append(pick_home_away(t1, t2, ha))

    return schedule


def build_weeks_10_game(
    team_names: List[str],
    seed: Optional[int] = None,
    max_rounds: Optional[int] = None,
) -> List[List[Tuple[str, str]]]:
    """
    Build a regular season as ``weeks -> games`` (each week: list of (home, away)).

    Uses at most 10 weeks and at most ``n - 1`` weeks (circle round-robin) by default,
    so the same two schools never meet twice in the same season within this pod unless
    ``max_rounds`` exceeds ``n - 1`` (one rematch round for small pods).
    """
    if seed is not None:
        random.seed(seed)
    teams = list(team_names)
    random.shuffle(teams)
    n = len(teams)
    if n < 2:
        return []

    if n % 2:
        teams = teams + [None]
        n += 1

    num_rounds = _circle_rr_num_rounds(n)
    if max_rounds is not None:
        num_rounds = min(int(max_rounds), 10)
    fixed = teams[0]
    others = teams[1:n]
    weeks: List[List[Tuple[str, str]]] = []
    ha = _ha_counts()

    for r in range(num_rounds):
        rotated = [others[(i - r) % (n - 1)] for i in range(n - 1)]
        order = [fixed] + rotated
        week_games: List[Tuple[str, str]] = []
        for i in range(n // 2):
            t1, t2 = order[i], order[n - 1 - i]
            if t1 is None or t2 is None:
                continue
            week_games.append(pick_home_away(t1, t2, ha))
        weeks.append(week_games)

    return rebalance_home_away_weeks(weeks)


def build_weeks_10_game_for_pods(
    pods: List[List[str]],
    base_seed: Optional[int] = None,
) -> List[List[Tuple[str, str]]]:
    """
    Run ``build_weeks_10_game`` inside each scheduling pod and concatenate games by week index.

    Pods with fewer than 2 teams are skipped (no games). Used for classification + region leagues.
    Week count matches the longest pod schedule (each at most 10 weeks, no duplicate pairings).
    """
    if not pods:
        return []
    pod_weeks_list: List[List[List[Tuple[str, str]]]] = []
    for i, pod in enumerate(pods):
        if len(pod) < 2:
            continue
        seed_i = None if base_seed is None else (base_seed + i * 100_003) % (2**31)
        pod_weeks_list.append(build_weeks_10_game(pod, seed=seed_i))
    if not pod_weeks_list:
        return []
    num_weeks = min(10, max(len(pw) for pw in pod_weeks_list))
    merged: List[List[Tuple[str, str]]] = [[] for _ in range(num_weeks)]
    for pod_weeks in pod_weeks_list:
        for wi in range(num_weeks):
            if wi < len(pod_weeks):
                merged[wi].extend(pod_weeks[wi])
    return rebalance_home_away_weeks(merged)
