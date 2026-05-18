"""
15-year league sim focused on Team Points / prestige movement.
Uses the same season loop as run_ten_season_test (games + playoffs + coach + update_prestige).
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

sys.path.insert(0, ".")

from systems.league_history import append_season, load_league_history
from systems.offseason_manager import run_offseason_all_teams
from systems.playbook_system import build_playbook_for_team
from systems.playoff_system import run_playoff
from systems.prestige_system import prestige_band_for_level
from systems.coach_career_system import run_coach_career_phase
from systems.prestige_system import update_prestige
from systems.schedule_system import build_schedule_10_game
from systems.teams_loader import build_teams_from_json

from scripts.run_ten_season_test import init_season_stats, run_game_with_playbooks

SEASONS = 15
OUT_PATH = "scripts/fifteen_year_prestige_sim_results.txt"


def _team_snapshot(teams: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for name, t in teams.items():
        tp = float(getattr(t, "team_points", 0.0) or 0.0)
        out[name] = {
            "prestige": int(getattr(t, "prestige", 5) or 5),
            "team_points": round(tp, 2),
            "last_delta": round(float(getattr(t, "team_points_last_delta", 0.0) or 0.0), 2),
        }
    return out


def _pick_sample_teams(teams: Dict[str, Any], n: int = 8) -> List[str]:
    """High prestige, low prestige, and spread of middling programs."""
    ranked = sorted(
        teams.keys(),
        key=lambda nm: (-int(getattr(teams[nm], "prestige", 5) or 5), -float(getattr(teams[nm], "team_points", 0) or 0)),
    )
    if len(ranked) <= n:
        return ranked
    lows = ranked[-2:]
    highs = ranked[:3]
    mids = ranked[len(ranked) // 2 - 2 : len(ranked) // 2 + 1]
    seen: List[str] = []
    for nm in highs + mids + lows:
        if nm not in seen:
            seen.append(nm)
    return seen[:n]


def main() -> None:
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    team_names = list(teams.keys())
    schedule = build_schedule_10_game(team_names)

    lines: List[str] = []
    lines.append("FRIDAY NIGHT DYNASTY — 15-YEAR TEAM POINTS / PRESTIGE SIMULATION")
    lines.append("=" * 72)
    lines.append(f"Teams: {len(team_names)} | Seasons: {SEASONS}")
    lines.append("")

    year0 = _team_snapshot(teams)
    prestige_changes_per_year: List[int] = []
    delta_values: List[float] = []
    champions: List[Tuple[int, str, int, float]] = []

    sample_names = _pick_sample_teams(teams)
    history_by_team: Dict[str, List[Tuple[int, int, float, float]]] = defaultdict(list)

    for nm in team_names:
        s = year0[nm]
        history_by_team[nm].append((0, s["prestige"], s["team_points"], 0.0))

    lines.append("SAMPLE PROGRAMS (tracked all 15 years)")
    lines.append("-" * 72)
    for nm in sample_names:
        p = int(getattr(teams[nm], "prestige", 5))
        tp = float(getattr(teams[nm], "team_points", 0) or 0)
        lo, hi = prestige_band_for_level(p)
        lines.append(f"  {nm}: start {p}★ ({tp:.2f} TP)  band {lo:.2f}–{hi:.2f}")
    lines.append("")

    for season_num in range(1, SEASONS + 1):
        before = _team_snapshot(teams)
        standings = {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}
        season_stats = init_season_stats(team_names)
        season_player_stats: dict = {}

        for home_name, away_name in schedule:
            home = teams[home_name]
            away = teams[away_name]
            run_game_with_playbooks(
                home,
                away,
                season_stats,
                standings,
                season_player_stats,
                build_playbook_for_team(home),
                build_playbook_for_team(away),
                season_num=season_num,
            )

        champion, bracket_results = run_playoff(teams, standings, team_names, None, season_player_stats)
        runner_up = ""
        if bracket_results:
            last = bracket_results[-1]
            runner_up = last["away"] if last["winner"] == last["home"] else last["home"]

        append_season(
            champion=champion,
            runner_up=runner_up,
            team_names=team_names,
            standings=standings,
            season_player_stats=season_player_stats,
        )

        league_history = load_league_history()
        coach_events, coach_changes = run_coach_career_phase(
            teams,
            league_history=league_history,
            standings=standings,
            current_year=season_num + 1,
        )
        update_prestige(teams, league_history, coach_changes=coach_changes)

        after = _team_snapshot(teams)
        changed = sum(1 for nm in team_names if before[nm]["prestige"] != after[nm]["prestige"])
        prestige_changes_per_year.append(changed)

        season_deltas = [after[nm]["last_delta"] for nm in team_names]
        delta_values.extend(season_deltas)

        ch = after.get(champion, before.get(champion, {}))
        champions.append((season_num, champion, int(ch.get("prestige", 0)), float(ch.get("team_points", 0))))

        for nm in team_names:
            history_by_team[nm].append(
                (season_num, after[nm]["prestige"], after[nm]["team_points"], after[nm]["last_delta"])
            )

        lines.append(f"SEASON {season_num} — Champion: {champion}")
        lines.append(
            f"  Prestige tier changes (league-wide): {changed} teams | "
            f"TP Δ range: {min(season_deltas):+.2f} to {max(season_deltas):+.2f} | "
            f"mean Δ: {statistics.mean(season_deltas):+.3f}"
        )
        lines.append(
            f"  Champion after season: {ch.get('prestige', '?')}★ "
            f"({ch.get('team_points', 0):.2f} TP, Δ {ch.get('last_delta', 0):+.2f})"
        )

        if season_num < SEASONS:
            run_offseason_all_teams(list(teams.values()), standings, season_stats)

    lines.append("")
    lines.append("=" * 72)
    lines.append("LEAGUE-WIDE SUMMARY")
    lines.append("=" * 72)
    lines.append(
        f"Teams changing prestige tier per year — "
        f"min {min(prestige_changes_per_year)}, max {max(prestige_changes_per_year)}, "
        f"avg {statistics.mean(prestige_changes_per_year):.1f}"
    )
    lines.append(
        f"Per-team seasonal TP Δ — min {min(delta_values):+.2f}, max {max(delta_values):+.2f}, "
        f"mean {statistics.mean(delta_values):+.3f}, stdev {statistics.pstdev(delta_values):.3f}"
    )

    final_prestige_dist: Dict[int, int] = defaultdict(int)
    for nm in team_names:
        final_prestige_dist[after[nm]["prestige"]] += 1
    lines.append("")
    lines.append("Final prestige distribution (year 15):")
    for p in range(15, 0, -1):
        c = final_prestige_dist.get(p, 0)
        if c:
            lines.append(f"  {p:2}★: {c} teams")

    tp_vals = [after[nm]["team_points"] for nm in team_names]
    lines.append(
        f"\nFinal TP range: {min(tp_vals):.2f} – {max(tp_vals):.2f} "
        f"(mean {statistics.mean(tp_vals):.2f})"
    )

    moved_up = sum(1 for nm in team_names if after[nm]["prestige"] > year0[nm]["prestige"])
    moved_down = sum(1 for nm in team_names if after[nm]["prestige"] < year0[nm]["prestige"])
    same = len(team_names) - moved_up - moved_down
    lines.append(
        f"\n15-year prestige movement vs save start: "
        f"{moved_up} up, {moved_down} down, {same} unchanged"
    )

    lines.append("")
    lines.append("STATE CHAMPIONS (prestige / TP after title year)")
    lines.append("-" * 72)
    for yr, ch, prest, tp in champions:
        lines.append(f"  Year {yr:2}: {ch} — {prest}★ ({tp:.2f} TP)")

    lines.append("")
    lines.append("SAMPLE PROGRAM TRAJECTORIES")
    lines.append("-" * 72)
    for nm in sample_names:
        lines.append(f"\n{nm}:")
        start_p, start_tp = year0[nm]["prestige"], year0[nm]["team_points"]
        end_p, end_tp = after[nm]["prestige"], after[nm]["team_points"]
        lines.append(f"  Start: {start_p}★ ({start_tp:.2f} TP)  →  End: {end_p}★ ({end_tp:.2f} TP)")
        for yr, prest, tp, d in history_by_team[nm][1:]:
            flag = ""
            if yr > 0 and history_by_team[nm][yr - 1][1] != prest:
                flag = "  ← tier change"
            lines.append(f"    Y{yr:02d}: {prest}★  {tp:5.2f} TP  (Δ {d:+.2f}){flag}")

    lines.append("")
    lines.append("TOP / BOTTOM MOVERS (15 years)")
    lines.append("-" * 72)
    movers = [
        (nm, after[nm]["prestige"] - year0[nm]["prestige"], after[nm]["team_points"] - year0[nm]["team_points"])
        for nm in team_names
    ]
    movers.sort(key=lambda x: (-x[1], -x[2]))
    lines.append("Biggest prestige gain:")
    for nm, dp, dtp in movers[:5]:
        lines.append(
            f"  {nm}: {year0[nm]['prestige']}★ → {after[nm]['prestige']}★ "
            f"({dtp:+.2f} TP total)"
        )
    lines.append("Biggest prestige loss:")
    for nm, dp, dtp in movers[-5:][::-1]:
        lines.append(
            f"  {nm}: {year0[nm]['prestige']}★ → {after[nm]['prestige']}★ "
            f"({dtp:+.2f} TP total)"
        )

    text = "\n".join(lines)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print(f"\n(Written to {OUT_PATH})")


if __name__ == "__main__":
    main()
