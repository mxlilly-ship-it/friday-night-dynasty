"""
Write Independence Patriots depth chart to a text file.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Team
from models.community import CommunityType
from systems import generate_team_roster
from systems.depth_chart import build_depth_chart

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

    depth_chart = build_depth_chart(team)

    lines = [
        "=" * 50,
        "  INDEPENDENCE PATRIOTS - DEPTH CHART",
        "=" * 50,
        "",
        f"Roster: {team.roster_size()} players",
        "",
        depth_chart.to_text(team=team),
    ]

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base, "independence_depth_chart.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
