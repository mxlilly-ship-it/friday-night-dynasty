"""
Coaching Card System — program identity, position, and platinum cards.

Defines HOW teams develop (tradeoffs, specialization). Integrates with
systems.development_system for offseason / winter / spring gains and
potential-ceiling breakthroughs.

CP purchase costs integrate with systems.coach_development (unified CP pool).
"""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

if TYPE_CHECKING:
    from models.coach import Coach
    from models.player import Player
    from models.team import Team

# ---------------------------------------------------------------------------
# Loadout limits
# ---------------------------------------------------------------------------
MAX_PROGRAM_IDENTITY = 1
MAX_POSITION_CARDS = 3
MAX_PLATINUM_CARDS = 2

POSITION_GROUPS: Dict[str, Set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "OL": {"OL"},
    "DL": {"DE", "DT"},
    "LB": {"LB"},
    "DB": {"CB", "S"},
    "SKILL": {"QB", "RB", "WR", "TE"},
    "FRONT7": {"DE", "DT", "LB"},
}

CARD_DEV_MULTIPLIER_CAP = 2.5

PLATINUM_REQUIRES: Dict[str, str] = {
    "platinum_qb_whisperer": "qb_whisperer",
    "platinum_ol_guru": "ol_guru",
    "platinum_rb_stable": "rb_stable",
    "platinum_wr_technician": "wr_technician",
    "platinum_te_mismatch": "te_mismatch",
    "platinum_air_attack": "air_attack",
    "platinum_ground_and_pound": "ground_and_pound",
    "platinum_dl_factory": "dl_factory",
    "platinum_linebacker_core": "linebacker_core",
    "platinum_db_ballhawks": "db_ballhawks",
    "platinum_run_stop_unit": "run_stop_unit",
    "platinum_coverage_shell": "coverage_shell",
}

EMPTY_LOADOUT: Dict[str, Any] = {
    "program_identity": None,
    "position": [],
    "platinum": [],
}


@dataclass(frozen=True)
class CardDef:
    id: str
    name: str
    layer: str  # program | position | platinum
    group: str  # UI theme: offense | line | skill | defense | identity
    accent: str
    ability: str
    tradeoff: str
    primary_groups: Tuple[str, ...] = ()
    requires: Optional[str] = None


def _card(
    id: str,
    name: str,
    layer: str,
    group: str,
    accent: str,
    ability: str,
    tradeoff: str,
    primary_groups: Tuple[str, ...] = (),
    requires: Optional[str] = None,
) -> CardDef:
    return CardDef(
        id=id,
        name=name,
        layer=layer,
        group=group,
        accent=accent,
        ability=ability,
        tradeoff=tradeoff,
        primary_groups=primary_groups,
        requires=requires,
    )


PROGRAM_IDENTITY_CARDS: Dict[str, CardDef] = {
    k: v
    for k, v in {
        "ceiling_raiser": _card(
            "ceiling_raiser",
            "Ceiling Raiser",
            "program",
            "identity",
            "#8B5CF6",
            "+12% potential cap; JR/SR dev +5% faster",
            "FR/SO development speed −6%",
        ),
        "developer": _card(
            "developer",
            "Developer",
            "program",
            "identity",
            "#22C55E",
            "All players develop +12% faster",
            "Program potential cap −8% for all players",
        ),
        "player_factory": _card(
            "player_factory",
            "Player Factory",
            "program",
            "identity",
            "#F59E0B",
            "80+ OVR players develop +22% faster",
            "Sub-70 OVR players develop −15% slower",
        ),
        "late_bloomer_developer": _card(
            "late_bloomer_developer",
            "Late Bloomer Developer",
            "program",
            "identity",
            "#A78BFA",
            "JR/SR development +35% faster",
            "FR/SO development −20% slower",
        ),
        "high_floor_program": _card(
            "high_floor_program",
            "High Floor Program",
            "program",
            "identity",
            "#38BDF8",
            "Sub-70 OVR: minimum +12% dev speed",
            "85+ OVR development −12%",
        ),
        "boom_or_bust": _card(
            "boom_or_bust",
            "Boom or Bust",
            "program",
            "identity",
            "#EF4444",
            "8% chance of +10–15 dev spike; boom adds potential",
            "~5% chance of reduced or zero development",
        ),
        "underdog_engine": _card(
            "underdog_engine",
            "Underdog Engine",
            "program",
            "identity",
            "#14B8A6",
            "Sub-72 OVR dev +22%; 5% potential bump chance",
            "80+ OVR dev slows; growth stalls above 85",
        ),
        "elite_standard": _card(
            "elite_standard",
            "Elite Standard",
            "program",
            "identity",
            "#EAB308",
            "88+ OVR dev +18%; 5% potential bump chance",
            "Sub-70 OVR development −10%",
        ),
        "from_the_bottom_up": _card(
            "from_the_bottom_up",
            "From the Bottom Up",
            "program",
            "identity",
            "#6366F1",
            "FR under-75 potential: +12% potential & +8% dev",
            "High-potential FR/SO: −12% development rate",
        ),
    }.items()
}

