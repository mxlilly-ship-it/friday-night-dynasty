"""
Run one team through 4 offseasons (no games) to see roster turnover and player development.
Output: four_seasons_dev.txt in project root.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Team
from models.community import CommunityType
from systems import generate_team_roster, run_full_offseason
from systems.coach_generator import assign_coaches_to_teams
from systems.team_ratings import calculate_player_overall
from systems.depth_chart import build_depth_chart


def _roster_summary(team, label: str) -> list:
    """Roster size, year distribution, and top 5 players by overall."""
    from systems.development_system import _get_player_year, _get_player_age

    lines = []
    lines.append(f"  Roster: {len(team.roster)} players")
    by_year = {}
    by_age = {}
    for p in team.roster:
        y = _get_player_year(p)
        a = _get_player_age(p)
        by_year[y] = by_year.get(y, 0) + 1
        by_age[a] = by_age.get(a, 0) + 1
    lines.append(f"  By year: Fr(9)={by_year.get(9,0)} So(10)={by_year.get(10,0)} Jr(11)={by_year.get(11,0)} Sr(12)={by_year.get(12,0)}")
    lines.append(f"  By age:  14={by_age.get(14,0)} 15={by_age.get(15,0)} 16={by_age.get(16,0)} 17={by_age.get(17,0)} 18={by_age.get(18,0)}")
    # Top 5 by overall
    with_overall = [(p, calculate_player_overall(p)) for p in team.roster]
    with_overall.sort(key=lambda x: -x[1])
    lines.append("  Top 5 (overall):")
    for p, ovr in with_overall[:5]:
        y = _get_player_year(p)
        yr = ["Fr", "So", "Jr", "Sr"][y - 9] if 9 <= y <= 12 else "?"
        lines.append(f"    {p.name} ({yr}) {p.position} ovr={ovr} pot={p.potential}")
    return lines


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base, "four_seasons_dev.txt")
    lines = []

    lines.append("FRIDAY NIGHT DYNASTY - 4 SEASON DEVELOPMENT TEST")
    lines.append("=" * 60)
    lines.append("One team, 4 offseasons: graduation -> advance age/year -> develop -> add freshmen")
    lines.append("")

    team = Team(
        name="Independence Patriots",
        prestige=8,
        community_type=CommunityType.BLUE_COLLAR,
        culture_grade=9,
        enrollment=1200,
        classification="4A",
    )
    generate_team_roster(team, two_way_chance=0.55)
    assign_coaches_to_teams([team])

    coach = team.coach
    lines.append(f"Team: {team.name}")
    lines.append(f"  Facilities: {team.facilities_grade}  Coach (dev): {coach.player_development if coach else 5}")
    lines.append("")

    # Season 0 (initial)
    lines.append("-" * 60)
    lines.append("BEFORE SEASON 1 (initial roster)")
    lines.append("-" * 60)
    lines.extend(_roster_summary(team, "Initial"))
    lines.append("")

    for season in range(1, 5):
        result = run_full_offseason(team, develop=True, add_freshmen=True)
        lines.append("-" * 60)
        lines.append(f"AFTER SEASON {season} (start of season {season + 1})")
        lines.append(f"  Offseason: removed {result['removed_count']} graduated, added {result['added_count']} freshmen")
        lines.append("-" * 60)
        lines.extend(_roster_summary(team, f"Season {season + 1}"))
        lines.append("")

    lines.append("=" * 60)
    lines.append("DONE - Roster has evolved over 4 offseasons.")
    lines.append("=" * 60)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_path}")
    print("\nSummary:")
    for line in lines:
        if line.startswith("  Roster:") or line.startswith("  By year:") or "AFTER SEASON" in line or "Offseason:" in line:
            print(line)


if __name__ == "__main__":
    main()
