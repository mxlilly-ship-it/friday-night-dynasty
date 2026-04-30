from __future__ import annotations

import random
import sys
from pathlib import Path
from dataclasses import dataclass
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.game_service import _submit_kickoff_play, submit_play
from engine.game_engine import Game


@dataclass
class TeamStub:
    name: str
    roster: list = None
    coach: object = None

    def __post_init__(self) -> None:
        if self.roster is None:
            self.roster = []


def sample_kickoffs(n: int = 5000) -> None:
    home = TeamStub("Home")
    away = TeamStub("Away")
    kick_types = [
        "KICKOFF_DEEP",
        "KICKOFF_MIDDLE_SQUIB",
        "KICKOFF_ONSIDE",
        "KICKOFF_SURPRISE_ONSIDE",
    ]
    return_types = [
        "KICKOFF_RETURN_MIDDLE_WEDGE",
        "KICKOFF_RETURN_FIELD_RETURN",
        "KICKOFF_RETURN_REVERSE",
    ]
    print("\nKickoff calibration")
    for k in kick_types:
        distances = []
        tbs = 0
        onside = 0
        ret_yds = []
        tds = 0
        for _ in range(n):
            g = Game()
            g.pending_kickoff = True
            g.kickoff_kicking_team = "home"
            g.possession = "home"
            out = _submit_kickoff_play(g, home, away, k, random.choice(return_types))
            r = out["result"]
            distances.append(int(r.get("kick_distance", 0)))
            tbs += 1 if r.get("touchback") else 0
            onside += 1 if r.get("onside_recovered") else 0
            if r.get("return_yards") is not None:
                ret_yds.append(int(r.get("return_yards") or 0))
            tds += 1 if r.get("kickoff_td") else 0
        avg_ret = mean([y for y in ret_yds if y > 0]) if any(y > 0 for y in ret_yds) else 0.0
        print(
            f"  {k:26s} dist={mean(distances):.1f} "
            f"tb%={(tbs / n) * 100:.1f} onside%={(onside / n) * 100:.1f} "
            f"ko_ret_avg={avg_ret:.1f} ko_td%={(tds / n) * 100:.2f}"
        )


def sample_punts(n: int = 5000) -> None:
    print("\nPunt calibration")
    home = TeamStub("Home")
    away = TeamStub("Away")
    punt_calls = [
        ("PUNT", "DEF_PUNT_RETURN"),
        ("PUNT_PRO", "DEF_PUNT_RETURN"),
        ("PUNT", "DEF_PUNT_BLOCK"),
        ("PUNT", "DEF_PUNT_ALL_OUT_BLOCK"),
    ]
    for off_call, def_call in punt_calls:
        gross = []
        ret = []
        for _ in range(n):
            g = Game()
            g.possession = "home"
            g.ball_position = 40
            g.down = 4
            g.yards_to_go = 8
            out = submit_play(g, home, away, off_call, def_call)
            r = out["result"]
            if r.get("punt"):
                gross.append(int(r.get("punt_gross_yards") or 0))
                ret.append(int(r.get("punt_return_yards") or 0))
        print(
            f"  {off_call:8s} vs {def_call:22s} "
            f"gross_avg={mean(gross):.1f} ret_avg={mean(ret):.1f}"
        )


def sample_field_goals(n: int = 5000) -> None:
    print("\nField goal calibration")
    home = TeamStub("Home")
    away = TeamStub("Away")
    spots = [70, 65, 60, 55, 50]  # ~47, 52, 57, 62, 67 yard attempts
    for spot in spots:
        good = 0
        for _ in range(n):
            g = Game()
            g.possession = "home"
            g.ball_position = spot
            g.down = 4
            g.yards_to_go = 6
            out = submit_play(g, home, away, "FIELD_GOAL", "DEF_FG_BLOCK")
            r = out["result"]
            good += 1 if r.get("field_goal_good") else 0
        dist = (100 - spot) + 17
        print(f"  {dist:2d}y FG good%={(good / n) * 100:.1f}")


if __name__ == "__main__":
    random.seed(7)
    sample_kickoffs()
    sample_punts()
    sample_field_goals()
