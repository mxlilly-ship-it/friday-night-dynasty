"""
Cross-region schedule planning: slot counts from league templates, user picks, pairing with locks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from systems.league_structure import classification_key, DEFAULT_REGION_KEY

if TYPE_CHECKING:
    from models.team import Team


@dataclass
class ClassTemplate:
    """Scheduling template for one classification bucket."""

    template_id: str
    classification: str
    region_names: List[str]
    region_sizes: List[int]
    cross_slot_count: int
    in_region_weeks: int


@dataclass
class CrossRegionSlot:
    slot_index: int
    label: str
    opponent_region: str
    eligible_teams: List[str]


def _team_class_region(teams: Dict[str, "Team"], team_name: str) -> Tuple[str, str]:
    t = teams.get(team_name)
    if not t:
        return "UNK", DEFAULT_REGION_KEY
    cls = classification_key(getattr(t, "classification", None))
    reg = (getattr(t, "region", None) or DEFAULT_REGION_KEY).strip() or DEFAULT_REGION_KEY
    return cls, reg


def _group_class_regions(teams: Dict[str, "Team"], classification: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for name, t in teams.items():
        cls = classification_key(getattr(t, "classification", None))
        if cls != classification:
            continue
        reg = (getattr(t, "region", None) or DEFAULT_REGION_KEY).strip() or DEFAULT_REGION_KEY
        out.setdefault(reg, []).append(name)
    for reg in out:
        out[reg] = sorted(out[reg])
    return out


def detect_class_template(teams: Dict[str, "Team"], classification: str) -> Optional[ClassTemplate]:
    """Return template metadata when this class matches a cross-region league layout."""
    regs = _group_class_regions(teams, classification)
    region_names = sorted(regs.keys())
    sizes = [len(regs[r]) for r in region_names]
    total = sum(sizes)

    if len(region_names) == 2 and total == 20 and all(s == 10 for s in sizes):
        return ClassTemplate("2x10", classification, region_names, sizes, 1, 9)

    if len(region_names) == 4 and total == 32 and all(s == 8 for s in sizes):
        return ClassTemplate("4x8x3", classification, region_names, sizes, 3, 7)

    if len(region_names) == 4 and total == 40 and all(s == 10 for s in sizes):
        return ClassTemplate("4x10", classification, region_names, sizes, 1, 9)

    if len(region_names) == 4 and total == 28 and all(s == 7 for s in sizes):
        return ClassTemplate("4x7x4", classification, region_names, sizes, 4, 7)

    return None


def _opponent_region_for_slot(template: ClassTemplate, user_region: str, slot_index: int) -> Optional[str]:
    if user_region not in template.region_names:
        return None
    ri = template.region_names.index(user_region)

    if template.template_id == "2x10":
        if slot_index != 0:
            return None
        other = [r for r in template.region_names if r != user_region]
        return other[0] if other else None

    if template.template_id == "4x8x3":
        pair_weeks = [
            ((0, 1), (2, 3)),
            ((0, 2), (1, 3)),
            ((0, 3), (1, 2)),
        ]
        if slot_index < 0 or slot_index >= len(pair_weeks):
            return None
        pairs = pair_weeks[slot_index]
        for a, b in pairs:
            if ri == a:
                return template.region_names[b]
            if ri == b:
                return template.region_names[a]
        return None

    if template.template_id == "4x10":
        if slot_index != 0:
            return None
        if ri in (0, 1):
            return template.region_names[1] if ri == 0 else template.region_names[0]
        if ri in (2, 3):
            return template.region_names[3] if ri == 2 else template.region_names[2]
        return None

    if template.template_id == "4x7x4":
        pair_weeks = [
            ((0, 1), (2, 3)),
            ((0, 2), (1, 3)),
            ((0, 3), (1, 2)),
            ((0, 1), (2, 3)),
        ]
        if slot_index < 0 or slot_index >= len(pair_weeks):
            return None
        pairs = pair_weeks[slot_index]
        for a, b in pairs:
            if ri == a:
                return template.region_names[b]
            if ri == b:
                return template.region_names[a]
        return None

    return None


def cross_region_slots_for_team(teams: Dict[str, "Team"], user_team: str) -> List[CrossRegionSlot]:
    """Slots the user must fill for out-of-region games (empty when pod-only class)."""
    if not user_team or user_team not in teams:
        return []
    cls, user_region = _team_class_region(teams, user_team)
    template = detect_class_template(teams, cls)
    if not template or template.cross_slot_count < 1:
        return []

    regs = _group_class_regions(teams, cls)
    slots: List[CrossRegionSlot] = []
    for si in range(template.cross_slot_count):
        opp_reg = _opponent_region_for_slot(template, user_region, si)
        if not opp_reg:
            continue
        eligible = list(regs.get(opp_reg, []))
        if not eligible:
            continue
        slots.append(
            CrossRegionSlot(
                slot_index=si,
                label=f"Out-of-region · vs {opp_reg}",
                opponent_region=opp_reg,
                eligible_teams=eligible,
            )
        )
    return slots


def cross_region_slots_to_json(slots: List[CrossRegionSlot]) -> List[Dict[str, Any]]:
    return [
        {
            "slot_index": s.slot_index,
            "label": s.label,
            "opponent_region": s.opponent_region,
            "eligible_teams": s.eligible_teams,
        }
        for s in slots
    ]


def normalize_cross_region_picks(
    teams: Dict[str, "Team"],
    user_team: str,
    raw_picks: Any,
) -> Dict[int, str]:
    """Validate and return {slot_index: opponent_name}."""
    slots = cross_region_slots_for_team(teams, user_team)
    if not slots:
        return {}

    by_slot = {s.slot_index: s for s in slots}
    required = set(by_slot.keys())
    if not isinstance(raw_picks, list):
        raise ValueError("Choose an opponent for each out-of-region game.")

    out: Dict[int, str] = {}
    for row in raw_picks:
        if not isinstance(row, dict):
            continue
        si = int(row.get("slot_index", -1))
        opp = str(row.get("opponent") or "").strip()
        if si not in by_slot:
            continue
        if not opp:
            raise ValueError(f"Pick an opponent for {by_slot[si].label}.")
        if opp not in by_slot[si].eligible_teams:
            raise ValueError(f"{opp} is not an eligible opponent for {by_slot[si].label}.")
        if opp == user_team:
            raise ValueError("You cannot schedule yourself.")
        out[si] = opp

    missing = required - set(out.keys())
    if missing:
        first = by_slot[min(missing)]
        raise ValueError(f"Pick an opponent for {first.label}.")
    return out


def pair_two_regions_with_locks(
    region_a: List[str],
    region_b: List[str],
    offset: int,
    locks: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    """
    1:1 pairings between two regions. ``locks`` are oriented (home, away) edges that must appear.
    Remaining teams paired with the same home/away alternation as ``_pair_two_regions_week``.
    """
    a_rem = list(region_a)
    b_rem = list(region_b)
    games: List[Tuple[str, str]] = []

    for home, away in locks:
        if home in a_rem and away in b_rem:
            games.append((home, away))
            a_rem.remove(home)
            b_rem.remove(away)
        elif away in a_rem and home in b_rem:
            games.append((away, home))
            a_rem.remove(away)
            b_rem.remove(home)
        else:
            raise ValueError("Cross-region pick conflicts with another school's schedule.")

    n = min(len(a_rem), len(b_rem))
    if len(a_rem) != len(b_rem):
        raise ValueError("Cross-region pairing could not balance remaining teams.")
    for i in range(n):
        home = a_rem[i]
        away = b_rem[(i + offset) % n] if n else b_rem[0]
        if i % 2 == 1:
            home, away = away, home
        games.append((home, away))
    return games


def locks_for_user_picks(
    teams: Dict[str, "Team"],
    user_team: str,
    picks: Dict[int, str],
) -> List[Tuple[str, str]]:
    """Convert user slot picks to (home, away) locks using standard pairing orientation."""
    cls, user_region = _team_class_region(teams, user_team)
    template = detect_class_template(teams, cls)
    if not template:
        return []
    regs = _group_class_regions(teams, cls)
    user_list = regs.get(user_region, [])
    if user_team not in user_list:
        return []
    user_idx = user_list.index(user_team)

    locks: List[Tuple[str, str]] = []
    for si, opponent in sorted(picks.items()):
        opp_reg = _opponent_region_for_slot(template, user_region, si)
        if not opp_reg:
            continue
        opp_list = regs.get(opp_reg, [])
        if opponent not in opp_list:
            continue
        # Match _pair_two_regions_week: even index in region_a list is home when r%2==0
        if user_idx % 2 == 0:
            locks.append((user_team, opponent))
        else:
            locks.append((opponent, user_team))
    return locks


def picks_dict_for_state(user_team: str, picks: Dict[int, str]) -> Dict[str, Dict[int, str]]:
    return {user_team: dict(picks)}


def lock_for_pick(
    teams: Dict[str, "Team"],
    user_team: str,
    slot_index: int,
    opponent: str,
) -> Tuple[str, str]:
    """Orient (home, away) for one user cross-region pick."""
    all_locks = locks_for_user_picks(teams, user_team, {slot_index: opponent})
    if not all_locks:
        raise ValueError("Invalid cross-region pick.")
    return all_locks[0]


def locks_for_cross_week(
    teams: Dict[str, "Team"],
    state: Optional[Dict[str, Any]],
    classification: str,
    region_a: str,
    region_b: str,
    slot_index: int,
) -> List[Tuple[str, str]]:
    """Locks for one cross-region week between two regions (user pick only)."""
    if not state:
        return []
    user = str(state.get("user_team") or "").strip()
    if not user:
        return []
    picks_raw = state.get("cross_region_picks") or {}
    user_picks = picks_raw.get(user) if isinstance(picks_raw, dict) else None
    if not isinstance(user_picks, dict):
        return []
    opp = user_picks.get(slot_index) or user_picks.get(str(slot_index))
    if not opp:
        return []
    opp = str(opp).strip()
    cls_u, user_reg = _team_class_region(teams, user)
    cls_o, opp_reg = _team_class_region(teams, opp)
    if cls_u != classification or cls_o != classification:
        return []
    if {user_reg, opp_reg} != {region_a, region_b}:
        return []
    return [lock_for_pick(teams, user, int(slot_index), opp)]


def auto_random_picks(teams: Dict[str, "Team"], user_team: str) -> Dict[int, str]:
    """Bulk autopilot: random eligible opponent per slot."""
    out: Dict[int, str] = {}
    for slot in cross_region_slots_for_team(teams, user_team):
        if slot.eligible_teams:
            out[slot.slot_index] = random.choice(slot.eligible_teams)
    return out
