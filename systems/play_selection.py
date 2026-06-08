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

# Plays at or below this pct are treated as not installed (UI lists full playbook; only active plays count).
ACTIVE_PLAY_PCT_THRESHOLD = 0.01

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


def is_active_play_pct(pct: float) -> bool:
    """True when a play is part of the season install (non-zero weight)."""
    try:
        return float(pct) > ACTIVE_PLAY_PCT_THRESHOLD
    except (TypeError, ValueError):
        return False


def filter_active_play_entries(
    entries: List[Tuple[str, float]],
) -> List[Tuple[str, float]]:
    """Keep only plays with meaningful call weight."""
    out: List[Tuple[str, float]] = []
    for play_id, pct in entries or []:
        try:
            p = float(pct)
        except (TypeError, ValueError):
            continue
        if is_active_play_pct(p):
            out.append((str(play_id), p))
    return out


def normalize_selection_for_storage(
    selection: Optional[Dict[str, List[Tuple[str, float]]]],
) -> Dict[str, List[Tuple[str, float]]]:
    """Drop 0% plays so grading and sim only see the installed package."""
    if not selection:
        return {}
    out: Dict[str, List[Tuple[str, float]]] = {}
    for cat, entries in selection.items():
        active = filter_active_play_entries(entries or [])
        if active:
            out[str(cat)] = active
    return out


def normalize_game_plan_payload_for_storage(
    offensive: Optional[Dict[str, Any]],
    defensive: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, List[Tuple[str, float]]], Dict[str, List[Tuple[str, float]]]]:
    """Convert UI game-plan dicts to stored season selection (active plays only)."""

    def _from_payload(side: Optional[Dict[str, Any]]) -> Dict[str, List[Tuple[str, float]]]:
        if not isinstance(side, dict):
            return {}
        raw: Dict[str, List[Tuple[str, float]]] = {}
        for cat, entries in side.items():
            if not entries:
                continue
            rows: List[Tuple[str, float]] = []
            for e in entries:
                if not isinstance(e, dict):
                    continue
                play_id = e.get("play_id")
                if not play_id:
                    continue
                try:
                    pct = float(e.get("pct", 0))
                except (TypeError, ValueError):
                    continue
                rows.append((str(play_id), pct))
            active = filter_active_play_entries(rows)
            if active:
                raw[str(cat)] = active
        return raw

    return _from_payload(offensive), _from_payload(defensive)


def _active_plays_per_category(selection: Dict[str, List[Tuple[str, float]]]) -> float:
    """Average count of active (non-zero pct) plays per populated category."""
    counts = [len(filter_active_play_entries(v)) for v in selection.values() if v]
    if not counts:
        return 0.0
    return sum(counts) / len(counts)


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

    off_selection = normalize_selection_for_storage(off_selection)
    def_selection = normalize_selection_for_storage(def_selection)

    # Actual load: average active plays per category (off has 6 categories, def has 4).
    off_cats = [v for v in off_selection.values() if filter_active_play_entries(v)]
    def_cats = [v for v in def_selection.values() if filter_active_play_entries(v)]
    avg_off_per_cat = _active_plays_per_category(off_selection) if off_cats else 0.0
    avg_def_per_cat = _active_plays_per_category(def_selection) if def_cats else 0.0
    if off_cats and def_cats:
        avg_plays_per_cat = (avg_off_per_cat + avg_def_per_cat) / 2.0
    elif off_cats:
        avg_plays_per_cat = avg_off_per_cat
    elif def_cats:
        avg_plays_per_cat = avg_def_per_cat
    else:
        avg_plays_per_cat = 0.0

    # Overload: ratio of selected plays per category to teachable. >1 = overloaded.
    if teachable_per_cat <= 0:
        overload = 2.0
    else:
        overload = avg_plays_per_cat / teachable_per_cat

    # Understanding score 0-100: low overload + high teaching = high score.
    understanding_score = _understanding_score_from_overload(overload)
    return _score_to_grade(understanding_score)


def _understanding_score_from_overload(overload: float) -> float:
    raw_score = 100.0 - (overload - 0.7) * 45.0
    return max(0.0, min(100.0, raw_score))


