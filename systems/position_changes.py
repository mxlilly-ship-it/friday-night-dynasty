"""
Preseason position reassignment: primary and optional secondary positions per player.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team

from systems.depth_chart import (
    DEFENSE_POSITIONS,
    OFFENSE_POSITIONS,
    SPECIALIST_POSITIONS,
    TWO_WAY_POSITION_FIT_THRESHOLD,
    _position_rating_defense,
    _position_rating_offense,
    _position_rating_specialist,
)

VALID_POSITIONS: Set[str] = set(OFFENSE_POSITIONS + DEFENSE_POSITIONS + SPECIALIST_POSITIONS)


def _side_for_position(pos: str) -> str:
    if pos in OFFENSE_POSITIONS:
        return "off"
    if pos in DEFENSE_POSITIONS:
        return "def"
    return "sp"


def apply_position_changes_to_team(team: "Team", changes: List[Dict[str, Any]]) -> None:
    """
    Apply user-submitted changes. Each item: player_name, position, optional secondary_position (null to clear).
    Raises ValueError on unknown player or invalid position.
    """
    if not changes:
        return
    by_name = {p.name: p for p in team.roster}
    for ch in changes:
        name = str(ch.get("player_name") or "").strip()
        if not name or name not in by_name:
            raise ValueError(f"Unknown player: {name!r}")
        pos = str(ch.get("position") or "").strip().upper()
        if pos not in VALID_POSITIONS:
            raise ValueError(f"Invalid position: {pos}")
        sec_raw = ch.get("secondary_position")
        sec_val: Optional[str]
        if sec_raw is None or sec_raw == "":
            sec_val = None
        else:
            sec_val = str(sec_raw).strip().upper()
            if sec_val not in VALID_POSITIONS:
                raise ValueError(f"Invalid secondary position: {sec_val}")
        if sec_val == pos:
            sec_val = None
        p = by_name[name]
        p.position = pos
        p.secondary_position = sec_val


def reassign_player_position_by_ratings(p: "Player") -> None:
    """CPU: set primary to best-fitting position; secondary if the other side has a strong fit."""
    candidates: List[tuple] = []
    for pos in OFFENSE_POSITIONS:
        candidates.append((pos, _position_rating_offense(p, pos), _side_for_position(pos)))
    for pos in DEFENSE_POSITIONS:
        candidates.append((pos, _position_rating_defense(p, pos), _side_for_position(pos)))
    for pos in SPECIALIST_POSITIONS:
        candidates.append((pos, _position_rating_specialist(p, pos), _side_for_position(pos)))
    candidates.sort(key=lambda x: -x[1])
    best_pos, _best_r, side = candidates[0]
    p.position = best_pos
    p.secondary_position = None
    if side == "sp":
        return
    other = "def" if side == "off" else "off"
    for pos, r, s in candidates:
        if s == other and pos != best_pos and r >= TWO_WAY_POSITION_FIT_THRESHOLD:
            p.secondary_position = pos
            break


def run_ai_position_changes_for_team(team: "Team") -> None:
    """CPU coaches: move players toward their best ratings (same rules as depth-chart fit)."""
    for p in team.roster:
        reassign_player_position_by_ratings(p)
