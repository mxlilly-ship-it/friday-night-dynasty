"""
Playbook system: collections of plays grouped into playbooks.
Teams/coaches use playbooks; the play caller selects from them in situations.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Stored on `Coach.offensive_formation` / `Coach.defensive_formation` (same field as preseason "playbook").
OFFENSIVE_PLAYBOOK_VALUES: Tuple[str, ...] = (
    "Spread",
    "Pro",
    "Flexbone",
    "Smashmouth",
    "Double Wing",
    "Wing T",
)
# Stored defensive *playbook* on Coach.defensive_formation (same field as preseason).
DEFENSIVE_PLAYBOOK_KEYS: Tuple[str, ...] = ("4-3", "3-4", "5-2", "3-3 Stack")
DEFENSIVE_BASE_VALUES: Tuple[str, ...] = DEFENSIVE_PLAYBOOK_KEYS  # legacy name for imports

OFFENSIVE_PLAYBOOK_FORMATIONS: Dict[str, List[str]] = {
    "Spread": ["Dual", "Trio", "Empty", "Doubles"],
    "Pro": ["Pro", "Twins", "Dual", "Doubles", "Trey Wing", "Wing"],
    "Flexbone": ["Flexbone", "Power I", "Dual"],
    "Smashmouth": ["Power I", "Trey Wing", "Wing", "Dual"],
    "Double Wing": ["Double Wing", "Power I", "Dual"],
    "Wing T": ["Wing T", "Power I", "Flexbone", "Dual"],
}

DEFENSIVE_PLAYBOOK_FORMATIONS: Dict[str, List[str]] = {
    "4-3": ["4-3", "Nickel", "Dime", "6-2"],
    "3-4": ["3-4", "5-2", "Nickel", "Dime", "6-2"],
    "5-2": ["5-2", "Nickel", "Dime", "6-2"],
    "3-3 Stack": ["3-3 Stack", "3-3 Stack 3-High", "Dime", "6-2"],
}


def normalize_coach_offensive_playbook(value: Any) -> str:
    """
    Return a valid offensive playbook label: Spread, Pro, Flexbone, Smashmouth, Double Wing, or Wing T.
    Fixes empty strings, unknown values, and legacy single-formation saves.
    """
    s = str(value).strip() if value is not None else ""
    if not s:
        return "Spread"
    if s in OFFENSIVE_PLAYBOOK_VALUES:
        return s
    from systems.formation_plays import list_formations

    known = set(list_formations())
    if s not in known:
        return "Spread"
    if s in ("Trio", "Empty", "Dual"):
        return "Spread"
    if s in ("Pro", "Twins", "Trey Wing", "Wing"):
        return "Pro"
    if s in ("Power I",):
        return "Flexbone"
    return "Spread"


def normalize_coach_defensive_front(value: Any) -> str:
    """
    Return a defensive playbook label stored on the coach: 4-3, 3-4, 5-2, or 3-3 Stack.
    Nickel / Dime / 6-2 / stack fronts are sub-packages only (expanded when building playbooks).
    """
    s = str(value).strip() if value is not None else ""
    if not s:
        return "4-3"
    if s in DEFENSIVE_PLAYBOOK_KEYS:
        return s
    if s == "Nickel":
        return "4-3"
    from systems.defensive_formations import list_defensive_formations

    known = set(list_defensive_formations())
    if s not in known:
        return "4-3"
    # Legacy saves may store a single front; map to the playbook that contains it.
    single_to_playbook: Dict[str, str] = {
        "4-3": "4-3",
        "3-4": "3-4",
        "5-2": "5-2",
        "Nickel": "4-3",
        "Dime": "4-3",
        "6-2": "4-3",
        "3-3 Stack": "3-3 Stack",
        "3-3 Stack 3-High": "3-3 Stack",
    }
    return single_to_playbook.get(s, "4-3")

from models.play import (
    Play,
    OffensivePlayCategory,
    DefensivePlayCategory,
)


@dataclass
class Playbook:
    """
    A playbook holds a set of offensive and defensive plays.
    Can be assigned to a team or coach; the play caller picks from it by situation.
    """
    name: str
    offensive_plays: List[Play] = field(default_factory=list)
    defensive_plays: List[Play] = field(default_factory=list)

    def __post_init__(self):
        for p in self.offensive_plays:
            if p.side != "offense":
                raise ValueError(f"Play {p.id} in offensive_plays must have side='offense'")
        for p in self.defensive_plays:
            if p.side != "defense":
                raise ValueError(f"Play {p.id} in defensive_plays must have side='defense'")

    def get_offensive_plays_by_category(
        self, category: OffensivePlayCategory
    ) -> List[Play]:
        """Return all offensive plays in the given category."""
        want = getattr(category, "name", None)
        if want is None:
            return []
        return [
            p
            for p in self.offensive_plays
            if getattr(p.offensive_category, "name", None) == want
        ]

    def get_defensive_plays_by_category(
        self, category: DefensivePlayCategory
    ) -> List[Play]:
        """Return all defensive plays in the given category."""
        want = getattr(category, "name", None)
        if want is None:
            return []
        return [
            p
            for p in self.defensive_plays
            if getattr(p.defensive_category, "name", None) == want
        ]

    def get_offensive_play_by_id(self, play_id: str) -> Optional[Play]:
        """Return the offensive play with the given id, or None."""
        for p in self.offensive_plays:
            if p.id == play_id:
                return p
        return None

    def get_defensive_play_by_id(self, play_id: str) -> Optional[Play]:
        """Return the defensive play with the given id, or None."""
        for p in self.defensive_plays:
            if p.id == play_id:
                return p
        return None

    def add_offensive_play(self, play: Play) -> None:
        """Add an offensive play. Raises if play is not offensive or id already exists."""
        if play.side != "offense":
            raise ValueError("Play must have side='offense'")
        if self.get_offensive_play_by_id(play.id) is not None:
            raise ValueError(f"Offensive play id '{play.id}' already in playbook")
        self.offensive_plays.append(play)

    def add_defensive_play(self, play: Play) -> None:
        """Add a defensive play. Raises if play is not defensive or id already exists."""
        if play.side != "defense":
            raise ValueError("Play must have side='defense'")
        if self.get_defensive_play_by_id(play.id) is not None:
            raise ValueError(f"Defensive play id '{play.id}' already in playbook")
        self.defensive_plays.append(play)

    def remove_offensive_play(self, play_id: str) -> bool:
        """Remove offensive play by id. Returns True if removed."""
        for i, p in enumerate(self.offensive_plays):
            if p.id == play_id:
                self.offensive_plays.pop(i)
                return True
        return False

    def remove_defensive_play(self, play_id: str) -> bool:
        """Remove defensive play by id. Returns True if removed."""
        for i, p in enumerate(self.defensive_plays):
            if p.id == play_id:
                self.defensive_plays.pop(i)
                return True
        return False

    def offensive_categories_present(self) -> List[OffensivePlayCategory]:
        """Return list of offensive categories that have at least one play."""
        seen = set()
        for p in self.offensive_plays:
            if p.offensive_category is not None:
                seen.add(p.offensive_category)
        return list(seen)

    def defensive_categories_present(self) -> List[DefensivePlayCategory]:
        """Return list of defensive categories that have at least one play."""
        seen = set()
        for p in self.defensive_plays:
            if p.defensive_category is not None:
                seen.add(p.defensive_category)
        return list(seen)

    def add_formation(self, formation_name: str) -> None:
        """
        Add all offensive plays for the given formation (e.g. "Dual").
        Skips any play whose id is already in this playbook.
        """
        from systems.formation_plays import get_formation_plays
        for play in get_formation_plays(formation_name):
            if self.get_offensive_play_by_id(play.id) is None:
                self.add_offensive_play(play)

    def add_defensive_formation(self, formation_name: str) -> None:
        """
        Add all defensive plays for the given formation (e.g. "4-3").
        Skips any play whose id is already in this playbook.
        """
        from systems.defensive_formations import get_defensive_formation_plays
        for play in get_defensive_formation_plays(formation_name):
            if self.get_defensive_play_by_id(play.id) is None:
                self.add_defensive_play(play)

    def get_offensive_plays_by_formation(self, formation: str) -> List[Play]:
        """Return all offensive plays that belong to the given formation."""
        return [p for p in self.offensive_plays if p.formation == formation]

    def get_defensive_plays_by_formation(self, formation: str) -> List[Play]:
        """Return all defensive plays that belong to the given formation."""
        return [p for p in self.defensive_plays if p.formation == formation]


def build_playbook_for_team(team: Any, name: Optional[str] = None) -> Playbook:
    """
    Build a Playbook from a team's coach formation choices.

    Offense:
    - Historically `coach.offensive_formation` was a single formation (Dual/Trio/Empty/Pro/Twins).
    - For now, we also support "offensive playbooks" stored in the same field:
      - "Spread"   -> Dual + Trio + Empty + Doubles
      - "Pro"      -> Pro + Twins + Dual + Doubles + Trey Wing + Wing
      - "Flexbone"   -> Flexbone + Power I + Dual
      - "Smashmouth" -> Power I + Trey Wing + Wing + Dual
      - "Double Wing" -> Double Wing + Power I + Dual
      - "Wing T"     -> Wing T + Power I + Flexbone + Dual

    Defense:
    - `coach.defensive_formation` holds a defensive *playbook* that expands into fronts:
      - "4-3" -> 4-3, Nickel, Dime, 6-2
      - "3-4" -> 3-4, 5-2, Nickel, Dime, 6-2
      - "5-2" -> 5-2, Nickel, Dime, 6-2
      - "3-3 Stack" -> 3-3 Stack, 3-3 Stack 3-High, Dime, 6-2
    - Any other normalized value falls back to a single formation list of itself.
    """
    label = name or (getattr(team, "name", "Team") + " playbook")
    pb = Playbook(label)
    coach = getattr(team, "coach", None)

    off_raw = getattr(coach, "offensive_formation", "Spread") if coach else "Spread"
    def_raw = getattr(coach, "defensive_formation", "4-3") if coach else "4-3"
    off_form = normalize_coach_offensive_playbook(off_raw)
    def_form = normalize_coach_defensive_front(def_raw)

    # Map playbook concepts to the underlying formation plays we actually have.
    off_form = str(off_form).strip()
    formations = OFFENSIVE_PLAYBOOK_FORMATIONS.get(off_form, [off_form])

    # De-dupe while preserving order.
    seen = set()
    formations_dedup: List[str] = []
    for f in formations:
        if f not in seen:
            formations_dedup.append(f)
            seen.add(f)

    for f in formations_dedup:
        pb.add_formation(f)
    def_form = str(def_form).strip()
    def_formations = DEFENSIVE_PLAYBOOK_FORMATIONS.get(def_form, [def_form])

    seen_def = set()
    def_formations_dedup: List[str] = []
    for f in def_formations:
        if f not in seen_def:
            def_formations_dedup.append(f)
            seen_def.add(f)

    for f in def_formations_dedup:
        pb.add_defensive_formation(f)
    return pb