def _score_to_grade(understanding_score: float) -> str:
    for i, (lo, hi) in enumerate(UNDERSTANDING_SCORE_BANDS):
        if lo <= understanding_score <= hi:
            return UNDERSTANDING_GRADES[i]
    return "F-"


def get_install_meter_meta(team: Any) -> Dict[str, Any]:
    """Coach/roster inputs for the Play Selection install meter UI."""
    coach = getattr(team, "coach", None)
    scheme_teach = getattr(coach, "scheme_teach", 5) if coach else 5
    scheme_teach = max(1, min(10, scheme_teach))
    avg_iq, avg_coach = _roster_avg_football_iq_and_coachability(team)
    teaching_score = (scheme_teach * 10 + avg_iq + avg_coach) / 3.0
    teaching_score = max(0, min(100, teaching_score))
    teachable_per_cat = 2 + (teaching_score / 100.0) * 8.0
    recommended = _plays_per_category_from_scheme_teach(scheme_teach)
    return {
        "scheme_teach": int(scheme_teach),
        "recommended_plays_per_category": int(recommended),
        "teachable_plays_per_category": round(teachable_per_cat, 1),
        "avg_football_iq": round(avg_iq, 1),
        "avg_coachability": round(avg_coach, 1),
    }


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

    off_selection = normalize_selection_for_storage(off_selection)
    def_selection = normalize_selection_for_storage(def_selection)

    def _side_learning_pct(selection: Dict[str, List[Tuple[str, float]]]) -> float:
        if not any(filter_active_play_entries(v) for v in selection.values()):
            return 0.0
        avg_per_cat = _active_plays_per_category(selection)
        if teachable_per_cat <= 0:
            return 0.0
        overload = avg_per_cat / teachable_per_cat
        return _understanding_score_from_overload(overload)

    off_pct = round(_side_learning_pct(off_selection))
    def_pct = round(_side_learning_pct(def_selection))
    grade = compute_understanding_grade(team, off_selection, def_selection)

    meta = get_install_meter_meta(team)
    return {
        "offensive_pct_learned": int(off_pct),
        "defensive_pct_learned": int(def_pct),
        "overall_grade": grade,
        **meta,
    }


def compute_learning_preview(
    team: Any,
    offensive: Optional[Dict[str, List[Tuple[str, float]]]] = None,
    defensive: Optional[Dict[str, List[Tuple[str, float]]]] = None,
) -> Dict[str, Any]:
    """
    Projected learning summary from draft selections (Play Selection UI live meter).
    """
    off_selection = normalize_selection_for_storage(offensive or {})
    def_selection = normalize_selection_for_storage(defensive or {})
    grade = compute_understanding_grade(team, off_selection, def_selection)
    coach = getattr(team, "coach", None)
    scheme_teach = getattr(coach, "scheme_teach", 5) if coach else 5
    scheme_teach = max(1, min(10, scheme_teach))
    avg_iq, avg_coach = _roster_avg_football_iq_and_coachability(team)
    teaching_score = (scheme_teach * 10 + avg_iq + avg_coach) / 3.0
    teaching_score = max(0, min(100, teaching_score))
    teachable_per_cat = 2 + (teaching_score / 100.0) * 8.0

    def _side(selection: Dict[str, List[Tuple[str, float]]]) -> Dict[str, Any]:
        avg_per_cat = _active_plays_per_category(selection)
        overload = (avg_per_cat / teachable_per_cat) if teachable_per_cat > 0 else 2.0
        return {
            "active_plays_per_category": round(avg_per_cat, 1),
            "pct_learned": int(round(_understanding_score_from_overload(overload))),
        }

    off_side = _side(off_selection)
    def_side = _side(def_selection)
    return {
        "offensive_pct_learned": off_side["pct_learned"],
        "defensive_pct_learned": def_side["pct_learned"],
        "offensive_active_plays_per_category": off_side["active_plays_per_category"],
        "defensive_active_plays_per_category": def_side["active_plays_per_category"],
        "overall_grade": grade,
        **get_install_meter_meta(team),
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
