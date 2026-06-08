"""
Parse program equipment catalog text effects and apply training bonuses at Training Results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from models.player import RATING_ATTR_MAX, RATING_ATTR_MIN

from systems.program_development_system import (
    _PP_POINTS_RE,
    catalog_item,
    ensure_team_program_fields,
    load_equipment_catalog,
)

MENTAL_ATTRIBUTES: Tuple[str, ...] = (
    "toughness",
    "effort",
    "football_iq",
    "coachability",
    "confidence",
    "discipline",
    "leadership",
    "composure",
)

POS_LINEMAN: FrozenSet[str] = frozenset({"OL", "TE"})
POS_QB: FrozenSet[str] = frozenset({"QB"})
POS_RECEIVING: FrozenSet[str] = frozenset({"WR", "TE", "RB"})
POS_PASS_RUSH: FrozenSet[str] = frozenset({"DE", "LB"})
POS_FRONT_SEVEN: FrozenSet[str] = frozenset({"DE", "DT", "LB"})
POS_DEFENSE: FrozenSet[str] = frozenset({"DE", "DT", "LB", "CB", "S"})
POS_KICKER: FrozenSet[str] = frozenset({"K"})

_PLUS_CLAUSE_RE = re.compile(
    r"plus\s+(\d+)\s+(.+?)(?:\s+for\s+(linemen?|qbs?))?\s*$",
    re.IGNORECASE,
)

# (phrase fragments, attribute key, default positions when no "for X" suffix)
_ATTR_PHRASES: List[Tuple[Tuple[str, ...], str, Optional[FrozenSet[str]]]] = [
    (("all run block", "run block", "run blocking"), "run_blocking", POS_LINEMAN),
    (("block shed",), "block_shedding", POS_FRONT_SEVEN),
    (("throw accuracy", "throwing accuracy"), "throw_accuracy", POS_QB),
    (("pass rush",), "pass_rush", POS_PASS_RUSH),
    (("rush defense",), "run_defense", POS_FRONT_SEVEN),
    (("tackling",), "tackling", POS_DEFENSE),
    (("catching",), "catching", POS_RECEIVING),
    (("kick accuracy",), "kick_accuracy", POS_KICKER),
    (("football iq",), "football_iq", None),
    (("coachability",), "coachability", None),
    (("composure",), "composure", None),
    (("confidence",), "confidence", None),
    (("effort",), "effort", None),
    (("discipline",), "discipline", None),
    (("toughness",), "toughness", None),
    (("leadership",), "leadership", None),
    (("speed",), "speed", None),
    (("agility",), "agility", None),
    (("acceleration",), "acceleration", None),
    (("strength",), "strength", None),
    (("balance",), "balance", None),
    (("jumping",), "jumping", None),
]


@dataclass
class EquipmentTrainingEffect:
    attr: str
    value: int
    positions: Optional[FrozenSet[str]] = None
    source_item_id: str = ""
    source_name: str = ""


def _strip_pp_from_text(text: str) -> str:
    cleaned = _PP_POINTS_RE.sub("", text or "")
    return cleaned.strip(" ,+")


def _position_set_from_suffix(suffix: Optional[str]) -> Optional[FrozenSet[str]]:
    if not suffix:
        return None
    s = suffix.strip().lower()
    if s in ("lineman", "linemen"):
        return POS_LINEMAN
    if s in ("qb", "qbs"):
        return POS_QB
    return None


def _resolve_phrase(phrase: str, value: int, suffix_positions: Optional[FrozenSet[str]]) -> List[Tuple[str, int, Optional[FrozenSet[str]]]]:
    """Return list of (attr, value, positions)."""
    p = (phrase or "").strip().lower()
    p = p.replace("accelartion", "acceleration")

    if "all mentals" in p:
        return [("__all_mentals__", value, None)]

    parts = re.split(r",|\s+and\s+", p) if ("," in p or " and " in p) else [p]
    out: List[Tuple[str, int, Optional[FrozenSet[str]]]] = []
    for part in parts:
        fragment = part.strip()
        if not fragment:
            continue
        matched = False
        for keys, attr, default_pos in _ATTR_PHRASES:
            if any(k in fragment for k in keys):
                pos = suffix_positions if suffix_positions is not None else default_pos
                out.append((attr, value, pos))
                matched = True
                break
        if not matched and fragment:
            # Unknown fragment — skip silently (PP-only clauses already stripped)
            pass
    return out


def parse_training_effects_from_lines(lines: Optional[List[Any]]) -> List[EquipmentTrainingEffect]:
    """Parse catalog ``attributes_affected`` into structured training effects (excludes PP)."""
    effects: List[EquipmentTrainingEffect] = []
    for raw_line in lines or []:
        text = _strip_pp_from_text(str(raw_line or ""))
        if not text:
            continue
        for segment in re.split(r"[,+]", text):
            segment = segment.strip()
            if not segment:
                continue
            m = _PLUS_CLAUSE_RE.match(segment)
            if not m:
                continue
            value = int(m.group(1))
            phrase = m.group(2).strip()
            suffix = m.group(3)
            suffix_pos = _position_set_from_suffix(suffix)
            for attr, val, positions in _resolve_phrase(phrase, value, suffix_pos):
                effects.append(EquipmentTrainingEffect(attr=attr, value=val, positions=positions))
    return effects


def aggregate_equipment_training_effects(
    team: Any,
    catalog: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Sum training effects from active owned equipment.
    Returns {effects, by_item, total_bonus_points, pp_grant} — pp_grant is informational only here.
    """
    ensure_team_program_fields(team)
    cat = catalog or load_equipment_catalog()
    merged: List[EquipmentTrainingEffect] = []
    by_item: List[Dict[str, Any]] = []

    for row in getattr(team, "program_equipment", []) or []:
        if not isinstance(row, dict):
            continue
        if float(row.get("seasons_remaining", 0) or 0) <= 0:
            continue
        iid = str(row.get("item_id") or row.get("id") or "").strip()
        if not iid:
            continue
        spec = catalog_item(iid, cat)
        if not spec:
            continue
        lines = spec.get("attributes_affected") or []
        item_effects = parse_training_effects_from_lines(lines)
        if not item_effects:
            continue
        name = str(spec.get("name") or iid)
        tagged = [
            EquipmentTrainingEffect(
                attr=e.attr,
                value=e.value,
                positions=e.positions,
                source_item_id=iid,
                source_name=name,
            )
            for e in item_effects
        ]
        merged.extend(tagged)
        by_item.append(
            {
                "item_id": iid,
                "name": name,
                "effects": [{"attr": e.attr, "value": e.value, "positions": sorted(e.positions) if e.positions else None} for e in item_effects],
            }
        )

    return {
        "effects": merged,
        "by_item": by_item,
        "item_count": len(by_item),
    }