POSITION_CARDS: Dict[str, CardDef] = {
    k: v
    for k, v in {
        "qb_whisperer": _card(
            "qb_whisperer",
            "QB Whisperer",
            "position",
            "offense",
            "#3B82F6",
            "QB dev +28%; +2% potential per offseason",
            "OL dev −10%",
            primary_groups=("QB",),
        ),
        "ol_guru": _card(
            "ol_guru",
            "OL Guru",
            "position",
            "line",
            "#78716C",
            "OL dev +28%; +2.5% potential per offseason",
            "Skill positions −8%",
            primary_groups=("OL",),
        ),
        "rb_stable": _card(
            "rb_stable",
            "RB Stable",
            "position",
            "skill",
            "#84CC16",
            "RB dev +24%; +2% potential per offseason",
            "OL dev −8%",
            primary_groups=("RB",),
        ),
        "wr_technician": _card(
            "wr_technician",
            "WR Technician",
            "position",
            "skill",
            "#06B6D4",
            "WR dev +26%; +2.5% potential per offseason",
            "RB dev −8%",
            primary_groups=("WR",),
        ),
        "te_mismatch": _card(
            "te_mismatch",
            "TE Mismatch",
            "position",
            "skill",
            "#8B5CF6",
            "TE dev +28%; WR dev +12%; +4% TE potential per offseason",
            "RB dev −8%",
            primary_groups=("TE", "WR"),
        ),
        "air_attack": _card(
            "air_attack",
            "Air Attack",
            "position",
            "offense",
            "#0EA5E9",
            "QB + WR dev +18%; +2% potential per offseason",
            "OL dev −8%",
            primary_groups=("QB", "WR"),
        ),
        "ground_and_pound": _card(
            "ground_and_pound",
            "Ground & Pound",
            "position",
            "line",
            "#B45309",
            "RB + OL dev +20%; +2% potential per offseason",
            "QB/WR dev −12%",
            primary_groups=("RB", "OL"),
        ),
        "dl_factory": _card(
            "dl_factory",
            "DL Factory",
            "position",
            "defense",
            "#DC2626",
            "DL dev +28%; +2% potential per offseason",
            "LB dev −8%",
            primary_groups=("DL",),
        ),
        "linebacker_core": _card(
            "linebacker_core",
            "Linebacker Core",
            "position",
            "defense",
            "#F97316",
            "LB dev +28%; +3% potential per offseason",
            "DB dev −8%",
            primary_groups=("LB",),
        ),
        "db_ballhawks": _card(
            "db_ballhawks",
            "DB Ballhawks",
            "position",
            "defense",
            "#10B981",
            "DB dev +28%; +2% potential per offseason",
            "DL dev −8%",
            primary_groups=("DB",),
        ),
        "run_stop_unit": _card(
            "run_stop_unit",
            "Run Stop Unit",
            "position",
            "defense",
            "#57534E",
            "Front 7 dev +22%; +3% potential per offseason",
            "DB dev −8%",
            primary_groups=("FRONT7",),
        ),
        "coverage_shell": _card(
            "coverage_shell",
            "Coverage Shell",
            "position",
            "defense",
            "#2563EB",
            "DB dev +28%; +2% potential per offseason",
            "DL dev −8%",
            primary_groups=("DB",),
        ),
    }.items()
}

