"""
Program Improvements PP (off-season spendable bank).

This module defines **one** pacing system for ``offseason_improvements_bank``: how much PP
the user earns at season end vs pillar upgrade costs in ``systems.program_progression`` (same
cost table as in-season progression; 1 PP = 1 progression point toward the next grade).

Design goals:
- Wins and losses materially move PP without needing dozens of seasons for a single tier jump.
- Post-season rewards reflect depth of run (every playoff victory + podium bonuses).

**Tune these constants together** until a profile season “feels” right versus upgrade costs::

    Typical single-level costs (Spend PP, three pillars tracked separately):

    1→2 −100   2→3 −300   …   9→10 −3000   (see ``UPGRADE_COST_BY_LEVEL``).

    Example sanity (order-of-magnitude, before goals / losses):

      • 10–2 regular slate with middling margins: ~ ± (10×−12 + 2×−9)
        ≈ (10×10 − 2×10 if using flat midpoint) … see margin tables below.

      • State champ: sum of playoff win PP + champ bonus (+one extra win line for title game).

All functions are pure (no I/O).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# --- Regular season: margin-based PP per game (win positive, loss negative). ---
#
# Bounds requested: about 5–15 per outing. Blowouts lean high; toss-ups lean low.


def pp_for_regular_margin(margin_abs: int) -> int:
    """Map absolute score differential to PP magnitude (applied + for wins, − for losses)."""
    m = abs(int(margin_abs))
    if m <= 3:
        return 7
    if m <= 7:
        return 9
    if m <= 13:
        return 12
    return 15


# --- Playoff games: PP per playoff win (+20 baseline). ---
PP_PER_PLAYOFF_WIN = 20

# --- One-time podium bonuses stacked **after** per-win tally (avoid double‑paying losers). ---
# Champion also counts their title game inside ``PP_PER_PLAYOFF_WIN``; bonus is incremental pride / exposure.
PP_BONUS_RUNNER_UP = 40          # Lost state title game but reached championship round
PP_BONUS_STATE_CHAMPION = 80     # Raised hardware

# Season goals (flex PP bank): each active facet met / missed adjusts bank by flat PP.
PP_PER_GOAL_MET = 50
PP_PER_GOAL_FAIL = -50

# Fallback when schedule boxes are unavailable (bulk import / corrupted week boards).
PP_REG_WIN_FALLBACK = 10
PP_REG_LOSS_FALLBACK = 10


def _collect_regular_season_games_pp(
    team_name: str,
    weeks: Any,
    week_results: Any,
) -> Tuple[int, int]:
    """
    Iterate ``weeks`` × ``week_results`` for rows involving ``team_name``.

    Returns (pp_total, games_counted_played).

    Uses margin-based PP when scores exist; skips unplayed / invalid rows.
    """
    if not team_name or not isinstance(weeks, list) or not isinstance(week_results, list):
        return 0, 0

    pts = 0
    played_ct = 0
    for wi, wk in enumerate(weeks):
        if not isinstance(wk, list):
            continue
        row = week_results[wi] if wi < len(week_results) else None
        if not isinstance(row, list):
            continue
        for gi, sched in enumerate(wk):
            if not isinstance(sched, dict):
                continue
            h = sched.get("home")
            a = sched.get("away")
            if team_name not in (h, a):
                continue
            r = row[gi] if gi < len(row) else None
            if not isinstance(r, dict) or not r.get("played"):
                continue
            hs = int(r.get("home_score", 0) or 0)
            ascore = int(r.get("away_score", 0) or 0)
            if hs == ascore:
                continue
            ours = hs if team_name == h else ascore
            theirs = ascore if team_name == h else hs
            mag = pp_for_regular_margin(ours - theirs)
            pts += mag if ours > theirs else -mag
            played_ct += 1
    return pts, played_ct


def count_playoff_wins(team_name: str, bracket_results: Any) -> int:
    if not team_name or not isinstance(bracket_results, list):
        return 0
    n = 0
    for g in bracket_results:
        if not isinstance(g, dict):
            continue
        h = str(g.get("home") or "")
        a = str(g.get("away") or "")
        if team_name != h and team_name != a:
            continue
        w = str(g.get("winner") or "")
        if w == team_name:
            n += 1
    return n


def _postseason_placement_pp(tier_s: str) -> Tuple[int, str]:
    tier = str(tier_s or "none").strip().lower()
    if tier == "champion":
        return PP_BONUS_STATE_CHAMPION, "state champion bonus"
    if tier == "championship":
        return PP_BONUS_RUNNER_UP, "state runner-up bonus"
    return 0, ""


def compute_season_program_pp_awards(
    *,
    team_name: str,
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    season_goals: Optional[Dict[str, Any]],
    weeks: Optional[Any],
    week_results: Optional[Any],
    postseason_tier: str,
) -> Dict[str, Any]:
    """
    Full PP breakdown for Improvements bank (integer ``pp_total``).

    Args:
      ``postseason_tier``: reuse league_service tier string
      (``champion`` | ``championship`` | ``semifinal`` | ``playoffs`` | ``none``).
    """

    tn = str(team_name or "").strip()
    srow_g = (standings or {}).get(tn) or {}
    wins = int(srow_g.get("wins", 0) or 0)
    losses = int(srow_g.get("losses", 0) or 0)

    rs_pp, counted = _collect_regular_season_games_pp(tn, weeks, week_results)

    if counted == 0 and tn:
        rs_pp = wins * PP_REG_WIN_FALLBACK - losses * PP_REG_LOSS_FALLBACK

    p_wins = count_playoff_wins(tn, bracket_results)
    playoff_pp = PP_PER_PLAYOFF_WIN * int(p_wins)

    placing_pp, placing_label = _postseason_placement_pp(postseason_tier)

    goal_fail = 0
    goal_met = 0
    win_goal = None
    stage_goal = None
    if isinstance(season_goals, dict):
        try:
            win_goal = int(season_goals.get("win_goal")) if season_goals.get("win_goal") is not None else None
        except (TypeError, ValueError):
            win_goal = None
        stage_goal = str(season_goals.get("stage_goal") or "").strip() or None

    if win_goal is not None:
        if wins < win_goal:
            goal_fail += 1
        else:
            goal_met += 1

    achieved_rank = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(
        str(postseason_tier or "none"),
        0,
    )
    if stage_goal == "Just to have fun":
        goal_met += 1
    elif stage_goal:
        goal_rank = None
        if stage_goal == "Winning Season":
            goal_rank = 0 if wins >= losses else 999
        elif stage_goal == "Playoffs":
            goal_rank = 1
        elif stage_goal == "Semifinal":
            goal_rank = 2
        elif stage_goal == "State Championship":
            goal_rank = 3
        elif stage_goal == "Title Winner":
            goal_rank = 4

        if goal_rank is not None:
            if goal_rank == 999:
                goal_fail += 1
            elif achieved_rank < goal_rank:
                goal_fail += 1
            else:
                goal_met += 1

    goal_pts = float(PP_PER_GOAL_MET) * float(goal_met) + float(PP_PER_GOAL_FAIL) * float(goal_fail)
    total_raw = float(rs_pp) + float(playoff_pp) + float(placing_pp) + float(goal_pts)
    pp_total = int(round(total_raw))

    return {
        "team": tn,
        "wins": wins,
        "losses": losses,
        "regular_season_pp": int(rs_pp),
        "regular_season_games_counted": int(counted),
        "playoff_wins": int(p_wins),
        "playoff_win_pp_each": PP_PER_PLAYOFF_WIN,
        "playoff_win_pp_total": int(playoff_pp),
        "postseason_tier": str(postseason_tier or "none"),
        "placement_bonus_pp": int(placing_pp),
        "placement_bonus_label": placing_label,
        # Back-compat aliases for lighter clients
        "wl_points": float(rs_pp),
        "postseason_points": float(playoff_pp + placing_pp),
        "goal_fail_count": goal_fail,
        "goal_met_count": int(goal_met),
        "goal_points": goal_pts,
        "total_raw": total_raw,
        "pp_total": pp_total,
    }
