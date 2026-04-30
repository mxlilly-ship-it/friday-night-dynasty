"""
Generate a full team roster (40-80 players) based on school size, enrollment,
culture, and community type. Ensures two-way players with primary position listed first.
"""

import random
from typing import List, Optional, TYPE_CHECKING

from models.team import Team
from models.community import CommunityType, get_community_rating
from systems.player_generator import generate_player, TWO_WAY_PAIRS

if TYPE_CHECKING:
    from models.player import Player


# Classification -> typical enrollment range and base roster influence
CLASSIFICATION_ENROLLMENT = {
    "1A": (100, 250),
    "2A": (250, 500),
    "3A": (500, 1000),
    "4A": (1000, 1800),
    "5A": (1800, 2800),
    "6A": (2800, 5000),
}

# Base roster size by classification
CLASSIFICATION_BASE_ROSTER = {
    "1A": 30,
    "2A": 35,
    "3A": 45,
    "4A": 55,
    "5A": 70,
    "6A": 85,
}

# Position distribution (ratios that sum to 1.0) - scaled to roster size
POSITION_RATIOS = {
    "QB": 0.05,
    "RB": 0.10,
    "WR": 0.14,
    "OL": 0.18,
    "TE": 0.05,
    "DE": 0.10,
    "DT": 0.07,
    "LB": 0.12,
    "CB": 0.09,
    "S": 0.07,
    "K": 0.02,
    "P": 0.02,
}


def _classify_from_enrollment(enrollment: int) -> str:
    """Derive classification from enrollment."""
    if enrollment < 250:
        return "1A"
    if enrollment < 500:
        return "2A"
    if enrollment < 1000:
        return "3A"
    if enrollment < 1800:
        return "4A"
    if enrollment < 2800:
        return "5A"
    return "6A"


def _enrollment_from_classification(classification: str) -> int:
    """Get midpoint enrollment for a classification."""
    low, high = CLASSIFICATION_ENROLLMENT.get(classification, (500, 1000))
    return (low + high) // 2


def calculate_roster_size(
    team: Team,
    enrollment: Optional[int] = None,
    classification: Optional[str] = None,
) -> int:
    """
    Calculate roster size (40-80) based on:
    - Classification / enrollment (school size)
    - Culture grade (1-10): good culture = higher turnout
    - Community type (culture, stability affect participation)
    """
    enroll = enrollment or team.enrollment
    class_ = classification or team.classification

    # Derive classification from enrollment or vice versa
    if enroll and not class_:
        class_ = _classify_from_enrollment(enroll)
    elif class_ and not enroll:
        enroll = _enrollment_from_classification(class_)
    elif not class_ and not enroll:
        class_ = "3A"
        enroll = 750

    base = CLASSIFICATION_BASE_ROSTER.get(class_, 54)

    # Culture grade (1-10): +0 to +12 players (culture 10 = strong turnout)
    culture_bonus = int((team.culture_grade - 5) * 2.4)  # 5=0, 10=+12

    # Community culture (1-10): strong football culture = more players
    community_culture = get_community_rating(team.community_type, "culture")
    community_bonus = int((community_culture - 5) * 1.5)  # 5=0, 10=+7

    # Enrollment influence (bigger school = more options)
    enroll_factor = min(8, max(-4, (enroll - 1000) // 500))  # cap influence

    size = base + culture_bonus + community_bonus + enroll_factor
    size += random.randint(-4, 5)  # variance
    return max(40, min(80, size))


def _scale_position_counts(roster_size: int) -> dict:
    """Scale position counts to roster size. Ensures minimums for key positions."""
    counts = {}
    for pos, ratio in POSITION_RATIOS.items():
        counts[pos] = max(1 if pos in ("K", "P", "QB") else 2, int(roster_size * ratio))
    # Adjust to hit target exactly (add/remove from flexible positions)
    total = sum(counts.values())
    diff = roster_size - total
    flex_positions = ["RB", "WR", "OL", "LB", "CB"]
    step = 1 if diff > 0 else -1
    for _ in range(abs(diff)):
        pos = random.choice(flex_positions)
        counts[pos] += step
        counts[pos] = max(2, counts[pos])
    return counts


def generate_team_roster(
    team: Team,
    enrollment: Optional[int] = None,
    classification: Optional[str] = None,
    two_way_chance: float = 0.55,
    kicking_chance: float = 0.12,
) -> List["Player"]:
    """
    Generate a full roster for a team and add players to team.roster.

    - team: Team to populate
    - enrollment: Override team enrollment (used for roster size calc)
    - classification: Override team classification (1A-6A)
    - two_way_chance: Chance a player has secondary position (default 55% - most HS players)
    - kicking_chance: Chance non-K/P has kicking ability

    Returns list of generated players. Team.roster is also populated.
    Players are generated with primary position first; two-way players have
    secondary_position set.
    """
    roster_size = calculate_roster_size(team, enrollment, classification)
    position_counts = _scale_position_counts(roster_size)

    team.roster.clear()
    players: List["Player"] = []

    for position, count in position_counts.items():
        for _ in range(count):
            # Two-way: high school players commonly play both ways
            sec = None
            if random.random() < two_way_chance and position in TWO_WAY_PAIRS and TWO_WAY_PAIRS[position]:
                sec = random.choice(TWO_WAY_PAIRS[position])
            kick = random.random() < kicking_chance or position in ("K", "P")

            player = generate_player(
                position=position,
                community_type=team.community_type,
                secondary_position=sec,
                has_kicking=kick,
                team_prestige=team.prestige,
                classification=team.classification,
                coach=team.coach,
            )
            players.append(player)
            team.add_player(player)

    return players
