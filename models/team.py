"""
Team model for high school football program.
Links to Community for base ratings and holds roster of Players.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .community import CommunityType, get_community_rating

if TYPE_CHECKING:
    from .player import Player
    from .coach import Coach


@dataclass
class Team:
    name: str
    nickname: Optional[str] = None
    prestige: int = 5          # 1-15
    community_type: CommunityType = CommunityType.SUBURBAN

    # School size (affects roster size)
    enrollment: Optional[int] = None    # Student enrollment
    classification: Optional[str] = None  # "1A", "2A", "3A", "4A", "5A", "6A"
    # Geographic / administrative region (e.g. "North", "Region I"). Same as classification for scheduling pods.
    region: Optional[str] = None

    # Records
    wins: int = 0
    losses: int = 0
    regional_championships: int = 0
    championships: int = 0

    # Grades (1-10) - can be modified by community, prestige, etc.
    facilities_grade: int = 5
    culture_grade: int = 5
    booster_support: int = 5

    # Roster: list of Player objects on this team
    roster: List["Player"] = field(default_factory=list)

    # Head coach (assigned when starting new save/dynasty)
    coach: Optional["Coach"] = None

    # ---------- SEASON PLAY SELECTION (set in offseason after Schedule Release) ----------
    # Each category is 100%; within each category, selected plays' pcts sum to 100% (e.g. Inside Run: FB Trap 40%, Iso 35%, Dive 25%).
    season_offensive_play_selection: Optional[Dict[str, List[Tuple[str, float]]]] = None  # category name -> [(play_id, pct), ...], pcts in list sum to 100
    season_defensive_play_selection: Optional[Dict[str, List[Tuple[str, float]]]] = None  # same: each category's list sums to 100%
    season_play_understanding_grade: Optional[str] = None  # A+ to F- (player understanding of the selected plays)

    # Optional: sub when stamina below this (e.g. {"RB": 60, "DE": 70, "WR": 65}). Overrides defaults in game_fatigue.
    sub_stamina_thresholds: Optional[Dict[str, int]] = None

    # User-edited depth order: position -> [player names in order]. Used by build_depth_chart when present.
    depth_chart_order: Optional[Dict[str, List[str]]] = None

    def __post_init__(self):
        self._clamp_values()

    def _clamp_values(self):
        """Ensure grades and prestige stay within valid ranges."""
        self.prestige = max(1, min(15, self.prestige))
        self.facilities_grade = max(1, min(10, self.facilities_grade))
        self.culture_grade = max(1, min(10, self.culture_grade))
        self.booster_support = max(1, min(10, self.booster_support))
        self.wins = max(0, self.wins)
        self.losses = max(0, self.losses)
        self.regional_championships = max(0, self.regional_championships)
        self.championships = max(0, self.championships)

    @property
    def record(self) -> str:
        """Return record as 'W-L'."""
        return f"{self.wins}-{self.losses}"

    @property
    def community_talent_pool(self) -> int:
        """Talent pool rating from community (1-10)."""
        return get_community_rating(self.community_type, "talent_pool")

    @property
    def community_facilities(self) -> int:
        """Facilities rating from community (1-10)."""
        return get_community_rating(self.community_type, "facilities")

    @property
    def community_culture(self) -> int:
        """Culture rating from community (1-10)."""
        return get_community_rating(self.community_type, "culture")

    @property
    def community_stability(self) -> int:
        """Stability rating from community (1-10)."""
        return get_community_rating(self.community_type, "stability")

    @property
    def community_exposure(self) -> int:
        """Exposure rating from community (1-10)."""
        return get_community_rating(self.community_type, "exposure")

    def add_player(self, player: "Player") -> None:
        """Add a player to the roster."""
        if player not in self.roster:
            self.roster.append(player)

    def remove_player(self, player: "Player") -> None:
        """Remove a player from the roster."""
        if player in self.roster:
            self.roster.remove(player)

    def roster_size(self) -> int:
        """Number of players on the roster."""
        return len(self.roster)
