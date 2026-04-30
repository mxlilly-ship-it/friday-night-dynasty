"""
Player model for high school football program.
Peak age range: 14-18
Skill / dev ratings use RATING_ATTR_MIN–RATING_ATTR_MAX (see below).
"""

from dataclasses import dataclass, field
from typing import Optional

# Floor allows "non-athlete" / developmental HS bodies; ceiling stays varsity-elite scale.
RATING_ATTR_MIN = 10
RATING_ATTR_MAX = 100


@dataclass
class Player:
    name: str

    # ---------- PHYSICAL ----------
    speed: int = 50           # RATING_ATTR_MIN–RATING_ATTR_MAX
    agility: int = 50
    acceleration: int = 50
    strength: int = 50
    balance: int = 50
    jumping: int = 50
    stamina: int = 50
    injury: int = 50         # Higher = less injury prone
    frame: int = 50          # Body frame/build
    height: int = 70         # Inches (e.g., 70 = 5'10")
    weight: int = 180        # Pounds

    # ---------- MENTAL ----------
    toughness: int = 50
    effort: int = 50
    football_iq: int = 50
    coachability: int = 50
    confidence: int = 50
    discipline: int = 50
    leadership: int = 50
    composure: int = 50

    # ---------- SKILLS ----------
    throw_power: int = 50
    throw_accuracy: int = 50
    decisions: int = 50
    catching: int = 50
    run_blocking: int = 50
    pass_blocking: int = 50
    vision: int = 50
    ball_security: int = 50
    break_tackle: int = 50
    elusiveness: int = 50
    route_running: int = 50
    coverage: int = 50
    blitz: int = 50
    pass_rush: int = 50
    run_defense: int = 50
    pursuit: int = 50
    tackling: int = 50
    block_shedding: int = 50

    # ---------- SPECIALISTS (K/P - any player can have kicking) ----------
    kick_power: int = 50
    kick_accuracy: int = 50

    # ---------- DEVELOPMENT ----------
    potential: int = 50           # Ceiling (RATING range)
    growth_rate: int = 50         # How fast they improve
    peak_age: int = 16           # Age when they hit peak (14-18)
    consistency: int = 50         # Game-to-game reliability
    late_bloomer: int = 50        # Higher = develops later
    early_bloomer: int = 50       # Higher = develops earlier

    # ---------- META (optional) ----------
    age: Optional[int] = None
    position: Optional[str] = None      # Primary position
    secondary_position: Optional[str] = None  # Two-way players
    year: Optional[int] = None          # Grade/year in school
    home_region: Optional[str] = None
    transfer_count: int = 0

    def __post_init__(self):
        """Validate ratings and clamp to valid ranges."""
        self._clamp_ratings()

    def _clamp_ratings(self):
        """Ensure all ratings stay within RATING_ATTR_MIN–RATING_ATTR_MAX; peak_age 14-18."""
        lo, hi = RATING_ATTR_MIN, RATING_ATTR_MAX
        attrs = [
            "speed", "agility", "acceleration", "strength", "balance",
            "jumping", "stamina", "injury", "frame",
            "toughness", "effort", "football_iq", "coachability",
            "confidence", "discipline", "leadership", "composure",
            "throw_power", "throw_accuracy", "decisions", "catching",
            "run_blocking", "pass_blocking", "vision", "ball_security",
            "break_tackle", "elusiveness", "route_running", "coverage",
            "blitz", "pass_rush", "run_defense", "pursuit", "tackling", "block_shedding",
            "kick_power", "kick_accuracy",
            "potential", "growth_rate", "consistency", "late_bloomer", "early_bloomer",
        ]
        for attr in attrs:
            val = getattr(self, attr)
            setattr(self, attr, max(lo, min(hi, val)))

        self.peak_age = max(14, min(18, self.peak_age))
        self.height = max(60, min(84, self.height))  # 5'0" to 7'0"
        self.weight = max(120, min(400, self.weight))

    def height_str(self) -> str:
        """Return height as feet'inches\" (e.g., 5'10\")."""
        ft = self.height // 12
        inches = self.height % 12
        return f"{ft}'{inches}\""
