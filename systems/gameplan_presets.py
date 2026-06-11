"""
Built-in offensive and defensive game plan presets (v2 grid).

Each preset applies a base philosophy, then shifts by score, field area,
and down-and-distance bucket so plans feel situational without hand-editing 280 cells.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from systems.gameplan_v2 import (
    DD_1_10,
    DD_2_1_3,
    DD_2_10P,
    DD_2_3_6,
    DD_2_7_10,
    DD_3_10P,
    DD_3_1_2,
    DD_3_3_6,
    DD_3_7_9,
    DD_4_ANY,
    DD_BUCKETS,
    DEFENSE_CATEGORIES,
    DEF_CAT_MAN,
    DEF_CAT_MAN_PRESSURE,
    DEF_CAT_ZONES,
    DEF_CAT_ZONE_PRESSURE,
    FIELD_AREAS,
    OFFENSE_CATEGORIES,
    SCORE_LEAD_10,
    SCORE_LEAD_3,
    SCORE_LEAD_7,
    SCORE_LOSE_10,
    SCORE_LOSE_3,
    SCORE_LOSE_7,
    SCORE_SITUATIONS,
    SCORE_TIED,
    AREA_BACKED_UP,
    AREA_GOAL_LINE,
    AREA_MIDDLE,
    AREA_REDZONE,
    OFF_CAT_INSIDE,
    OFF_CAT_LONG,
    OFF_CAT_MEDIUM,
    OFF_CAT_OUTSIDE,
    OFF_CAT_PLAY_ACTION,
    OFF_CAT_QUICK,
    validate_plan,
)


PresetMeta = Dict[str, str]

OFFENSIVE_PRESET_DEFINITIONS: List[PresetMeta] = [
    {
        "id": "balanced",
        "name": "Balanced",
        "description": "Even run/pass mix that shifts slightly with score and down & distance.",
    },
    {
        "id": "run_heavy",
        "name": "Run Heavy",
        "description": "Ground-oriented attack — lean run, especially when leading or in short-yardage spots.",
    },
    {
        "id": "spread",
        "name": "Spread / Pass",
        "description": "Spread the field — more quick, medium, and deep throws; run sparingly.",
    },
    {
        "id": "ball_control",
        "name": "Ball Control",
        "description": "Short passing and runs to chew clock — quick game and runs, very little deep.",
    },
]

# Base category weights before situational tweaks (need not sum to 100 yet).
_BASE_PROFILES: Dict[str, Dict[str, int]] = {
    "balanced": {
        OFF_CAT_INSIDE: 18,
        OFF_CAT_OUTSIDE: 17,
        OFF_CAT_QUICK: 18,
        OFF_CAT_MEDIUM: 17,
        OFF_CAT_LONG: 15,
        OFF_CAT_PLAY_ACTION: 15,
    },
    "run_heavy": {
        OFF_CAT_INSIDE: 28,
        OFF_CAT_OUTSIDE: 22,
        OFF_CAT_QUICK: 14,
        OFF_CAT_MEDIUM: 12,
        OFF_CAT_LONG: 8,
        OFF_CAT_PLAY_ACTION: 16,
    },
    "spread": {
        OFF_CAT_INSIDE: 10,
        OFF_CAT_OUTSIDE: 8,
        OFF_CAT_QUICK: 22,
        OFF_CAT_MEDIUM: 26,
        OFF_CAT_LONG: 24,
        OFF_CAT_PLAY_ACTION: 10,
    },
    "ball_control": {
        OFF_CAT_INSIDE: 24,
        OFF_CAT_OUTSIDE: 20,
        OFF_CAT_QUICK: 28,
        OFF_CAT_MEDIUM: 14,
        OFF_CAT_LONG: 4,
        OFF_CAT_PLAY_ACTION: 10,
    },
}


def _shift_categories(categories: List[str], weights: Dict[str, int], changes: Dict[str, int]) -> Dict[str, int]:
    out = {c: int(weights.get(c, 0)) for c in categories}
    for cat, delta in changes.items():
        if cat in out:
            out[cat] += int(delta)
    return out


def _normalize_categories(categories: List[str], weights: Dict[str, int]) -> Dict[str, int]:
    """Convert floating-ish weights to integer percentages summing to 100."""
    floored = {c: max(0, int(weights.get(c, 0))) for c in categories}
    total = sum(floored.values())
    if total <= 0:
        base = 100 // len(categories)
        rem = 100 - base * len(categories)
        out = {c: base for c in categories}
        for i, c in enumerate(categories):
            if i < rem:
                out[c] += 1
        return out
    scaled = {c: max(0, int(round(floored[c] * 100 / total))) for c in categories}
    diff = 100 - sum(scaled.values())
    order = sorted(categories, key=lambda c: scaled[c], reverse=True)
    i = 0
    while diff != 0 and order:
        cat = order[i % len(order)]
        if diff > 0:
            scaled[cat] += 1
            diff -= 1
        elif scaled[cat] > 0:
            scaled[cat] -= 1
            diff += 1
        i += 1
    return scaled


def _shift(weights: Dict[str, int], changes: Dict[str, int]) -> Dict[str, int]:
    return _shift_categories(OFFENSE_CATEGORIES, weights, changes)


def _normalize(weights: Dict[str, int]) -> Dict[str, int]:
    return _normalize_categories(OFFENSE_CATEGORIES, weights)


def _score_adjustments(score_situation: str) -> Dict[str, int]:
    if score_situation == SCORE_LEAD_10:
        return {
            OFF_CAT_INSIDE: 6,
            OFF_CAT_OUTSIDE: 6,
            OFF_CAT_QUICK: -4,
            OFF_CAT_MEDIUM: -4,
            OFF_CAT_LONG: -4,
        }
    if score_situation == SCORE_LEAD_7:
        return {
            OFF_CAT_INSIDE: 4,
            OFF_CAT_OUTSIDE: 4,
            OFF_CAT_QUICK: -2,
            OFF_CAT_MEDIUM: -3,
            OFF_CAT_LONG: -3,
        }
    if score_situation == SCORE_LEAD_3:
        return {
            OFF_CAT_INSIDE: 2,
            OFF_CAT_OUTSIDE: 2,
            OFF_CAT_QUICK: -1,
            OFF_CAT_MEDIUM: -2,
            OFF_CAT_LONG: -1,
        }
    if score_situation == SCORE_LOSE_3:
        return {
            OFF_CAT_INSIDE: -2,
            OFF_CAT_OUTSIDE: -2,
            OFF_CAT_QUICK: 2,
            OFF_CAT_MEDIUM: 2,
        }
    if score_situation == SCORE_LOSE_7:
        return {
            OFF_CAT_INSIDE: -4,
            OFF_CAT_OUTSIDE: -4,
            OFF_CAT_QUICK: 3,
            OFF_CAT_MEDIUM: 3,
            OFF_CAT_LONG: 2,
        }
    if score_situation == SCORE_LOSE_10:
        return {
            OFF_CAT_INSIDE: -5,
            OFF_CAT_OUTSIDE: -5,
            OFF_CAT_QUICK: 4,
            OFF_CAT_MEDIUM: 4,
            OFF_CAT_LONG: 2,
        }
    return {}


def _field_adjustments(field_area: str) -> Dict[str, int]:
    if field_area == AREA_BACKED_UP:
        return {
            OFF_CAT_QUICK: 4,
            OFF_CAT_MEDIUM: 2,
            OFF_CAT_LONG: -6,
        }
    if field_area == AREA_REDZONE:
        return {
            OFF_CAT_INSIDE: 6,
            OFF_CAT_OUTSIDE: 2,
            OFF_CAT_QUICK: 4,
            OFF_CAT_MEDIUM: -4,
            OFF_CAT_LONG: -8,
        }
    if field_area == AREA_GOAL_LINE:
        return {
            OFF_CAT_INSIDE: 12,
            OFF_CAT_OUTSIDE: 4,
            OFF_CAT_QUICK: 2,
            OFF_CAT_MEDIUM: -6,
            OFF_CAT_LONG: -10,
            OFF_CAT_PLAY_ACTION: -2,
        }
    return {}


def _dd_adjustments(dd_bucket: str, preset_id: str) -> Dict[str, int]:
    if dd_bucket == DD_1_10:
        return {}
    if dd_bucket == DD_2_10P:
        return {
            OFF_CAT_MEDIUM: 3,
            OFF_CAT_LONG: 2,
            OFF_CAT_INSIDE: -3,
            OFF_CAT_OUTSIDE: -2,
        }
    if dd_bucket == DD_2_7_10:
        return {
            OFF_CAT_QUICK: 2,
            OFF_CAT_MEDIUM: 2,
            OFF_CAT_INSIDE: -2,
            OFF_CAT_OUTSIDE: -2,
        }
    if dd_bucket == DD_2_3_6:
        return {
            OFF_CAT_INSIDE: 4,
            OFF_CAT_OUTSIDE: 3,
            OFF_CAT_LONG: -3,
            OFF_CAT_MEDIUM: -4,
        }
    if dd_bucket == DD_2_1_3:
        return {
            OFF_CAT_INSIDE: 8,
            OFF_CAT_OUTSIDE: 4,
            OFF_CAT_QUICK: -4,
            OFF_CAT_MEDIUM: -4,
            OFF_CAT_LONG: -4,
        }
    if dd_bucket == DD_3_10P:
        return {
            OFF_CAT_QUICK: 6,
            OFF_CAT_MEDIUM: 6,
            OFF_CAT_LONG: 4,
            OFF_CAT_INSIDE: -8,
            OFF_CAT_OUTSIDE: -8,
        }
    if dd_bucket == DD_3_7_9:
        return {
            OFF_CAT_QUICK: 4,
            OFF_CAT_MEDIUM: 4,
            OFF_CAT_INSIDE: -4,
            OFF_CAT_OUTSIDE: -4,
        }
    if dd_bucket == DD_3_3_6:
        if preset_id == "run_heavy":
            return {
                OFF_CAT_INSIDE: 6,
                OFF_CAT_OUTSIDE: 4,
                OFF_CAT_QUICK: -4,
                OFF_CAT_MEDIUM: -3,
                OFF_CAT_LONG: -3,
            }
        if preset_id == "spread":
            return {
                OFF_CAT_QUICK: 4,
                OFF_CAT_MEDIUM: 3,
                OFF_CAT_INSIDE: -4,
                OFF_CAT_OUTSIDE: -3,
            }
        return {
            OFF_CAT_INSIDE: 3,
            OFF_CAT_OUTSIDE: 2,
            OFF_CAT_QUICK: 2,
            OFF_CAT_MEDIUM: -3,
            OFF_CAT_LONG: -4,
        }
    if dd_bucket == DD_3_1_2:
        return {
            OFF_CAT_INSIDE: 10,
            OFF_CAT_OUTSIDE: 5,
            OFF_CAT_QUICK: -5,
            OFF_CAT_MEDIUM: -5,
            OFF_CAT_LONG: -5,
        }
    if dd_bucket == DD_4_ANY:
        if preset_id in ("spread", "balanced"):
            return {
                OFF_CAT_QUICK: 5,
                OFF_CAT_MEDIUM: 4,
                OFF_CAT_INSIDE: -5,
                OFF_CAT_OUTSIDE: -4,
            }
        if preset_id == "ball_control":
            return {
                OFF_CAT_QUICK: 6,
                OFF_CAT_INSIDE: 2,
                OFF_CAT_LONG: -8,
            }
        return {
            OFF_CAT_INSIDE: 4,
            OFF_CAT_OUTSIDE: 3,
            OFF_CAT_QUICK: 3,
            OFF_CAT_MEDIUM: -4,
            OFF_CAT_LONG: -6,
        }
    return {}


def _build_cell(preset_id: str, score_situation: str, field_area: str, dd_bucket: str) -> Dict[str, int]:
    base = copy.deepcopy(_BASE_PROFILES[preset_id])
    w = base
    for adj in (
        _score_adjustments(score_situation),
        _field_adjustments(field_area),
        _dd_adjustments(dd_bucket, preset_id),
    ):
        w = _shift(w, adj)
    return _normalize(w)


def make_offensive_preset_plan(preset_id: str) -> Dict[str, Dict[str, Dict[str, Dict[str, int]]]]:
    if preset_id not in _BASE_PROFILES:
        raise ValueError(f"Unknown offensive preset: {preset_id}")
    plan: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {}
    for ss in SCORE_SITUATIONS:
        plan[ss] = {}
        for area in FIELD_AREAS:
            plan[ss][area] = {}
            for dd in DD_BUCKETS:
                plan[ss][area][dd] = _build_cell(preset_id, ss, area, dd)
    ok, errs = validate_plan(plan, categories=OFFENSE_CATEGORIES)
    if not ok:
        raise ValueError("Preset failed validation: " + "; ".join(errs[:5]))
    return plan


def list_offensive_preset_catalog() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for meta in OFFENSIVE_PRESET_DEFINITIONS:
        pid = meta["id"]
        out.append(
            {
                **meta,
                "builtin": True,
                "plan": make_offensive_preset_plan(pid),
            }
        )
    return out


def get_offensive_preset_plan(preset_id: str) -> Dict[str, Any]:
    for entry in list_offensive_preset_catalog():
        if entry["id"] == preset_id:
            return copy.deepcopy(entry)
    raise ValueError(f"Unknown offensive preset: {preset_id}")


# ---------- Defensive presets ----------

DEFENSIVE_PRESET_DEFINITIONS: List[PresetMeta] = [
    {
        "id": "balanced",
        "name": "Balanced",
        "description": "Even split across coverages and pressures with light situational shifts.",
    },
    {
        "id": "zone_heavy",
        "name": "Zone Heavy",
        "description": "Bend-don't-break — sit in zones, keep the ball in front, fewer blitz gambles.",
    },
    {
        "id": "bring_pressure",
        "name": "Bring Pressure",
        "description": "Aggressive blitz looks — zone and man pressure to disrupt the quarterback.",
    },
    {
        "id": "man_coverage",
        "name": "Man Coverage",
        "description": "Lock in man coverage and match up on receivers across the field.",
    },
    {
        "id": "man_pressure_heavy",
        "name": "Man Pressure Heavy",
        "description": "Send heat — heavy man pressure with tight man coverage behind it.",
    },
]

_DEF_BASE_PROFILES: Dict[str, Dict[str, int]] = {
    "balanced": {
        DEF_CAT_ZONES: 25,
        DEF_CAT_MAN: 25,
        DEF_CAT_ZONE_PRESSURE: 25,
        DEF_CAT_MAN_PRESSURE: 25,
    },
    "zone_heavy": {
        DEF_CAT_ZONES: 45,
        DEF_CAT_MAN: 25,
        DEF_CAT_ZONE_PRESSURE: 18,
        DEF_CAT_MAN_PRESSURE: 12,
    },
    "bring_pressure": {
        DEF_CAT_ZONES: 20,
        DEF_CAT_MAN: 15,
        DEF_CAT_ZONE_PRESSURE: 35,
        DEF_CAT_MAN_PRESSURE: 30,
    },
    "man_coverage": {
        DEF_CAT_ZONES: 25,
        DEF_CAT_MAN: 40,
        DEF_CAT_ZONE_PRESSURE: 10,
        DEF_CAT_MAN_PRESSURE: 25,
    },
    "man_pressure_heavy": {
        DEF_CAT_ZONES: 10,
        DEF_CAT_MAN: 22,
        DEF_CAT_ZONE_PRESSURE: 8,
        DEF_CAT_MAN_PRESSURE: 60,
    },
}


def _def_score_adjustments(score_situation: str) -> Dict[str, int]:
    if score_situation == SCORE_LEAD_10:
        return {
            DEF_CAT_ZONES: 8,
            DEF_CAT_MAN: 4,
            DEF_CAT_ZONE_PRESSURE: -6,
            DEF_CAT_MAN_PRESSURE: -6,
        }
    if score_situation == SCORE_LEAD_7:
        return {
            DEF_CAT_ZONES: 5,
            DEF_CAT_MAN: 3,
            DEF_CAT_ZONE_PRESSURE: -4,
            DEF_CAT_MAN_PRESSURE: -4,
        }
    if score_situation == SCORE_LEAD_3:
        return {
            DEF_CAT_ZONES: 3,
            DEF_CAT_MAN: 2,
            DEF_CAT_ZONE_PRESSURE: -2,
            DEF_CAT_MAN_PRESSURE: -3,
        }
    if score_situation == SCORE_LOSE_3:
        return {
            DEF_CAT_ZONE_PRESSURE: 3,
            DEF_CAT_MAN_PRESSURE: 3,
            DEF_CAT_ZONES: -2,
            DEF_CAT_MAN: -4,
        }
    if score_situation == SCORE_LOSE_7:
        return {
            DEF_CAT_ZONE_PRESSURE: 5,
            DEF_CAT_MAN_PRESSURE: 5,
            DEF_CAT_ZONES: -3,
            DEF_CAT_MAN: -7,
        }
    if score_situation == SCORE_LOSE_10:
        return {
            DEF_CAT_ZONE_PRESSURE: 6,
            DEF_CAT_MAN_PRESSURE: 6,
            DEF_CAT_ZONES: -4,
            DEF_CAT_MAN: -8,
        }
    return {}


def _def_field_adjustments(field_area: str) -> Dict[str, int]:
    if field_area == AREA_BACKED_UP:
        return {
            DEF_CAT_ZONE_PRESSURE: 4,
            DEF_CAT_MAN_PRESSURE: 3,
            DEF_CAT_ZONES: -4,
            DEF_CAT_MAN: -3,
        }
    if field_area == AREA_REDZONE:
        return {
            DEF_CAT_MAN: 6,
            DEF_CAT_ZONES: 4,
            DEF_CAT_ZONE_PRESSURE: -4,
            DEF_CAT_MAN_PRESSURE: -6,
        }
    if field_area == AREA_GOAL_LINE:
        return {
            DEF_CAT_MAN: 10,
            DEF_CAT_ZONES: 4,
            DEF_CAT_ZONE_PRESSURE: -6,
            DEF_CAT_MAN_PRESSURE: -8,
        }
    return {}


def _def_dd_adjustments(dd_bucket: str, preset_id: str) -> Dict[str, int]:
    if dd_bucket == DD_1_10:
        return {}
    if dd_bucket == DD_2_10P:
        return {
            DEF_CAT_ZONE_PRESSURE: 4,
            DEF_CAT_MAN_PRESSURE: 3,
            DEF_CAT_ZONES: -4,
            DEF_CAT_MAN: -3,
        }
    if dd_bucket == DD_2_7_10:
        return {
            DEF_CAT_ZONE_PRESSURE: 3,
            DEF_CAT_MAN_PRESSURE: 2,
            DEF_CAT_ZONES: -2,
            DEF_CAT_MAN: -3,
        }
    if dd_bucket in (DD_2_3_6, DD_2_1_3):
        return {
            DEF_CAT_MAN: 5,
            DEF_CAT_ZONES: 3,
            DEF_CAT_ZONE_PRESSURE: -4,
            DEF_CAT_MAN_PRESSURE: -4,
        }
    if dd_bucket == DD_3_10P:
        if preset_id == "man_pressure_heavy":
            return {
                DEF_CAT_MAN_PRESSURE: 10,
                DEF_CAT_MAN: 4,
                DEF_CAT_ZONES: -8,
                DEF_CAT_ZONE_PRESSURE: -6,
            }
        return {
            DEF_CAT_ZONES: 6,
            DEF_CAT_ZONE_PRESSURE: 6,
            DEF_CAT_MAN: -4,
            DEF_CAT_MAN_PRESSURE: -8,
        }
    if dd_bucket == DD_3_7_9:
        if preset_id == "man_pressure_heavy":
            return {
                DEF_CAT_MAN_PRESSURE: 8,
                DEF_CAT_MAN: 3,
                DEF_CAT_ZONES: -5,
                DEF_CAT_ZONE_PRESSURE: -6,
            }
        return {
            DEF_CAT_ZONE_PRESSURE: 5,
            DEF_CAT_MAN_PRESSURE: 3,
            DEF_CAT_ZONES: 2,
            DEF_CAT_MAN: -10,
        }
    if dd_bucket == DD_3_3_6:
        if preset_id in ("man_coverage", "man_pressure_heavy"):
            return {
                DEF_CAT_MAN: 6,
                DEF_CAT_MAN_PRESSURE: 4,
                DEF_CAT_ZONES: -5,
                DEF_CAT_ZONE_PRESSURE: -5,
            }
        return {
            DEF_CAT_MAN: 4,
            DEF_CAT_ZONES: 4,
            DEF_CAT_ZONE_PRESSURE: -4,
            DEF_CAT_MAN_PRESSURE: -4,
        }
    if dd_bucket == DD_3_1_2:
        return {
            DEF_CAT_MAN: 8,
            DEF_CAT_ZONES: 4,
            DEF_CAT_ZONE_PRESSURE: -4,
            DEF_CAT_MAN_PRESSURE: -8,
        }
    if dd_bucket == DD_4_ANY:
        if preset_id == "man_pressure_heavy":
            return {
                DEF_CAT_MAN_PRESSURE: 8,
                DEF_CAT_MAN: 2,
                DEF_CAT_ZONES: -5,
                DEF_CAT_ZONE_PRESSURE: -5,
            }
        if preset_id == "bring_pressure":
            return {
                DEF_CAT_ZONE_PRESSURE: 5,
                DEF_CAT_MAN_PRESSURE: 5,
                DEF_CAT_ZONES: -5,
                DEF_CAT_MAN: -5,
            }
        return {
            DEF_CAT_ZONES: 4,
            DEF_CAT_MAN: 3,
            DEF_CAT_ZONE_PRESSURE: 2,
            DEF_CAT_MAN_PRESSURE: -9,
        }
    return {}


def _build_def_cell(preset_id: str, score_situation: str, field_area: str, dd_bucket: str) -> Dict[str, int]:
    base = copy.deepcopy(_DEF_BASE_PROFILES[preset_id])
    w = base
    for adj in (
        _def_score_adjustments(score_situation),
        _def_field_adjustments(field_area),
        _def_dd_adjustments(dd_bucket, preset_id),
    ):
        w = _shift_categories(DEFENSE_CATEGORIES, w, adj)
    return _normalize_categories(DEFENSE_CATEGORIES, w)


def make_defensive_preset_plan(preset_id: str) -> Dict[str, Dict[str, Dict[str, Dict[str, int]]]]:
    if preset_id not in _DEF_BASE_PROFILES:
        raise ValueError(f"Unknown defensive preset: {preset_id}")
    plan: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {}
    for ss in SCORE_SITUATIONS:
        plan[ss] = {}
        for area in FIELD_AREAS:
            plan[ss][area] = {}
            for dd in DD_BUCKETS:
                plan[ss][area][dd] = _build_def_cell(preset_id, ss, area, dd)
    ok, errs = validate_plan(plan, categories=DEFENSE_CATEGORIES)
    if not ok:
        raise ValueError("Defensive preset failed validation: " + "; ".join(errs[:5]))
    return plan


def list_defensive_preset_catalog() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for meta in DEFENSIVE_PRESET_DEFINITIONS:
        pid = meta["id"]
        out.append(
            {
                **meta,
                "builtin": True,
                "plan": make_defensive_preset_plan(pid),
            }
        )
    return out


def get_defensive_preset_plan(preset_id: str) -> Dict[str, Any]:
    for entry in list_defensive_preset_catalog():
        if entry["id"] == preset_id:
            return copy.deepcopy(entry)
    raise ValueError(f"Unknown defensive preset: {preset_id}")
