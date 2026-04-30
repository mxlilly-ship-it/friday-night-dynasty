"""
Play model for Friday Night Dynasty.
Defines individual plays and their categories for offense and defense.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class OffensivePlayCategory(Enum):
    """Offensive play categories for playbook and play calling."""
    INSIDE_RUN = "Inside Run"
    OUTSIDE_RUN = "Outside Run"
    SHORT_PASS = "Short Pass"
    MEDIUM_PASS = "Medium Pass"
    LONG_PASS = "Long Pass"
    PLAY_ACTION = "Play Action"


class DefensivePlayCategory(Enum):
    """Defensive play categories for playbook and play calling."""
    ZONES = "Zones"
    MANS = "Mans"
    ZONE_PRESSURE = "Zone Pressure"
    MAN_PRESSURE = "Man Pressure"


@dataclass
class Play:
    """
    A single play (offensive or defensive).
    Used by playbooks and the play caller; the play engine executes the result.
    """
    id: str
    name: str
    side: str  # "offense" or "defense"

    # Exactly one of these is set depending on side
    offensive_category: Optional[OffensivePlayCategory] = None
    defensive_category: Optional[DefensivePlayCategory] = None

    # Formation (offense only): e.g. "Dual", "Spread"
    formation: Optional[str] = None

    # Optional metadata for flavor, balance, or future engine use
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.side = self.side.lower()
        if self.side not in ("offense", "defense"):
            raise ValueError('side must be "offense" or "defense"')
        if self.side == "offense" and self.offensive_category is None:
            raise ValueError("offensive play must have offensive_category")
        if self.side == "defense" and self.defensive_category is None:
            raise ValueError("defensive play must have defensive_category")
        if self.side == "offense" and self.defensive_category is not None:
            self.defensive_category = None
        if self.side == "defense" and self.offensive_category is not None:
            self.offensive_category = None

    @property
    def category(self) -> Optional[Enum]:
        """Return the relevant category (offensive or defensive) for this play."""
        return self.offensive_category if self.side == "offense" else self.defensive_category
