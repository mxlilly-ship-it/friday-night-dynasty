"""
Run one regular-season simulation and write a focused summary text file.

Output: ``season_summary.txt`` at project root.
Sections:
  1. Teams
  2. Per-team season summary (plays, rush yds, pass yds, total yds, W-L, PF-PA)
  3. Game-by-game scores
"""

from __future__ import annotations

import os
import sys

# Allow ``python scripts/run_season_summary.py`` from project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_season import (  # noqa: E402
    init_season_stats,
    run_game_silent,
)
from systems.schedule_system import build_schedule_10_game  # noqa: E402
from systems.teams_loader import build_teams_from_json  # noqa: E402


SUMMARY_PATH = "season_summary.txt"


def _fmt_team_row(name: str, plays: int, rush: int, passing: int, total: int, w: int, l: int, pf: int, pa: int) -> str:
    return (
        f"  {name:<24} {plays:>5}  {rush:>6}  {passing:>6}  {total:>6}  "
        f"{w:>2}-{l:<2}  PF {pf:>4}  PA {pa:>4}  PD {pf - pa:+5d}"
    )


def main() -> None:
    print("Building teams...")
    teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    team_names = list(teams.keys())
    print(f"Loaded {len(team_names)} teams.")

    standings = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    season_stats = init_season_stats(team_names)
    team_schedules = {n: [] for n in team_names}

    schedule = build_schedule_10_game(team_names)
    print(f"Simulating {len(schedule)} regular-season games...")

    # run_game_silent updates season_stats / standings / team_schedules in place.
    for idx, (home_name, away_name) in enumerate(schedule, 1):
        run_game_silent(
            teams[home_name],
            teams[away_name],
            teams,
            season_stats,
            standings,
            output_lines=[],            # discard verbose box score output
            season_player_stats=None,
            team_schedules=team_schedules,
        )
        if idx % 25 == 0 or idx == len(schedule):
            print(f"  ... played {idx}/{len(schedule)} games")

    lines: list[str] = []
    lines.append("FRIDAY NIGHT DYNASTY — ONE-SEASON SUMMARY")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"League size: {len(team_names)} teams | Regular-season games: {len(schedule)}")
    lines.append("")

    lines.append("TEAMS")
    lines.append("-" * 78)
    cols = 3
    for i in range(0, len(team_names), cols):
        chunk = team_names[i : i + cols]
        lines.append("  " + "".join(f"{n:<26}" for n in chunk).rstrip())
    lines.append("")

    lines.append("PER-TEAM SEASON SUMMARY")
    lines.append("-" * 78)
    lines.append("  " + f"{'Team':<24} {'Plays':>5}  {'Rush':>6}  {'Pass':>6}  {'Total':>6}  {'W-L':>5}  {'PF':>7}  {'PA':>7}  {'PD':>7}")
    order = sorted(
        team_names,
        key=lambda n: (-standings[n]["wins"], -(standings[n]["points_for"] - standings[n]["points_against"])),
    )
    for n in order:
        s = season_stats[n]
        rec = standings[n]
        plays = int(s.get("total_plays") or 0)
        rush = int(s.get("rush_yards") or 0)
        passing = int(s.get("pass_yards") or 0)
        total = rush + passing
        lines.append(
            _fmt_team_row(n, plays, rush, passing, total, rec["wins"], rec["losses"], rec["points_for"], rec["points_against"])
        )
    lines.append("")

    lines.append("GAME-BY-GAME SCORES")
    lines.append("-" * 78)
    # team_schedules entries: (opponent, "W"|"L", score_for, score_against, "vs"|"@")
    seen: set[tuple[str, str]] = set()
    for n in team_names:
        for (opp, _result, my_score, opp_score, ha) in team_schedules[n]:
            if ha != "vs":
                continue
            key = tuple(sorted((n, opp)))
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {n} {my_score} - {opp} {opp_score}")
    lines.append("")

    lines.append("=" * 78)
    lines.append("END OF SUMMARY")
    lines.append("=" * 78)

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SUMMARY_PATH)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
