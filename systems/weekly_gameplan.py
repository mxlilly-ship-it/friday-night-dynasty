"""
Weekly gameplan package: grid OR call sheet, usage, practice, halftime, team script.
Used by league save/load and play_caller during sim.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional, Tuple

from models.play import DefensivePlayCategory, OffensivePlayCategory

try:
    from systems.gameplan_v2 import (
        DEFENSE_CATEGORIES,
        OFFENSE_CATEGORIES,
        make_default_defense_plan,
        make_default_offense_plan,
        validate_plan as validate_grid_plan,
    )
except ImportError:
    OFFENSE_CATEGORIES = []
    DEFENSE_CATEGORIES = []
    make_default_offense_plan = None  # type: ignore
    make_default_defense_plan = None  # type: ignore
    validate_grid_plan = None  # type: ignore

PACKAGE_VERSION = 1

PRACTICE_DAYS = ("mon", "tue", "wed", "thu")
PRACTICE_PILLARS_OFF = (
    "pass_game",
    "run_game",
    "third_down",
    "red_zone",
    "goal_line",
    "opponent_prep",
    "conditioning",
    "rest",
)
PRACTICE_PILLARS_DEF = (
    "pass_defense",
    "run_defense",
    "third_down",
    "red_zone",
    "goal_line",
    "opponent_prep",
    "conditioning",
    "rest",
)

OFF_CALLSHEET_KEYS = (
    "opening",
    "base_dd",
    "third_long",
    "third_medium",
    "third_short",
    "fourth_long",
    "fourth_medium",
    "fourth_short",
    "red_zone",
    "backed_up",
    "goal_line",
    "two_minute",
)
OFF_CALLSHEET_SIZES = {
    "opening": 10,
    "base_dd": 15,
    "third_long": 3,
    "third_medium": 3,
    "third_short": 3,
    "fourth_long": 2,
    "fourth_medium": 2,
    "fourth_short": 2,
    "red_zone": 5,
    "backed_up": 3,
    "goal_line": 3,
    "two_minute": 4,
}

DEF_CALLSHEET_KEYS = (
    "base_dd",
    "third_long",
    "third_medium",
    "third_short",
    "fourth_long",
    "fourth_medium",
    "fourth_short",
    "red_zone",
    "goal_line",
    "opponent_backed_up",
    "two_minute",
)
DEF_CALLSHEET_SIZES = {
    "base_dd": 8,
    "third_long": 3,
    "third_medium": 3,
    "third_short": 3,
    "fourth_long": 2,
    "fourth_medium": 2,
    "fourth_short": 2,
    "red_zone": 3,
    "goal_line": 3,
    "opponent_backed_up": 2,
    "two_minute": 3,
}

HALFTIME_TRIGGERS_OFF = {
    "run_stuffed": "Our run game is getting stuffed",
    "qb_pressure": "QB under pressure",
    "third_down_fail": "Losing on 3rd down",
    "rz_stalled": "Red zone stalled",
    "need_chunks": "Need chunk plays",
    "pass_taken_away": "Pass game taken away",
    "blitz_beat_us": "Their blitz is beating us",
}
HALFTIME_TRIGGERS_DEF = {
    "run_gashing": "Their run game is gashing us",
    "pass_beating": "Their pass game is beating us",
    "explosives": "They're hitting explosives",
    "third_down_leaks": "Losing on 3rd down",
    "rz_struggling": "Red zone defense struggling",
    "qb_scramble": "Their QB is hurting us",
}

HALFTIME_RESPONSES_OFF: Dict[str, Dict[str, str]] = {
    "run_stuffed": {"A": "Attack perimeter", "B": "Pound inside", "C": "Play-action"},
    "qb_pressure": {"A": "Quick game", "B": "Move pocket", "C": "Max protect shots"},
    "third_down_fail": {"A": "Quick to sticks", "B": "Run on short 3rd", "C": "Take a shot"},
    "rz_stalled": {"A": "Power run", "B": "Spread quick RZ", "C": "Play-action RZ"},
    "need_chunks": {"A": "Vertical shots", "B": "Play-action deep", "C": "Perimeter smoke"},
    "pass_taken_away": {"A": "Commit to run", "B": "Misdirection", "C": "Tempo looks"},
    "blitz_beat_us": {"A": "Hot quick", "B": "Screens", "C": "Slide and run"},
}
HALFTIME_RESPONSES_DEF: Dict[str, Dict[str, str]] = {
    "run_gashing": {"A": "Heavier packages", "B": "Blitz more", "C": "Play more zone"},
    "pass_beating": {"A": "More man", "B": "Zone shell", "C": "Pressure QB"},
    "explosives": {"A": "Deep safety help", "B": "Press man", "C": "Simulated pressure"},
    "third_down_leaks": {"A": "Tighten short zone", "B": "Heat on 3rd", "C": "Bracket #1"},
    "rz_struggling": {"A": "Goal-line heavies", "B": "Man match RZ", "C": "Blitz RZ"},
    "qb_scramble": {"A": "Spy contain", "B": "Rush with lanes", "C": "Lock coverage"},
}

HALFTIME_CAT_OFF: Dict[str, Dict[str, Dict[str, float]]] = {
    "run_stuffed": {
        "A": {"Outside Run": 1.25},
        "B": {"Inside Run": 1.25},
        "C": {"Play Action": 1.2, "Medium": 1.1},
    },
    "qb_pressure": {
        "A": {"Quick": 1.3},
        "B": {"Outside Run": 1.15, "Quick": 1.1},
        "C": {"Play Action": 1.2, "Medium": 1.15},
    },
    "third_down_fail": {
        "A": {"Quick": 1.25},
        "B": {"Inside Run": 1.2},
        "C": {"Medium": 1.15, "Long": 1.1},
    },
    "rz_stalled": {
        "A": {"Inside Run": 1.25},
        "B": {"Quick": 1.15, "Medium": 1.1},
        "C": {"Play Action": 1.25},
    },
    "need_chunks": {
        "A": {"Long": 1.3},
        "B": {"Play Action": 1.2, "Medium": 1.15},
        "C": {"Outside Run": 1.1, "Quick": 1.1},
    },
    "pass_taken_away": {
        "A": {"Inside Run": 1.2, "Outside Run": 1.15},
        "B": {"Play Action": 1.25},
        "C": {"Quick": 1.1, "Outside Run": 1.1},
    },
    "blitz_beat_us": {
        "A": {"Quick": 1.3},
        "B": {"Quick": 1.15, "Outside Run": 1.1},
        "C": {"Inside Run": 1.2},
    },
}

HALFTIME_CAT_DEF: Dict[str, Dict[str, Dict[str, float]]] = {
    "run_gashing": {
        "A": {"Zones": 1.25},
        "B": {"Zone Pressure": 1.2, "Man Pressure": 1.15},
        "C": {"Zones": 1.2},
    },
    "pass_beating": {
        "A": {"Man": 1.2, "Man Pressure": 1.1},
        "B": {"Zones": 1.25},
        "C": {"Zone Pressure": 1.2, "Man Pressure": 1.15},
    },
    "explosives": {
        "A": {"Zones": 1.25},
        "B": {"Man": 1.2},
        "C": {"Zone Pressure": 1.15},
    },
    "third_down_leaks": {
        "A": {"Zones": 1.2},
        "B": {"Zone Pressure": 1.2, "Man Pressure": 1.15},
        "C": {"Man": 1.2},
    },
    "rz_struggling": {
        "A": {"Zones": 1.25},
        "B": {"Man": 1.2},
        "C": {"Man Pressure": 1.2, "Zone Pressure": 1.15},
    },
    "qb_scramble": {
        "A": {"Zones": 1.2},
        "B": {"Zone Pressure": 1.15},
        "C": {"Man": 1.2},
    },
}


def _empty_practice(side: str) -> Dict[str, Dict[str, int]]:
    pillars = PRACTICE_PILLARS_OFF if side == "offense" else PRACTICE_PILLARS_DEF
    day_tpl = {p: 0 for p in pillars}
    return {d: dict(day_tpl) for d in PRACTICE_DAYS}


def _empty_callsheet(side: str) -> Dict[str, Any]:
    keys = OFF_CALLSHEET_KEYS if side == "offense" else DEF_CALLSHEET_KEYS
    sizes = OFF_CALLSHEET_SIZES if side == "offense" else DEF_CALLSHEET_SIZES
    out: Dict[str, Any] = {k: [""] * sizes[k] for k in keys}
    if side == "offense":
        out["vertical_shots"] = "balanced"
    else:
        out["pressure_tendency"] = "balanced"
    return out


def default_team_script() -> Dict[str, Any]:
    return {
        "pace": 50,
        "clock_management": 50,
        "risk": 50,
        "ball_security": 50,
        "garbage_time": 70,
        "youth_reps": 40,
        "four_minute": 50,
        "go_for_2": 50,
        "vertical_shots": "balanced",
        "pressure_tendency": "balanced",
        "def_run_fit": 50,
        "def_coverage": 50,
        "def_third_down": 50,
    }


def default_halftime_slots() -> List[Dict[str, Optional[str]]]:
    return [
        {"trigger": None, "response": None},
        {"trigger": None, "response": None},
        {"trigger": None, "response": None},
    ]


def default_side_package(side: str, grid: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if grid is None:
        if side == "offense" and make_default_offense_plan:
            grid = make_default_offense_plan()
        elif side == "defense" and make_default_defense_plan:
            grid = make_default_defense_plan()
        else:
            grid = {}
    usage: Dict[str, Any] = {
        "rb_carry_split": "50_50",
        "wr_target_order": ["", "", "", "", ""],
        "qb_designed_runs": 50,
    }
    if side == "defense":
        usage = {"coverage": "normal"}
    return {
        "version": PACKAGE_VERSION,
        "gameplan_mode": "grid",
        "confirmed": False,
        "grid": grid,
        "callsheet": _empty_callsheet(side),
        "usage": usage,
        "practice": _empty_practice(side),
        "halftime": {"slots": default_halftime_slots()},
    }


def normalize_side_package(raw: Any, side: str, legacy_grid: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge legacy grid-only saves into full side package."""
    base = default_side_package(side)
    if isinstance(raw, dict) and raw.get("gameplan_mode"):
        pkg = copy.deepcopy(raw)
    elif isinstance(legacy_grid, dict) and legacy_grid:
        pkg = default_side_package(side, legacy_grid)
    elif isinstance(raw, dict) and _looks_like_grid(raw):
        pkg = default_side_package(side, raw)
    else:
        pkg = base

    pkg["version"] = PACKAGE_VERSION
    mode = str(pkg.get("gameplan_mode") or "grid").lower()
    pkg["gameplan_mode"] = "callsheet" if mode == "callsheet" else "grid"
    if not isinstance(pkg.get("grid"), dict):
        pkg["grid"] = default_side_package(side)["grid"]
    if not isinstance(pkg.get("callsheet"), dict):
        pkg["callsheet"] = _empty_callsheet(side)
    else:
        pkg["callsheet"] = _normalize_callsheet(pkg["callsheet"], side)
    if not isinstance(pkg.get("usage"), dict):
        pkg["usage"] = default_side_package(side)["usage"]
    if not isinstance(pkg.get("practice"), dict):
        pkg["practice"] = _empty_practice(side)
    else:
        pkg["practice"] = _normalize_practice(pkg["practice"], side)
    if not isinstance(pkg.get("halftime"), dict):
        pkg["halftime"] = {"slots": default_halftime_slots()}
    else:
        slots = pkg["halftime"].get("slots")
        if not isinstance(slots, list):
            pkg["halftime"] = {"slots": default_halftime_slots()}
    pkg["confirmed"] = bool(pkg.get("confirmed"))
    return pkg


