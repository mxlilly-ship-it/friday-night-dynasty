"""
Generate a new roster and write it to roster.txt.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Team
from models.community import CommunityType
from systems import generate_team_roster
from systems import team_ratings


def main():
    team = Team(
        name="Independence Patriots",
        prestige=8,
        community_type=CommunityType.BLUE_COLLAR,
        culture_grade=9,
        enrollment=1200,
        classification="4A",
    )
    generate_team_roster(team, two_way_chance=0.55)

    lines = [
        "=" * 60,
        "  INDEPENDENCE PATRIOTS - ROSTER",
        "=" * 60,
        "",
        f"Total: {team.roster_size()} players",
        "",
    ]

    # Group by primary position
    by_pos = {}
    for p in team.roster:
        by_pos.setdefault(p.position, []).append(p)

    for pos in ["QB", "RB", "WR", "OL", "TE", "DE", "DT", "LB", "CB", "S", "K", "P"]:
        players = by_pos.get(pos, [])
        if not players:
            continue
        lines.append(f"{pos} ({len(players)})")
        lines.append("-" * 50)
        for p in sorted(players, key=lambda x: -team_ratings.calculate_player_overall(x)):
            sec = f" / {p.secondary_position}" if p.secondary_position else ""
            overall = team_ratings.calculate_player_overall(p)
            off = team_ratings.calculate_player_offense_overall(p)
            def_ = team_ratings.calculate_player_defense_overall(p)
            pot = p.potential
            tier = team_ratings.get_overall_tier(pot)
            two_way = " *" if team_ratings.is_two_way(p) else ""
            lines.append(f"  {p.name}{sec}  Yr{p.year}  Overall {overall} | Off {off} | Def {def_} | Pot {pot} ({tier}){two_way}")
        lines.append("")

    lines.append("* = two-way player")
    lines.append("")
    lines.append("Talent tiers (by potential): Bench 40-55 | Role 56-65 | Solid 66-75 | All-State 76-85 | Elite 86-95 | Generational 96+")
    lines.append("")

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base, "roster.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