PLATINUM_CARDS: Dict[str, CardDef] = {
    pid: _card(
        pid,
        f"Platinum {POSITION_CARDS[base].name}",
        "platinum",
        POSITION_CARDS[base].group,
        "#E5E7EB",
        "5–12% offseason breakthrough chance near potential cap",
        "Requires base position card; ceiling-only (no speed boost)",
        primary_groups=POSITION_CARDS[base].primary_groups,
        requires=base,
    )
    for pid, base in PLATINUM_REQUIRES.items()
}

ALL_CARDS: Dict[str, CardDef] = {
    **PROGRAM_IDENTITY_CARDS,
    **POSITION_CARDS,
    **PLATINUM_CARDS,
}


def card_catalog_for_api() -> List[Dict[str, Any]]:
    """Serializable catalog for frontend."""
    out: List[Dict[str, Any]] = []
    for c in ALL_CARDS.values():
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "layer": c.layer,
                "group": c.group,
                "accent": c.accent,
                "ability": c.ability,
                "tradeoff": c.tradeoff,
                "primary_groups": list(c.primary_groups),
                "requires": c.requires,
            }
        )
    return out


def normalize_loadout(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return deepcopy(EMPTY_LOADOUT)
    pid = raw.get("program_identity")
    pid = str(pid).strip() if pid else None
    if pid and pid not in PROGRAM_IDENTITY_CARDS:
        pid = None
    pos: List[str] = []
    for x in raw.get("position") or []:
        s = str(x).strip()
        if s in POSITION_CARDS and s not in pos:
            pos.append(s)
    plat: List[str] = []
    for x in raw.get("platinum") or []:
        s = str(x).strip()
        if s in PLATINUM_CARDS and s not in plat:
            plat.append(s)
    return {"program_identity": pid, "position": pos[:MAX_POSITION_CARDS], "platinum": plat[:MAX_PLATINUM_CARDS]}


def get_coach_loadout(coach: Optional["Coach"]) -> Dict[str, Any]:
    if coach is None:
        return deepcopy(EMPTY_LOADOUT)
    raw = getattr(coach, "coaching_cards", None)
    return normalize_loadout(raw if isinstance(raw, dict) else None)


def validate_loadout(loadout: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    lo = normalize_loadout(loadout)
    if lo["program_identity"] and lo["program_identity"] not in PROGRAM_IDENTITY_CARDS:
        errors.append("Invalid program identity card.")
    if len(lo["position"]) > MAX_POSITION_CARDS:
        errors.append(f"Maximum {MAX_POSITION_CARDS} position cards.")
    if len(lo["platinum"]) > MAX_PLATINUM_CARDS:
        errors.append(f"Maximum {MAX_PLATINUM_CARDS} platinum cards.")
    pos_set = set(lo["position"])
    for p in lo["platinum"]:
        req = PLATINUM_REQUIRES.get(p)
        if not req:
            errors.append(f"Unknown platinum card: {p}")
        elif req not in pos_set:
            errors.append(f"Platinum {p} requires base card {req}.")
    return (len(errors) == 0, errors)


def _player_positions(player: "Player") -> Set[str]:
    out: Set[str] = set()
    for raw in (getattr(player, "position", None), getattr(player, "secondary_position", None)):
        p = str(raw or "").strip().upper()
        if p:
            out.add(p)
    return out


def _player_in_group(player: "Player", group_key: str) -> bool:
    codes = _player_positions(player)
    if group_key in codes:
        return True
    g = POSITION_GROUPS.get(group_key, set())
    return bool(codes & g)


def _year_band(player: "Player") -> str:
    y = getattr(player, "year", None)
    if y is None:
        age = int(getattr(player, "age", 15) or 15)
        y = min(12, max(9, 9 + max(0, age - 14)))
    y = int(y)
    if y <= 10:
        return "FR_SO"
    return "JR_SR"


def _player_ovr(player: "Player") -> int:
    try:
        from systems.team_ratings import calculate_player_overall

        return int(calculate_player_overall(player))
    except Exception:
        return 50


def effective_potential_cap(player: "Player", coach: Optional["Coach"]) -> int:
    """Potential ceiling after program identity modifiers."""
    base = int(getattr(player, "potential", 50) or 50)
    lo = get_coach_loadout(coach)
    pid = lo.get("program_identity")
    mult = 1.0
    if pid == "ceiling_raiser":
        mult *= 1.12
    elif pid == "developer":
        mult *= 0.92
    return max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, int(round(base * mult))))