def _looks_like_grid(d: Dict[str, Any]) -> bool:
    for k in d:
        if isinstance(d.get(k), dict):
            return True
    return False


def _normalize_callsheet(cs: Dict[str, Any], side: str) -> Dict[str, Any]:
    keys = OFF_CALLSHEET_KEYS if side == "offense" else DEF_CALLSHEET_KEYS
    sizes = OFF_CALLSHEET_SIZES if side == "offense" else DEF_CALLSHEET_SIZES
    out = _empty_callsheet(side)
    for k in keys:
        raw = cs.get(k)
        if isinstance(raw, list):
            lst = [str(x or "").strip() for x in raw[: sizes[k]]]
            while len(lst) < sizes[k]:
                lst.append("")
            out[k] = lst
    if side == "offense":
        v = str(cs.get("vertical_shots") or "balanced").lower()
        out["vertical_shots"] = v if v in ("conservative", "balanced", "aggressive") else "balanced"
    else:
        p = str(cs.get("pressure_tendency") or "balanced").lower()
        out["pressure_tendency"] = p if p in ("conservative", "balanced", "aggressive") else "balanced"
    return out


def _normalize_practice(pr: Dict[str, Any], side: str) -> Dict[str, Any]:
    pillars = PRACTICE_PILLARS_OFF if side == "offense" else PRACTICE_PILLARS_DEF
    out = _empty_practice(side)
    for day in PRACTICE_DAYS:
        row = pr.get(day)
        if not isinstance(row, dict):
            continue
        total = 0
        for p in pillars:
            try:
                v = max(0, min(50, int(row.get(p, 0) or 0)))
            except Exception:
                v = 0
            out[day][p] = v
            total += v
        if total > 50:
            scale = 50.0 / total
            for p in pillars:
                out[day][p] = int(round(out[day][p] * scale))
    return out


