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


@dataclass
class CrossRegionPick:
    opponent: str
    user_home: Optional[bool] = None


def parse_stored_pick(raw: Any) -> CrossRegionPick:
    """Read a cross-region pick from save state (legacy str or {opponent, user_home})."""
    if isinstance(raw, dict):
        opp = str(raw.get("opponent") or "").strip()
        if "user_home" in raw:
            uh = raw.get("user_home")
            return CrossRegionPick(opp, None if uh is None else bool(uh))
        return CrossRegionPick(opp, None)
    return CrossRegionPick(str(raw or "").strip(), None)


def default_user_home_for_slot(slot_index: int) -> bool:
    """Default home/away when the user has not chosen (even slots home)."""
    return int(slot_index) % 2 == 0


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

    if len(region_names) == 4 and total >= 16:
        sizes_set = set(sizes)
        if not (total == 32 and sizes_set == {8}) and not (total == 40 and sizes_set == {10}):
            return ClassTemplate("4xNx2", classification, region_names, sizes, 2, 8)

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

    if template.template_id == "4xNx2":
        pair_weeks = [
            ((0, 1), (2, 3)),
            ((0, 2), (1, 3)),
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
) -> Dict[int, CrossRegionPick]:
    """Validate and return {slot_index: CrossRegionPick}."""
    slots = cross_region_slots_for_team(teams, user_team)
    if not slots:
        return {}

    by_slot = {s.slot_index: s for s in slots}
    required = set(by_slot.keys())
    if not isinstance(raw_picks, list):
        raise ValueError("Choose an opponent for each out-of-region game.")

    out: Dict[int, CrossRegionPick] = {}
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
        uh_raw = row.get("user_home")
        if uh_raw is None:
            user_home: Optional[bool] = default_user_home_for_slot(si)
        else:
            user_home = bool(uh_raw)
        out[si] = CrossRegionPick(opp, user_home)

    missing = required - set(out.keys())
    if missing:
        first = by_slot[min(missing)]
        raise ValueError(f"Pick an opponent for {first.label}.")
    return out


def bye_week_index_for_team(
    pod: List[str],
    rr_week: List[List[Tuple[str, str]]],
    team: str,
) -> Optional[int]:
    """Week index where ``team`` has its in-region bye, if exactly one bye week exists."""
    found: Optional[int] = None
    for wi, week in enumerate(rr_week):
        playing = {home for home, _away in week} | {away for _home, away in week}
        if team not in playing:
            if found is not None:
                return None
            found = wi
    return found


def build_rr_with_team_bye_on_week(
    pod: List[str],
    team: str,
    target_week: int,
    *,
    seed_base: int = 0,
) -> List[List[Tuple[str, str]]]:
    """Build a pod round-robin where ``team`` has its bye on ``target_week``."""
    from systems.schedule_system import build_weeks_10_game

    if team not in pod:
        return build_weeks_10_game(list(pod), seed=seed_base)
    for seed in range(int(seed_base), int(seed_base) + 500):
        rr = build_weeks_10_game(list(pod), seed=seed)
        if bye_week_index_for_team(pod, rr, team) == target_week:
            return rr
    return build_weeks_10_game(list(pod), seed=seed_base)


def align_4x7_slot0_bye_weeks(
    regs_list: List[List[str]],
    rr_weeks: List[List[List[Tuple[str, str]]]],
    teams: Dict[str, "Team"],
    state: Optional[Dict[str, Any]],
    classification: str,
) -> Optional[int]:
    """
    For 4x7x4 slot 0, rebuild opponent pod schedules so picked opponents share
    each team's bye week. Returns the last opponent region index rebuilt, if any.
    """
    if not state:
        return None
    last_opp_ri: Optional[int] = None
    for team_name in cross_region_pick_team_names(state):
        opp_ri = _align_4x7_slot0_bye_week_for_team(
            regs_list,
            rr_weeks,
            teams,
            state,
            classification,
            team_name,
        )
        if opp_ri is not None:
            last_opp_ri = opp_ri
    return last_opp_ri