def _position_dev_modifiers(loadout: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    """
    Per position-group (dev_multiplier, potential_pct_per_year).
    Diminishing returns: second card hitting same primary group gets 0.75× on dev boost.
    """
    mods: Dict[str, Tuple[float, float]] = {}
    hit_count: Dict[str, int] = {}

    def bump(group: str, dev_delta: float, pot_pct: float) -> None:
        n = hit_count.get(group, 0)
        if n <= 0:
            scale = 1.0
        elif n == 1:
            scale = 0.75
        else:
            scale = 0.50
        hit_count[group] = n + 1
        cur_d, cur_p = mods.get(group, (0.0, 0.0))
        mods[group] = (cur_d + dev_delta * scale, cur_p + pot_pct * scale)

    for cid in loadout.get("position") or []:
        if cid == "qb_whisperer":
            bump("QB", 0.28, 0.02)
            bump("OL", -0.10, 0.0)
        elif cid == "ol_guru":
            bump("OL", 0.28, 0.025)
            for g in ("QB", "RB", "WR", "TE"):
                bump(g, -0.08, 0.0)
        elif cid == "rb_stable":
            bump("RB", 0.24, 0.02)
            bump("OL", -0.08, 0.0)
        elif cid == "wr_technician":
            bump("WR", 0.26, 0.025)
            bump("RB", -0.08, 0.0)
        elif cid == "te_mismatch":
            bump("TE", 0.28, 0.04)
            bump("WR", 0.12, 0.0)
            bump("RB", -0.08, 0.0)
        elif cid == "air_attack":
            bump("QB", 0.18, 0.02)
            bump("WR", 0.18, 0.02)
            bump("OL", -0.08, 0.0)
        elif cid == "ground_and_pound":
            bump("RB", 0.20, 0.02)
            bump("OL", 0.20, 0.02)
            bump("QB", -0.12, 0.0)
            bump("WR", -0.12, 0.0)
        elif cid == "dl_factory":
            bump("DL", 0.28, 0.02)
            bump("LB", -0.08, 0.0)
        elif cid == "linebacker_core":
            bump("LB", 0.28, 0.03)
            bump("DB", -0.08, 0.0)
        elif cid == "db_ballhawks":
            bump("DB", 0.28, 0.02)
            bump("DL", -0.08, 0.0)
        elif cid == "run_stop_unit":
            bump("FRONT7", 0.22, 0.03)
            bump("DB", -0.08, 0.0)
        elif cid == "coverage_shell":
            bump("DB", 0.28, 0.02)
            bump("DL", -0.08, 0.0)
    return mods


def _group_dev_multiplier(player: "Player", loadout: Dict[str, Any]) -> float:
    mods = _position_dev_modifiers(loadout)
    mult = 1.0
    for gkey, (dev_d, _) in mods.items():
        if _player_in_group(player, gkey):
            mult *= 1.0 + dev_d
    return max(0.25, mult)


def _identity_dev_multiplier(player: "Player", coach: Optional["Coach"], loadout: Dict[str, Any]) -> float:
    pid = loadout.get("program_identity")
    if not pid:
        return 1.0
    ovr = _player_ovr(player)
    band = _year_band(player)
    pot = int(getattr(player, "potential", 50) or 50)
    mult = 1.0

    if pid == "developer":
        mult *= 1.12
    elif pid == "player_factory":
        if ovr >= 80:
            mult *= 1.22
        elif ovr < 70:
            mult *= 0.85
    elif pid == "late_bloomer_developer":
        if band == "JR_SR":
            mult *= 1.35
        else:
            mult *= 0.80
    elif pid == "ceiling_raiser":
        if band == "FR_SO":
            mult *= 0.94
        else:
            mult *= 1.05
    elif pid == "high_floor_program":
        if ovr < 70:
            mult = max(mult, 1.12)
        elif ovr >= 85:
            mult *= 0.88
    elif pid == "underdog_engine":
        if ovr < 72:
            mult *= 1.22
        elif ovr >= 85:
            mult *= 0.20
        elif ovr >= 80:
            mult *= 0.80
    elif pid == "elite_standard":
        if ovr >= 88:
            mult *= 1.18
        elif ovr < 70:
            mult *= 0.90
    elif pid == "from_the_bottom_up":
        if band == "FR_SO" and pot < 75:
            mult *= 1.08
        elif band == "FR_SO" and pot >= 75:
            mult *= 0.88

    return max(0.1, mult)


def coaching_card_dev_multiplier(
    player: "Player",
    team: "Team",
    *,
    phase: str = "offseason",
) -> float:
    """Combined dev speed multiplier for one development pass."""
    coach = getattr(team, "coach", None)
    loadout = get_coach_loadout(coach)
    identity_mult = _identity_dev_multiplier(player, coach, loadout)
    position_mult = _group_dev_multiplier(player, loadout)
    if loadout.get("program_identity") in ("developer", "high_floor_program"):
        position_mult = 1.0 + (position_mult - 1.0) * 0.85
    m = identity_mult * position_mult

    return max(0.05, min(CARD_DEV_MULTIPLIER_CAP, m))


def roll_boom_or_bust_outcome(player: "Player", team: "Team") -> Optional[str]:
    """Returns 'boom', 'bust', or None for this offseason pass."""
    loadout = get_coach_loadout(getattr(team, "coach", None))
    if loadout.get("program_identity") != "boom_or_bust":
        return None
    r = random.random()
    if r < 0.08:
        return "boom"
    if r < 0.13:
        return "bust"
    return None


def apply_boom_or_bust_gain(base_gain: int, outcome: Optional[str]) -> int:
    if outcome == "boom":
        return base_gain + random.randint(10, 15)
    if outcome == "bust":
        if base_gain <= 0:
            return 0
        return max(0, int(round(base_gain * 0.5)))
    return base_gain


def apply_offseason_card_extras(team: "Team") -> Dict[str, Any]:
    """
    After Training Results: yearly potential bumps, identity pot rolls, platinum breakthroughs.
    """
    coach = getattr(team, "coach", None)
    loadout = get_coach_loadout(coach)
    pos_mods = _position_dev_modifiers(loadout)
    reports: List[Dict[str, Any]] = []

    for player in list(team.roster):
        if not getattr(player, "potential", None):
            continue
        before_pot = int(player.potential)
        ovr = _player_ovr(player)
        band = _year_band(player)

        # Position card yearly potential %
        pot_bump = 0.0
        for gkey, (_, pot_pct) in pos_mods.items():
            if pot_pct > 0 and _player_in_group(player, gkey):
                pot_bump += pot_pct
        if pot_bump > 0:
            inc = max(1, int(round(before_pot * pot_bump)))
            player.potential = min(RATING_ATTR_MAX, before_pot + inc)

        # Identity: small potential roll chances
        pid = loadout.get("program_identity")
        if pid in ("boom_or_bust", "underdog_engine", "elite_standard") and random.random() < 0.05:
            if pid == "underdog_engine" and ovr >= 72:
                pass
            elif pid == "elite_standard" and ovr < 88:
                pass
            else:
                player.potential = min(RATING_ATTR_MAX, int(player.potential) + random.randint(2, 5))

        if pid == "boom_or_bust" and random.random() < 0.08:
            player.potential = min(RATING_ATTR_MAX, int(player.potential) + random.randint(3, 5))

        if pid == "from_the_bottom_up" and band == "FR_SO" and before_pot < 75:
            inc = max(1, int(round(before_pot * 0.12)))
            player.potential = min(RATING_ATTR_MAX, int(player.potential) + inc)

        # Platinum breakthrough
        cap = effective_potential_cap(player, coach)
        gap = cap - ovr
        if 0 <= gap <= 12:
            chance = 0.0
            for plat_id in loadout.get("platinum") or []:
                base = PLATINUM_REQUIRES.get(plat_id)
                if not base:
                    continue
                card = POSITION_CARDS.get(base)
                if not card:
                    continue
                if any(_player_in_group(player, g) for g in card.primary_groups):
                    chance += random.uniform(0.08, 0.12)
            chance = min(0.40, chance)
            if chance > 0 and random.random() < chance:
                inc = random.randint(3, 6)
                player.potential = min(RATING_ATTR_MAX, int(player.potential) + inc)
                reports.append(
                    {
                        "player": getattr(player, "name", "?"),
                        "type": "platinum_breakthrough",
                        "potential_gain": inc,
                    }
                )

        if int(player.potential) != before_pot:
            reports.append(
                {
                    "player": getattr(player, "name", "?"),
                    "type": "potential_change",
                    "before": before_pot,
                    "after": int(player.potential),
                }
            )

    return {"events": reports}


# ---------------------------------------------------------------------------
# CP costs (unified coach development pool)
# ---------------------------------------------------------------------------
CARD_REFUND_RATE = 0.5

IDENTITY_EQUIP_COST: Dict[str, int] = {
    "boom_or_bust": 28,
    "from_the_bottom_up": 28,
    "ceiling_raiser": 38,
    "elite_standard": 38,
    "player_factory": 38,
    "developer": 48,
    "high_floor_program": 48,
    "underdog_engine": 48,
    "late_bloomer_developer": 48,
}

IDENTITY_SWAP_FEE: Dict[str, int] = {
    "boom_or_bust": 12,
    "from_the_bottom_up": 12,
    "ceiling_raiser": 16,
    "elite_standard": 16,
    "player_factory": 16,
    "developer": 20,
    "high_floor_program": 20,
    "underdog_engine": 20,
    "late_bloomer_developer": 20,
}

POSITION_EQUIP_COST: Dict[str, int] = {
    "qb_whisperer": 32,
    "ol_guru": 32,
    "dl_factory": 32,
    "linebacker_core": 32,
    "air_attack": 28,
    "ground_and_pound": 28,
    "rb_stable": 24,
    "wr_technician": 24,
    "te_mismatch": 24,
    "db_ballhawks": 24,
    "run_stop_unit": 20,
    "coverage_shell": 20,
}

PLATINUM_EQUIP_COST = 36


def loadout_card_ids(loadout: Optional[Dict[str, Any]]) -> List[str]:
    lo = normalize_loadout(loadout)
    ids: List[str] = []
    if lo.get("program_identity"):
        ids.append(str(lo["program_identity"]))
    ids.extend(list(lo.get("position") or []))
    ids.extend(list(lo.get("platinum") or []))
    return ids


def card_equip_cost(card_id: str) -> int:
    cid = str(card_id or "").strip()
    if cid in PROGRAM_IDENTITY_CARDS:
        return int(IDENTITY_EQUIP_COST.get(cid, 38))
    if cid in POSITION_CARDS:
        return int(POSITION_EQUIP_COST.get(cid, 24))
    if cid in PLATINUM_CARDS:
        return PLATINUM_EQUIP_COST
    return 0


def identity_swap_fee(identity_id: Optional[str]) -> int:
    if not identity_id:
        return 0
    return int(IDENTITY_SWAP_FEE.get(str(identity_id), 16))


def compute_loadout_equip_cost(loadout: Optional[Dict[str, Any]]) -> float:
    return float(sum(card_equip_cost(cid) for cid in loadout_card_ids(loadout)))


def compute_loadout_change_cp(
    old_loadout: Optional[Dict[str, Any]],
    new_loadout: Optional[Dict[str, Any]],
    ledger: Optional[Dict[str, float]] = None,
) -> Tuple[float, Dict[str, float], Dict[str, Any]]:
    """
    Net CP to deduct from bank when switching loadouts.
    Returns (net_cost, new_ledger, detail).
  """
    old = normalize_loadout(old_loadout)
    new = normalize_loadout(new_loadout)
    paid = {str(k): max(0.0, float(v or 0.0)) for k, v in (ledger or {}).items()}

    old_ids = set(loadout_card_ids(old))
    new_ids = set(loadout_card_ids(new))
    refunds: Dict[str, float] = {}
    charges: Dict[str, float] = {}

    for cid in sorted(old_ids - new_ids):
        amount = paid.get(cid, float(card_equip_cost(cid)))
        refunds[cid] = round(amount * CARD_REFUND_RATE, 1)

    new_ledger: Dict[str, float] = {}
    for cid in sorted(old_ids & new_ids):
        new_ledger[cid] = paid.get(cid, float(card_equip_cost(cid)))

    for cid in sorted(new_ids - old_ids):
        cost = float(card_equip_cost(cid))
        charges[cid] = cost
        new_ledger[cid] = cost

    swap_fee = 0.0
    old_id = old.get("program_identity")
    new_id = new.get("program_identity")
    if old_id and new_id and old_id != new_id:
        swap_fee = float(identity_swap_fee(new_id))

    refund_total = sum(refunds.values())
    charge_total = sum(charges.values()) + swap_fee
    net_cost = round(charge_total - refund_total, 1)

    detail = {
        "refunds": refunds,
        "charges": charges,
        "identity_swap_fee": swap_fee,
        "refund_total": round(refund_total, 1),
        "charge_total": round(charge_total, 1),
        "net_cost": net_cost,
    }
    return net_cost, new_ledger, detail


def card_cp_costs_for_api() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for cid in PROGRAM_IDENTITY_CARDS:
        out[cid] = card_equip_cost(cid)
    for cid in POSITION_CARDS:
        out[cid] = card_equip_cost(cid)
    for cid in PLATINUM_CARDS:
        out[cid] = card_equip_cost(cid)
    return out


def ai_select_coaching_cards(coach: Optional["Coach"], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """CPU coaches pick a viable specialized loadout."""
    lo = normalize_loadout(existing)
    if lo["program_identity"] and lo["position"]:
        ok, _ = validate_loadout(lo)
        if ok:
            return lo

    identity = random.choice(list(PROGRAM_IDENTITY_CARDS.keys()))
    # Bias toward rebuild-friendly identities for low-rated coaches
    dev = int(getattr(coach, "player_development", 5) or 5) if coach else 5
    if dev >= 7:
        identity = random.choice(["player_factory", "elite_standard", "ceiling_raiser", identity])

    pools = [
        ["qb_whisperer", "air_attack", "wr_technician"],
        ["ground_and_pound", "ol_guru", "rb_stable"],
        ["dl_factory", "linebacker_core", "run_stop_unit"],
        ["db_ballhawks", "coverage_shell", "linebacker_core"],
    ]
    chosen_pool = random.choice(pools)
    n_pos = random.randint(1, MAX_POSITION_CARDS)
    position = chosen_pool[:n_pos]
    platinum: List[str] = []
    if position and random.random() < 0.45:
        base = random.choice(position)
        plat_id = f"platinum_{base}"
        if plat_id in PLATINUM_CARDS:
            platinum.append(plat_id)
    out = normalize_loadout({"program_identity": identity, "position": position, "platinum": platinum})
    ok, _ = validate_loadout(out)
    return out if ok else deepcopy(EMPTY_LOADOUT)


def apply_loadout_to_coach(coach: "Coach", loadout: Dict[str, Any]) -> None:
    lo = normalize_loadout(loadout)
    ok, errs = validate_loadout(lo)
    if not ok:
        raise ValueError("; ".join(errs))
    coach.coaching_cards = lo