def _player_matches_positions(player: Any, positions: Optional[FrozenSet[str]]) -> bool:
    if not positions:
        return True
    pos = str(getattr(player, "position", "") or "").strip().upper()
    sec = str(getattr(player, "secondary_position", "") or "").strip().upper()
    if pos in positions:
        return True
    if sec and sec in positions:
        return True
    return False


def _apply_flat_attr_boost(player: Any, attr: str, value: int) -> int:
    """Apply flat bonus capped by potential room. Returns points actually added."""
    if value <= 0 or not hasattr(player, attr):
        return 0
    current = int(getattr(player, attr, 50) or 50)
    potential = int(getattr(player, "potential", 100) or 100)
    room = max(0, potential - current)
    gain = min(int(value), room)
    if gain <= 0:
        return 0
    new_val = max(RATING_ATTR_MIN, min(RATING_ATTR_MAX, current + gain))
    setattr(player, attr, new_val)
    return new_val - current


def apply_equipment_training_bonuses_to_player(
    player: Any,
    effects: List[EquipmentTrainingEffect],
) -> int:
    """Apply aggregated equipment effects to one player after normal development."""
    total, _ = apply_equipment_training_bonuses_to_player_detailed(player, effects)
    return total


def apply_equipment_training_bonuses_to_player_detailed(
    player: Any,
    effects: List[EquipmentTrainingEffect],
) -> Tuple[int, Dict[str, int]]:
    """Apply equipment effects; return (total points, per-attribute equipment gains)."""
    total = 0
    per_attr: Dict[str, int] = {}
    for eff in effects:
        if not _player_matches_positions(player, eff.positions):
            continue
        if eff.attr == "__all_mentals__":
            for mental in MENTAL_ATTRIBUTES:
                gain = _apply_flat_attr_boost(player, mental, eff.value)
                if gain > 0:
                    per_attr[mental] = per_attr.get(mental, 0) + gain
                    total += gain
        else:
            gain = _apply_flat_attr_boost(player, eff.attr, eff.value)
            if gain > 0:
                per_attr[eff.attr] = per_attr.get(eff.attr, 0) + gain
                total += gain
    return total, per_attr


def summarize_equipment_for_training_ui(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compact rows for UI: item name + human label."""
    rows: List[Dict[str, Any]] = []
    for block in summary.get("by_item") or []:
        if not isinstance(block, dict):
            continue
        parts: List[str] = []
        for e in block.get("effects") or []:
            if not isinstance(e, dict):
                continue
            attr = str(e.get("attr") or "")
            val = int(e.get("value") or 0)
            pos = e.get("positions")
            if attr == "__all_mentals__":
                label = f"+{val} all mentals"
            else:
                label = f"+{val} {attr.replace('_', ' ')}"
            if pos:
                label += f" ({', '.join(pos)})"
            parts.append(label)
        if parts:
            rows.append({"name": block.get("name") or block.get("item_id"), "labels": parts})
    return rows