def _align_4x7_slot0_bye_week_for_team(
    regs_list: List[List[str]],
    rr_weeks: List[List[List[Tuple[str, str]]]],
    teams: Dict[str, "Team"],
    state: Optional[Dict[str, Any]],
    classification: str,
    team_name: str,
) -> Optional[int]:
    user = str(team_name or "").strip()
    if not user or user not in teams:
        return None
    picks_raw = state.get("cross_region_picks") or {}
    user_picks = picks_raw.get(user) if isinstance(picks_raw, dict) else None
    if not isinstance(user_picks, dict):
        return None
    raw = user_picks.get(0)
    if raw is None:
        raw = user_picks.get("0")
    pick = parse_stored_pick(raw)
    if not pick.opponent or pick.opponent not in teams:
        return None

    cls_u, user_reg = _team_class_region(teams, user)
    if cls_u != classification:
        return None
    template = detect_class_template(teams, cls_u)
    if not template or template.template_id != "4x7x4":
        return None
    opp_reg = _opponent_region_for_slot(template, user_reg, 0)
    if not opp_reg:
        return None
    try:
        user_ri = template.region_names.index(user_reg)
        opp_ri = template.region_names.index(opp_reg)
    except ValueError:
        return None

    opponent = pick.opponent
    user_pod = regs_list[user_ri]
    opp_pod = regs_list[opp_ri]
    user_bye_wi = bye_week_index_for_team(user_pod, rr_weeks[user_ri], user)
    if user_bye_wi is None:
        return None
    if bye_week_index_for_team(opp_pod, rr_weeks[opp_ri], opponent) == user_bye_wi:
        return None

    seed_base = hash((user, opponent, user_bye_wi, classification)) % (2**31)
    rr_weeks[opp_ri] = build_rr_with_team_bye_on_week(
        opp_pod,
        opponent,
        user_bye_wi,
        seed_base=seed_base,
    )
    return opp_ri


def locks_for_bye_teams(
    locks: List[Tuple[str, str]],
    bye_a: str,
    bye_b: str,
) -> List[Tuple[str, str]]:
    """Keep only locks that match the two bye teams in this slot-0 week."""
    pair = frozenset({bye_a, bye_b})
    out: List[Tuple[str, str]] = []
    for home, away in locks:
        if frozenset({home, away}) == pair:
            out.append((home, away))
    return out


def pair_two_regions_with_locks(
    region_a: List[str],
    region_b: List[str],
    offset: int,
    locks: List[Tuple[str, str]],
    ha_counts: Optional[Dict[str, Dict[str, int]]] = None,
) -> List[Tuple[str, str]]:
    """
    1:1 pairings between two regions. ``locks`` are oriented (home, away) edges that must appear.
    Remaining teams paired with home/away balanced when ``ha_counts`` is provided.
    """
    from systems.schedule_system import pick_home_away, record_home_away

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
            # Lock does not apply to this pairing pool (e.g. slot-0 bye week mismatch).
            continue
        if ha_counts is not None:
            record_home_away(games[-1][0], games[-1][1], ha_counts)

    n = min(len(a_rem), len(b_rem))
    if len(a_rem) != len(b_rem):
        raise ValueError("Cross-region pairing could not balance remaining teams.")
    for i in range(n):
        t1 = a_rem[i]
        t2 = b_rem[(i + offset) % n] if n else b_rem[0]
        if ha_counts is not None:
            games.append(pick_home_away(t1, t2, ha_counts))
        else:
            home, away = t1, t2
            if i % 2 == 1:
                home, away = away, home
            games.append((home, away))
    return games


def _orient_user_pick(
    user_team: str,
    opponent: str,
    pick: CrossRegionPick,
    *,
    user_list: List[str],
    ha_counts: Optional[Dict[str, Dict[str, int]]] = None,
) -> Tuple[str, str]:
    from systems.schedule_system import pick_home_away

    if pick.user_home is True:
        return user_team, opponent
    if pick.user_home is False:
        return opponent, user_team
    if ha_counts is not None:
        return pick_home_away(user_team, opponent, ha_counts)
    if user_list.index(user_team) % 2 == 0:
        return user_team, opponent
    return opponent, user_team


