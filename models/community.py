"""
Community types and their attribute ratings (1-10 scale).
Affects talent pool, facilities, culture, stability, and exposure.
"""

from enum import Enum
from typing import Dict


class CommunityType(str, Enum):
    RURAL = "rural"
    URBAN = "urban"
    SUBURBAN = "suburban"
    AFFLUENT = "affluent"
    BLUE_COLLAR = "blue-collar"
    FOOTBALL_FACTORY = "football factory"


# Attribute ratings by community type (1-10)
COMMUNITY_RATINGS: Dict[CommunityType, Dict[str, int]] = {
    CommunityType.RURAL: {
        "talent_pool": 4,
        "facilities": 4,
        "culture": 9,
        "stability": 8,
        "exposure": 3,
    },
    CommunityType.URBAN: {
        "talent_pool": 8,
        "facilities": 6,
        "culture": 5,
        "stability": 5,
        "exposure": 7,
    },
    CommunityType.SUBURBAN: {
        "talent_pool": 7,
        "facilities": 7,
        "culture": 7,
        "stability": 8,
        "exposure": 6,
    },
    CommunityType.AFFLUENT: {
        "talent_pool": 6,
        "facilities": 9,
        "culture": 6,
        "stability": 8,
        "exposure": 8,
    },
    CommunityType.BLUE_COLLAR: {
        "talent_pool": 7,
        "facilities": 3,
        "culture": 9,
        "stability": 7,
        "exposure": 5,
    },
    CommunityType.FOOTBALL_FACTORY: {
        "talent_pool": 9,
        "facilities": 9,
        "culture": 10,
        "stability": 9,
        "exposure": 10,
    },
}


def get_community_rating(community_type: CommunityType, attribute: str) -> int:
    """Get the rating for an attribute in a community type."""
    return COMMUNITY_RATINGS.get(community_type, {}).get(attribute, 5)
