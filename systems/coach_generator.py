"""
Coach generator for high school football program.
Generates coaches with name, age, offensive/defensive style, and skills (1-10).
Better programs (prestige, community wealth, higher classification) attract better coaches.
"""

import random
from typing import TYPE_CHECKING, List, Optional

from models.coach import Coach, OffensiveStyle, DefensiveStyle
from models.community import get_community_rating
from systems.playbook_system import DEFENSIVE_PLAYBOOK_KEYS, OFFENSIVE_PLAYBOOK_VALUES

if TYPE_CHECKING:
    from models.team import Team

# First names commonly used for coaches
COACH_FIRST_NAMES = [
    "Mike", "Jim", "Bill", "Dave", "Tom", "Steve", "Mark", "Chris", "Dan", "Jeff",
    "Bob", "Rick", "Tony", "Joe", "Gary", "Ken", "Greg", "Scott", "Brian", "Kevin",
    "Matt", "Brad", "Todd", "Andy", "Jason", "Eric", "Ryan", "Adam", "Josh", "Nick",
]

# Last names for coaches
COACH_LAST_NAMES = [
    "Johnson", "Smith", "Williams", "Brown", "Jones", "Davis", "Miller", "Wilson",
    "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "Martin", "Lee", "Thompson",
    "White", "Harris", "Clark", "Lewis", "Robinson", "Walker", "Hall", "Young",
    "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nelson", "Carter",
    "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker",
    "Evans", "Edwards", "Collins", "Stewart", "Morris", "Rogers", "Reed", "Cook",
]


def generate_coach_name() -> str:
    """Generate a random coach name."""
    return f"{random.choice(COACH_FIRST_NAMES)} {random.choice(COACH_LAST_NAMES)}"


def _roll_skill(base: int = 5, variance: int = 2) -> int:
    """Roll a 1-10 skill with variance around base."""
    return max(1, min(10, base + random.randint(-variance, variance)))


def get_program_attractiveness(team: "Team") -> int:
    """
    Score how attractive a program is to coaches (0-10).
    Based on prestige, community wealth (facilities), and classification.
    Higher = better coaches are drawn to the job.
    """
    prestige = getattr(team, "prestige", 5) or 5
    # Prestige 1-15 -> 0-5 points (linear scale)
    prestige_score = max(0, min(5, (prestige - 1) * 5 // 14))

    # Community wealth: use facilities rating (1-10) as proxy for wealth/resources
    community_type = getattr(team, "community_type", None)
    facilities = get_community_rating(community_type, "facilities") if community_type else 5
    wealth_score = max(0, min(3, (facilities - 1) * 3 // 9))  # 1->0, 10->3

    # Classification: 6A = biggest, most attractive; 1A = smallest
    classification = getattr(team, "classification", None) or ""
    class_map = {"6A": 2, "5A": 2, "4A": 1, "3A": 1, "2A": 0, "1A": 0}
    class_score = class_map.get(classification.upper(), 0)

    return min(10, prestige_score + wealth_score + class_score)


def generate_coach(
    name: Optional[str] = None,
    age: Optional[int] = None,
    offensive_style: Optional[OffensiveStyle] = None,
    defensive_style: Optional[DefensiveStyle] = None,
    skill_bias: Optional[str] = None,
    team_prestige: Optional[int] = None,
    attractiveness_bonus: Optional[int] = None,
) -> Coach:
    """
    Generate a single coach.

    - name: If None, random first + last name
    - age: If None, random 28-62
    - offensive_style / defensive_style: If None, random choice
    - skill_bias: Optional "playcalling" | "development" | "outreach" | "culture" | "recruiting" | "scheme_teach" to slightly favor one skill
    - team_prestige: If provided (1-15), higher prestige can slightly boost skill rolls (legacy; prefer attractiveness_bonus)
    - attractiveness_bonus: 0-3+; added to base for all skills so better programs get better coaches
    """
    name = name or generate_coach_name()
    age = age if age is not None else random.randint(28, 62)
    offensive_style = offensive_style or random.choice(list(OffensiveStyle))
    defensive_style = defensive_style or random.choice(list(DefensiveStyle))
    offensive_formation = random.choice(OFFENSIVE_PLAYBOOK_VALUES)
    # Weight toward classic fronts but mix in 5-2 and 3-3 Stack for league variety.
    _def_pb_roll = random.random()
    if _def_pb_roll < 0.38:
        defensive_formation = "4-3"
    elif _def_pb_roll < 0.72:
        defensive_formation = "3-4"
    elif _def_pb_roll < 0.86:
        defensive_formation = "5-2"
    else:
        defensive_formation = "3-3 Stack"
    # Fallback if keys ever change
    if defensive_formation not in DEFENSIVE_PLAYBOOK_KEYS:
        defensive_formation = random.choice(DEFENSIVE_PLAYBOOK_KEYS)

    base = 5
    bonus = attractiveness_bonus if attractiveness_bonus is not None else 0
    if bonus == 0 and team_prestige is not None:
        bonus = max(0, (team_prestige - 5) // 3)

    playcalling = _roll_skill(base + bonus, 2) + (1 if skill_bias == "playcalling" else 0)
    player_development = _roll_skill(base + bonus, 2) + (1 if skill_bias == "development" else 0)
    community_outreach = _roll_skill(base + bonus, 2) + (1 if skill_bias == "outreach" else 0)
    culture = _roll_skill(base + bonus, 2) + (1 if skill_bias == "culture" else 0)
    recruiting = _roll_skill(base + bonus, 2) + (1 if skill_bias == "recruiting" else 0)
    scheme_teach = _roll_skill(base + bonus, 2) + (1 if skill_bias == "scheme_teach" else 0)

    winter_strength_pct = random.choice([40, 50, 50, 60])  # 50/50 most common
    spring_offense = random.choice(["run_blocking", "pass_protection", "receiving", "pass_game", "run_game"])
    spring_defense = random.choice(["run_defense", "pass_rush", "tackling", "pass_defense", "block_defeat"])

    return Coach(
        name=name,
        age=age,
        preferred_schemes={},
        offensive_style=offensive_style,
        defensive_style=defensive_style,
        offensive_formation=offensive_formation,
        defensive_formation=defensive_formation,
        winter_strength_pct=winter_strength_pct,
        spring_offense_focus=spring_offense,
        spring_defense_focus=spring_defense,
        playcalling=min(10, playcalling),
        player_development=min(10, player_development),
        community_outreach=min(10, community_outreach),
        culture=min(10, culture),
        recruiting=min(10, recruiting),
        scheme_teach=min(10, scheme_teach),
    )


def generate_coach_for_team(team: "Team") -> Coach:
    """
    Generate a coach and return them (caller assigns to team.coach).
    Better programs (prestige, community wealth/facilities, higher classification) attract
    better coaches via a higher attractiveness score and skill bonus.
    """
    attractiveness = get_program_attractiveness(team)
    # Map 0-10 attractiveness to skill bonus: 0-2 -> 0, 3-4 -> 1, 5-6 -> 2, 7+ -> 3
    attractiveness_bonus = min(3, attractiveness // 2)
    return generate_coach(attractiveness_bonus=attractiveness_bonus)


def assign_coaches_to_teams(teams: List["Team"]) -> None:
    """
    Generate and assign a coach to each team. Use when starting a new save/dynasty.
    """
    for team in teams:
        team.coach = generate_coach_for_team(team)