def locks_for_user_picks(
    teams: Dict[str, "Team"],
    user_team: str,
    picks: Dict[int, CrossRegionPick],
    ha_counts: Optional[Dict[str, Dict[str, int]]] = None,
) -> List[Tuple[str, str]]:
    """Convert user slot picks to (home, away) locks."""
    cls, user_region = _team_class_region(teams, user_team)
    template = detect_class_template(teams, cls)
    if not template:
        return []
    regs = _group_class_regions(teams, cls)
    user_list = regs.get(user_region, [])
    if user_team not in user_list:
        return []

    locks: List[Tuple[str, str]] = []
    for si, pick in sorted(picks.items()):
        opponent = pick.opponent
        opp_reg = _opponent_region_for_slot(template, user_region, si)
        if not opp_reg:
            continue
        opp_list = regs.get(opp_reg, [])
        if opponent not in opp_list:
            continue
        locks.append(
            _orient_user_pick(
                user_team,
                opponent,
                pick,
                user_list=user_list,
                ha_counts=ha_counts,
            )
        )
    return locks


def picks_dict_for_state(user_team: str, picks: Dict[int, CrossRegionPick]) -> Dict[str, Dict[int, Any]]:
    return {
        user_team: {
            si: {"opponent": p.opponent, "user_home": p.user_home}
            for si, p in picks.items()
        }
    }


def cross_region_pick_team_names(state: Optional[Dict[str, Any]]) -> List[str]:
    """Teams with stored out-of-region picks (multiplayer uses every entry; SP may set user_team)."""
    if not state:
        return []
    picks_raw = state.get("cross_region_picks") or {}
    if not isinstance(picks_raw, dict):
        picks_raw = {}
    names: List[str] = []
    user = str(state.get("user_team") or "").strip()
    if user:
        names.append(user)
    for tn in picks_raw:
        s = str(tn).strip()
        if s and s not in names:
            names.append(s)
    return names


def lock_for_pick(
    teams: Dict[str, "Team"],
    user_team: str,
    slot_index: int,
    opponent: str,
    ha_counts: Optional[Dict[str, Dict[str, int]]] = None,
    *,
    user_home: Optional[bool] = None,
) -> Tuple[str, str]:
    """Orient (home, away) for one user cross-region pick."""
    pick = CrossRegionPick(opponent, user_home)
    all_locks = locks_for_user_picks(teams, user_team, {slot_index: pick}, ha_counts)
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
    """Locks for one cross-region week between two regions (all stored picks in this slot)."""
    if not state:
        return []
    picks_raw = state.get("cross_region_picks") or {}
    if not isinstance(picks_raw, dict):
        return []

    locks: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for team_name in cross_region_pick_team_names(state):
        user_picks = picks_raw.get(team_name)
        if not isinstance(user_picks, dict):
            continue
        raw = user_picks.get(slot_index) or user_picks.get(str(slot_index))
        if not raw:
            continue
        pick = parse_stored_pick(raw)
        if not pick.opponent:
            continue
        cls_u, user_reg = _team_class_region(teams, team_name)
        cls_o, opp_reg = _team_class_region(teams, pick.opponent)
        if cls_u != classification or cls_o != classification:
            continue
        if {user_reg, opp_reg} != {region_a, region_b}:
            continue
        try:
            edge = lock_for_pick(
                teams,
                team_name,
                int(slot_index),
                pick.opponent,
                user_home=pick.user_home,
            )
        except ValueError:
            continue
        key = (edge[0], edge[1])
        rev = (edge[1], edge[0])
        if key in seen or rev in seen:
            continue
        seen.add(key)
        locks.append(edge)
    return locks


def auto_random_picks(teams: Dict[str, "Team"], user_team: str) -> Dict[int, CrossRegionPick]:
    """Bulk autopilot: random eligible opponent per slot with alternating home/away."""
    out: Dict[int, CrossRegionPick] = {}
    for slot in cross_region_slots_for_team(teams, user_team):
        if slot.eligible_teams:
            out[slot.slot_index] = CrossRegionPick(
                random.choice(slot.eligible_teams),
                default_user_home_for_slot(slot.slot_index),
            )
    return out
