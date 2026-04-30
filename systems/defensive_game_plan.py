"""
Defensive game plan creator: spreadsheet-like play call distribution by situation and area.
Each (Situation × Area) cell has 4 categories that must sum to 100%.

Spreadsheet layout:
- Rows = Situations: Base D&D, 3rd & Long, 3rd & Medium, 3rd & Short, High Redzone, Low Redzone, Goal Line.
- Columns = Areas: Backed-Up, Middle Field, High Redzone, Low Redzone, Goal Line.
- Each cell = 4 numbers (Zones, Man, Zone Pressure, Man Pressure) that sum to 100.

Usage:
- Edit data/default_defensive_game_plan.json (or a copy) like a spreadsheet.
- Load with load_defensive_game_plan(path) and attach to a coach: coach.defensive_game_plan = load_defensive_game_plan("data/my_defense_plan.json").
- The play caller uses coach.defensive_game_plan when present to pick defensive play categories.
"""

import json
from typing import Dict, List, Tuple

from models.play import DefensivePlayCategory

# Reuse situations and areas from offensive game plan (same grid)
from systems.game_plan import (
    GAME_PLAN_AREAS,
    GAME_PLAN_SITUATIONS,
    resolve_area,
    resolve_situation,
)


# ---------- Defensive play categories (must sum to 100 per cell) ----------
CATEGORY_ZONES = "Zones"
CATEGORY_MAN = "Man"
CATEGORY_ZONE_PRESSURE = "Zone Pressure"
CATEGORY_MAN_PRESSURE = "Man Pressure"

DEFENSIVE_GAME_PLAN_CATEGORIES: List[str] = [
    CATEGORY_ZONES,
    CATEGORY_MAN,
    CATEGORY_ZONE_PRESSURE,
    CATEGORY_MAN_PRESSURE,
]

# Map game plan category -> DefensivePlayCategory for play caller
CATEGORY_TO_DEFENSIVE: Dict[str, DefensivePlayCategory] = {
    CATEGORY_ZONES: DefensivePlayCategory.ZONES,
    CATEGORY_MAN: DefensivePlayCategory.MANS,
    CATEGORY_ZONE_PRESSURE: DefensivePlayCategory.ZONE_PRESSURE,
    CATEGORY_MAN_PRESSURE: DefensivePlayCategory.MAN_PRESSURE,
}


def default_cell() -> Dict[str, int]:
    """Single cell default: 25% each (4 categories sum to 100)."""
    return {c: 25 for c in DEFENSIVE_GAME_PLAN_CATEGORIES}


def make_default_defensive_game_plan() -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Build default defensive game plan: every (situation, area) cell = default_cell().
    Structure: plan[situation][area] = { category: pct, ... }
    """
    plan: Dict[str, Dict[str, Dict[str, int]]] = {}
    for situation in GAME_PLAN_SITUATIONS:
        plan[situation] = {}
        for area in GAME_PLAN_AREAS:
            plan[situation][area] = default_cell()
    return plan


def validate_cell(cell: Dict[str, int]) -> Tuple[bool, str]:
    """Return (valid, error_message). Valid if all 4 categories present and sum to 100."""
    if set(cell.keys()) != set(DEFENSIVE_GAME_PLAN_CATEGORIES):
        return False, f"Cell must have exactly: {DEFENSIVE_GAME_PLAN_CATEGORIES}"
    total = sum(cell[c] for c in DEFENSIVE_GAME_PLAN_CATEGORIES)
    if total != 100:
        return False, f"Categories must sum to 100 (got {total})"
    if any(cell[c] < 0 for c in DEFENSIVE_GAME_PLAN_CATEGORIES):
        return False, "Percentages cannot be negative"
    return True, ""


def validate_defensive_game_plan(
    plan: Dict[str, Dict[str, Dict[str, int]]]
) -> Tuple[bool, List[str]]:
    """Return (all_valid, list of error messages)."""
    errors: List[str] = []
    for situation in GAME_PLAN_SITUATIONS:
        if situation not in plan:
            errors.append(f"Missing situation: {situation}")
            continue
        for area in GAME_PLAN_AREAS:
            if area not in plan[situation]:
                errors.append(f"Missing area {area} for situation {situation}")
                continue
            ok, msg = validate_cell(plan[situation][area])
            if not ok:
                errors.append(f"{situation} / {area}: {msg}")
    return (len(errors) == 0, errors)


def get_weights_for_cell(cell: Dict[str, int]) -> Dict[DefensivePlayCategory, float]:
    """Convert a defensive game plan cell to DefensivePlayCategory -> weight for play caller."""
    out: Dict[DefensivePlayCategory, float] = {}
    for cat_name, dc in CATEGORY_TO_DEFENSIVE.items():
        raw = cell.get(cat_name, 0)
        try:
            p = float(raw)
        except Exception:
            p = 0.0
        out[dc] = max(0.0, p)
    return out


def get_weights_from_defensive_game_plan(
    game_plan: Dict[str, Dict[str, Dict[str, int]]],
    down: int,
    yards_to_go: int,
    ball_position: int,
) -> Dict[DefensivePlayCategory, float]:
    """
    Resolve (situation, area) from down/yards_to_go/ball_position and return
    that cell's weights as DefensivePlayCategory -> float.
    If cell missing or invalid, returns balanced default (25 each).
    """
    situation = resolve_situation(down, yards_to_go, ball_position)
    area = resolve_area(ball_position)
    if situation not in game_plan or area not in game_plan[situation]:
        return get_weights_for_cell(default_cell())
    cell = game_plan[situation][area]
    ok, _ = validate_cell(cell)
    if not ok:
        return get_weights_for_cell(default_cell())
    return get_weights_for_cell(cell)


def save_defensive_game_plan(
    plan: Dict[str, Dict[str, Dict[str, int]]], path: str
) -> None:
    """Write defensive game plan to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)


def load_defensive_game_plan(
    path: str,
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Load defensive game plan from JSON. Validates; on error raises ValueError."""
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    ok, errors = validate_defensive_game_plan(plan)
    if not ok:
        raise ValueError("Invalid defensive game plan: " + "; ".join(errors))
    return plan
