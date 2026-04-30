"""
Schedule system: regular season as circle round-robin (up to 10 rounds) with shuffled order.

Each team plays at most one game per round. A full single round-robin has ``n - 1`` rounds
(``n`` = team count after adding a bye slot if odd). Running more than ``n - 1`` rounds repeats
the same opponent pairings, so we cap rounds at ``min(10, n - 1)``.
"""

import random
from typing import List, Optional, Tuple


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

    for r in range(num_rounds):
        rotated = [others[(i - r) % (n - 1)] for i in range(n - 1)]
        order = [fixed] + rotated
        for i in range(n // 2):
            t1, t2 = order[i], order[n - 1 - i]
            if t1 is not None and t2 is not None:
                if r % 2 == 0:
                    schedule.append((t1, t2))
                else:
                    schedule.append((t2, t1))

    return schedule


def build_weeks_10_game(team_names: List[str], seed: Optional[int] = None) -> List[List[Tuple[str, str]]]:
    """
    Build a regular season as ``weeks -> games`` (each week: list of (home, away)).

    Uses at most 10 weeks and at most ``n - 1`` weeks (circle round-robin), whichever is smaller,
    so the same two schools never meet twice in the same season within this pod.
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
    fixed = teams[0]
    others = teams[1:n]
    weeks: List[List[Tuple[str, str]]] = []

    for r in range(num_rounds):
        rotated = [others[(i - r) % (n - 1)] for i in range(n - 1)]
        order = [fixed] + rotated
        week_games: List[Tuple[str, str]] = []
        for i in range(n // 2):
            t1, t2 = order[i], order[n - 1 - i]
            if t1 is None or t2 is None:
                continue
            if r % 2 == 0:
                week_games.append((t1, t2))
            else:
                week_games.append((t2, t1))
        weeks.append(week_games)

    return weeks


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
    return merged
