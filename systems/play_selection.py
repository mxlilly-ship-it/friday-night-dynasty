"""
Season play selection: coaches pick which plays to teach for the upcoming season.
Runs in offseason after Schedule Release. Better scheme_teach = can teach more plays well;
too many plays + low teaching + low player football_iq/coachability = poor understanding grade.
Players with better understanding get a small execution boost; poor understanding = small penalty.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from models.play import OffensivePlayCategory, DefensivePlayCategory

# Offensive categories (must sum to 100% per category)
OFFENSIVE_CATEGORIES = [
    OffensivePlayCategory.INSIDE_RUN,
    OffensivePlayCategory.OUTSIDE_RUN,
    OffensivePlayCategory.SHORT_PASS,   # Quick Game
    OffensivePlayCategory.MEDIUM_PASS,  # Medium Passing
    OffensivePlayCategory.LONG_PASS,    # Deep Pass
    OffensivePlayCategory.PLAY_ACTION,
]

# Defensive categories (must sum to 100% per category)
DEFENSIVE_CATEGORIES = [
    DefensivePlayCategory.ZONES,        # Zone Coverage
    DefensivePlayCategory.MANS,         # Man Coverage
    DefensivePlayCategory.ZONE_PRESSURE,
    DefensivePlayCategory.MAN_PRESSURE,
]

# Letter grades for player understanding (A+ down to F-)
UNDERSTANDING_GRADES = [
    "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F+", "F", "F-",
]

# Score thresholds: index 0 = A+ (93+), ..., index -1 = F- (0-52). Ranges [lo, hi] for each grade.
UNDERSTANDING_SCORE_BANDS = [
    (93, 100),   # A+
    (90, 92),    # A
    (87, 89),    # A-
    (83, 86),    # B+
    (80, 82),    # B
    (77, 79),    # B-
    (73, 76),    # C+
    (70, 72),    # C
    (67, 69),    # C-
    (63, 66),    # D+
    (60, 62),    # D
    (57, 59),    # D-
    (53, 56),    # F+
    (50, 52),    # F
    (0, 49),     # F-
]


def _plays_per_category_from_scheme_teach(scheme_teach: int) -> int:
    """
    How many plays per category the coach can teach effectively (1-10 scale).
    Larger defensive playbooks make install selective: cap stays modest even for elite teachers.
    """
    # scheme_teach 1 -> 2, 10 -> 6 (was up to 10) — forces prioritization each preseason.
    n = 2 + (scheme_teach - 1) * 4 // 9
    return max(2, min(6, n))


def _build_playbook(team: Any) -> Any:
    """Build team playbook from coach formation choices."""
    from systems.playbook_system import build_playbook_for_team
    return build_playbook_for_team(team)


def run_play_selection_for_team(team: Any) -> Dict[str, Any]:
    """
    Play Selection phase: coach selects plays for the season.

    Each category is worth 100%. Within each category, the coach selects specific plays
    and the percentages assigned to those plays must sum to 100% for that category.
    Example: Inside Run (100%) = FB Trap 40%, Iso 35%, Dive 25%. Outside Run (100%) =
    Power G 50%, Toss 30%, Counter 20%. So it's plays-within-category that sum to 100%,
    not categories summing to 100 overall.

    Uses coach.scheme_teach to decide how many plays per category can be taught.
    Auto-picks that many plays per category and assigns equal % so each category's
    selected plays sum to 100%. Selection is locked for the season.

    Sets team.season_offensive_play_selection and team.season_defensive_play_selection.
    Returns summary for logging/UI.
    """
    coach = getattr(team, "coach", None)
    scheme_teach = getattr(coach, "scheme_teach", 5) if coach else 5
    scheme_teach = max(1, min(10, scheme_teach))

    pb = _build_playbook(team)
    off_selection: Dict[str, List[Tuple[str, float]]] = {}
    def_selection: Dict[str, List[Tuple[str, float]]] = {}

    # Per category: selected plays' percentages sum to 100% for that category only.
    n_off = _plays_per_category_from_scheme_teach(scheme_teach)
    for cat in OFFENSIVE_CATEGORIES:
        plays = pb.get_offensive_plays_by_category(cat)
        if not plays:
            off_selection[cat.name] = []
            continue
        chosen = plays[: n_off]
        pct_each = 100.0 / len(chosen) if chosen else 0.0  # this category's 100% split across chosen plays
        off_selection[cat.name] = [(p.id, pct_each) for p in chosen]

    n_def = _plays_per_category_from_scheme_teach(scheme_teach)
    for cat in DEFENSIVE_CATEGORIES:
        plays = pb.get_defensive_plays_by_category(cat)
        if not plays:
            def_selection[cat.name] = []
            continue
        # Sample so expanded playbooks (Nickel/Dime/6-2/etc.) are not always starved after base-front plays.
        k = min(n_def, len(plays))
        chosen = random.sample(plays, k)
        pct_each = 100.0 / len(chosen) if chosen else 0.0  # this category's 100% split across chosen plays
        def_selection[cat.name] = [(p.id, pct_each) for p in chosen]

    team.season_offensive_play_selection = off_selection
    team.season_defensive_play_selection = def_selection

    total_off = sum(len(v) for v in off_selection.values())
    total_def = sum(len(v) for v in def_selection.values())
    return {
        "offensive_selection": off_selection,
        "defensive_selection": def_selection,
        "plays_per_category_off": n_off,
        "plays_per_category_def": n_def,
        "total_offensive_plays": total_off,
        "total_defensive_plays": total_def,
    }


def _roster_avg_football_iq_and_coachability(team: Any) -> Tuple[float, float]:
    """Return (avg football_iq, avg coachability) for roster (1-100 scale). Empty roster = 50, 50."""
    roster = getattr(team, "roster", []) or []
    if not roster:
        return 50.0, 50.0
    iq = sum(getattr(p, "football_iq", 50) for p in roster) / len(roster)
    coach = sum(getattr(p, "coachability", 50) for p in roster) / len(roster)
    return float(iq), float(coach)


def compute_understanding_grade(
    team: Any,
    off_selection: Optional[Dict[str, List[Tuple[str, float]]]] = None,
    def_selection: Optional[Dict[str, List[Tuple[str, float]]]] = None,
) -> str:
    """
    Compute player understanding grade (A+ to F-) from:
    - Coach scheme_teach (ability to teach schemes)
    - Roster avg football_iq and coachability
    - Number of plays selected (too many plays + low teaching/iq = bad grade)

    High scheme_teach + high iq/coachability + few plays per category -> A+.
    Low scheme_teach + low iq/coachability + many plays -> F-.
    """
    off_selection = off_selection or getattr(team, "season_offensive_play_selection", None) or {}
    def_selection = def_selection or getattr(team, "season_defensive_play_selection", None) or {}

    coach = getattr(team, "coach", None)
    scheme_teach = getattr(coach, "scheme_teach", 5) if coach else 5
    scheme_teach = max(1, min(10, scheme_teach))

    avg_iq, avg_coach = _roster_avg_football_iq_and_coachability(team)
    # Teaching capacity: 0-100 scale. scheme_teach 1-10 -> 10-100; iq and coachability 1-100.
    teaching_score = (scheme_teach * 10 + avg_iq + avg_coach) / 3.0
    teaching_score = max(0, min(100, teaching_score))

    # How many plays can they effectively teach per category? 2 to 10 based on teaching_score.
    teachable_per_cat = 2 + (teaching_score / 100.0) * 8.0

    # Actual load: average plays per category (off has 6 categories, def has 4).
    num_off_cats = max(1, len([k for k, v in off_selection.items() if v]))
    num_def_cats = max(1, len([k for k, v in def_selection.items() if v]))
    total_off_plays = sum(len(v) for v in off_selection.values())
    total_def_plays = sum(len(v) for v in def_selection.values())
    avg_off_per_cat = total_off_plays / num_off_cats if num_off_cats else 0
    avg_def_per_cat = total_def_plays / num_def_cats if num_def_cats else 0
    avg_plays_per_cat = (avg_off_per_cat + avg_def_per_cat) / 2.0 if (num_off_cats or num_def_cats) else 0

    # Overload: ratio of selected plays per category to teachable. >1 = overloaded.
    if teachable_per_cat <= 0:
        overload = 2.0
    else:
        overload = avg_plays_per_cat / teachable_per_cat

    # Understanding score 0-100: low overload + high teaching = high score.
    # overload 0.5 -> bonus; 1.0 -> neutral; 1.5+ -> penalty
    raw_score = 100.0 - (overload - 0.7) * 45.0  # 0.7 overload -> 100; 2.0 -> 41.5
    understanding_score = max(0, min(100, raw_score))

    # Map to letter grade
    for i, (lo, hi) in enumerate(UNDERSTANDING_SCORE_BANDS):
        if lo <= understanding_score <= hi:
            return UNDERSTANDING_GRADES[i]
    return "F-"


def compute_learning_summary(team: Any) -> Dict[str, Any]:
    """
    Per-side "percent learned" (0–100) from teaching capacity vs plays-per-category load,
    plus overall letter grade (same formula as compute_understanding_grade).

    Used on the Play Selection Results screen before/after the phase runs; values match
    the engine's understanding model split by offense vs defense workload.
    """
    off_selection = getattr(team, "season_offensive_play_selection", None) or {}
    def_selection = getattr(team, "season_defensive_play_selection", None) or {}

    coach = getattr(team, "coach", None)
    scheme_teach = getattr(coach, "scheme_teach", 5) if coach else 5
    scheme_teach = max(1, min(10, scheme_teach))

    avg_iq, avg_coach = _roster_avg_football_iq_and_coachability(team)
    teaching_score = (scheme_teach * 10 + avg_iq + avg_coach) / 3.0
    teaching_score = max(0, min(100, teaching_score))
    teachable_per_cat = 2 + (teaching_score / 100.0) * 8.0

    def _side_learning_pct(selection: Dict[str, List[Tuple[str, float]]]) -> float:
        num_cats = max(1, len([k for k, v in selection.items() if v]))
        total_plays = sum(len(v) for v in selection.values())
        avg_per_cat = total_plays / num_cats if num_cats else 0.0
        if teachable_per_cat <= 0:
            return 0.0
        overload = avg_per_cat / teachable_per_cat
        raw_score = 100.0 - (overload - 0.7) * 45.0
        return max(0.0, min(100.0, raw_score))

    off_pct = round(_side_learning_pct(off_selection))
    def_pct = round(_side_learning_pct(def_selection))
    grade = compute_understanding_grade(team, off_selection, def_selection)

    return {
        "offensive_pct_learned": int(off_pct),
        "defensive_pct_learned": int(def_pct),
        "overall_grade": grade,
    }


def run_play_selection_results_for_team(team: Any) -> Dict[str, Any]:
    """
    Play Selection Results phase: compute and store player understanding grade.
    Requires team.season_offensive_play_selection and season_defensive_play_selection
    to already be set (by run_play_selection_for_team).

    Sets team.season_play_understanding_grade (A+ to F-).
    Returns summary for logging/UI.
    """
    grade = compute_understanding_grade(team)
    team.season_play_understanding_grade = grade
    return {
        "grade": grade,
        "offensive_plays": sum(len(v) for v in (team.season_offensive_play_selection or {}).values()),
        "defensive_plays": sum(len(v) for v in (team.season_defensive_play_selection or {}).values()),
    }


def get_understanding_modifier(grade: Optional[str]) -> float:
    """
    Return a multiplier for play execution based on understanding grade.
    A+ -> small boost (1.03); F- -> small penalty (0.97). None or unknown -> 1.0.
    """
    if not grade:
        return 1.0
    try:
        idx = UNDERSTANDING_GRADES.index(grade)
        # 0 (A+) -> 1.03, 7 (C) -> 1.0, 14 (F-) -> 0.97
        return round(1.03 - (idx / 14.0) * 0.06, 3)
    except ValueError:
        return 1.0
