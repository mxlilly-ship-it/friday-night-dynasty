"""
Game plan creator: spreadsheet-like play call distribution by situation and area.
Each (Situation × Area) cell has 6 categories that must sum to 100%.

Spreadsheet layout:
- Rows = Situations: Base D&D, 3rd & Long, 3rd & Medium, 3rd & Short, High Redzone, Low Redzone, Goal Line.
- Columns = Areas: Backed-Up, Middle Field, High Redzone, Low Redzone, Goal Line.
- Each cell = 6 numbers (Inside Run, Outside Run, Quick Game, Medium Passing, Deep Passing, Play Action Pass) that sum to 100.

Usage:
- Edit data/default_game_plan.json (or a copy) like a spreadsheet: change percentages per situation/area.
- Load with load_game_plan(path) and attach to a coach: coach.game_plan = load_game_plan("data/my_plan.json").
- The play caller uses coach.game_plan when present to pick offensive play categories.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from models.play import OffensivePlayCategory


# ---------- Situations (down & distance context) ----------
SITUATION_BASE_D_D = "Base D&D"
SITUATION_3RD_LONG = "3rd & Long"
SITUATION_3RD_MEDIUM = "3rd & Medium"
SITUATION_3RD_SHORT = "3rd & Short"
SITUATION_HIGH_REDZONE = "High Redzone"
SITUATION_LOW_REDZONE = "Low Redzone"
SITUATION_GOAL_LINE = "Goal Line"

GAME_PLAN_SITUATIONS: List[str] = [
    SITUATION_BASE_D_D,
    SITUATION_3RD_LONG,
    SITUATION_3RD_MEDIUM,
    SITUATION_3RD_SHORT,
    SITUATION_HIGH_REDZONE,
    SITUATION_LOW_REDZONE,
    SITUATION_GOAL_LINE,
]

# ---------- Areas (field position; ball_position 0-100, own goal -> opponent goal) ----------
AREA_BACKED_UP = "Backed-Up"       # own 1-20
AREA_MIDDLE_FIELD = "Middle Field" # own 21 - opp 21
AREA_HIGH_REDZONE = "High Redzone" # opp 20-12
AREA_LOW_REDZONE = "Low Redzone"   # opp 11-4
AREA_GOAL_LINE = "Goal Line"       # opp 3-1

# (min_ball_position, max_ball_position) inclusive for each area
GAME_PLAN_AREAS: Dict[str, Tuple[int, int]] = {
    AREA_BACKED_UP: (1, 20),       # -1 to -20 in “own yard” terms = our 1-20
    AREA_MIDDLE_FIELD: (21, 79),   # -21 to +21
    AREA_HIGH_REDZONE: (80, 88),   # +20 to +12 (opp 20 to 12)
    AREA_LOW_REDZONE: (89, 96),   # +11 to +4
    AREA_GOAL_LINE: (97, 99),      # +3 to +1
}

# ---------- Play categories (must sum to 100 per cell) ----------
CATEGORY_INSIDE_RUN = "Inside Run"
CATEGORY_OUTSIDE_RUN = "Outside Run"
CATEGORY_QUICK_GAME = "Quick Game"
CATEGORY_MEDIUM_PASSING = "Medium Passing"
CATEGORY_DEEP_PASSING = "Deep Passing"
CATEGORY_PLAY_ACTION_PASS = "Play Action Pass"

GAME_PLAN_CATEGORIES: List[str] = [
    CATEGORY_INSIDE_RUN,
    CATEGORY_OUTSIDE_RUN,
    CATEGORY_QUICK_GAME,
    CATEGORY_MEDIUM_PASSING,
    CATEGORY_DEEP_PASSING,
    CATEGORY_PLAY_ACTION_PASS,
]

# Map game plan category -> OffensivePlayCategory for play caller
CATEGORY_TO_OFFENSIVE: Dict[str, OffensivePlayCategory] = {
    CATEGORY_INSIDE_RUN: OffensivePlayCategory.INSIDE_RUN,
    CATEGORY_OUTSIDE_RUN: OffensivePlayCategory.OUTSIDE_RUN,
    CATEGORY_QUICK_GAME: OffensivePlayCategory.SHORT_PASS,
    CATEGORY_MEDIUM_PASSING: OffensivePlayCategory.MEDIUM_PASS,
    CATEGORY_DEEP_PASSING: OffensivePlayCategory.LONG_PASS,
    CATEGORY_PLAY_ACTION_PASS: OffensivePlayCategory.PLAY_ACTION,
}


def resolve_situation(down: int, yards_to_go: int, ball_position: int) -> str:
    """
    Resolve current situation from down, yards_to_go, and ball_position.
    Redzone/goal line situations take precedence when in those areas.
    """
    # Field position overrides: in redzone/goal line, use that situation
    if ball_position >= 97:
        return SITUATION_GOAL_LINE
    if ball_position >= 89:
        return SITUATION_LOW_REDZONE
    if ball_position >= 80:
        return SITUATION_HIGH_REDZONE

    if down == 3:
        if yards_to_go >= 7:
            return SITUATION_3RD_LONG
        if yards_to_go >= 4:
            return SITUATION_3RD_MEDIUM
        return SITUATION_3RD_SHORT

    return SITUATION_BASE_D_D


def resolve_area(ball_position: int) -> str:
    """Resolve current area from ball_position (0-100)."""
    for area, (lo, hi) in GAME_PLAN_AREAS.items():
        if lo <= ball_position <= hi:
            return area
    if ball_position <= 0:
        return AREA_BACKED_UP
    return AREA_GOAL_LINE  # 100 = touchdown


def default_cell() -> Dict[str, int]:
    """Single cell default: roughly balanced (all 6 categories sum to 100)."""
    n = len(GAME_PLAN_CATEGORIES)
    base = 100 // n
    remainder = 100 - base * n
    out = {c: base for c in GAME_PLAN_CATEGORIES}
    for i, c in enumerate(GAME_PLAN_CATEGORIES):
        if i < remainder:
            out[c] += 1
    return out


def make_default_game_plan() -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Build default game plan: every (situation, area) cell = default_cell().
    Structure: plan[situation][area] = { category: pct, ... }
    """
    plan: Dict[str, Dict[str, Dict[str, int]]] = {}
    for situation in GAME_PLAN_SITUATIONS:
        plan[situation] = {}
        for area in GAME_PLAN_AREAS:
            plan[situation][area] = default_cell()
    return plan


