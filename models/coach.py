"""
Coach model for high school football program.
Skills are 1-10. Schemes will be fleshed out later.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OffensiveStyle(Enum):
    """Preferred offensive philosophy."""
    HEAVY_RUN = "Heavy Run"
    LEAN_RUN = "Lean Run"
    BALANCED = "Balanced"
    LEAN_PASS = "Lean Pass"
    HEAVY_PASS = "Heavy Pass"


class DefensiveStyle(Enum):
    """Preferred defensive philosophy."""
    BASE = "Base"
    HEAVY_PRESSURE = "Heavy Pressure"
    AGGRESSIVE_MAN = "Aggressive Man"
    CONSERVATIVE_MAN = "Conservative Man"
    PRIMARY_ZONE = "Primary Zone"
    AGGRESSIVE_ZONE = "Aggressive Zone"


@dataclass
class Coach:
    name: str
    age: int = 35

    # ---------- SCHEMES (to be fleshed out later) ----------
    preferred_schemes: Dict[str, Any] = field(default_factory=dict)

    # ---------- PHILOSOPHY ----------
    offensive_style: OffensiveStyle = OffensiveStyle.BALANCED
    defensive_style: DefensiveStyle = DefensiveStyle.BASE

    # ---------- PLAYBOOK (formation choice) ----------
    offensive_formation: str = "Spread"   # "Spread" | "Pro" | "Flexbone" | "Smashmouth" | "Double Wing" | "Wing T"; used to build playbook
    defensive_formation: str = "4-3"     # Defensive playbook: "4-3" | "3-4" | "5-2" | "3-3 Stack" → expanded fronts in sim

    # ---------- OFFSEASON FOCUS ----------
    # Winter Phase 1 & 2: physical development split. Must sum to 100.
    winter_strength_pct: int = 50        # % toward strength; remainder = speed/quickness (50 = 50/50)
    # Spring Ball: targeted skill development focus
    spring_offense_focus: str = "run_game"   # run_blocking | pass_protection | receiving | pass_game | run_game
    spring_defense_focus: str = "pass_defense"   # run_defense | pass_rush | tackling | pass_defense | block_defeat

    # ---------- SKILL SETS (1-10) ----------
    playcalling: int = 5           # Better in-game play calls
    player_development: int = 5    # Develop players faster
    community_outreach: int = 5    # Fundraising, facilities, upgrades
    culture: int = 5               # Grow program culture
    recruiting: int = 5             # Attract better incoming freshmen
    scheme_teach: int = 5          # Ability to teach schemes; higher = run more plays efficiently (worse coaches can't teach as many plays well)

    # ---------- CAREER TRACKING ----------
    years_at_school: int = 0       # Seasons at current school (reset on hire)
    years_since_scheme_change: int = 0  # Can change scheme every 3 years
    # Last calendar season year when offensive/defensive playbook was changed (Spread, 4-3, …); 0 = never locked
    last_preferred_playbook_change_year: int = 0
    hot_seat: int = 0              # 0–100 job pressure (updated each offseason carousel)

    def __post_init__(self):
        self._clamp_skills()

    def _clamp_skills(self) -> None:
        """Ensure all skills stay 1-10; offseason focus valid."""
        for attr in ("playcalling", "player_development", "community_outreach", "culture", "recruiting", "scheme_teach"):
            val = getattr(self, attr)
            setattr(self, attr, max(1, min(10, val)))
        self.age = max(21, min(75, self.age))
        self.hot_seat = max(0, min(100, int(getattr(self, "hot_seat", 0) or 0)))
        self.winter_strength_pct = max(0, min(100, self.winter_strength_pct))
        if self.spring_offense_focus not in ("run_blocking", "pass_protection", "receiving", "pass_game", "run_game"):
            self.spring_offense_focus = "run_game"
        if self.spring_defense_focus not in ("run_defense", "pass_rush", "tackling", "pass_defense", "block_defeat"):
            self.spring_defense_focus = "pass_defense"


def _coerce_offensive_style(value: Any) -> OffensiveStyle:
    if isinstance(value, OffensiveStyle):
        return value
    s = str(value).strip().replace(" ", "_").upper()
    for e in OffensiveStyle:
        if e.name == s or e.value == str(value).strip():
            return e
    # try match by partial
    for e in OffensiveStyle:
        if s.replace("_", "") in e.name.replace("_", ""):
            return e
    return OffensiveStyle.BALANCED


def _coerce_defensive_style(value: Any) -> DefensiveStyle:
    if isinstance(value, DefensiveStyle):
        return value
    s = str(value).strip().replace(" ", "_").upper()
    for e in DefensiveStyle:
        if e.name == s or e.value == str(value).strip():
            return e
    for e in DefensiveStyle:
        if s.replace("_", "") in e.name.replace("_", ""):
            return e
    return DefensiveStyle.BASE


def apply_coach_config_dict(coach: "Coach", config: Dict[str, Any]) -> None:
    """Apply API/client dict to coach (strings → enums, then clamp)."""
    if not config:
        coach._clamp_skills()
        return
    fields = getattr(coach, "__dataclass_fields__", {})
    for k, v in config.items():
        if k == "offensive_style":
            coach.offensive_style = _coerce_offensive_style(v)
        elif k == "defensive_style":
            coach.defensive_style = _coerce_defensive_style(v)
        elif k in fields:
            setattr(coach, k, v)
    coach._clamp_skills()