def normalize_matchup_entry(entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    entry = dict(entry) if isinstance(entry, dict) else {}
    off_legacy = entry.get("offense") if isinstance(entry.get("offense"), dict) else None
    def_legacy = entry.get("defense") if isinstance(entry.get("defense"), dict) else None
    off_pkg = normalize_side_package(entry.get("offense_package"), "offense", off_legacy if _looks_like_grid(off_legacy or {}) else None)
    def_pkg = normalize_side_package(entry.get("defense_package"), "defense", def_legacy if _looks_like_grid(def_legacy or {}) else None)
    script = entry.get("team_script")
    if not isinstance(script, dict):
        script = default_team_script()
    else:
        script = {**default_team_script(), **script}
    return {
        "offense_package": off_pkg,
        "defense_package": def_pkg,
        "team_script": script,
        "offense": off_pkg["grid"] if off_pkg["gameplan_mode"] == "grid" else off_legacy,
        "defense": def_pkg["grid"] if def_pkg["gameplan_mode"] == "grid" else def_legacy,
        "updated_at": entry.get("updated_at"),
    }


def validate_side_package(pkg: Dict[str, Any], side: str) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    mode = pkg.get("gameplan_mode")
    if mode == "grid" and validate_grid_plan and isinstance(pkg.get("grid"), dict):
        cats = OFFENSE_CATEGORIES if side == "offense" else DEFENSE_CATEGORIES
        ok, g_errs = validate_grid_plan(pkg["grid"], categories=cats)
        if not ok:
            errs.extend(g_errs[:5])
    for day in PRACTICE_DAYS:
        row = (pkg.get("practice") or {}).get(day) or {}
        pillars = PRACTICE_PILLARS_OFF if side == "offense" else PRACTICE_PILLARS_DEF
        total = sum(int(row.get(p, 0) or 0) for p in pillars)
        if total > 50:
            errs.append(f"Practice {day} exceeds 50 points ({total})")
    return len(errs) == 0, errs


def _practice_pillar_totals(pkg: Dict[str, Any], side: str) -> Dict[str, int]:
    pr = pkg.get("practice") or {}
    pillars = PRACTICE_PILLARS_OFF if side == "offense" else PRACTICE_PILLARS_DEF
    totals = {p: 0 for p in pillars}
    for day in PRACTICE_DAYS:
        row = pr.get(day) if isinstance(pr.get(day), dict) else {}
        for p in pillars:
            totals[p] += int(row.get(p, 0) or 0)
    return totals


def _pillar_factor(points: int, max_pts: int = 200, boost: float = 0.18) -> float:
    return 1.0 + min(max(points, 0), max_pts) / float(max_pts) * boost


def practice_offense_label_multipliers(pkg: Dict[str, Any]) -> Dict[str, float]:
    """Category label multipliers from Mon–Thu practice totals."""
    t = _practice_pillar_totals(pkg, "offense")
    mult = {
        "Inside Run": 1.0,
        "Outside Run": 1.0,
        "Quick": 1.0,
        "Medium": 1.0,
        "Long": 1.0,
        "Play Action": 1.0,
    }
    mult["Quick"] *= _pillar_factor(t.get("pass_game", 0))
    mult["Medium"] *= _pillar_factor(t.get("pass_game", 0))
    mult["Long"] *= _pillar_factor(t.get("pass_game", 0))
    mult["Play Action"] *= _pillar_factor(t.get("pass_game", 0), boost=0.12)
    mult["Inside Run"] *= _pillar_factor(t.get("run_game", 0))
    mult["Outside Run"] *= _pillar_factor(t.get("run_game", 0))
    mult["Quick"] *= _pillar_factor(t.get("third_down", 0), boost=0.10)
    mult["Medium"] *= _pillar_factor(t.get("third_down", 0), boost=0.10)
    mult["Inside Run"] *= _pillar_factor(t.get("red_zone", 0), boost=0.10)
    mult["Play Action"] *= _pillar_factor(t.get("red_zone", 0), boost=0.10)
    mult["Inside Run"] *= _pillar_factor(t.get("goal_line", 0), boost=0.12)
    prep = _pillar_factor(t.get("opponent_prep", 0), boost=0.08)
    for k in mult:
        mult[k] *= prep
    rest_pen = 1.0 - min(t.get("rest", 0), 80) / 80.0 * 0.06
    cond = 1.0 + min(t.get("conditioning", 0), 80) / 80.0 * 0.04
    for k in mult:
        mult[k] *= rest_pen * cond
    return mult


def practice_defense_label_multipliers(pkg: Dict[str, Any]) -> Dict[str, float]:
    t = _practice_pillar_totals(pkg, "defense")
    mult = {
        "Zones": 1.0,
        "Man": 1.0,
        "Zone Pressure": 1.0,
        "Man Pressure": 1.0,
    }
    mult["Zones"] *= _pillar_factor(t.get("pass_defense", 0))
    mult["Man"] *= _pillar_factor(t.get("pass_defense", 0))
    mult["Zone Pressure"] *= _pillar_factor(t.get("pass_defense", 0), boost=0.10)
    mult["Man Pressure"] *= _pillar_factor(t.get("pass_defense", 0), boost=0.10)
    mult["Zones"] *= _pillar_factor(t.get("run_defense", 0), boost=0.10)
    mult["Man"] *= _pillar_factor(t.get("run_defense", 0), boost=0.10)
    prep = _pillar_factor(t.get("opponent_prep", 0), boost=0.08)
    for k in mult:
        mult[k] *= prep
    return mult


def vertical_shots_multiplier(mode: str) -> Dict[str, float]:
    m = str(mode or "balanced").lower()
    if m == "conservative":
        return {"Long": 0.75, "Medium": 1.05, "Quick": 1.08}
    if m == "aggressive":
        return {"Long": 1.35, "Medium": 1.08, "Play Action": 1.10}
    return {"Long": 1.0, "Medium": 1.0, "Quick": 1.0}


def usage_offense_play_weight_boost(pkg: Dict[str, Any], play: Any) -> float:
    usage = pkg.get("usage") if isinstance(pkg.get("usage"), dict) else {}
    boost = 1.0
    qb_runs = max(0, min(100, int(usage.get("qb_designed_runs", 50) or 50)))
    pid = str(getattr(play, "id", "") or "").lower()
    if "option" in pid or "sweep" in pid or "read" in pid:
        boost *= 1.0 + (qb_runs - 50) / 100.0 * 0.35
    return max(0.5, boost)


def usage_defense_pressure_boost(pkg: Dict[str, Any]) -> Tuple[float, float]:
    """Return (coverage_weight, pressure_weight) multipliers."""
    usage = pkg.get("usage") if isinstance(pkg.get("usage"), dict) else {}
    cov = str(usage.get("coverage") or "normal").lower()
    cs = pkg.get("callsheet") if isinstance(pkg.get("callsheet"), dict) else {}
    press = str(cs.get("pressure_tendency") or "balanced").lower()
    cov_w, press_w = 1.0, 1.0
    if cov == "bracket_1":
        cov_w = 1.25
        press_w = 0.92
    elif cov == "rotation_1":
        cov_w = 1.12
        press_w = 0.95
    if press == "conservative":
        press_w *= 0.82
    elif press == "aggressive":
        press_w *= 1.28
    return cov_w, press_w


def _script_slider_norm(script: Dict[str, Any], key: str) -> float:
    """Map 0–100 slider to ~0.5–1.5 multiplier (50 → 1.0)."""
    raw = max(0, min(100, int(script.get(key, 50) or 50)))
    return 0.5 + raw / 100.0


def team_script_defense_weight_adjustment(
    script: Optional[Dict[str, Any]],
    *,
    down: int = 1,
    yards_to_go: int = 10,
) -> Tuple[float, float]:
    """Adjust (coverage_weight, pressure_weight) from defense team-script sliders."""
    if not isinstance(script, dict):
        return 1.0, 1.0
    cov_w, press_w = 1.0, 1.0
    press = str(script.get("pressure_tendency") or "balanced").lower()
    if press == "conservative":
        press_w *= 0.88
        cov_w *= 1.08
    elif press == "aggressive":
        press_w *= 1.15
        cov_w *= 0.95
    run_fit = _script_slider_norm(script, "def_run_fit")
    cov_w *= 0.92 + run_fit * 0.08
    press_w *= 1.08 - (run_fit - 1.0) * 0.12
    coverage_style = _script_slider_norm(script, "def_coverage")
    cov_w *= 0.95 + (coverage_style - 1.0) * 0.1
    press_w *= 0.98 + (coverage_style - 1.0) * 0.08
    if down == 3:
        third = _script_slider_norm(script, "def_third_down")
        press_w *= 0.85 + third * 0.15
    return max(0.5, cov_w), max(0.5, press_w)


def weekly_sim_enabled(game: Any) -> bool:
    if game is None:
        return True
    return bool(getattr(game, "use_weekly_gameplan_sim", True))


def record_first_half_stat(
    game: Any,
    offense_team: Any,
    defense_team: Any,
    result: Dict[str, Any],
    *,
    down_before: int,
    is_run: bool,
) -> None:
    """Track 1H stats for halftime trigger evaluation (sim only)."""
    if not weekly_sim_enabled(game):
        return
    if int(getattr(game, "quarter", 1)) > 2:
        return
    init_callsheet_runtime(game)
    off_name = getattr(offense_team, "name", "off")
    def_name = getattr(defense_team, "name", "def")
    off_rt = _team_runtime(game, off_name)
    def_rt = _team_runtime(game, def_name)
    fh_off = off_rt["first_half"]
    fh_def = def_rt["first_half"]
    yards = int(result.get("yards", 0) or 0)
    if is_run:
        fh_off["rush_att"] = int(fh_off.get("rush_att", 0)) + 1
        fh_off["rush_yards"] = int(fh_off.get("rush_yards", 0)) + yards
    else:
        fh_off["pass_att"] = int(fh_off.get("pass_att", 0)) + 1
        fh_off["pass_yards"] = int(fh_off.get("pass_yards", 0)) + yards
    if yards >= 20:
        fh_off["explosives"] = int(fh_off.get("explosives", 0)) + 1
    if result.get("sack"):
        fh_off["sacks_taken"] = int(fh_off.get("sacks_taken", 0)) + 1
    if yards < 0:
        fh_off["negative_plays"] = int(fh_off.get("negative_plays", 0)) + 1
    if down_before == 3:
        fh_off["third_att"] = int(fh_off.get("third_att", 0)) + 1
        if result.get("first_down") or result.get("touchdown"):
            fh_off["third_conv"] = int(fh_off.get("third_conv", 0)) + 1
    bp = int(getattr(game, "ball_position", 50))
    if 80 <= bp <= 94:
        fh_off["rz_trips"] = int(fh_off.get("rz_trips", 0)) + 1
        if result.get("touchdown"):
            fh_off["rz_td"] = int(fh_off.get("rz_td", 0)) + 1
    if is_run:
        fh_def["opp_rush_yards"] = int(fh_def.get("opp_rush_yards", 0)) + yards
    else:
        fh_def["opp_pass_yards"] = int(fh_def.get("opp_pass_yards", 0)) + yards
    if yards >= 20:
        fh_def["opp_explosives"] = int(fh_def.get("opp_explosives", 0)) + 1
    if down_before == 3 and (result.get("first_down") or result.get("touchdown")):
        fh_def["opp_third_conv"] = int(fh_def.get("opp_third_conv", 0)) + 1
    if result.get("touchdown") and bp >= 80:
        fh_def["opp_rz_td"] = int(fh_def.get("opp_rz_td", 0)) + 1
    if result.get("sack"):
        fh_def["opp_sacks"] = int(fh_def.get("opp_sacks", 0)) + 1


def risk_to_go_for_it_max_ytg(risk: int) -> int:
    """Map risk knob 0-100 to yards-to-go threshold for 4th down decisions."""
    r = max(0, min(100, int(risk)))
    return max(1, min(10, 1 + int(round(r * 7 / 100))))


def apply_packages_to_coach(coach: Any, entry: Dict[str, Any], *, is_user: bool = True) -> None:
    if coach is None or not isinstance(entry, dict):
        return
    norm = normalize_matchup_entry(entry)
    off_pkg = norm["offense_package"]
    def_pkg = norm["defense_package"]
    script = norm["team_script"]

    coach.weekly_offense_package = off_pkg
    coach.weekly_defense_package = def_pkg
    coach.team_script = script

    if off_pkg.get("gameplan_mode") == "grid" and isinstance(off_pkg.get("grid"), dict):
        coach.game_plan_v2_offense = off_pkg["grid"]
    if def_pkg.get("gameplan_mode") == "grid" and isinstance(def_pkg.get("grid"), dict):
        coach.game_plan_v2_defense = def_pkg["grid"]

    risk = int(script.get("risk", 50) or 50)
    coach.fourth_down_go_for_it_max_ytg = risk_to_go_for_it_max_ytg(risk)
    coach.go_for_two_tendency = max(0, min(100, int(script.get("go_for_2", 50) or 50)))


def init_callsheet_runtime(game: Any) -> None:
    if not hasattr(game, "callsheet_runtime") or not isinstance(game.callsheet_runtime, dict):
        game.callsheet_runtime = {}


def _team_runtime(game: Any, team_name: str) -> Dict[str, Any]:
    init_callsheet_runtime(game)
    rt = game.callsheet_runtime
    if team_name not in rt:
        rt[team_name] = {
            "opening_index": 0,
            "opening_complete": False,
            "rotations": {},
            "first_half": {
                "rush_yards": 0,
                "rush_att": 0,
                "pass_yards": 0,
                "pass_att": 0,
                "third_conv": 0,
                "third_att": 0,
                "explosives": 0,
                "sacks_taken": 0,
                "negative_plays": 0,
                "rz_trips": 0,
                "rz_td": 0,
                "opp_rush_yards": 0,
                "opp_pass_yards": 0,
                "opp_explosives": 0,
                "opp_third_conv": 0,
                "opp_rz_td": 0,
                "opp_sacks": 0,
            },
            "halftime_overlay_off": None,
            "halftime_overlay_def": None,
        }
    return rt[team_name]


def is_two_minute(quarter: int, time_remaining: int) -> bool:
    return quarter in (2, 4) and time_remaining <= 120


def resolve_callsheet_bucket(
    side: str,
    situation: Any,
    *,
    offense_team: Any,
    defense_team: Any,
    game: Any,
) -> Optional[str]:
    """Return bucket key for call sheet mode, or None for base/opening special handling."""
    down = int(situation.down)
    ytg = int(situation.yards_to_go)
    bp = int(situation.ball_position)
    q = int(situation.quarter)
    tr = int(situation.time_remaining)

    if is_two_minute(q, tr):
        return "two_minute"

    if bp >= 95:
        return "goal_line"
    if bp >= 80:
        return "red_zone"
    if side == "defense" and bp <= 20:
        return "opponent_backed_up"
    if side == "offense" and bp <= 20:
        return "backed_up"

    if down == 4:
        if ytg >= 7:
            return "fourth_long"
        if ytg >= 4:
            return "fourth_medium"
        return "fourth_short"
    if down == 3:
        if ytg >= 7:
            return "third_long"
        if ytg >= 4:
            return "third_medium"
        return "third_short"

    if down in (1, 2) and 21 <= bp <= 79:
        if side == "offense":
            team = offense_team
            rt = _team_runtime(game, getattr(team, "name", "off"))
            if not rt.get("opening_complete"):
                return "opening"
        return "base_dd"
    return None


def pick_callsheet_play_id(
    side: str,
    bucket: str,
    pkg: Dict[str, Any],
    offense_team: Any,
    defense_team: Any,
    game: Any,
    rng: random.Random,
) -> Optional[str]:
    cs = pkg.get("callsheet") or {}
    team = offense_team if side == "offense" else defense_team
    team_name = getattr(team, "name", "team")
    rt = _team_runtime(game, team_name)
    slots: List[str] = list(cs.get(bucket) or [])

    if bucket == "opening" and side == "offense":
        idx = int(rt.get("opening_index", 0))
        if idx >= len(slots) or idx >= 10:
            rt["opening_complete"] = True
            bucket = "base_dd"
            slots = list(cs.get("base_dd") or [])
        else:
            pid = str(slots[idx] or "").strip()
            rt["opening_index"] = idx + 1
            if rt["opening_index"] >= 10:
                rt["opening_complete"] = True
            if pid:
                return pid
            return None

    filled = [str(s).strip() for s in slots if str(s).strip()]
    if not filled:
        return None

    if bucket == "base_dd":
        return rng.choice(filled)

    rot = rt["rotations"]
    i = int(rot.get(bucket, 0))
    pid = filled[i % len(filled)]
    rot[bucket] = i + 1
    return pid


def installed_play_ids(team: Any, side: str) -> set:
    from systems.play_selection import filter_active_play_entries

    sel = (
        getattr(team, "season_offensive_play_selection", None)
        if side == "offense"
        else getattr(team, "season_defensive_play_selection", None)
    )
    out: set = set()
    if not isinstance(sel, dict):
        return out
    for entries in sel.values():
        if not isinstance(entries, list):
            continue
        for play_id, pct in filter_active_play_entries(entries):
            out.add(str(play_id))
    return out


def apply_halftime_overlays(game: Any, offense_team: Any, defense_team: Any) -> None:
    """Evaluate 1H stats at start of Q3 and set halftime category overlays."""
    if int(getattr(game, "quarter", 1)) != 3:
        return
    init_callsheet_runtime(game)
    for side, team, pkg_key in (
        ("offense", offense_team, "weekly_offense_package"),
        ("defense", defense_team, "weekly_defense_package"),
    ):
        coach = getattr(team, "coach", None)
        if coach is None:
            continue
        pkg = getattr(coach, pkg_key, None)
        if not isinstance(pkg, dict):
            continue
        team_name = getattr(team, "name", "")
        rt = _team_runtime(game, team_name)
        key = "halftime_overlay_off" if side == "offense" else "halftime_overlay_def"
        if rt.get(key) is not None:
            continue
        overlay = _eval_halftime(pkg, side, rt.get("first_half") or {})
        rt[key] = overlay


def _eval_halftime(pkg: Dict[str, Any], side: str, fh: Dict[str, int]) -> Optional[Dict[str, float]]:
    slots = (pkg.get("halftime") or {}).get("slots") or []
    triggers = HALFTIME_TRIGGERS_OFF if side == "offense" else HALFTIME_TRIGGERS_DEF
    cat_map = HALFTIME_CAT_OFF if side == "offense" else HALFTIME_CAT_DEF
    merged: Dict[str, float] = {}
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        trig = slot.get("trigger")
        resp = slot.get("response")
        if not trig or not resp or resp not in ("A", "B", "C"):
            continue
        if not _trigger_fired(str(trig), side, fh):
            continue
        deltas = cat_map.get(str(trig), {}).get(str(resp), {})
        for cat, mult in deltas.items():
            merged[cat] = merged.get(cat, 1.0) * float(mult)
    return merged if merged else None


def _trigger_fired(trig: str, side: str, fh: Dict[str, int]) -> bool:
    if side == "offense":
        if trig == "run_stuffed":
            att = max(1, int(fh.get("rush_att", 0)))
            return (fh.get("rush_yards", 0) / att) < 3.5 and att >= 6
        if trig == "qb_pressure":
            return int(fh.get("sacks_taken", 0)) >= 2
        if trig == "third_down_fail":
            att = int(fh.get("third_att", 0))
            return att >= 3 and fh.get("third_conv", 0) / max(1, att) < 0.35
        if trig == "rz_stalled":
            return int(fh.get("rz_trips", 0)) >= 2 and int(fh.get("rz_td", 0)) == 0
        if trig == "need_chunks":
            return int(fh.get("explosives", 0)) == 0 and int(fh.get("pass_att", 0)) >= 8
        if trig == "pass_taken_away":
            pa = max(1, int(fh.get("pass_att", 0)))
            return pa >= 6 and fh.get("pass_yards", 0) / pa < 5.0
        if trig == "blitz_beat_us":
            return int(fh.get("sacks_taken", 0)) >= 1 or int(fh.get("negative_plays", 0)) >= 3
    else:
        if trig == "run_gashing":
            return int(fh.get("opp_rush_yards", 0)) >= 80
        if trig == "pass_beating":
            return int(fh.get("opp_pass_yards", 0)) >= 100
        if trig == "explosives":
            return int(fh.get("opp_explosives", 0)) >= 2
        if trig == "third_down_leaks":
            return int(fh.get("opp_third_conv", 0)) >= 3
        if trig == "rz_struggling":
            return int(fh.get("opp_rz_td", 0)) >= 2
        if trig == "qb_scramble":
            return int(fh.get("opp_pass_yards", 0)) >= 90 and int(fh.get("opp_sacks", 0)) == 0
    return False


def script_pace_multiplier(script: Dict[str, Any]) -> float:
    pace = max(0, min(100, int(script.get("pace", 50) or 50)))
    # 50 = 1.0, 0 = ~1.12 drain (slower/more time), 100 = ~0.88 (faster/more plays)
    return 1.0 + (50 - pace) * 0.0024


def apply_halftime_category_weights(
    weights: Dict[Any, float],
    game: Any,
    team_name: str,
    side: str,
    enum_map: Dict[str, Any],
) -> Dict[Any, float]:
    rt = _team_runtime(game, team_name)
    key = "halftime_overlay_off" if side == "offense" else "halftime_overlay_def"
    overlay = rt.get(key)
    if not isinstance(overlay, dict):
        return weights
    out = dict(weights)
    for cat_label, mult in overlay.items():
        enum_val = enum_map.get(cat_label)
        if enum_val is not None and enum_val in out:
            out[enum_val] = out[enum_val] * float(mult)
    return out


def autofill_callsheet_from_install(team: Any, side: str) -> Dict[str, Any]:
    """Fill empty call sheet slots from top installed plays by category fit."""
    cs = _empty_callsheet(side)
    sel = (
        getattr(team, "season_offensive_play_selection", None)
        if side == "offense"
        else getattr(team, "season_defensive_play_selection", None)
    )
    if not isinstance(sel, dict):
        return cs
    from systems.play_selection import filter_active_play_entries

    by_cat: Dict[str, List[str]] = {}
    for cat, entries in sel.items():
        if not isinstance(entries, list):
            continue
        ids = [str(pid) for pid, _ in filter_active_play_entries(entries)]
        if ids:
            by_cat[str(cat)] = ids

    def fill_bucket(key: str, cats: List[str]) -> None:
        picks: List[str] = []
        for c in cats:
            picks.extend(by_cat.get(c, [])[:3])
        if not picks:
            return
        n = len(cs.get(key) or [])
        for i in range(n):
            if cs[key][i]:
                continue
            cs[key][i] = picks[i % len(picks)]

    if side == "offense":
        fill_bucket("opening", ["INSIDE_RUN", "OUTSIDE_RUN", "SHORT_PASS"])
        fill_bucket("base_dd", ["INSIDE_RUN", "OUTSIDE_RUN", "SHORT_PASS", "MEDIUM_PASS"])
        fill_bucket("third_long", ["MEDIUM_PASS", "LONG_PASS"])
        fill_bucket("third_medium", ["SHORT_PASS", "MEDIUM_PASS"])
        fill_bucket("third_short", ["INSIDE_RUN", "OUTSIDE_RUN"])
        fill_bucket("fourth_long", ["MEDIUM_PASS", "LONG_PASS"])
        fill_bucket("fourth_medium", ["SHORT_PASS", "MEDIUM_PASS"])
        fill_bucket("fourth_short", ["INSIDE_RUN", "OUTSIDE_RUN"])
        fill_bucket("red_zone", ["INSIDE_RUN", "SHORT_PASS", "PLAY_ACTION"])
        fill_bucket("backed_up", ["OUTSIDE_RUN", "SHORT_PASS"])
        fill_bucket("goal_line", ["INSIDE_RUN", "PLAY_ACTION"])
        fill_bucket("two_minute", ["SHORT_PASS", "MEDIUM_PASS"])
    else:
        fill_bucket("base_dd", ["ZONES", "MANS", "ZONE_PRESSURE", "MAN_PRESSURE"])
        fill_bucket("third_long", ["ZONES", "ZONE_PRESSURE", "MAN_PRESSURE"])
        fill_bucket("third_medium", ["ZONES", "MANS"])
        fill_bucket("third_short", ["ZONES", "MANS"])
        fill_bucket("fourth_long", ["ZONE_PRESSURE", "MAN_PRESSURE"])
        fill_bucket("fourth_medium", ["ZONES", "MAN_PRESSURE"])
        fill_bucket("fourth_short", ["ZONES", "MANS"])
        fill_bucket("red_zone", ["ZONES", "MANS"])
        fill_bucket("goal_line", ["ZONES", "MANS"])
        fill_bucket("opponent_backed_up", ["MAN_PRESSURE", "ZONE_PRESSURE"])
        fill_bucket("two_minute", ["ZONES", "MANS"])
    return cs


def autofill_side_package(team: Any, side: str) -> Dict[str, Any]:
    pkg = default_side_package(side)
    coach = getattr(team, "coach", None)
    style = getattr(coach, "offensive_style", None) if side == "offense" and coach else None
    if side == "offense" and style is not None:
        name = getattr(style, "name", "")
        if "PASS" in str(name).upper():
            pkg["gameplan_mode"] = "callsheet"
        pkg["callsheet"] = autofill_callsheet_from_install(team, side)
    elif side == "defense":
        pkg["callsheet"] = autofill_callsheet_from_install(team, side)
    return pkg


def attach_cpu_coach_packages_for_game(
    home_team: Any,
    away_team: Any,
    *,
    user_team: Optional[str] = None,
    cpu_teams: Optional[set[str]] = None,
) -> None:
    """Attach autofill weekly packages to non-user coaches before sim."""
    for team in (home_team, away_team):
        name = getattr(team, "name", "")
        if cpu_teams is not None:
            if name not in cpu_teams:
                continue
        elif user_team and name == user_team:
            continue
        coach = getattr(team, "coach", None)
        if coach is None:
            continue
        off_pkg = autofill_side_package(team, "offense")
        def_pkg = autofill_side_package(team, "defense")
        script = default_team_script()
        entry = {
            "offense_package": off_pkg,
            "defense_package": def_pkg,
            "team_script": script,
        }
        apply_packages_to_coach(coach, entry)


def export_full_package(entry: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_matchup_entry(entry)
    return {
        "version": PACKAGE_VERSION,
        "offense_package": norm["offense_package"],
        "defense_package": norm["defense_package"],
        "team_script": norm["team_script"],
    }
