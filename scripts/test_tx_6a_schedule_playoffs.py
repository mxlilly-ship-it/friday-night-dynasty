#!/usr/bin/env python3
"""Schedule + playoff check for the Texas 6A league file.

Schedule: 10 games each, every district pair once, no rematches, one game per week.
Playoffs: top 64 by the records those games produce, then a full 64-team bracket.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.league_service import _init_playoffs_multiclass  # noqa: E402
from models.team import Team  # noqa: E402
from systems.generate_team_roster import generate_team_roster  # noqa: E402
from systems.league_structure import build_regular_season_weeks  # noqa: E402
from systems.playoff_system import run_next_playoff_round  # noqa: E402
from systems.playoff_systems import get_playoff_system  # noqa: E402

LEAGUE = ROOT / "data" / "tx_6a_league.json"


def _fail(msg: str) -> None:
    print("FAIL", msg)
    raise SystemExit(1)


def main() -> None:
    random.seed(6)
    data = json.loads(LEAGUE.read_text(encoding="utf-8"))
    if data.get("playoff_system") != "top64":
        _fail(f"league playoff_system is {data.get('playoff_system')}, expected top64")
    cfg = get_playoff_system("top64")
    if cfg.bracket_size != 64:
        _fail(f"top64 bracket_size is {cfg.bracket_size}")

    teams = {}
    by_district = defaultdict(list)
    for row in data["teams"]:
        t = Team(
            name=row["name"],
            nickname=row.get("nickname"),
            classification=row["classification"],
            region=row["region"],
            prestige=int(row["prestige"]),
        )
        teams[row["name"]] = t
        by_district[row["region"]].append(row["name"])

    weeks = build_regular_season_weeks(teams, {"user_team": "Duncanville", "playoff_system": "top64"})
    counts = defaultdict(int)
    pairs = defaultdict(int)
    for wk in weeks:
        seen = set()
        for home, away in wk:
            if home in seen or away in seen or home == away:
                _fail(f"team plays twice in one week: {home} vs {away}")
            seen.add(home)
            seen.add(away)
            counts[home] += 1
            counts[away] += 1
            pairs[tuple(sorted((home, away)))] += 1

    if len(counts) != 249:
        _fail(f"scheduled {len(counts)} teams, expected 249")
    short = [n for n, c in counts.items() if c != 10]
    if short:
        _fail(f"{len(short)} teams do not have 10 games, e.g. {short[:5]}")
    rematches = [p for p, n in pairs.items() if n != 1]
    if rematches:
        _fail(f"{len(rematches)} rematches")
    missing_district = []
    for names in by_district.values():
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                if pairs[tuple(sorted((a, b)))] != 1:
                    missing_district.append((a, b))
    if missing_district:
        _fail(f"{len(missing_district)} district games missing, e.g. {missing_district[:3]}")
    print(f"schedule ok: {len(weeks)} weeks, 249 teams x 10 games, every district game played once")

    standings = {
        n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in teams
    }
    for wk in weeks:
        for home, away in wk:
            hp = teams[home].prestige
            ap = teams[away].prestige
            if hp > ap or (hp == ap and home < away):
                winner, loser, wsc, lsc = home, away, 28, 14
            else:
                winner, loser, wsc, lsc = away, home, 28, 14
            standings[winner]["wins"] += 1
            standings[loser]["losses"] += 1
            standings[winner]["points_for"] += wsc
            standings[winner]["points_against"] += lsc
            standings[loser]["points_for"] += lsc
            standings[loser]["points_against"] += wsc

    state = {"user_team": "Duncanville", "playoff_system": "top64", "teams": {}}
    playoffs = _init_playoffs_multiclass(state, teams, standings)
    bracket = (playoffs.get("by_class") or {}).get("6A")
    if not bracket:
        _fail(f"no 6A bracket in {list((playoffs.get('by_class') or {}).keys())}")
    seeds = bracket.get("seeds") or []
    if len(seeds) != 64:
        _fail(f"bracket has {len(seeds)} seeds, expected 64")
    seeded_names = [str(s["team"]) for s in sorted(seeds, key=lambda s: int(s["seed"]))]
    if [int(s["seed"]) for s in sorted(seeds, key=lambda s: int(s["seed"]))] != list(range(1, 65)):
        _fail("seeds are not numbered 1 through 64")

    def _key(name: str):
        s = standings[name]
        return (s["wins"], s["points_for"] - s["points_against"])

    for earlier, later in zip(seeded_names, seeded_names[1:]):
        if _key(earlier) < _key(later):
            _fail(f"seed order broken: {later} ranks ahead of {earlier}")
    cut = _key(seeded_names[-1])
    left_out = [n for n in teams if n not in set(seeded_names) and _key(n) > cut]
    if left_out:
        _fail(f"better teams left out of the top 64: {left_out[:5]}")
    top_name, last_name = seeded_names[0], seeded_names[-1]
    print(
        f"playoff field ok: 1 {top_name} ({standings[top_name]['wins']}-"
        f"{standings[top_name]['losses']}) vs 64 {last_name} "
        f"({standings[last_name]['wins']}-{standings[last_name]['losses']})"
    )

    print("simulating 63 playoff games...")
    for name in seeded_names:
        generate_team_roster(teams[name])
    results = []
    champion = None
    completed = False
    with redirect_stdout(StringIO()):
        for _ in range(6):
            champion, completed = run_next_playoff_round(
                teams, standings, seeded_names, results
            )
            if completed:
                break
    rounds = Counter(r.get("round") for r in results)
    expected = {
        "Round of 64": 32,
        "Round of 32": 16,
        "Round of 16": 8,
        "Quarterfinal": 4,
        "Semifinal": 2,
        "Championship": 1,
    }
    if dict(rounds) != expected:
        _fail(f"round counts {dict(rounds)} != {expected}")
    opening = {
        frozenset((r.get("home"), r.get("away")))
        for r in results
        if r.get("round") == "Round of 64"
    }
    for i in range(32):
        pair = frozenset((seeded_names[i], seeded_names[63 - i]))
        if pair not in opening:
            _fail(f"Round of 64 missing {seeded_names[i]} vs {seeded_names[63 - i]}")
    if not completed or not champion:
        _fail("bracket did not finish")
    print(f"playoff ok: {sum(rounds.values())} games, 1 vs 64 in the first round, champion {champion}")
    print("PASS")


if __name__ == "__main__":
    main()