def validate_cell(cell: Dict[str, int]) -> Tuple[bool, str]:
    """Return (valid, error_message). Valid if all categories present and sum to 100."""
    if set(cell.keys()) != set(GAME_PLAN_CATEGORIES):
        return False, f"Cell must have exactly: {GAME_PLAN_CATEGORIES}"
    total = sum(cell[c] for c in GAME_PLAN_CATEGORIES)
    if total != 100:
        return False, f"Categories must sum to 100 (got {total})"
    if any(cell[c] < 0 for c in GAME_PLAN_CATEGORIES):
        return False, "Percentages cannot be negative"
    return True, ""


def validate_game_plan(plan: Dict[str, Dict[str, Dict[str, int]]]) -> Tuple[bool, List[str]]:
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


def get_weights_for_cell(cell: Dict[str, int]) -> Dict[OffensivePlayCategory, float]:
    """Convert a game plan cell (category name -> pct) to OffensivePlayCategory -> weight for play caller."""
    out: Dict[OffensivePlayCategory, float] = {}
    for cat_name, oc in CATEGORY_TO_OFFENSIVE.items():
        raw = cell.get(cat_name, 0)
        try:
            p = float(raw)
        except Exception:
            p = 0.0
        out[oc] = max(0.0, p)
    return out


def get_weights_from_game_plan(
    game_plan: Dict[str, Dict[str, Dict[str, int]]],
    down: int,
    yards_to_go: int,
    ball_position: int,
) -> Dict[OffensivePlayCategory, float]:
    """
    Resolve (situation, area) from down/yards_to_go/ball_position and return
    that cell’s weights as OffensivePlayCategory -> float.
    If cell missing or invalid, returns balanced default.
    """
    situation = resolve_situation(down, yards_to_go, ball_position)
    area = resolve_area(ball_position)
    if situation not in game_plan or area not in game_plan[situation]:
        # Balanced fallback
        return get_weights_for_cell(default_cell())
    cell = game_plan[situation][area]
    ok, _ = validate_cell(cell)
    if not ok:
        return get_weights_for_cell(default_cell())
    return get_weights_for_cell(cell)


def save_game_plan(plan: Dict[str, Dict[str, Dict[str, int]]], path: str) -> None:
    """Write game plan to JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)


def load_game_plan(path: str) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Load game plan from JSON. Validates; on error raises ValueError."""
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    ok, errors = validate_game_plan(plan)
    if not ok:
        raise ValueError("Invalid game plan: " + "; ".join(errors))
    return plan
