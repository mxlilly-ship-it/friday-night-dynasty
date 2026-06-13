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

# Hard caps for primary tags (aligned with roster generation targets).
PRIMARY_POSITION_CAPS: Dict[str, int] = {
    "QB": 2,
    "K": 2,
    "P": 2,
}


def _side_for_position(pos: str) -> str:
    if pos in OFFENSE_POSITIONS:
        return "off"
    if pos in DEFENSE_POSITIONS:
        return "def"
    return "sp"


def _rating_at(player: "Player", pos: str) -> float:
    if pos in OFFENSE_POSITIONS:
        return _position_rating_offense(player, pos)
    if pos in DEFENSE_POSITIONS:
        return _position_rating_defense(player, pos)
    if pos in SPECIALIST_POSITIONS:
        return _position_rating_specialist(player, pos)
    return 0.0


def _primary_position_targets(roster_size: int) -> Dict[str, int]:
    """Target primary counts per position for a roster (sums to roster_size)."""
    from systems.generate_team_roster import _scale_position_counts

    return _scale_position_counts(max(1, roster_size))


def _position_fill_priority(pos: str, cap: int) -> tuple:
    """Fill specialists and QB before flexible positions."""
    if pos == "K":
        return (0, 0, pos)
    if pos == "P":
        return (0, 1, pos)
    if pos == "QB":
        return (0, 2, pos)
    return (1, cap, pos)


def _assign_balanced_primary_positions(roster: List["Player"]) -> Dict[str, str]:
    """
    Assign one primary position per player respecting roster targets.
    Prevents piles of QBs/K/P when many players grade similarly at one spot.
    """
    if not roster:
        return {}

    by_name = {p.name: p for p in roster}
    targets = _primary_position_targets(len(roster))
    for pos, hard_cap in PRIMARY_POSITION_CAPS.items():
        if pos in targets:
            targets[pos] = min(targets[pos], hard_cap)

    assignments: Dict[str, str] = {}
    unassigned: List[str] = [p.name for p in roster]
    counts: Dict[str, int] = {pos: 0 for pos in targets}

    fill_order = sorted(targets.keys(), key=lambda p: _position_fill_priority(p, targets[p]))

    for pos in fill_order:
        cap = targets[pos]
        if cap <= 0:
            continue
        candidates = sorted(unassigned, key=lambda name: -_rating_at(by_name[name], pos))
        for name in candidates:
            if counts[pos] >= cap:
                break
            assignments[name] = pos
            unassigned.remove(name)
            counts[pos] += 1

    flex_positions = [
        pos
        for pos in targets
        if pos not in SPECIALIST_POSITIONS and pos != "QB"
    ]
    for name in list(unassigned):
        p = by_name[name]
        options = [
            (pos, _rating_at(p, pos))
            for pos in flex_positions
            if counts.get(pos, 0) < targets.get(pos, 0)
        ]
        options.sort(key=lambda x: -x[1])
        if options:
            pos = options[0][0]
        else:
            pos = max(flex_positions, key=lambda pos: _rating_at(p, pos))
        assignments[name] = pos
        unassigned.remove(name)
        counts[pos] = counts.get(pos, 0) + 1

    return assignments


def _assign_secondary_for_player(p: "Player", primary: str) -> Optional[str]:
    """Best two-way secondary on the opposite side of the ball."""
    candidates: List[tuple] = []
    for pos in OFFENSE_POSITIONS:
        candidates.append((pos, _position_rating_offense(p, pos), _side_for_position(pos)))
    for pos in DEFENSE_POSITIONS:
        candidates.append((pos, _position_rating_defense(p, pos), _side_for_position(pos)))
    candidates.sort(key=lambda x: -x[1])

    primary_side = _side_for_position(primary)
    if primary_side == "sp":
        return None
    other = "def" if primary_side == "off" else "off"
    for pos, r, s in candidates:
        if pos == primary:
            continue
        if s == other and r >= TWO_WAY_POSITION_FIT_THRESHOLD:
            return pos
    return None


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


def recommend_balanced_positions_for_team(team: "Team") -> Dict[str, Dict[str, Optional[str]]]:
    """Balanced primary/secondary per player — same rules as CPU preseason assignment."""
    roster = list(team.roster)
    primaries = _assign_balanced_primary_positions(roster)
    out: Dict[str, Dict[str, Optional[str]]] = {}
    for p in roster:
        primary = primaries.get(p.name, p.position)
        out[p.name] = {
            "position": primary,
            "secondary_position": _assign_secondary_for_player(p, primary),
        }
    return out


def recommend_player_positions(
    p: "Player",
    team: Optional["Team"] = None,
) -> Dict[str, Optional[str]]:
    """Coach recommendation for one player (balanced when team context is provided)."""
    if team is not None:
        recs = recommend_balanced_positions_for_team(team)
        if p.name in recs:
            return recs[p.name]

    candidates: List[tuple] = []
    for pos in OFFENSE_POSITIONS:
        candidates.append((pos, _position_rating_offense(p, pos), _side_for_position(pos)))
    for pos in DEFENSE_POSITIONS:
        candidates.append((pos, _position_rating_defense(p, pos), _side_for_position(pos)))
    for pos in SPECIALIST_POSITIONS:
        candidates.append((pos, _position_rating_specialist(p, pos), _side_for_position(pos)))
    candidates.sort(key=lambda x: -x[1])
    best_pos, _best_r, side = candidates[0]
    secondary: Optional[str] = None
    if side != "sp":
        other = "def" if side == "off" else "off"
        for pos, r, s in candidates:
            if s == other and pos != best_pos and r >= TWO_WAY_POSITION_FIT_THRESHOLD:
                secondary = pos
                break
    return {"position": best_pos, "secondary_position": secondary}


def reassign_player_position_by_ratings(p: "Player") -> None:
    """Legacy single-player reassignment (unbalanced). Prefer run_ai_position_changes_for_team."""
    rec = recommend_player_positions(p)
    p.position = str(rec["position"] or p.position)
    p.secondary_position = rec.get("secondary_position")


def run_ai_position_changes_for_team(team: "Team") -> None:
    """CPU coaches: balanced roster assignment by position fit and target counts."""
    roster = list(team.roster)
    primaries = _assign_balanced_primary_positions(roster)
    for p in roster:
        primary = primaries.get(p.name, p.position)
        p.position = primary
        p.secondary_position = _assign_secondary_for_player(p, primary)
