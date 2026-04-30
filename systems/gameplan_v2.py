"""
V2 Coach Gameplan
-----------------
This is the new coach-facing "gameplan file" used by the simulator for play calling.

Dimensions:
- Score situation (Lead/Lose bands)
- Field area (Backed Up / Middle / RedZone / Goal Line)
- Down & distance bucket (rows the coach edits)

Each cell contains category percentages that must sum to 100.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models.play import OffensivePlayCategory, DefensivePlayCategory


# ---------- Score situations ----------
SCORE_LEAD_10 = "Leading by 10+"
SCORE_LEAD_7 = "Leading by 7"
SCORE_LEAD_3 = "Leading by 3"
SCORE_TIED = "Tied"
SCORE_LOSE_3 = "Losing by 3"
SCORE_LOSE_7 = "Losing by 7"
SCORE_LOSE_10 = "Losing by 10+"

SCORE_SITUATIONS: List[str] = [
    SCORE_LEAD_10,
    SCORE_LEAD_7,
    SCORE_LEAD_3,
    SCORE_TIED,
    SCORE_LOSE_3,
    SCORE_LOSE_7,
    SCORE_LOSE_10,
]


def resolve_score_situation(score_for: int, score_against: int) -> str:
    """Return the score band for the team we're planning for (the coach's team)."""
    diff = int(score_for) - int(score_against)
    if diff >= 10:
        return SCORE_LEAD_10
    if diff >= 7:
        return SCORE_LEAD_7
    if diff >= 3:
        return SCORE_LEAD_3
    if diff <= -10:
        return SCORE_LOSE_10
    if diff <= -7:
        return SCORE_LOSE_7
    if diff <= -3:
        return SCORE_LOSE_3
    return SCORE_TIED


# ---------- Field areas (ball_position 0-100; own goal -> opponent goal) ----------
AREA_BACKED_UP = "Backed Up (-20 to -1)"  # own 1-20
AREA_MIDDLE = "Middle of Field (-21 to 21)"  # own 21 - opp 21
AREA_REDZONE = "RedZone (20 to 5)"  # opp 20-6 (see bounds)
AREA_GOAL_LINE = "Goal Line (5 to 1)"  # opp 5-1

FIELD_AREAS: List[str] = [AREA_BACKED_UP, AREA_MIDDLE, AREA_REDZONE, AREA_GOAL_LINE]

# inclusive bounds in ball_position terms
FIELD_AREA_BOUNDS: Dict[str, Tuple[int, int]] = {
    AREA_BACKED_UP: (1, 20),
    AREA_MIDDLE: (21, 79),
    # Opp 20 to 6 => 80 to 94. (Opp 5 to 1 => 95 to 99)
    AREA_REDZONE: (80, 94),
    AREA_GOAL_LINE: (95, 99),
}


def resolve_field_area(ball_position: int) -> str:
    bp = int(ball_position)
    for area, (lo, hi) in FIELD_AREA_BOUNDS.items():
        if lo <= bp <= hi:
            return area
    if bp <= 0:
        return AREA_BACKED_UP
    return AREA_GOAL_LINE


# ---------- Down & distance buckets (rows) ----------
DD_1_10 = "1&10"
DD_2_10P = "2&10+"
DD_2_7_10 = "2&7-10"
DD_2_3_6 = "2&3-6"
DD_2_1_3 = "2&1-3"
DD_3_10P = "3&10+"
DD_3_7_9 = "3&7-9"
DD_3_3_6 = "3&3-6"
DD_3_1_2 = "3&1-2"
DD_4_ANY = "4th"

DD_BUCKETS: List[str] = [
    DD_1_10,
    DD_2_10P,
    DD_2_7_10,
    DD_2_3_6,
    DD_2_1_3,
    DD_3_10P,
    DD_3_7_9,
    DD_3_3_6,
    DD_3_1_2,
    DD_4_ANY,
]


def resolve_dd_bucket(down: int, yards_to_go: int) -> str:
    d = int(down)
    y = int(yards_to_go)
    if d <= 1:
        return DD_1_10
    if d == 2:
        if y >= 10:
            return DD_2_10P
        if y >= 7:
            return DD_2_7_10
        if y >= 3:
            return DD_2_3_6
        return DD_2_1_3
    if d == 3:
        if y >= 10:
            return DD_3_10P
        if y >= 7:
            return DD_3_7_9
        if y >= 3:
            return DD_3_3_6
        return DD_3_1_2
    return DD_4_ANY


# ---------- Categories ----------
OFF_CAT_INSIDE = "Inside Run"
OFF_CAT_OUTSIDE = "Outside Run"
OFF_CAT_QUICK = "Quick"
OFF_CAT_MEDIUM = "Medium"
OFF_CAT_LONG = "Long"
OFF_CAT_PLAY_ACTION = "Play Action"

OFFENSE_CATEGORIES: List[str] = [
    OFF_CAT_INSIDE,
    OFF_CAT_OUTSIDE,
    OFF_CAT_QUICK,
    OFF_CAT_MEDIUM,
    OFF_CAT_LONG,
    OFF_CAT_PLAY_ACTION,
]

OFFENSE_CATEGORY_TO_ENUM: Dict[str, OffensivePlayCategory] = {
    OFF_CAT_INSIDE: OffensivePlayCategory.INSIDE_RUN,
    OFF_CAT_OUTSIDE: OffensivePlayCategory.OUTSIDE_RUN,
    OFF_CAT_QUICK: OffensivePlayCategory.SHORT_PASS,
    OFF_CAT_MEDIUM: OffensivePlayCategory.MEDIUM_PASS,
    OFF_CAT_LONG: OffensivePlayCategory.LONG_PASS,
    OFF_CAT_PLAY_ACTION: OffensivePlayCategory.PLAY_ACTION,
}

DEF_CAT_ZONES = "Zones"
DEF_CAT_MAN = "Man"
DEF_CAT_ZONE_PRESSURE = "Zone Pressure"
DEF_CAT_MAN_PRESSURE = "Man Pressure"

DEFENSE_CATEGORIES: List[str] = [
    DEF_CAT_ZONES,
    DEF_CAT_MAN,
    DEF_CAT_ZONE_PRESSURE,
    DEF_CAT_MAN_PRESSURE,
]

DEFENSE_CATEGORY_TO_ENUM: Dict[str, DefensivePlayCategory] = {
    DEF_CAT_ZONES: DefensivePlayCategory.ZONES,
    DEF_CAT_MAN: DefensivePlayCategory.MANS,
    DEF_CAT_ZONE_PRESSURE: DefensivePlayCategory.ZONE_PRESSURE,
    DEF_CAT_MAN_PRESSURE: DefensivePlayCategory.MAN_PRESSURE,
}


def _default_cell(categories: List[str]) -> Dict[str, int]:
    n = len(categories)
    base = 100 // max(1, n)
    remainder = 100 - base * n
    out = {c: base for c in categories}
    for i, c in enumerate(categories):
        if i < remainder:
            out[c] += 1
    return out


def make_default_offense_plan() -> Dict[str, Dict[str, Dict[str, Dict[str, int]]]]:
    """
    plan[score_situation][field_area][dd_bucket] = {category: pct}
    """
    plan: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {}
    for ss in SCORE_SITUATIONS:
        plan[ss] = {}
        for area in FIELD_AREAS:
            plan[ss][area] = {}
            for dd in DD_BUCKETS:
                plan[ss][area][dd] = _default_cell(OFFENSE_CATEGORIES)
    return plan


def make_default_defense_plan() -> Dict[str, Dict[str, Dict[str, Dict[str, int]]]]:
    plan: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {}
    for ss in SCORE_SITUATIONS:
        plan[ss] = {}
        for area in FIELD_AREAS:
            plan[ss][area] = {}
            for dd in DD_BUCKETS:
                plan[ss][area][dd] = _default_cell(DEFENSE_CATEGORIES)
    return plan


def validate_cell(cell: Dict[str, Any], *, categories: List[str]) -> Tuple[bool, str]:
    if not isinstance(cell, dict):
        return False, "Cell must be an object"
    if set(cell.keys()) != set(categories):
        return False, f"Cell must have exactly: {categories}"
    try:
        total = sum(int(cell[c]) for c in categories)
    except Exception:
        return False, "Cell values must be integers"
    if total != 100:
        return False, f"Categories must sum to 100 (got {total})"
    if any(int(cell[c]) < 0 for c in categories):
        return False, "Percentages cannot be negative"
    return True, ""


def validate_plan(plan: Dict[str, Any], *, categories: List[str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(plan, dict):
        return False, ["Plan must be an object"]
    for ss in SCORE_SITUATIONS:
        if ss not in plan:
            errors.append(f"Missing score situation: {ss}")
            continue
        for area in FIELD_AREAS:
            if area not in plan[ss]:
                errors.append(f"Missing field area {area} for {ss}")
                continue
            for dd in DD_BUCKETS:
                if dd not in plan[ss][area]:
                    errors.append(f"Missing row {dd} for {ss} / {area}")
                    continue
                ok, msg = validate_cell(plan[ss][area][dd], categories=categories)
                if not ok:
                    errors.append(f"{ss} / {area} / {dd}: {msg}")
    return (len(errors) == 0, errors)


def get_offense_weights_from_plan(
    plan: Dict[str, Any],
    *,
    down: int,
    yards_to_go: int,
    ball_position: int,
    score_for: int,
    score_against: int,
) -> Dict[OffensivePlayCategory, float]:
    ss = resolve_score_situation(score_for, score_against)
    area = resolve_field_area(ball_position)
    dd = resolve_dd_bucket(down, yards_to_go)
    try:
        cell = plan[ss][area][dd]
    except Exception:
        cell = _default_cell(OFFENSE_CATEGORIES)
    ok, _ = validate_cell(cell, categories=OFFENSE_CATEGORIES)
    if not ok:
        cell = _default_cell(OFFENSE_CATEGORIES)
    # Always include every category (0% is valid). Callers must not KeyError on missing enums.
    out: Dict[OffensivePlayCategory, float] = {}
    for label, enum_cat in OFFENSE_CATEGORY_TO_ENUM.items():
        raw = cell.get(label, 0)
        try:
            p = float(raw)
        except Exception:
            p = 0.0
        out[enum_cat] = max(0.0, p)
    return out


def get_defense_weights_from_plan(
    plan: Dict[str, Any],
    *,
    down: int,
    yards_to_go: int,
    ball_position: int,
    score_for: int,
    score_against: int,
) -> Dict[DefensivePlayCategory, float]:
    ss = resolve_score_situation(score_for, score_against)
    area = resolve_field_area(ball_position)
    dd = resolve_dd_bucket(down, yards_to_go)
    try:
        cell = plan[ss][area][dd]
    except Exception:
        cell = _default_cell(DEFENSE_CATEGORIES)
    ok, _ = validate_cell(cell, categories=DEFENSE_CATEGORIES)
    if not ok:
        cell = _default_cell(DEFENSE_CATEGORIES)
    out: Dict[DefensivePlayCategory, float] = {}
    for label, enum_cat in DEFENSE_CATEGORY_TO_ENUM.items():
        raw = cell.get(label, 0)
        try:
            p = float(raw)
        except Exception:
            p = 0.0
        out[enum_cat] = max(0.0, p)
    return out

