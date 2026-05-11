"""
Simulate 15 offseason transfer cycles using the live transfer_system (stage 1 + stage 2).

Each year (aligned with game flow: season results -> graduation/roster turnover -> transfers):
  - Synthetic regular-season standings (10 games / team)
  - run_offseason_roster_turnover per team (graduation, age, trim, freshmen)
  - Auto depth chart order sync (so portal playing-time pressure matches roster)
  - run_transfer_stage_1 / run_transfer_stage_2

Writes a plain-text report (default: transfer_sim_15_years.txt in project root).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Project root = parent of scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from systems.depth_chart import build_depth_chart
from systems.offseason_manager import run_offseason_roster_turnover
from systems.teams_loader import build_teams_from_json
from systems.transfer_system import run_transfer_stage_1, run_transfer_stage_2


def _sync_auto_depth_chart_order(team: Any) -> None:
    dc = build_depth_chart(team)
    order: Dict[str, List[str]] = {}
    for pos, lst in dc.offense.items():
        order[pos] = [str(getattr(p, "name", "")) for p in (lst or []) if p is not None]
    for pos, lst in dc.defense.items():
        order[pos] = [str(getattr(p, "name", "")) for p in (lst or []) if p is not None]
    team.depth_chart_order = order


def _random_standings(rng: random.Random, team_names: List[str], games: int = 10) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name in team_names:
        w = rng.randint(0, games)
        l = games - w
        out[name] = {
            "wins": w,
            "losses": l,
            "points_for": rng.randint(60, 420),
            "points_against": rng.randint(60, 420),
        }
    return out


def _champion_from_standings(standings: Dict[str, Dict[str, Any]], rng: random.Random) -> str:
    best: List[str] = []
    best_w = -1
    for tn, row in standings.items():
        w = int(row.get("wins", 0) or 0)
        if w > best_w:
            best_w = w
            best = [tn]
        elif w == best_w:
            best.append(tn)
    return str(rng.choice(best)) if best else ""


def run_sim(
    years: int,
    seed: int,
    *,
    user_team: str | None,
    season_goals: Dict[str, Any] | None,
) -> List[str]:
    rng = random.Random(seed)
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    team_names = sorted(teams.keys())
    league_history: Dict[str, Any] = {"seasons": []}

    lines: List[str] = []
    lines.append("Friday Night Dynasty — transfer portal simulation")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Years: {years} | RNG seed: {seed} | Teams: {len(team_names)}")
    lines.append(f"User team (goal pressure): {user_team or '(none — CPU-only expectations)'}")
    lines.append("")

    total_portal = 0
    total_moved = 0
    total_blocked = 0

    for y in range(1, years + 1):
        standings = _random_standings(rng, team_names)
        champ = _champion_from_standings(standings, rng)
        bracket_results: List[Dict[str, Any]] = []

        lines.append("=" * 72)
        lines.append(f"YEAR {y} — pre-transfer standings (synthetic 10-game season)")
        lines.append("=" * 72)
        for tn in team_names:
            row = standings[tn]
            lines.append(
                f"  {tn:24}  {int(row['wins'])}-{int(row['losses'])}  "
                f"PF {int(row['points_for'])}  PA {int(row['points_against'])}"
            )
        lines.append(f"  Synthetic champion (tiebreak random): {champ or 'n/a'}")
        lines.append("")

        grad_total = add_total = 0
        for t in teams.values():
            rot = run_offseason_roster_turnover(t, league_history=league_history, add_freshmen=True, trim_roster_enabled=True)
            grad_total += int(rot.get("graduated_count", 0) or 0)
            add_total += int(rot.get("added_count", 0) or 0)
            _sync_auto_depth_chart_order(t)

        lines.append(f"Roster turnover (all teams): graduated {grad_total}, incoming freshmen {add_total}")
        lines.append("")

        s1 = run_transfer_stage_1(
            teams,
            standings,
            current_year=y,
            season_goals=season_goals,
            user_team=user_team,
            bracket_results=bracket_results,
            champion=champ,
        )
        lines.append("--- Transfers I (portal entries) ---")
        lines.append(str(s1.get("summary", "")))
        entries = list(s1.get("entries") or [])
        total_portal += len(entries)
        for row in entries:
            lines.append(
                f"    {row.get('player')}  {row.get('position'):3}  {row.get('from_team')}  "
                f"score={row.get('score')}  region={row.get('region')}"
            )
        lines.append("")

        s2 = run_transfer_stage_2(teams, standings, s1, current_year=y)
        lines.append("--- Transfers II (commitments) ---")
        lines.append(str(s2.get("summary", "")))
        lines.append(f"    blocked (cap / no dest / error): {int(s2.get('blocked_count', 0) or 0)}")
        moved = list(s2.get("entries") or [])
        total_moved += len(moved)
        total_blocked += int(s2.get("blocked_count", 0) or 0)
        for row in moved:
            lines.append(
                f"    {row.get('player')}  {row.get('position'):3}  {row.get('from_team')} -> {row.get('to_team')}  "
                f"({row.get('from_region')} -> {row.get('to_region')})"
            )
        lines.append("")

    lines.append("=" * 72)
    lines.append(f"TOTALS ({years} cycles)")
    lines.append("=" * 72)
    lines.append(f"  Portal selections (stage-1 entries after league cap): {total_portal}")
    lines.append(f"  Finalized transfers (stage-2): {total_moved}")
    lines.append(f"  Blocked (cumulative stage-2 counter): {total_blocked}")
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description="15-year transfer portal simulation (current transfer_system).")
    ap.add_argument("--years", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--output",
        type=str,
        default="",
        help="Output .txt path (default: transfer_sim_15_years.txt in project root)",
    )
    ap.add_argument("--user-team", type=str, default="", help="If set, applies season_goals miss pressure for this team.")
    ap.add_argument("--win-goal", type=int, default=8, help="Win goal for user team (if --user-team set).")
    ap.add_argument("--stage-goal", type=str, default="playoffs", help="Stage goal: none|playoffs|semifinal|championship|champion")
    args = ap.parse_args()

    out_path = args.output.strip() or os.path.join(ROOT, "transfer_sim_15_years.txt")

    season_goals: Dict[str, Any] | None = None
    ut = args.user_team.strip() or None
    if ut:
        season_goals = {"win_goal": int(args.win_goal), "stage_goal": str(args.stage_goal or "playoffs").strip().lower()}

    lines = run_sim(int(args.years), int(args.seed), user_team=ut, season_goals=season_goals)
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {len(lines)} lines to {out_path}")


if __name__ == "__main__":
    main()
