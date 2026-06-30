"""Smoke test for offseason 7-on-7 tournament sim."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.team import Team
from models.player import Player
from systems.seven_on_seven import (
    TOURNAMENT_TIERS,
    _group_stage_pairings,
    run_seven_on_seven_tournament,
)


def _fake_team(name: str, prestige: int) -> Team:
    t = Team(name=name, prestige=prestige)
    t.roster = [
        Player(name=f"{name} QB", position="QB", throw_accuracy=70, throw_power=68, decisions=66, speed=62),
        Player(name=f"{name} WR1", position="WR", catching=72, route_running=70, speed=74, agility=71),
        Player(name=f"{name} WR2", position="WR", catching=68, route_running=67, speed=70, agility=69),
        Player(name=f"{name} CB1", position="CB", coverage=70, speed=72, agility=71, tackling=60),
        Player(name=f"{name} CB2", position="CB", coverage=67, speed=69, agility=68, tackling=58),
    ]
    return t


def main() -> None:
    names = [f"Team {i}" for i in range(1, 17)]
    teams = {n: _fake_team(n, 4 + i) for i, n in enumerate(names)}
    user = "Team 1"

    for tier in TOURNAMENT_TIERS:
        result = run_seven_on_seven_tournament(teams, user, tier, seed=42)
        assert len(result["teams"]) == 8
        assert user in result["teams"]
        assert len(result["group_games"]) == 16
        assert len(result["standings"]) == 8
        assert result["champion"] in result["teams"]
        assert result["user_record"].count("-") == 1
        user_games = [g for g in result["group_games"] if g["user_involved"]]
        assert len(user_games) == 4, f"expected 4 group games for user, got {len(user_games)}"
        for row in result["standings"]:
            total = int(row["w"]) + int(row["l"])
            assert total == 4, f"{row['team']} record {row['w']}-{row['l']} is only {total} games"
        for g in result["group_games"]:
            assert int(g["home_score"]) != int(g["away_score"]), "group game ended in a tie"
        print(f"{tier}: champion={result['champion']} user={result['user_finish']} ({result['user_record']})")

    field = [f"T{i}" for i in range(8)]
    pairs = _group_stage_pairings(field)
    assert len(pairs) == 16
    per_team = {n: 0 for n in field}
    for a, b in pairs:
        per_team[a] += 1
        per_team[b] += 1
    assert all(c == 4 for c in per_team.values())
    print("ok")


if __name__ == "__main__":
    main()
