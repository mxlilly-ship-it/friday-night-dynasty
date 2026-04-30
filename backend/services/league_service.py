import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.storage.db import db
from systems.save_system import (
    get_save_dir,
    save_league,
    ensure_save_has_history_and_records,
    player_to_dict,
    team_from_dict,
    team_to_dict,
)
from systems.teams_loader import build_teams_from_json, build_teams_from_configs
from models.coach import apply_coach_config_dict
from systems.league_structure import (
    default_league_structure,
    ensure_league_structure_in_state,
    playoff_pool_team_names,
)
from run_season import init_season_stats, parse_scores_from_final_line, run_game_silent, run_scrimmage_game
from systems.playoff_system import run_next_playoff_round_8, run_playoff, seed_teams
from systems.league_history import append_season
from systems.prestige_system import update_prestige
from systems.development_system import (
    build_ai_winter_training_allocations,
    normalize_winter_training_allocations,
    run_offseason_development,
    run_spring_ball_development,
    run_winter_training_session,
)
from systems.offseason_manager import reset_team_season_stats, run_offseason_roster_turnover
from systems.team_ratings import calculate_player_overall
from systems.league_history import load_league_history
from systems.save_system import league_history_path
from systems.win_path_io import (
    io_path_candidates,
    isfile_any,
    makedirs_with_path_fallback,
    open_binary_with_path_fallback,
    open_text_with_path_fallback,
    os_replace_with_path_fallback,
    shutil_move_with_fallback,
    unlink_if_exists_any,
)
from systems.coach_development import (
    COACH_DEV_SKILLS,
    apply_ai_coach_season_development,
    apply_coach_development,
    build_offseason_coach_dev_banks_for_league,
    compute_coach_development_bank,
)
from systems.position_changes import apply_position_changes_to_team, run_ai_position_changes_for_team
from systems.regional_titles import award_regular_season_regional_titles
from systems.play_selection import (
    run_play_selection_for_team,
    run_play_selection_results_for_team,
    compute_learning_summary,
    OFFENSIVE_CATEGORIES,
    DEFENSIVE_CATEGORIES,
)
from systems.preferred_playbook import (
    PREFERRED_PLAYBOOK_CHANGE_INTERVAL_SEASONS,
    coach_may_change_preferred_playbooks,
    coach_record_preferred_playbook_change,
    next_eligible_season_for_preferred_playbooks,
)
from systems.playbook_system import (
    build_playbook_for_team,
    normalize_coach_defensive_front,
    normalize_coach_offensive_playbook,
)
from systems.transfer_system import run_transfer_stage_1, run_transfer_stage_2
from backend.services.game_service import create_game as create_game_record
from backend.services.game_service import game_state_dict, build_coach_postgame_box_assets
from systems.game_stats import (
    season_stats_map_from_jsonable,
    season_stats_map_to_jsonable,
    player_game_stats_map_to_json_list,
)
from systems.gameplan_v2 import (
    make_default_offense_plan as make_default_offense_gameplan_v2,
    make_default_defense_plan as make_default_defense_gameplan_v2,
    validate_plan as validate_gameplan_v2,
    OFFENSE_CATEGORIES as GAMEPLAN_V2_OFF_CATEGORIES,
    DEFENSE_CATEGORIES as GAMEPLAN_V2_DEF_CATEGORIES,
)

logger = logging.getLogger(__name__)


def _apply_user_preseason_playbook_payload(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    playbook: Dict[str, Any],
) -> None:
    """Apply Playbook Select payload for the user coach; enforces the preferred-playbook change interval."""
    if not playbook:
        return
    user_team = state.get("user_team")
    if not user_team or user_team not in teams:
        return
    coach = teams[user_team].coach
    if not coach:
        return
    cy = max(1, int(state.get("current_year", 1)))
    new_off = None
    new_def = None
    if "offensive_playbook" in playbook:
        new_off = normalize_coach_offensive_playbook(playbook["offensive_playbook"])
    if "defensive_playbook" in playbook:
        new_def = normalize_coach_defensive_front(playbook["defensive_playbook"])
    if new_off is None and new_def is None:
        return
    cur_off = normalize_coach_offensive_playbook(getattr(coach, "offensive_formation", ""))
    cur_def = normalize_coach_defensive_front(getattr(coach, "defensive_formation", ""))
    changing_off = new_off is not None and new_off != cur_off
    changing_def = new_def is not None and new_def != cur_def
    if changing_off or changing_def:
        if not coach_may_change_preferred_playbooks(coach, cy):
            nxt = next_eligible_season_for_preferred_playbooks(coach)
            raise ValueError(
                f"Preferred playbooks can only be changed once every {PREFERRED_PLAYBOOK_CHANGE_INTERVAL_SEASONS} seasons "
                f"(next eligible season: {nxt})."
            )
    if new_off is not None:
        coach.offensive_formation = new_off
    if new_def is not None:
        coach.defensive_formation = new_def
    if changing_off or changing_def:
        coach_record_preferred_playbook_change(coach, cy)


def format_recap_schedule_line(
    week_index_0: int,
    team_name: str,
    home: Any,
    away: Any,
    played: bool,
    home_score: int,
    away_score: int,
    ot: bool,
) -> str:
    """Single SCHEDULE line for season recap .txt: includes W / L / T when played."""
    loc = "vs" if team_name == home else "@"
    opp = away if team_name == home else home
    if not played:
        return f"Week {week_index_0 + 1}: {loc} {opp} — (not played)"
    hs = int(home_score)
    as_ = int(away_score)
    my = hs if team_name == home else as_
    opps = as_ if team_name == home else hs
    if my > opps:
        wl = "W"
    elif my < opps:
        wl = "L"
    else:
        wl = "T"
    ot_s = " (OT)" if ot else ""
    return f"Week {week_index_0 + 1}: {loc} {opp} — {wl} {my}-{opps}{ot_s}"


_RECAP_PLAYOFF_ROUND_ORDER = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}


def format_recap_playoff_line(team_name: str, game: Dict[str, Any]) -> str:
    """Single POSTSEASON line for season recap .txt (team's playoff game)."""
    rnd = str(game.get("round") or "Playoff")
    home = game.get("home")
    away = game.get("away")
    hs = int(game.get("home_score", 0) or 0)
    as_ = int(game.get("away_score", 0) or 0)
    ot = bool(game.get("ot", False))
    loc = "vs" if team_name == home else "@"
    opp = away if team_name == home else home
    my = hs if team_name == home else as_
    opps = as_ if team_name == home else hs
    if my > opps:
        wl = "W"
    elif my < opps:
        wl = "L"
    else:
        wl = "T"
    ot_s = " (OT)" if ot else ""
    return f"{rnd}: {loc} {opp} — {wl} {my}-{opps}{ot_s}"


def recap_postseason_lines_for_team(team_name: str, bracket_results: List[Dict[str, Any]]) -> List[str]:
    """Ordered playoff game lines for one team (empty if they did not play in the bracket)."""
    if not team_name or not bracket_results:
        return []
    games: List[Tuple[int, Dict[str, Any]]] = []
    for g in bracket_results:
        if not isinstance(g, dict):
            continue
        h, a = g.get("home"), g.get("away")
        if h != team_name and a != team_name:
            continue
        rnd = str(g.get("round") or "")
        order = _RECAP_PLAYOFF_ROUND_ORDER.get(rnd, 0)
        games.append((order, g))
    games.sort(key=lambda x: x[0])
    return [format_recap_playoff_line(team_name, g) for _, g in games]


def _classification_of_team(teams: Dict[str, Any], name: Optional[str]) -> str:
    if not name or name not in teams:
        return "UNK"
    t = teams[name]
    if isinstance(t, dict):
        c = t.get("classification")
    else:
        c = getattr(t, "classification", None)
    return str(c).strip() or "UNK"


def _team_names_by_classification(teams: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for name in teams:
        c = _classification_of_team(teams, name)
        out.setdefault(c, []).append(name)
    for k in out:
        out[k] = sorted(out[k])
    return out


def _playoffs_global_completed(playoffs: Dict[str, Any]) -> bool:
    bc = playoffs.get("by_class")
    if isinstance(bc, dict) and bc:
        return all(bool(x.get("completed")) for x in bc.values() if isinstance(x, dict))
    return bool(playoffs.get("completed"))


def _ensure_playoffs_migrated(state: Dict[str, Any], teams: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure playoffs use ``by_class`` + ``user_class``; migrate legacy single bracket."""
    p = state.setdefault("playoffs", {})
    if not isinstance(p, dict):
        state["playoffs"] = {}
        p = state["playoffs"]
    if isinstance(p.get("by_class"), dict) and p["by_class"]:
        if not p.get("user_class"):
            ut = state.get("user_team")
            p["user_class"] = _classification_of_team(teams, ut) if ut else next(iter(p["by_class"]), None)
        return p
    if p.get("seeds") is not None or p.get("bracket_results") is not None:
        ut = state.get("user_team")
        uc = _classification_of_team(teams, ut) if ut else "UNK"
        inner = {
            "num_teams": int(p.get("num_teams") or 8),
            "seeds": list(p.get("seeds") or []),
            "bracket_results": list(p.get("bracket_results") or []),
            "completed": bool(p.get("completed")),
            "champion": p.get("champion"),
            "runner_up": p.get("runner_up"),
        }
        p["by_class"] = {uc: inner}
        p["user_class"] = uc
    return p


def _init_playoffs_multiclass(state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]) -> Dict[str, Any]:
    """One 8-team bracket per classification with at least 8 schools."""
    groups = _team_names_by_classification(teams)
    by_class: Dict[str, Any] = {}
    for cls, names in groups.items():
        if len(names) < 8:
            continue
        seeded = seed_teams(names, standings, top_n=8)
        by_class[cls] = {
            "num_teams": 8,
            "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        }
    ut = state.get("user_team")
    uc = _classification_of_team(teams, ut) if ut else None
    if uc and uc not in by_class:
        pool = _playoff_pool_team_names(state, teams)
        if len(pool) >= 8:
            seeded = seed_teams(pool, standings, top_n=8)
            by_class[uc] = {
                "num_teams": 8,
                "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
                "bracket_results": [],
                "completed": False,
                "champion": None,
                "runner_up": None,
            }
    if not by_class:
        pool = _playoff_pool_team_names(state, teams)
        if len(pool) >= 8:
            seeded = seed_teams(pool, standings, top_n=8)
            key = uc or "UNK"
            by_class[key] = {
                "num_teams": 8,
                "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
                "bracket_results": [],
                "completed": False,
                "champion": None,
                "runner_up": None,
            }
            uc = key
    return {
        "by_class": by_class,
        "user_class": uc or (next(iter(by_class)) if by_class else None),
        "completed": False,
    }


def _ensure_all_eligible_playoff_brackets(
    state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]
) -> None:
    """Ensure ``playoffs.by_class`` has a bracket for every classification with ≥8 teams.

    Idempotent: does not remove or reset brackets that already have seeds or any played games.
    Needed because legacy migration and early init only stored the user's class, so other classes
    never received a ``by_class`` entry even when eligible.
    """
    playoffs = state.setdefault("playoffs", {})
    if not isinstance(playoffs, dict):
        state["playoffs"] = {}
        playoffs = state["playoffs"]
    groups = _team_names_by_classification(teams)
    bc = playoffs.setdefault("by_class", {})
    for cls, names in groups.items():
        if len(names) < 8:
            continue
        if cls in bc and isinstance(bc[cls], dict):
            sub = bc[cls]
            seeds = sub.get("seeds")
            br = sub.get("bracket_results") or []
            if isinstance(seeds, list) and len(seeds) >= 1:
                continue
            if isinstance(br, list) and len(br) > 0:
                continue
        seeded = seed_teams(names, standings, top_n=8)
        bc[cls] = {
            "num_teams": 8,
            "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        }
    playoffs["by_class"] = bc
    ut = state.get("user_team")
    if ut and not playoffs.get("user_class"):
        playoffs["user_class"] = _classification_of_team(teams, ut)


def _flatten_playoff_bracket_results(playoffs: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(playoffs, dict):
        return []
    bc = playoffs.get("by_class")
    if isinstance(bc, dict) and bc:
        out: List[Dict[str, Any]] = []
        for pdata in bc.values():
            if isinstance(pdata, dict):
                out.extend(list(pdata.get("bracket_results") or []))
        return out
    return list(playoffs.get("bracket_results") or [])


def _recap_merged_bracket_results(state: Dict[str, Any], bracket_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer flattened multiclass brackets so per-team recaps and labels see all playoff games."""
    po = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
    if po:
        flat = _flatten_playoff_bracket_results(po)
        if flat:
            return flat
    return [g for g in (bracket_results or []) if isinstance(g, dict)]


_LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def _safe_logo_name(team_name: str) -> str:
    cleaned = "".join(c for c in str(team_name or "") if c.isalnum() or c in " _-").strip()
    if not cleaned:
        cleaned = "team"
    return cleaned


def _safe_path_segment(s: str, *, default: str = "user") -> str:
    """Single directory name safe on Windows (no | : ? * etc.). Auth subs often use ``provider|id``."""
    cleaned = "".join(c for c in str(s or "") if c.isalnum() or c in " _-").strip() or default
    # Windows device names are invalid as path components even with extensions.
    if cleaned.upper() in {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        cleaned = f"_{cleaned}_"
    return cleaned


def _normalize_name(s: str) -> str:
    raw = str(s or "").strip().lower()
    return "".join(c for c in raw if c.isalnum())


def _saves_base_dir() -> str:
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "saves")
    return os.path.abspath(base)


def _get_user_logo_dir(user_id: str) -> str:
    safe_user = _safe_path_segment(user_id, default="user")
    return os.path.join(_saves_base_dir(), safe_user, "_logos")


def save_team_logo(user_id: str, team_name: str, data: bytes, extension: str) -> str:
    ext = str(extension or "").lower().strip()
    if ext not in _LOGO_EXTENSIONS:
        raise ValueError("Unsupported logo file type. Use PNG, JPG, JPEG, or WEBP.")
    if not data:
        raise ValueError("Logo file is empty.")
    safe_name = _safe_logo_name(team_name)
    logo_dir = _get_user_logo_dir(user_id)
    logo_dir_abs = os.path.abspath(os.path.normpath(logo_dir))
    try:
        makedirs_with_path_fallback(logo_dir_abs)
    except OSError:
        os.makedirs(logo_dir, exist_ok=True)
    for old_ext in _LOGO_EXTENSIONS:
        unlink_if_exists_any(os.path.abspath(os.path.join(logo_dir, f"{safe_name}{old_ext}")))
    out_plain = os.path.abspath(os.path.join(logo_dir, f"{safe_name}{ext}"))
    f = open_binary_with_path_fallback(out_plain, "wb")
    try:
        f.write(data)
        return f.name
    finally:
        f.close()


def get_team_logo_path(user_id: str, team_name: str) -> Optional[str]:
    safe_name = _safe_logo_name(team_name)
    logo_dir = _get_user_logo_dir(user_id)
    for ext in _LOGO_EXTENSIONS:
        plain = os.path.abspath(os.path.join(logo_dir, f"{safe_name}{ext}"))
        for p in io_path_candidates(plain):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                continue
    return None


def _stem_variants_for_logo_match(stem: str) -> List[str]:
    """Try filename stems with common suffixes stripped (e.g. Martinsburg_logo → Martinsburg)."""
    stem = str(stem or "").strip()
    if not stem:
        return []
    variants: List[str] = [stem]
    for suffix in ("_logo", "-logo", "_LOGO", "-LOGO", " logo"):
        if len(stem) > len(suffix) and stem.lower().endswith(suffix.lower()):
            variants.append(stem[: -len(suffix)].strip())
    out: List[str] = []
    seen = set()
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def match_logo_filename_to_team(teams: List[str], filename_stem: str) -> Optional[str]:
    by_norm: Dict[str, str] = {}
    for t in teams:
        name = str(t or "").strip()
        if not name:
            continue
        by_norm[_normalize_name(name)] = name
    for stem in _stem_variants_for_logo_match(filename_stem):
        stem_norm = _normalize_name(stem)
        if stem_norm and stem_norm in by_norm:
            return by_norm[stem_norm]
    return None


PRESEASON_STAGES: List[str] = [
    "Playbook Select",
    "Play Selection",
    "Play Selection Results",
    "Position changes",
    "Set Depth Chart",
    "Scrimmage 1",
    "Scrimmage 2",
    "Set Goals",
]


def _apply_preseason_position_changes_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    playbook: Dict[str, Any],
) -> None:
    """User team: optional list of position changes. Other teams: AI re-rates positions."""
    user_team_name = state.get("user_team")
    raw = playbook.get("position_changes") if isinstance(playbook, dict) else None
    changes = raw if isinstance(raw, list) else []
    for name, t in teams.items():
        if name == user_team_name:
            apply_position_changes_to_team(t, changes)
        else:
            run_ai_position_changes_for_team(t)

OFFSEASON_UI_STAGES: List[str] = [
    "Graduation",
    "Coach development",
    "Winter 1",
    "Winter 2",
    "Spring Ball",
    "Transfers I",
    "Transfers II",
    "Transfers III",
    "7 on 7",
    "Training Results",
    "Freshman Class",
    "Improvements",
    "Coaching carousel I",
    "Coaching carousel II",
    "Coaching carousel III",
    "Schedule Release",
]


def _normalize_offseason_stage_name(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    lowered = s.lower()
    compact = "".join(ch for ch in lowered if ch.isalnum())
    if compact in ("coachdevelopment", "coachingdevelopment"):
        return "Coach development"
    if compact in ("transfers", "transfer"):
        return "Transfers I"
    if compact in ("transfersi", "transferi", "transferstage1"):
        return "Transfers I"
    if compact in ("transfersii", "transferii", "transferstage2"):
        return "Transfers II"
    if compact in ("transfersiii", "transferiii", "transferstage3", "transferreview"):
        return "Transfers III"
    return s


def _winter_allocations_from_legacy_strength_pct(strength_pct: int) -> Dict[str, int]:
    s = max(0, min(100, int(strength_pct)))
    alloc = {
        "squat": int(round(s * 0.35)),
        "bench": int(round(s * 0.25)),
        "cleans": int(round((100 - s) * 0.3)),
        "cod": int(round((100 - s) * 0.2)),
        "speed": int(round((100 - s) * 0.25)),
        "plyometrics": int(round((100 - s) * 0.15)),
        "football_iq": 0,
    }
    return normalize_winter_training_allocations(alloc)


def _improvement_pp_delta(from_level: int, to_level: int) -> int:
    """
    Compute PP delta for moving a single program grade between levels.
    Upgrades cost PP; downgrades refund PP.

    Cost pattern: 1→2 = 20, 2→3 = 40, ..., 9→10 = 180 (20 * current level).
    """
    a = max(1, min(10, int(from_level or 1)))
    b = max(1, min(10, int(to_level or 1)))
    if b == a:
        return 0
    if b > a:
        cost = sum(20 * k for k in range(a, b))
        return -int(cost)
    refund = sum(20 * k for k in range(b, a))
    return int(refund)


def _postseason_tier_for_team(team_name: str, standings: Dict[str, Any], bracket_results: List[Dict[str, Any]], champion: str) -> str:
    """
    Returns one of: "champion" | "championship" | "semifinal" | "playoffs" | "none"
    """
    if not team_name:
        return "none"
    if team_name == (champion or ""):
        return "champion"
    made_playoffs = any(
        isinstance(g, dict) and (g.get("home") == team_name or g.get("away") == team_name)
        for g in (bracket_results or [])
    )
    # Determine furthest round reached from bracket results
    best = 0
    order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
    for g in bracket_results or []:
        if not isinstance(g, dict):
            continue
        if g.get("home") != team_name and g.get("away") != team_name:
            continue
        rnd = str(g.get("round") or "")
        best = max(best, int(order.get(rnd, 0)))
    if best >= 3:
        return "championship"
    if best >= 2:
        return "semifinal"
    if made_playoffs:
        return "playoffs"
    return "none"


def _season_pp_awards_for_team(
    team_name: str,
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    season_goals: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Award points earned during the season that can be spent on Improvements.

    Rules (as requested):
    - win: +0.5
    - loss: -0.5
    - postseason bonus (max tier):
      playoffs: +1, semifinal: +2, championship: +4, champion: +6
    - fail to make a goal: -2 (evaluated for win goal and stage goal independently)
    """
    srow = (standings or {}).get(team_name) or {}
    wins = int(srow.get("wins", 0) or 0)
    losses = int(srow.get("losses", 0) or 0)
    wl_points = 0.5 * wins - 0.5 * losses

    tier = _postseason_tier_for_team(team_name, standings, bracket_results, champion)
    tier_points_map = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 4, "champion": 6}
    postseason_points = float(tier_points_map.get(tier, 0))

    # Goals
    goal_fail = 0
    win_goal = None
    stage_goal = None
    if isinstance(season_goals, dict):
        try:
            win_goal = int(season_goals.get("win_goal")) if season_goals.get("win_goal") is not None else None
        except Exception:
            win_goal = None
        stage_goal = str(season_goals.get("stage_goal") or "").strip() or None

    if win_goal is not None and wins < win_goal:
        goal_fail += 1

    achieved_rank = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(tier, 0)
    goal_rank = None
    if stage_goal:
        # Map UI goal strings to a comparable rank.
        if stage_goal == "Winning Season":
            # "Winning season" = at least .500
            goal_rank = 0 if wins >= losses else 999
        elif stage_goal == "Playoffs":
            goal_rank = 1
        elif stage_goal == "Semifinal":
            goal_rank = 2
        elif stage_goal == "State Championship":
            goal_rank = 3
        elif stage_goal == "Title Winner":
            goal_rank = 4
    if goal_rank is not None:
        if goal_rank == 999:
            goal_fail += 1
        elif achieved_rank < goal_rank:
            goal_fail += 1

    goal_points = -2.0 * float(goal_fail)
    total = wl_points + postseason_points + goal_points
    # Store PP as integer (allow halves by rounding to nearest int, with .5 up)
    pp_total = int(round(total))

    return {
        "team": team_name,
        "wins": wins,
        "losses": losses,
        "wl_points": wl_points,
        "postseason_tier": tier,
        "postseason_points": postseason_points,
        "goal_fail_count": goal_fail,
        "goal_points": goal_points,
        "total_raw": total,
        "pp_total": pp_total,
    }


def normalize_offseason_stages(state: Dict[str, Any]) -> bool:
    """
    Migrate in-memory offseason stage list/index when OFFSEASON_UI_STAGES grows (old saves on disk).
    Maps by stage name so the player stays on the same logical step.
    Returns True if state was changed.
    """
    if str(state.get("season_phase") or "").strip().lower() != "offseason":
        return False
    canonical = list(OFFSEASON_UI_STAGES)
    current = list(state.get("offseason_stages") or [])
    if current == canonical:
        return False

    raw_idx = int(state.get("offseason_stage_index", 0))
    if current:
        idx = max(0, min(raw_idx, len(current) - 1))
        old_stage = _normalize_offseason_stage_name(current[idx])
    else:
        old_stage = None

    state["offseason_stages"] = canonical
    if old_stage and old_stage in canonical:
        state["offseason_stage_index"] = canonical.index(old_stage)
    else:
        state["offseason_stage_index"] = max(0, min(raw_idx, len(canonical) - 1))
    return True


def _regular_season_week_boards(
    teams: Dict[str, Any],
    state: Dict[str, Any],
) -> Tuple[List[List[Dict[str, str]]], List[List[Dict[str, Any]]]]:
    """Build ``weeks`` + empty ``week_results`` from classification/region pods."""
    from systems.league_structure import build_regular_season_weeks

    raw = build_regular_season_weeks(teams, state)
    weeks: List[List[Dict[str, str]]] = [[{"home": h, "away": a} for (h, a) in wk] for wk in raw]
    week_results: List[List[Dict[str, Any]]] = [
        [{"played": False, "home_score": 0, "away_score": 0, "ot": False} for _ in wk] for wk in weeks
    ]
    return weeks, week_results


def _playoff_pool_team_names(state: Dict[str, Any], teams: Dict[str, Any]) -> List[str]:
    return playoff_pool_team_names(state, teams)


def _assign_scrimmage_opponents_for_state(state: Dict[str, Any]) -> None:
    """Pick two scrimmage opponents for the user team; excludes regular-season opponents. Persists in state."""
    user_team_name = state.get("user_team")
    team_names = [t.get("name") for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
    if not user_team_name or user_team_name not in team_names:
        state["preseason_scrimmage_opponents"] = []
        return
    scheduled_opponents = set()
    for wk in state.get("weeks") or []:
        for g in wk or []:
            if isinstance(g, dict):
                h, a = g.get("home"), g.get("away")
                if h == user_team_name and a:
                    scheduled_opponents.add(a)
                elif a == user_team_name and h:
                    scheduled_opponents.add(h)
    eligible = [t for t in team_names if t != user_team_name and t not in scheduled_opponents]
    if not eligible:
        eligible = [t for t in team_names if t != user_team_name]
    if len(eligible) >= 2:
        chosen = random.sample(eligible, 2)
        state["preseason_scrimmage_opponents"] = [
            {"opponent": chosen[0], "user_home": random.random() < 0.5},
            {"opponent": chosen[1], "user_home": random.random() < 0.5},
        ]
    elif len(eligible) == 1:
        state["preseason_scrimmage_opponents"] = [
            {"opponent": eligible[0], "user_home": random.random() < 0.5},
            {"opponent": eligible[0], "user_home": random.random() >= 0.5},
        ]
    else:
        state["preseason_scrimmage_opponents"] = []


def _snapshot_player_overalls(team: Any) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for player in list(team.roster):
        out[player.name] = calculate_player_overall(player)
    return out


def _finalize_offseason_to_preseason(state: Dict[str, Any], teams: Dict[str, Any]) -> None:
    """After interactive offseason: play selection + results for user team, reset W/L, enter preseason."""
    user_team_name = state.get("user_team")
    ut = teams.get(user_team_name) if user_team_name else None
    if ut:
        try:
            run_play_selection_for_team(ut)
        except Exception:
            logger.exception("run_play_selection_for_team (offseason finalize)")
        try:
            run_play_selection_results_for_team(ut)
        except Exception:
            logger.exception("run_play_selection_results_for_team (offseason finalize)")
    for t in teams.values():
        reset_team_season_stats(t)
    state["season_phase"] = "preseason"
    state["preseason_stage_index"] = 0
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["current_week"] = 1
    state["preseason_scrimmages"] = []
    state.pop("offseason_stage_index", None)
    state.pop("offseason_stages", None)
    state.pop("offseason_training_results", None)
    state.pop("offseason_graduation_report", None)
    state.pop("offseason_coach_dev_bank", None)
    state.pop("offseason_coach_dev_banks", None)
    state.pop("offseason_spring_ball_results", None)
    state.pop("offseason_winter_training_results", None)
    state.pop("offseason_coach_carousel", None)
    state.pop("offseason_coach_carousel_last_events", None)
    state.pop("offseason_coach_carousel_hot_seat", None)


def _empty_coach_dev_bank() -> Dict[str, Any]:
    return {
        "cp_total": 0.0,
        "allocated_total": 0.0,
        "available_cp": 0.0,
        "allocations": {sk: 0.0 for sk in COACH_DEV_SKILLS},
        "levels": {sk: 1 for sk in COACH_DEV_SKILLS},
        "thresholds": {1: 0, 2: 20, 3: 50, 4: 90, 5: 140, 6: 200, 7: 275, 8: 350, 9: 425, 10: 500},
        "breakdown": None,
        "applied": None,
    }


def _merge_user_coach_development_body(bank: Dict[str, Any], body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure apply_coach_development receives coach_dev_allocations object."""
    out: Dict[str, Any] = dict(body) if isinstance(body, dict) else {}
    alloc = out.get("coach_dev_allocations")
    if not isinstance(alloc, dict):
        alloc = bank.get("allocations")
    if not isinstance(alloc, dict):
        alloc = {sk: 0.0 for sk in COACH_DEV_SKILLS}
    out["coach_dev_allocations"] = {sk: float(alloc.get(sk, 0.0) or 0.0) for sk in COACH_DEV_SKILLS}
    return out


def _apply_coaching_carousel_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    league_history: Dict[str, Any],
    step_name: str,
) -> None:
    """Run one coaching carousel step; mutates teams and state. Clears carousel blob after step III."""
    from systems.coach_carousel import run_coach_carousel_step

    sg = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    ut = state.get("user_team")
    carousel_year = max(1, int(state.get("current_year", 1)))
    step_map = {"Coaching carousel I": 1, "Coaching carousel II": 2, "Coaching carousel III": 3}
    step = step_map[step_name]
    persist_in = None if step == 1 else state.get("offseason_coach_carousel")
    if step > 1 and persist_in is None:
        raise ValueError("Coaching carousel state is missing; reload your save or continue from Improvements.")
    persist, events, cc, hs = run_coach_carousel_step(
        teams,
        league_history,
        state.get("standings"),
        step,
        persist_in,
        ut,
        sg,
        carousel_year,
    )
    state["offseason_coach_carousel"] = persist
    state["offseason_coach_carousel_last_events"] = (events or [])[-40:]
    state["offseason_coach_carousel_hot_seat"] = hs or {}
    if step == 3:
        update_prestige(teams, league_history, coach_changes=cc)
        season_year = max(1, int(state.get("current_year", 1)) - 1)
        ch = list(state.get("coaching_history") or [])
        ch.append({"year": season_year, "events": list(events or []), "hot_seat_by_team": dict(hs or {})})
        state["coaching_history"] = ch[-100:]
        state.pop("offseason_coach_carousel", None)


TRANSFER_NEWS_TEMPLATES: List[str] = [
    "[PLAYER] ([POSITION]) enters the portal from [TEAM] in [REGION].",
    "Portal watch: [PLAYER] leaves [TEAM], seeking a better role in [REGION].",
    "[TEAM] sees [PLAYER] ([POSITION]) test transfer options around [REGION].",
    "[PLAYER] starts a transfer search after offseason changes at [TEAM].",
    "Depth-chart ripple: [PLAYER] ([POSITION]) exits [TEAM] in [REGION].",
    "[PLAYER] enters the portal from [TEAM] after weighing playing time.",
    "Transfer signal from [TEAM]: [PLAYER] ([POSITION]) is now available.",
    "[PLAYER] chooses the portal route out of [TEAM], region [REGION].",
    "[TEAM] loses [PLAYER] to the portal wave in [REGION].",
    "Coaches track [PLAYER] ([POSITION]) after portal entry from [TEAM].",
    "[PLAYER] departs [TEAM] for transfer opportunities in [REGION].",
    "Offseason movement: [PLAYER] leaves [TEAM] and enters the portal.",
    "[TEAM] confirms [PLAYER] ([POSITION]) is entering transfer circulation.",
    "[PLAYER] seeks a fresh start away from [TEAM] in [REGION].",
    "[TEAM] portal update: [PLAYER] now exploring transfer destinations.",
    "[PLAYER] transfers from [TEAM] to [DEST_TEAM] ([REGION]).",
    "Destination set: [PLAYER] ([POSITION]) lands at [DEST_TEAM] from [TEAM].",
    "Transfer finalized: [DEST_TEAM] adds [PLAYER] out of [TEAM].",
    "[DEST_TEAM] strengthens with [PLAYER], formerly of [TEAM].",
    "[PLAYER] completes move from [TEAM] to [DEST_TEAM] in [REGION].",
    "[DEST_TEAM] wins a portal battle for [PLAYER] ([POSITION]).",
    "Roster move: [PLAYER] exits [TEAM] and joins [DEST_TEAM].",
    "[PLAYER] finds a new home at [DEST_TEAM] after leaving [TEAM].",
    "Portal resolution: [DEST_TEAM] signs transfer [PLAYER] from [TEAM].",
    "[PLAYER] switches colors, moving [TEAM] -> [DEST_TEAM].",
    "[DEST_TEAM] lands [PLAYER] ([POSITION]) in regional transfer cycle.",
    "Transfer wire: [PLAYER] departs [TEAM] for [DEST_TEAM].",
    "[PLAYER] completes regional move to [DEST_TEAM] from [TEAM].",
    "[DEST_TEAM] adds depth with transfer [PLAYER] from [TEAM].",
    "[PLAYER] and [DEST_TEAM] finalize transfer after offseason portal process.",
]


def _transfer_render(template: str, payload: Dict[str, Any]) -> str:
    out = template
    for k, v in payload.items():
        out = out.replace(f"[{k}]", str(v))
    return out


def _append_transfer_news_events(state: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
    existing = list(state.get("offseason_transfer_news_events") or [])
    existing.extend(events)
    state["offseason_transfer_news_events"] = existing[-120:]


SPRING_OFFENSE_FOCUS_OPTIONS: Tuple[str, ...] = ("run_blocking", "pass_protection", "receiving", "pass_game", "run_game")
SPRING_DEFENSE_FOCUS_OPTIONS: Tuple[str, ...] = ("run_defense", "pass_rush", "tackling", "pass_defense", "block_defeat")


def _assign_cpu_spring_ball_focuses(teams: Dict[str, Team], user_team_name: str) -> None:
    """Spread CPU spring-ball focuses so coaches don't all pick the same options."""
    cpu_names = [n for n, t in teams.items() if n != user_team_name and getattr(t, "coach", None) is not None]
    if not cpu_names:
        return
    random.shuffle(cpu_names)
    off_shift = random.randrange(len(SPRING_OFFENSE_FOCUS_OPTIONS))
    def_shift = random.randrange(len(SPRING_DEFENSE_FOCUS_OPTIONS))
    for i, name in enumerate(cpu_names):
        coach = getattr(teams[name], "coach", None)
        if coach is None:
            continue
        off = SPRING_OFFENSE_FOCUS_OPTIONS[(i + off_shift) % len(SPRING_OFFENSE_FOCUS_OPTIONS)]
        de = SPRING_DEFENSE_FOCUS_OPTIONS[((i * 2) + def_shift) % len(SPRING_DEFENSE_FOCUS_OPTIONS)]
        prev_off = str(getattr(coach, "spring_offense_focus", "") or "")
        prev_def = str(getattr(coach, "spring_defense_focus", "") or "")
        if prev_off == off and prev_def == de:
            de = SPRING_DEFENSE_FOCUS_OPTIONS[(SPRING_DEFENSE_FOCUS_OPTIONS.index(de) + 1) % len(SPRING_DEFENSE_FOCUS_OPTIONS)]
        coach.spring_offense_focus = off
        coach.spring_defense_focus = de


def advance_offseason(
    user_id: str,
    save_id: str,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Advance one interactive offseason stage (winter x2, spring, placeholders, training, schedule).
    Final Continue after Schedule Release moves the save into preseason (play selection already resolved in finalize).
    Freshman Class is view-only (incoming freshmen are already on the roster after year rollover).
    """
    state, save_dir = load_state(user_id, save_id)
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "offseason":
        raise ValueError("save is not in offseason")

    body = body or {}
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    stages: List[str] = list(state.get("offseason_stages") or OFFSEASON_UI_STAGES)
    state["offseason_stages"] = stages
    idx = int(state.get("offseason_stage_index", 0))
    if idx >= len(stages):
        raise ValueError("offseason already complete; load save or continue from preseason")

    current = _normalize_offseason_stage_name(stages[idx])
    user_team_name = state.get("user_team")
    ut = teams.get(user_team_name) if user_team_name else None

    if current in ("Winter 1", "Winter 2"):
        winter_results = state.get("offseason_winter_training_results")
        ack_winter = bool(body.get("winter_training_ack_results"))
        if isinstance(winter_results, dict) and str(winter_results.get("stage") or "") == current and ack_winter:
            state.pop("offseason_winter_training_results", None)
        elif isinstance(winter_results, dict) and str(winter_results.get("stage") or "") == current and not ack_winter:
            raise ValueError("Review Winter training results, then press Continue again to advance.")
        else:
            ws = body.get("winter_strength_pct")
            if ws is not None and ut and ut.coach:
                ut.coach.winter_strength_pct = max(0, min(100, int(ws)))

            results_by_team: Dict[str, Any] = {}
            user_alloc_raw = body.get("winter_training_allocations")
            for name, t in teams.items():
                if name == user_team_name:
                    if isinstance(user_alloc_raw, dict):
                        alloc = normalize_winter_training_allocations(user_alloc_raw)
                    else:
                        legacy_pct = int(getattr(getattr(t, "coach", None), "winter_strength_pct", 50) or 50)
                        alloc = _winter_allocations_from_legacy_strength_pct(legacy_pct)
                else:
                    alloc = build_ai_winter_training_allocations(t)
                results_by_team[name] = run_winter_training_session(t, alloc, current)

            user_result = results_by_team.get(user_team_name) if user_team_name else None
            state["offseason_winter_training_results"] = {
                "stage": current,
                "by_team": results_by_team,
                "user_team_result": user_result,
                "resolved": True,
            }
            # Stay on winter stage one extra Continue so user can view results.
            state["offseason_stage_index"] = idx
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            save_state(user_id, save_id, state, save_dir)
            return {"state": state}

    elif current == "Spring Ball":
        so = body.get("spring_offense_focus")
        sd = body.get("spring_defense_focus")
        spring_results = state.get("offseason_spring_ball_results")
        ack = bool(body.get("spring_ball_ack_results"))
        if isinstance(spring_results, dict) and ack:
            state.pop("offseason_spring_ball_results", None)
            # Results acknowledged; allow normal stage advance.
        elif isinstance(spring_results, dict) and not ack:
            raise ValueError("Review Spring Ball results, then press Continue again to advance.")
        else:
            if ut and ut.coach:
                if so is not None:
                    s = str(so).strip().lower()
                    if s in SPRING_OFFENSE_FOCUS_OPTIONS:
                        ut.coach.spring_offense_focus = s
                if sd is not None:
                    d = str(sd).strip().lower()
                    if d in SPRING_DEFENSE_FOCUS_OPTIONS:
                        ut.coach.spring_defense_focus = d

            _assign_cpu_spring_ball_focuses(teams, user_team_name)
            results_by_team: Dict[str, Any] = {}
            for name, t in teams.items():
                results_by_team[name] = run_spring_ball_development(t)

            user_result = results_by_team.get(user_team_name) if user_team_name else None
            state["offseason_spring_ball_results"] = {
                "by_team": results_by_team,
                "user_team_result": user_result,
                "resolved": True,
            }
            # Stay on Spring Ball one extra Continue so user can view results.
            state["offseason_stage_index"] = idx
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            save_state(user_id, save_id, state, save_dir)
            return {"state": state}

    elif current == "Improvements":
        if not ut:
            pass
        else:
            bank = state.get("offseason_improvements_bank")
            if not isinstance(bank, dict):
                bank = {"pp_total": 0, "pp_remaining": 0, "breakdown": None, "applied": {}}
            pp_remaining = int(bank.get("pp_remaining", bank.get("pp_total", 0)) or 0)

            # Desired target levels (optional; default to current)
            fac_to = body.get("improve_facilities_grade")
            cul_to = body.get("improve_culture_grade")
            boo_to = body.get("improve_booster_support")
            fac_from = int(getattr(ut, "facilities_grade", 5) or 5)
            cul_from = int(getattr(ut, "culture_grade", 5) or 5)
            boo_from = int(getattr(ut, "booster_support", 5) or 5)
            fac_to_i = fac_from if fac_to is None else max(1, min(10, int(fac_to)))
            cul_to_i = cul_from if cul_to is None else max(1, min(10, int(cul_to)))
            boo_to_i = boo_from if boo_to is None else max(1, min(10, int(boo_to)))

            delta_pp = 0
            delta_pp += _improvement_pp_delta(fac_from, fac_to_i)
            delta_pp += _improvement_pp_delta(cul_from, cul_to_i)
            delta_pp += _improvement_pp_delta(boo_from, boo_to_i)

            new_remaining = pp_remaining + int(delta_pp)
            if new_remaining < 0:
                raise ValueError("Not enough PP for those improvements.")

            ut.facilities_grade = fac_to_i
            ut.culture_grade = cul_to_i
            ut.booster_support = boo_to_i

            bank["pp_remaining"] = new_remaining
            bank["applied"] = {
                "facilities_grade": {"from": fac_from, "to": fac_to_i},
                "culture_grade": {"from": cul_from, "to": cul_to_i},
                "booster_support": {"from": boo_from, "to": boo_to_i},
                "pp_delta": int(delta_pp),
            }
            state["offseason_improvements_bank"] = bank

    elif current == "Coach development":
        banks_cd = state.get("offseason_coach_dev_banks")
        if not isinstance(banks_cd, dict):
            banks_cd = {}
        if user_team_name and user_team_name not in banks_cd:
            legacy = state.get("offseason_coach_dev_bank")
            if isinstance(legacy, dict):
                banks_cd[user_team_name] = legacy
        for name, t in teams.items():
            coach = getattr(t, "coach", None)
            if not coach:
                continue
            b = banks_cd.get(name)
            if not isinstance(b, dict):
                b = _empty_coach_dev_bank()
                banks_cd[name] = b
            if name == user_team_name and ut and ut.coach:
                apply_coach_development(ut.coach, b, _merge_user_coach_development_body(b, body))
            elif name != user_team_name:
                apply_ai_coach_season_development(coach, b)
        if user_team_name:
            ub = banks_cd.get(user_team_name)
            if isinstance(ub, dict):
                state["offseason_coach_dev_bank"] = ub
        state["offseason_coach_dev_banks"] = banks_cd

    elif current in ("Coaching carousel I", "Coaching carousel II", "Coaching carousel III"):
        lh = load_league_history(league_history_path(save_dir))
        _apply_coaching_carousel_stage(state, teams, lh, current)

    elif current == "Transfers I":
        payload = run_transfer_stage_1(teams, state.get("standings") or {}, current_year=max(1, int(state.get("current_year", 1))))
        state["offseason_transfer_stage_1"] = payload
        transfer_events: List[Dict[str, Any]] = []
        for i, row in enumerate(payload.get("entries") or []):
            tpl = TRANSFER_NEWS_TEMPLATES[i % 15]
            detail = _transfer_render(
                tpl,
                {
                    "PLAYER": row.get("player", "Player"),
                    "TEAM": row.get("team", "Team"),
                    "POSITION": row.get("position", "ATH"),
                    "REGION": row.get("region", "State"),
                    "DEST_TEAM": "TBD",
                },
            )
            transfer_events.append(
                {
                    "type": "transfer_portal",
                    "player": row.get("player"),
                    "team": row.get("team"),
                    "position": row.get("position"),
                    "region": row.get("region"),
                    "detail": detail,
                }
            )
        _append_transfer_news_events(state, transfer_events)
    elif current == "Transfers II":
        stage1 = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else {}
        payload = run_transfer_stage_2(
            teams,
            state.get("standings") or {},
            stage1,
            current_year=max(1, int(state.get("current_year", 1))),
        )
        state["offseason_transfer_stage_2"] = payload
        moved_entries = [r for r in list(payload.get("entries") or []) if r.get("to_team")]
        state["offseason_transfer_review"] = {
            "entries": moved_entries,
            "moved_count": len(moved_entries),
            "blocked_count": int(payload.get("blocked_count", 0) or 0),
        }
        transfer_events = []
        for i, row in enumerate(payload.get("entries") or []):
            tpl = TRANSFER_NEWS_TEMPLATES[15 + (i % 15)]
            detail = _transfer_render(
                tpl,
                {
                    "PLAYER": row.get("player", "Player"),
                    "TEAM": row.get("from_team", "Team"),
                    "POSITION": row.get("position", "ATH"),
                    "REGION": row.get("to_region", row.get("from_region", "State")),
                    "DEST_TEAM": row.get("to_team", "Team"),
                },
            )
            transfer_events.append(
                {
                    "type": "transfer_commit",
                    "player": row.get("player"),
                    "team": row.get("from_team"),
                    "to_team": row.get("to_team"),
                    "position": row.get("position"),
                    "region": row.get("to_region", row.get("from_region")),
                    "detail": detail,
                }
            )
        _append_transfer_news_events(state, transfer_events)
    elif current in ("Transfers III", "7 on 7", "Graduation"):
        pass

    elif current == "Training Results":
        # Snapshot roster order + overalls so every player gets a row (name collisions won't drop rows).
        before_rows: List[Dict[str, Any]] = []
        if ut:
            for p in list(ut.roster):
                before_rows.append(
                    {
                        "name": p.name,
                        "position": p.position,
                        "before": calculate_player_overall(p),
                    }
                )
        for t in teams.values():
            run_offseason_development(t)
        deltas: List[Dict[str, Any]] = []
        if ut:
            after_roster = list(ut.roster)
            for i, p in enumerate(after_roster):
                b = int(before_rows[i]["before"]) if i < len(before_rows) else calculate_player_overall(p)
                a = calculate_player_overall(p)
                deltas.append(
                    {
                        "name": p.name,
                        "position": p.position or (before_rows[i].get("position") if i < len(before_rows) else None),
                        "before": b,
                        "after": a,
                        "delta": a - b,
                    }
                )
        state["offseason_training_results"] = {"players": deltas}

    elif current == "Freshman Class":
        pass

    elif current == "Schedule Release":
        pass

    # QoL: advancing from Improvements also executes Coaching carousel I immediately,
    # so users do not need an extra click just to start the carousel.
    if current == "Improvements":
        lh = load_league_history(league_history_path(save_dir))
        _apply_coaching_carousel_stage(state, teams, lh, "Coaching carousel I")
        state["offseason_stage_index"] = idx + 2
    else:
        state["offseason_stage_index"] = idx + 1
    if current == "Spring Ball":
        state.pop("offseason_spring_ball_results", None)
    if current in ("Winter 1", "Winter 2"):
        state.pop("offseason_winter_training_results", None)
    state["teams"] = [team_to_dict(t) for t in teams.values()]

    new_idx = int(state["offseason_stage_index"])
    if new_idx >= len(stages):
        teams2 = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
        _finalize_offseason_to_preseason(state, teams2)
        state["teams"] = [team_to_dict(t) for t in teams2.values()]

    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


def _extract_box_score_text(recap: str) -> str:
    text = (recap or "").strip()
    if not text:
        return ""
    lines = text.splitlines()
    idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("FINAL:"):
            idx = i
            break
    if idx >= 0:
        return "\n".join(lines[idx:]).strip()
    return text


def _team_stat_snapshot(season_stats: Dict[str, Dict[str, Any]], team_name: str) -> Dict[str, int]:
    s = season_stats.get(team_name) or {}
    return {
        "total_plays": int(s.get("total_plays", 0) or 0),
        "rush_yards": int(s.get("rush_yards", 0) or 0),
        "pass_yards": int(s.get("pass_yards", 0) or 0),
        "turnovers": int(s.get("turnovers", 0) or 0),
        "explosive_run": int(s.get("explosive_run", 0) or 0),
        "explosive_pass": int(s.get("explosive_pass", 0) or 0),
    }


def _team_stat_delta(before: Dict[str, int], after: Dict[str, int]) -> Dict[str, int]:
    keys = {"total_plays", "rush_yards", "pass_yards", "turnovers", "explosive_run", "explosive_pass"}
    out: Dict[str, int] = {}
    for k in keys:
        out[k] = int(after.get(k, 0) - before.get(k, 0))
    out["total_yards"] = int(out.get("rush_yards", 0) + out.get("pass_yards", 0))
    out["explosives"] = int(out.get("explosive_run", 0) + out.get("explosive_pass", 0))
    return out


def get_week_game_text(user_id: str, save_id: str, week_num: int, game_index: int, kind: str) -> Tuple[str, str]:
    """Return (filename, text) for week game export kind: box-score|game-log."""
    state, _save_dir = load_state(user_id, save_id)
    weeks = state.get("weeks") or []
    results = state.get("week_results") or []
    if week_num < 1 or week_num > len(weeks):
        raise ValueError("invalid week")
    wk_idx = week_num - 1
    wk_games = weeks[wk_idx] or []
    if game_index < 0 or game_index >= len(wk_games):
        raise ValueError("invalid game index")
    g = wk_games[game_index] or {}
    wk_res = results[wk_idx] if wk_idx < len(results) else []
    r = wk_res[game_index] if game_index < len(wk_res) else {}
    home = str(g.get("home", "Home"))
    away = str(g.get("away", "Away"))
    hs = int(r.get("home_score", 0))
    as_ = int(r.get("away_score", 0))
    ot = bool(r.get("ot"))
    played = bool(r.get("played"))
    matchup = f"{home}_vs_{away}".replace(" ", "_")

    if kind == "box-score":
        fname = f"week{week_num:02d}_{matchup}_box_score.txt"
        if not played:
            return fname, f"Week {week_num} - {home} vs {away}\n\nGame not played yet."
        txt = str(r.get("box_score_text") or "").strip()
        if not txt:
            recap = str(r.get("recap") or "")
            txt = _extract_box_score_text(recap).strip()
        if not txt:
            txt = f"FINAL: {home} {hs} - {away} {as_}{' (OT)' if ot else ''}"
        return fname, txt

    if kind == "game-log":
        fname = f"week{week_num:02d}_{matchup}_game_log.txt"
        if not played:
            return fname, f"Week {week_num} - {home} vs {away}\n\nGame not played yet."
        txt = str(r.get("game_log_text") or "").strip()
        if not txt:
            txt = "No detailed play log available for this game."
        return fname, txt

    raise ValueError("kind must be box-score or game-log")


def get_playoff_game_text(
    user_id: str,
    save_id: str,
    round_name: str,
    home: str,
    away: str,
    kind: str,
    classification: Optional[str] = None,
) -> Tuple[str, str]:
    """Return (filename, text) for playoff game export kind: box-score|game-log."""
    state, _save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    playoffs = _ensure_playoffs_migrated(state, teams) if isinstance(state.get("playoffs"), dict) else {}
    cls = str(classification or "").strip()
    if cls:
        bc = playoffs.get("by_class") if isinstance(playoffs, dict) else None
        sub = bc.get(cls) if isinstance(bc, dict) else None
        if isinstance(sub, dict):
            results = list(sub.get("bracket_results") or [])
        else:
            results = _flatten_playoff_bracket_results(playoffs)
    else:
        results = _flatten_playoff_bracket_results(playoffs)
    rn = str(round_name or "").strip()
    hn = str(home or "").strip()
    an = str(away or "").strip()
    if not rn or not hn or not an:
        raise ValueError("missing round/home/away")
    g = next((x for x in results if str(x.get("round") or "") == rn and str(x.get("home") or "") == hn and str(x.get("away") or "") == an), None)
    matchup = f"{hn}_vs_{an}".replace(" ", "_")
    safe_round = rn.lower().replace(" ", "_")

    if kind == "box-score":
        fname = f"playoffs_{safe_round}_{matchup}_box_score.txt"
        if not g:
            return fname, f"{rn} - {hn} vs {an}\n\nGame not played yet."
        txt = str(g.get("box_score_text") or "").strip()
        if not txt:
            hs = g.get("home_score", 0)
            as_ = g.get("away_score", 0)
            txt = f"FINAL: {hn} {hs} - {an} {as_}\n\nNo detailed box score was recorded for this playoff game."
        return fname, txt

    if kind == "game-log":
        fname = f"playoffs_{safe_round}_{matchup}_game_log.txt"
        if not g:
            return fname, f"{rn} - {hn} vs {an}\n\nGame not played yet."
        txt = str(g.get("game_log_text") or "").strip()
        if not txt:
            txt = "No detailed play log available for this playoff game."
        return fname, txt

    raise ValueError("kind must be box-score or game-log")


def _user_save_dir(user_id: str, save_name: str) -> str:
    # namespace: saves/<user>/<save>
    safe_user = _safe_path_segment(user_id, default="user")
    safe_save = _safe_path_segment(save_name, default="Untitled")
    return os.path.join(_saves_base_dir(), safe_user, safe_save)


_LEAGUE_SAVE_FILENAME = "league_save.json"
_WIN_INVALID_NAME_CHARS = frozenset('<>:"|?*')
_WIN_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)


def _win32_path_segments_valid(path: str) -> bool:
    """Reject paths Windows cannot open (e.g. ``|`` in a folder name), even if some APIs mis-report them."""
    if os.name != "nt":
        return True
    if not path or not str(path).strip():
        return False
    try:
        norm = os.path.normpath(path)
        _drive, tail = os.path.splitdrive(norm)
        for part in tail.replace("\\", "/").split("/"):
            if not part or part in (".", ".."):
                continue
            if any(ch in part for ch in _WIN_INVALID_NAME_CHARS):
                return False
            if part.endswith(" ") or part.endswith("."):
                return False
            root, _ext = os.path.splitext(part)
            key = (root or part).upper()
            if key in _WIN_RESERVED_NAMES:
                return False
    except (OSError, TypeError, ValueError):
        return False
    return True


def _league_save_plain_path(save_dir: str) -> str:
    return os.path.abspath(os.path.join(os.path.normpath(save_dir), _LEAGUE_SAVE_FILENAME))


def _has_league_save_file(save_dir: str) -> bool:
    try:
        return bool(save_dir) and isfile_any(_league_save_plain_path(save_dir))
    except (OSError, TypeError, ValueError):
        return False


def _scan_user_save_dirs_for_matching_league(user_id: str, save_name: str) -> Optional[str]:
    """
    If DB paths are wrong (e.g. Windows-invalid stored_dir) but data lives under saves/<safe_user>/<any>/,
    find a directory whose league_save.json save_name matches this row's save_name.
    """
    import json

    target = str(save_name or "").strip()
    if not target:
        return None
    user_root = os.path.join(_saves_base_dir(), _safe_path_segment(user_id, default="user"))
    if not _safe_isdir(user_root):
        return None
    try:
        names = sorted(os.listdir(user_root))
    except OSError:
        return None
    for entry in names:
        if entry == "_logos":
            continue
        cand = os.path.join(user_root, entry)
        if not _safe_isdir(cand) or not _has_league_save_file(cand):
            continue
        jplain = _league_save_plain_path(cand)
        try:
            with open_text_with_path_fallback(jplain, "r") as f:
                data = json.load(f)
        except Exception:
            continue
        if isinstance(data, dict) and str(data.get("save_name") or "").strip() == target:
            return cand
    return None


def _resolve_save_directory(user_id: str, save_name: str, stored_dir: str) -> str:
    """Prefer canonical user/save dir when league_save exists there; else legacy stored_dir; else scan; else canonical (new)."""
    stored = str(stored_dir or "")
    canonical = _user_save_dir(user_id, save_name)
    if _has_league_save_file(canonical):
        return canonical
    if stored and _win32_path_segments_valid(stored) and _has_league_save_file(stored):
        return stored
    scanned = _scan_user_save_dirs_for_matching_league(user_id, save_name)
    if scanned:
        return scanned
    return canonical


def _migrate_save_dir_if_changed(user_id: str, save_id: str, resolved_dir: str, stored_dir: str) -> None:
    stored = str(stored_dir or "")
    if not resolved_dir or os.path.normpath(resolved_dir) == os.path.normpath(stored):
        return
    try:
        now = int(time.time())
        with db() as conn:
            conn.execute(
                "UPDATE saves SET save_dir=?, updated_at=? WHERE id=? AND user_id=?",
                (resolved_dir, now, save_id, user_id),
            )
    except Exception:
        pass


def _safe_isdir(path: str) -> bool:
    try:
        return bool(path) and os.path.isdir(path)
    except (OSError, TypeError, ValueError):
        return False


def create_save(
    user_id: str,
    save_name: str,
    user_team: str,
    coach_config: Dict[str, Any],
    *,
    start_year: Optional[int] = None,
    teams_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    provided_rows = None
    if isinstance(teams_data, dict):
        maybe_rows = teams_data.get("teams")
        if isinstance(maybe_rows, list):
            provided_rows = [r for r in maybe_rows if isinstance(r, dict)]
    if provided_rows is not None:
        teams = build_teams_from_configs(provided_rows, generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    else:
        teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
    if user_team not in teams:
        raise ValueError("user_team not found")

    coach = teams[user_team].coach
    if coach and coach_config:
        apply_coach_config_dict(coach, coach_config)

    if start_year is None:
        current_year = 2026
    else:
        y = int(start_year)
        if y < 1900:
            raise ValueError("start_year must be 1900 or later")
        current_year = y

    # CPU coaches start with playbooks locked to this season so AI cannot flip them until eligible; user coach stays 0 until first change
    for tm_name, tm in teams.items():
        c = tm.coach
        if c and tm_name != user_team:
            c.last_preferred_playbook_change_year = int(current_year)

    team_names = sorted(teams.keys())
    ls = default_league_structure()
    stub_state: Dict[str, Any] = {"league_structure": ls}
    weeks, week_results = _regular_season_week_boards(teams, stub_state)
    standings = {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}

    save_dir = _user_save_dir(user_id, save_name)
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(save_dir)))
    except OSError:
        os.makedirs(save_dir, exist_ok=True)

    # save_system currently derives path from save_name; we write directly by temporarily using a name that maps to the directory.
    # For now, write via save_system, then move into the user dir.
    # Simpler: write league_save.json directly by calling save_league with an absolute-dir-aware wrapper later.
    tmp_name = f"__tmp__{uuid.uuid4()}"
    tmp_dir = get_save_dir(tmp_name)
    save_league(
        tmp_name,
        teams,
        current_year,
        user_team=user_team,
        current_week=1,
        season_phase="regular",
        weeks=weeks,
        week_results=week_results,
        standings=standings,
        league_structure=ls,
    )
    ensure_save_has_history_and_records(tmp_dir)

    # Move tmp save folder to user namespaced folder
    # Windows: shutil.move handles cross-volume if needed.
    import shutil

    if os.path.exists(save_dir):
        shutil.rmtree(save_dir, ignore_errors=True)
    shutil_move_with_fallback(tmp_dir, save_dir)

    save_id = str(uuid.uuid4())
    now = int(time.time())
    with db() as conn:
        conn.execute(
            "INSERT INTO saves (id, user_id, save_name, save_dir, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (save_id, user_id, save_name, save_dir, now, now),
        )

    # New dynasties start in preseason before Week 1 regular season.
    state, _save_dir = load_state(user_id, save_id)
    state["season_phase"] = "preseason"
    state["current_week"] = 1
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["preseason_stage_index"] = 0
    state["season_goals"] = state.get("season_goals") or []
    save_state(user_id, save_id, state, _save_dir)

    return {"save_id": save_id}


def list_saves(user_id: str) -> List[Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, save_name, updated_at FROM saves WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [{"save_id": r["id"], "save_name": r["save_name"], "updated_at": r["updated_at"]} for r in rows]


def delete_save(user_id: str, save_id: str) -> None:
    """Delete a save: remove from DB, delete associated games, and remove save directory."""
    import shutil
    row = _get_save_row(user_id, save_id)
    save_name = row["save_name"]
    stored_dir = str(row["save_dir"] or "")
    effective_dir = _resolve_save_directory(user_id, save_name, stored_dir)
    dirs_to_remove = {effective_dir}
    if stored_dir and os.path.normpath(stored_dir) != os.path.normpath(effective_dir):
        dirs_to_remove.add(stored_dir)

    with db() as conn:
        conn.execute("DELETE FROM games WHERE save_id=?", (save_id,))
        conn.execute("DELETE FROM saves WHERE id=? AND user_id=?", (save_id, user_id))

    for d in dirs_to_remove:
        if _safe_isdir(d):
            shutil.rmtree(d, ignore_errors=True)


def _ensure_scrimmage_opponents(state: Dict[str, Any], team_names: List[str], user_team_name: str) -> bool:
    """Ensure preseason_scrimmage_opponents is set when at Scrimmage 1/2. Returns True if state was modified."""
    if state.get("preseason_scrimmage_opponents"):
        return False
    stages = state.get("preseason_stages") or list(PRESEASON_STAGES)
    idx = int(state.get("preseason_stage_index", 0))
    if idx >= len(stages):
        return False
    if stages[idx] not in ("Scrimmage 1", "Scrimmage 2"):
        return False
    if not user_team_name or user_team_name not in team_names:
        return False
    scheduled_opponents = set()
    for wk in state.get("weeks") or []:
        for g in wk or []:
            if isinstance(g, dict):
                h, a = g.get("home"), g.get("away")
                if h == user_team_name and a:
                    scheduled_opponents.add(a)
                elif a == user_team_name and h:
                    scheduled_opponents.add(h)
    eligible = [t for t in team_names if t != user_team_name and t not in scheduled_opponents]
    if not eligible:
        eligible = [t for t in team_names if t != user_team_name]
    if len(eligible) >= 2:
        chosen = random.sample(eligible, 2)
        state["preseason_scrimmage_opponents"] = [
            {"opponent": chosen[0], "user_home": random.random() < 0.5},
            {"opponent": chosen[1], "user_home": random.random() < 0.5},
        ]
    elif len(eligible) == 1:
        state["preseason_scrimmage_opponents"] = [
            {"opponent": eligible[0], "user_home": random.random() < 0.5},
            {"opponent": eligible[0], "user_home": random.random() >= 0.5},
        ]
    else:
        state["preseason_scrimmage_opponents"] = []
    return True


def get_save(user_id: str, save_id: str) -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, save_name, save_dir FROM saves WHERE id=? AND user_id=?",
            (save_id, user_id),
        ).fetchone()
    if not row:
        raise ValueError("save not found")
    save_name = row["save_name"]
    stored_dir = str(row["save_dir"] or "")
    save_dir = _resolve_save_directory(user_id, save_name, stored_dir)
    # Load league_save.json directly by using load_league on a temp name is awkward; instead read file.
    import json

    with open_text_with_path_fallback(_league_save_plain_path(save_dir), "r") as f:
        state = json.load(f)

    _migrate_save_dir_if_changed(user_id, save_id, save_dir, stored_dir)

    if normalize_offseason_stages(state):
        save_state(user_id, save_id, state, save_dir)

    if str(state.get("season_phase") or "").strip().lower() == "playoffs":
        teams_map = {
            t["name"]: team_from_dict(t) for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")
        }
        st = state.get("standings") or {
            n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in teams_map
        }
        _ensure_playoffs_migrated(state, teams_map)
        if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
            state["playoffs"] = _init_playoffs_multiclass(state, teams_map, st)
        _ensure_all_eligible_playoff_brackets(state, teams_map, st)
        save_state(user_id, save_id, state, save_dir)

    # Ensure scrimmage opponents are set when at Scrimmage 1/2 (fixes old saves or edge cases)
    if state.get("season_phase") == "preseason":
        team_names = [t.get("name") for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
        user_team_name = state.get("user_team")
        if _ensure_scrimmage_opponents(state, team_names, user_team_name):
            save_state(user_id, save_id, state, save_dir)

    return {"save_id": row["id"], "save_name": row["save_name"], "state": state}


def _get_save_row(user_id: str, save_id: str) -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, save_name, save_dir FROM saves WHERE id=? AND user_id=?",
            (save_id, user_id),
        ).fetchone()
    if not row:
        raise ValueError("save not found")
    return {"save_id": row["id"], "save_name": row["save_name"], "save_dir": row["save_dir"]}


def load_state(user_id: str, save_id: str) -> Tuple[Dict[str, Any], str]:
    row = _get_save_row(user_id, save_id)
    import json

    save_name = row["save_name"]
    stored_dir = str(row["save_dir"] or "")
    save_dir = _resolve_save_directory(user_id, save_name, stored_dir)

    with open_text_with_path_fallback(_league_save_plain_path(save_dir), "r") as f:
        state = json.load(f)
    normalize_offseason_stages(state)
    ensure_league_structure_in_state(state)

    _migrate_save_dir_if_changed(user_id, save_id, save_dir, stored_dir)
    return state, save_dir


def _begin_playoffs_phase(state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]) -> None:
    """Enter playoffs and init brackets (no regional awards — those mutate state['teams'] separately)."""
    state["season_phase"] = "playoffs"
    state["playoff_season_player_stats"] = {}
    _ensure_playoffs_migrated(state, teams)
    if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
        state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
    _ensure_all_eligible_playoff_brackets(state, teams, standings)


def save_state(user_id: str, save_id: str, state: Dict[str, Any], save_dir: str) -> None:
    import json

    raw_ps = state.get("playoff_season_player_stats")
    if raw_ps:
        state["playoff_season_player_stats"] = season_stats_map_to_jsonable(
            season_stats_map_from_jsonable(raw_ps)
        )
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(save_dir)))
    except OSError:
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError:
            pass
    dest_plain = _league_save_plain_path(save_dir)
    payload = json.dumps(state, indent=2, ensure_ascii=False)
    tmp_plain = f"{dest_plain}.tmp.{uuid.uuid4().hex}"
    try:
        with open_text_with_path_fallback(tmp_plain, "w") as f:
            f.write(payload)
        os_replace_with_path_fallback(tmp_plain, dest_plain)
    except OSError as err:
        # Windows can sporadically throw EINVAL during atomic replace; fall back
        # to a direct write so season/playoff progression does not hard-fail.
        try:
            with open_text_with_path_fallback(dest_plain, "w") as f:
                f.write(payload)
            try:
                unlink_if_exists_any(tmp_plain)
            except OSError:
                pass
        except OSError:
            try:
                unlink_if_exists_any(tmp_plain)
            except OSError:
                pass
            raise err
    now = int(time.time())
    with db() as conn:
        conn.execute("UPDATE saves SET updated_at=? WHERE id=? AND user_id=?", (now, save_id, user_id))


def _pct_map_from_season_selection(entries: Any) -> Dict[str, float]:
    """Parse season_*_play_selection category list into play_id -> pct."""
    m: Dict[str, float] = {}
    if not entries:
        return m
    for item in entries:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                m[str(item[0])] = float(item[1])
            elif isinstance(item, dict):
                m[str(item.get("play_id", ""))] = float(item.get("pct", 0))
        except (TypeError, ValueError):
            continue
    return m


def _normalize_category_pcts(rows: List[Dict[str, Any]]) -> None:
    """In-place: scale rows so pcts sum to ~100 when off; equal split if all zero."""
    if not rows:
        return
    total = sum(float(r.get("pct", 0) or 0) for r in rows)
    if total < 99.5 or total > 100.5:
        if total <= 0:
            eq = 100.0 / len(rows)
            for r in rows:
                r["pct"] = eq
        else:
            for r in rows:
                r["pct"] = (float(r.get("pct", 0) or 0) / total) * 100.0


def _merge_offensive_playbook_for_display(pb: Any, off_sel: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Every play in the team playbook for each category, merged with saved season pcts."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for cat in OFFENSIVE_CATEGORIES:
        key = cat.name
        plays = pb.get_offensive_plays_by_category(cat)
        pmap = _pct_map_from_season_selection(off_sel.get(key))
        rows: List[Dict[str, Any]] = [
            {
                "play_id": p.id,
                "name": p.name,
                "formation": p.formation or "",
                "pct": float(pmap.get(p.id, 0.0)),
            }
            for p in plays
        ]
        _normalize_category_pcts(rows)
        out[key] = rows
    return out


def _merge_defensive_playbook_for_display(pb: Any, def_sel: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Every play in the team playbook for each category, merged with saved season pcts."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for cat in DEFENSIVE_CATEGORIES:
        key = cat.name
        plays = pb.get_defensive_plays_by_category(cat)
        pmap = _pct_map_from_season_selection(def_sel.get(key))
        rows: List[Dict[str, Any]] = [
            {
                "play_id": p.id,
                "name": p.name,
                "formation": p.formation or "",
                "pct": float(pmap.get(p.id, 0.0)),
            }
            for p in plays
        ]
        _normalize_category_pcts(rows)
        out[key] = rows
    return out


def get_play_selection_for_team(user_id: str, save_id: str) -> Dict[str, Any]:
    """Return user team's play selection with play names for the game plan UI."""
    try:
        state, save_dir = load_state(user_id, save_id)
    except Exception:
        return {"offensive": {}, "defensive": {}}

    teams_list = state.get("teams") or []
    teams = {}
    for t in teams_list:
        try:
            team_obj = team_from_dict(t) if isinstance(t, dict) else None
            if team_obj:
                teams[team_obj.name] = team_obj
        except Exception:
            continue

    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        return {"offensive": {}, "defensive": {}}

    team = teams[user_team_name]
    if not getattr(team, "season_offensive_play_selection", None) or not getattr(
        team, "season_defensive_play_selection", None
    ):
        try:
            run_play_selection_for_team(team)
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            save_state(user_id, save_id, state, save_dir)
        except Exception:
            pass

    try:
        pb = build_playbook_for_team(team)
    except Exception:
        return {"offensive": {}, "defensive": {}}

    off_sel = getattr(team, "season_offensive_play_selection", None) or {}
    def_sel = getattr(team, "season_defensive_play_selection", None) or {}

    # Full playbook per category (Nickel/Dime/6-2 etc.), not only the small auto-installed subset.
    return {
        "offensive": _merge_offensive_playbook_for_display(pb, off_sel),
        "defensive": _merge_defensive_playbook_for_display(pb, def_sel),
    }


def get_play_learning_summary(user_id: str, save_id: str) -> Dict[str, Any]:
    """How well the user's plays are learned (off/def % + overall grade) for results UI."""
    try:
        state, _save_dir = load_state(user_id, save_id)
    except Exception:
        return {
            "offensive_pct_learned": 0,
            "defensive_pct_learned": 0,
            "overall_grade": None,
        }

    teams_list = state.get("teams") or []
    teams: Dict[str, Any] = {}
    for t in teams_list:
        try:
            team_obj = team_from_dict(t) if isinstance(t, dict) else None
            if team_obj:
                teams[team_obj.name] = team_obj
        except Exception:
            continue

    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        return {
            "offensive_pct_learned": 0,
            "defensive_pct_learned": 0,
            "overall_grade": None,
        }

    team = teams[user_team_name]
    try:
        return compute_learning_summary(team)
    except Exception:
        return {
            "offensive_pct_learned": 0,
            "defensive_pct_learned": 0,
            "overall_grade": None,
        }


def update_depth_chart(user_id: str, save_id: str, depth_chart: Dict[str, List[str]]) -> Dict[str, Any]:
    """Save user's depth chart order and return updated state."""
    state, save_dir = load_state(user_id, save_id)
    teams_list = state.get("teams") or []
    teams = {t["name"]: team_from_dict(t) for t in teams_list if isinstance(t, dict)}
    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        return state
    ut = teams[user_team_name]
    ut.depth_chart_order = {
        k: [str(n) for n in v] if isinstance(v, list) else []
        for k, v in depth_chart.items()
        if isinstance(k, str) and k.strip()
    }
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    save_state(user_id, save_id, state, save_dir)
    return state


def _week_result_slot_played(slot: Any) -> bool:
    """Only skip silent sim when the slot is explicitly marked complete (bool True)."""
    if not isinstance(slot, dict):
        return False
    return slot.get("played") is True


def get_user_matchup(state: Dict[str, Any]) -> Optional[Tuple[str, str, int, int]]:
    user_team = state.get("user_team")
    weeks = state.get("weeks") or []
    current_week = int(state.get("current_week", 1))
    if not user_team or current_week < 1 or current_week > len(weeks):
        return None
    wk_idx = current_week - 1
    wk = weeks[wk_idx]
    for gi, g in enumerate(wk):
        if g.get("home") == user_team or g.get("away") == user_team:
            return g["home"], g["away"], wk_idx, gi
    return None


def _coach_gameplan_v2_matchup_key(state: Dict[str, Any]) -> Optional[str]:
    """
    Return a stable key for the user's next game.
    Works for regular season and playoffs (when applicable).
    """
    user_team = state.get("user_team")
    if not user_team:
        return None
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s == "playoffs":
        try:
            m = resolve_playoff_coach_matchup(state, str(user_team))
        except Exception:
            m = None
        if not m:
            return None
        home, away = m[0], m[1]
        return f"playoff:{home} vs {away}"
    m2 = get_user_matchup(state)
    if not m2:
        return None
    home, away, wk_idx, gi = m2
    return f"week:{wk_idx + 1}:{gi}:{home} vs {away}"


def attach_user_coach_gameplan_v2_from_save_state(
    state: Dict[str, Any],
    home_team: Any,
    away_team: Any,
    user_team_name: Optional[str],
) -> None:
    """
    Copy the user's saved matchup gameplan from league state onto their coach object.
    Playable games rebuild teams from JSON and otherwise would miss game_plan_v2_* on Coach.
    """
    if not user_team_name:
        return
    key = _coach_gameplan_v2_matchup_key(state)
    store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
    entry = store.get(key) if key and isinstance(store, dict) else None
    if not isinstance(entry, dict):
        return
    if getattr(home_team, "name", None) == user_team_name:
        target = home_team
    elif getattr(away_team, "name", None) == user_team_name:
        target = away_team
    else:
        return
    coach = getattr(target, "coach", None)
    if coach is None:
        return
    off_plan = entry.get("offense")
    def_plan = entry.get("defense")
    fourth_down = entry.get("fourth_down")
    if isinstance(off_plan, dict):
        coach.game_plan_v2_offense = off_plan
    if isinstance(def_plan, dict):
        coach.game_plan_v2_defense = def_plan
    if isinstance(fourth_down, dict):
        try:
            coach.fourth_down_go_for_it_max_ytg = max(
                0, min(10, int(fourth_down.get("go_for_it_max_ytg", 2)))
            )
        except Exception:
            coach.fourth_down_go_for_it_max_ytg = 2


def get_coach_gameplan_v2(user_id: str, save_id: str) -> Dict[str, Any]:
    """
    Get the coach gameplan (OFF + DEF) for the user's next game.
    Stored inside the save so it travels with the dynasty.
    """
    state, _save_dir = load_state(user_id, save_id)
    key = _coach_gameplan_v2_matchup_key(state)
    store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
    entry = store.get(key) if key and isinstance(store, dict) else None

    offense = None
    defense = None
    fourth_down = None
    if isinstance(entry, dict):
        offense = entry.get("offense")
        defense = entry.get("defense")
        fourth_down = entry.get("fourth_down")

    if not isinstance(offense, dict):
        offense = make_default_offense_gameplan_v2()
    if not isinstance(defense, dict):
        defense = make_default_defense_gameplan_v2()

    if not isinstance(fourth_down, dict):
        fourth_down = {"go_for_it_max_ytg": 2}
    try:
        fourth_down["go_for_it_max_ytg"] = max(0, min(10, int(fourth_down.get("go_for_it_max_ytg", 2))))
    except Exception:
        fourth_down["go_for_it_max_ytg"] = 2

    # Validate and fall back to defaults if corrupted.
    ok_off, _ = validate_gameplan_v2(offense, categories=GAMEPLAN_V2_OFF_CATEGORIES)
    ok_def, _ = validate_gameplan_v2(defense, categories=GAMEPLAN_V2_DEF_CATEGORIES)
    if not ok_off:
        offense = make_default_offense_gameplan_v2()
    if not ok_def:
        defense = make_default_defense_gameplan_v2()

    return {
        "matchup_key": key,
        "offense": offense,
        "defense": defense,
        "fourth_down": fourth_down,
        "meta": {
            "season_phase": str(state.get("season_phase") or ""),
            "current_week": int(state.get("current_week", 1) or 1),
            "user_team": str(state.get("user_team") or ""),
        },
    }


def save_coach_gameplan_v2(
    user_id: str,
    save_id: str,
    *,
    offense: Optional[Dict[str, Any]] = None,
    defense: Optional[Dict[str, Any]] = None,
    fourth_down: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Save the user's coach gameplan for the next game."""
    state, save_dir = load_state(user_id, save_id)
    key = _coach_gameplan_v2_matchup_key(state)
    if not key:
        raise ValueError("No upcoming game found to attach a gameplan to.")

    store = state.get("coach_gameplans_v2")
    if not isinstance(store, dict):
        store = {}

    entry = store.get(key)
    if not isinstance(entry, dict):
        entry = {}

    if offense is not None:
        ok, errs = validate_gameplan_v2(offense, categories=GAMEPLAN_V2_OFF_CATEGORIES)
        if not ok:
            raise ValueError("Invalid OFF gameplan: " + "; ".join(errs[:10]))
        entry["offense"] = offense

    if defense is not None:
        ok, errs = validate_gameplan_v2(defense, categories=GAMEPLAN_V2_DEF_CATEGORIES)
        if not ok:
            raise ValueError("Invalid DEF gameplan: " + "; ".join(errs[:10]))
        entry["defense"] = defense

    if fourth_down is not None:
        if not isinstance(fourth_down, dict):
            raise ValueError("Invalid 4th down settings: must be an object.")
        try:
            go_max = max(0, min(10, int(fourth_down.get("go_for_it_max_ytg", 2))))
        except Exception:
            raise ValueError("Invalid 4th down settings: go_for_it_max_ytg must be a number.")
        entry["fourth_down"] = {"go_for_it_max_ytg": go_max}

    entry["updated_at"] = int(time.time())
    store[key] = entry
    state["coach_gameplans_v2"] = store
    save_state(user_id, save_id, state, save_dir)
    return get_coach_gameplan_v2(user_id, save_id)


def get_team_history(user_id: str, save_id: str, team_name: str) -> Dict[str, Any]:
    """History for a single team from this save's league_history.json."""
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    names = sorted(list(teams.keys()))
    team = str(team_name or "").strip()
    if not team:
        team = str(state.get("user_team") or "")
    if team and team not in teams:
        # allow viewing teams that existed historically but not currently
        pass

    hist = load_league_history(league_history_path(save_dir))
    seasons = hist.get("seasons") or []

    def postseason_label(team_n: str, season_entry: Dict[str, Any]) -> str:
        if team_n == season_entry.get("state_champion"):
            return "State Champion"
        if team_n == season_entry.get("runner_up"):
            return "Runner-up"
        playoffs = season_entry.get("playoffs") if isinstance(season_entry.get("playoffs"), dict) else {}
        br = playoffs.get("bracket_results") or []
        order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
        best = None
        for g in br or []:
            if not isinstance(g, dict):
                continue
            if g.get("home") != team_n and g.get("away") != team_n:
                continue
            rnd = str(g.get("round") or "")
            v = order.get(rnd)
            if v and (best is None or v > best):
                best = v
        if best == 2:
            return "Semifinalist"
        if best == 1:
            return "Quarterfinalist"
        return "—"

    rows: List[Dict[str, Any]] = []
    for s in seasons:
        if not isinstance(s, dict):
            continue
        year = s.get("year")
        standings_list = s.get("standings") or []
        st_row = None
        if isinstance(standings_list, list):
            for r in standings_list:
                if isinstance(r, dict) and r.get("team") == team:
                    st_row = r
                    break
        if not st_row:
            continue
        coach = st_row.get("coach") if isinstance(st_row.get("coach"), str) else ""
        recaps = s.get("team_recaps") if isinstance(s.get("team_recaps"), dict) else {}
        recap_path = recaps.get(team) if isinstance(recaps.get(team), str) else None
        rows.append({
            "year": year,
            "wins": int(st_row.get("wins", 0) or 0),
            "losses": int(st_row.get("losses", 0) or 0),
            "postseason": postseason_label(team, s),
            "coach": coach or "—",
            "has_recap": bool(recap_path),
        })

    rows.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    return {"team_name": team, "team_names": names, "history": rows}


def get_coach_history(user_id: str, save_id: str, coach_name: str) -> Dict[str, Any]:
    """Season rows for every team/year this coach appears on in league_history.json."""
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    names = sorted(list(teams.keys()))
    target = str(coach_name or "").strip().lower()
    if not target:
        return {"coach_name": "", "team_names": names, "history": []}

    hist = load_league_history(league_history_path(save_dir))
    seasons = hist.get("seasons") or []

    def postseason_label(team_n: str, season_entry: Dict[str, Any]) -> str:
        if team_n == season_entry.get("state_champion"):
            return "State Champion"
        if team_n == season_entry.get("runner_up"):
            return "Runner-up"
        playoffs = season_entry.get("playoffs") if isinstance(season_entry.get("playoffs"), dict) else {}
        br = playoffs.get("bracket_results") or []
        order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
        best = None
        for g in br or []:
            if not isinstance(g, dict):
                continue
            if g.get("home") != team_n and g.get("away") != team_n:
                continue
            rnd = str(g.get("round") or "")
            v = order.get(rnd)
            if v and (best is None or v > best):
                best = v
        if best == 2:
            return "Semifinalist"
        if best == 1:
            return "Quarterfinalist"
        return "—"

    rows: List[Dict[str, Any]] = []
    for s in seasons:
        if not isinstance(s, dict):
            continue
        year = s.get("year")
        standings_list = s.get("standings") or []
        if not isinstance(standings_list, list):
            continue
        for st_row in standings_list:
            if not isinstance(st_row, dict):
                continue
            c = st_row.get("coach")
            if not isinstance(c, str) or c.strip().lower() != target:
                continue
            team_n = str(st_row.get("team") or "")
            if not team_n:
                continue
            recaps = s.get("team_recaps") if isinstance(s.get("team_recaps"), dict) else {}
            recap_path = recaps.get(team_n) if isinstance(recaps.get(team_n), str) else None
            rows.append({
                "year": year,
                "team": team_n,
                "wins": int(st_row.get("wins", 0) or 0),
                "losses": int(st_row.get("losses", 0) or 0),
                "postseason": postseason_label(team_n, s),
                "coach": c.strip() or "—",
                "has_recap": bool(recap_path),
            })

    rows.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    return {"coach_name": str(coach_name).strip(), "team_names": names, "history": rows}


def get_team_season_recap_text(user_id: str, save_id: str, team_name: str, year: int) -> str:
    """Load the saved recap .txt for the requested team/year."""
    _state, save_dir = load_state(user_id, save_id)
    hist = load_league_history(league_history_path(save_dir))
    seasons = hist.get("seasons") or []
    team = str(team_name or "").strip()
    if not team:
        raise ValueError("Missing team name")
    y = int(year)
    for s in seasons:
        if not isinstance(s, dict):
            continue
        if int(s.get("year", 0) or 0) != y:
            continue
        recaps = s.get("team_recaps") if isinstance(s.get("team_recaps"), dict) else {}
        rel = recaps.get(team) if isinstance(recaps.get(team), str) else None
        if not rel:
            break
        p = os.path.abspath(os.path.join(save_dir, rel))
        if not p.startswith(os.path.abspath(save_dir)):
            raise ValueError("Invalid recap path")
        if not isfile_any(p):
            raise ValueError("Recap file not found")
        with open_text_with_path_fallback(os.path.abspath(p), "r") as f:
            return f.read()
    raise ValueError("Recap not available for that season/team")


def sim_week(user_id: str, save_id: str) -> Dict[str, Any]:
    state, save_dir = load_state(user_id, save_id)
    phase_s = str(state.get("season_phase") or "").strip().lower()
    stages_pre = state.get("preseason_stages") or []
    pre_i = int(state.get("preseason_stage_index", 0))
    # Preseason flow finished on file but phase not updated — normalize so week sim can run.
    if phase_s == "preseason" and isinstance(stages_pre, list) and len(stages_pre) > 0 and pre_i >= len(stages_pre):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
        save_state(user_id, save_id, state, save_dir)
        phase_s = "regular"
    if phase_s == "preseason":
        raise ValueError(
            "This save is still in preseason. Use Play or Simulate on the scrimmage panel for practice games, "
            "then Continue to advance. Finish all preseason steps before simming the regular season."
        )
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    season_stats = init_season_stats(team_names)
    season_player_stats: Dict[int, Any] = {}

    current_week = int(state.get("current_week", 1))
    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}

    if current_week < 1:
        raise ValueError("invalid current week")
    if current_week > len(weeks):
        # End of regular season: enter playoffs (do NOT run offseason yet).
        # Regional titles were applied when the final week was simmed; avoid double-count here.
        state["season_phase"] = "playoffs"
        state["playoff_season_player_stats"] = {}
        _ensure_playoffs_migrated(state, teams)
        if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
            state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
        _ensure_all_eligible_playoff_brackets(state, teams, standings)
        save_state(user_id, save_id, state, save_dir)
        return {"state": state}

    wk_idx = current_week - 1
    while len(week_results) <= wk_idx:
        week_results.append([])
    # Keep week_results aligned with weeks[wk_idx] so gi always matches the scheduled game.
    while len(week_results[wk_idx]) < len(weeks[wk_idx]):
        week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})
    for gi, g in enumerate(weeks[wk_idx]):
        while len(week_results[wk_idx]) <= gi:
            week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})
        if _week_result_slot_played(week_results[wk_idx][gi]):
            continue
        home = g["home"]
        away = g["away"]
        home_before = _team_stat_snapshot(season_stats, home)
        away_before = _team_stat_snapshot(season_stats, away)
        game_lines: List[str] = []
        play_lines: List[str] = []

        # Apply user's saved coach gameplan (v2) only for the user's matchup.
        user_team = state.get("user_team")
        restore_attrs: Optional[Tuple[Any, Any]] = None
        if user_team and user_team in teams and (home == user_team or away == user_team):
            try:
                key = _coach_gameplan_v2_matchup_key(state)
                store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
                entry = store.get(key) if key and isinstance(store, dict) else None
                off_plan = entry.get("offense") if isinstance(entry, dict) else None
                def_plan = entry.get("defense") if isinstance(entry, dict) else None
                fourth_down = entry.get("fourth_down") if isinstance(entry, dict) else None
                coach = getattr(teams[user_team], "coach", None)
                if coach is not None:
                    prev_off = getattr(coach, "game_plan_v2_offense", None)
                    prev_def = getattr(coach, "game_plan_v2_defense", None)
                    prev_4th = getattr(coach, "fourth_down_go_for_it_max_ytg", None)
                    restore_attrs = (prev_off, prev_def, prev_4th)
                    if isinstance(off_plan, dict):
                        coach.game_plan_v2_offense = off_plan
                    if isinstance(def_plan, dict):
                        coach.game_plan_v2_defense = def_plan
                    if isinstance(fourth_down, dict):
                        try:
                            coach.fourth_down_go_for_it_max_ytg = max(0, min(10, int(fourth_down.get("go_for_it_max_ytg", 2))))
                        except Exception:
                            coach.fourth_down_go_for_it_max_ytg = 2
            except Exception:
                restore_attrs = None

        stats_map = run_game_silent(
            teams[home],
            teams[away],
            teams,
            season_stats,
            standings,
            game_lines,
            season_player_stats,
            team_schedules=None,
            game_log_lines=play_lines,
        )

        if restore_attrs is not None and user_team and user_team in teams:
            try:
                coach = getattr(teams[user_team], "coach", None)
                if coach is not None:
                    coach.game_plan_v2_offense = restore_attrs[0]
                    coach.game_plan_v2_defense = restore_attrs[1]
                    coach.fourth_down_go_for_it_max_ytg = restore_attrs[2]
            except Exception:
                pass
        hs = as_ = 0
        ot = False
        for line in reversed(game_lines):
            if isinstance(line, str) and line.startswith("FINAL:"):
                ot = "(OT)" in line
                parsed = parse_scores_from_final_line(line)
                if parsed is not None:
                    hs, as_ = parsed
                break
        box_score_text = _extract_box_score_text("\n".join(game_lines))
        game_log_header = [
            f"GAME LOG: {home} vs {away} (Week {current_week})",
            "=" * 60,
        ]
        if play_lines:
            game_log_text = "\n".join(game_log_header + [""] + play_lines).strip()
        else:
            game_log_text = "\n".join(game_log_header + ["", "No play-by-play recorded."]).strip()
        recap = "\n".join(game_lines).strip()
        home_after = _team_stat_snapshot(season_stats, home)
        away_after = _team_stat_snapshot(season_stats, away)
        week_results[wk_idx][gi] = {
            "played": True,
            "home_score": hs,
            "away_score": as_,
            "ot": ot,
            "recap": recap,
            "box_score_text": box_score_text,
            "game_log_text": game_log_text,
            "team_stats": {
                home: _team_stat_delta(home_before, home_after),
                away: _team_stat_delta(away_before, away_after),
            },
            "player_stats": player_game_stats_map_to_json_list(stats_map or {}),
        }

    state["standings"] = standings
    state["week_results"] = week_results
    state["current_week"] = current_week + 1
    if state["current_week"] > len(weeks):
        award_regular_season_regional_titles(state)
        _begin_playoffs_phase(state, teams, standings)
    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


# -------------------------
# Stateless (in-memory) simulation for browser-imported bundles
# -------------------------


def sim_week_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """In-memory variant of sim_week: mutates and returns state (no disk I/O)."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    stages_pre = state.get("preseason_stages") or []
    pre_i = int(state.get("preseason_stage_index", 0))
    if phase_s == "preseason" and isinstance(stages_pre, list) and len(stages_pre) > 0 and pre_i >= len(stages_pre):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
        phase_s = "regular"
    if phase_s == "preseason":
        raise ValueError(
            "This save is still in preseason. Use Play or Simulate on the scrimmage panel for practice games, "
            "then Continue to advance. Finish all preseason steps before simming the regular season."
        )

    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    season_stats = init_season_stats(team_names)
    season_player_stats: Dict[int, Any] = {}

    current_week = int(state.get("current_week", 1))
    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}

    if current_week < 1:
        raise ValueError("invalid current week")
    if current_week > len(weeks):
        state["season_phase"] = "playoffs"
        _ensure_playoffs_migrated(state, teams)
        if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
            state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
        _ensure_all_eligible_playoff_brackets(state, teams, standings)
        state["playoff_season_player_stats"] = {}
        state["standings"] = standings
        state["week_results"] = week_results
        return state

    wk_idx = current_week - 1
    while len(week_results) <= wk_idx:
        week_results.append([])
    while len(week_results[wk_idx]) < len(weeks[wk_idx]):
        week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})

    for gi, g in enumerate(weeks[wk_idx]):
        while len(week_results[wk_idx]) <= gi:
            week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})
        if _week_result_slot_played(week_results[wk_idx][gi]):
            continue
        home = g["home"]
        away = g["away"]
        home_before = _team_stat_snapshot(season_stats, home)
        away_before = _team_stat_snapshot(season_stats, away)
        game_lines: List[str] = []
        play_lines: List[str] = []

        user_team = state.get("user_team")
        restore_attrs: Optional[Tuple[Any, Any]] = None
        if user_team and user_team in teams and (home == user_team or away == user_team):
            try:
                key = _coach_gameplan_v2_matchup_key(state)
                store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
                entry = store.get(key) if key and isinstance(store, dict) else None
                off_plan = entry.get("offense") if isinstance(entry, dict) else None
                def_plan = entry.get("defense") if isinstance(entry, dict) else None
                fourth_down = entry.get("fourth_down") if isinstance(entry, dict) else None
                coach = getattr(teams[user_team], "coach", None)
                if coach is not None:
                    prev_off = getattr(coach, "game_plan_v2_offense", None)
                    prev_def = getattr(coach, "game_plan_v2_defense", None)
                    prev_4th = getattr(coach, "fourth_down_go_for_it_max_ytg", None)
                    restore_attrs = (prev_off, prev_def, prev_4th)
                    if isinstance(off_plan, dict):
                        coach.game_plan_v2_offense = off_plan
                    if isinstance(def_plan, dict):
                        coach.game_plan_v2_defense = def_plan
                    if isinstance(fourth_down, dict):
                        try:
                            coach.fourth_down_go_for_it_max_ytg = max(0, min(10, int(fourth_down.get("go_for_it_max_ytg", 2))))
                        except Exception:
                            coach.fourth_down_go_for_it_max_ytg = 2
            except Exception:
                restore_attrs = None

        stats_map = run_game_silent(
            teams[home],
            teams[away],
            teams,
            season_stats,
            standings,
            game_lines,
            season_player_stats,
            team_schedules=None,
            game_log_lines=play_lines,
        )

        if restore_attrs is not None and user_team and user_team in teams:
            try:
                coach = getattr(teams[user_team], "coach", None)
                if coach is not None:
                    coach.game_plan_v2_offense = restore_attrs[0]
                    coach.game_plan_v2_defense = restore_attrs[1]
                    coach.fourth_down_go_for_it_max_ytg = restore_attrs[2]
            except Exception:
                pass

        hs = as_ = 0
        ot = False
        for line in reversed(game_lines):
            if isinstance(line, str) and line.startswith("FINAL:"):
                ot = "(OT)" in line
                parsed = parse_scores_from_final_line(line)
                if parsed is not None:
                    hs, as_ = parsed
                break
        box_score_text = _extract_box_score_text("\n".join(game_lines))
        game_log_header = [f"GAME LOG: {home} vs {away} (Week {current_week})", "=" * 60]
        game_log_text = (
            "\n".join(game_log_header + [""] + play_lines).strip()
            if play_lines
            else "\n".join(game_log_header + ["", "No play-by-play recorded."]).strip()
        )
        recap = "\n".join(game_lines).strip()
        home_after = _team_stat_snapshot(season_stats, home)
        away_after = _team_stat_snapshot(season_stats, away)
        week_results[wk_idx][gi] = {
            "played": True,
            "home_score": hs,
            "away_score": as_,
            "ot": ot,
            "recap": recap,
            "box_score_text": box_score_text,
            "game_log_text": game_log_text,
            "team_stats": {home: _team_stat_delta(home_before, home_after), away: _team_stat_delta(away_before, away_after)},
            "player_stats": player_game_stats_map_to_json_list(stats_map or {}),
        }

    state["standings"] = standings
    state["week_results"] = week_results
    state["current_week"] = current_week + 1
    entering_playoffs = state["current_week"] > len(weeks)
    if entering_playoffs:
        _begin_playoffs_phase(state, teams, standings)
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    if entering_playoffs:
        award_regular_season_regional_titles(state)
    return state


def sim_playoffs_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """In-memory variant of sim_playoffs."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        raise ValueError("save is not in playoffs")
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    _ensure_playoffs_migrated(state, teams)
    if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
        state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
    _ensure_all_eligible_playoff_brackets(state, teams, standings)
    playoffs = state["playoffs"]
    if any(
        len(list(x.get("bracket_results") or [])) > 0
        for x in (playoffs.get("by_class") or {}).values()
        if isinstance(x, dict)
    ):
        raise ValueError("Playoffs already in progress.")
    season_player_stats: Dict[int, Any] = dict(state.get("playoff_season_player_stats") or {})
    output_lines: List[str] = []
    by_class = playoffs.setdefault("by_class", {})
    uc = playoffs.get("user_class")
    user_champ = ""
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict):
            continue
        names_in_class = _team_names_by_classification(teams).get(cls) or []
        if len(names_in_class) < 8:
            continue
        pool = names_in_class
        champion, bracket_results = run_playoff(teams, standings, pool, output_lines, season_player_stats, num_teams=8)
        runner_up = ""
        if bracket_results:
            champ_game = bracket_results[-1]
            runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]
        seeded = seed_teams(pool, standings, top_n=8)
        pdata.update(
            {
                "num_teams": 8,
                "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
                "bracket_results": bracket_results,
                "completed": True,
                "champion": champion,
                "runner_up": runner_up,
            }
        )
        by_class[cls] = pdata
        if cls == uc:
            user_champ = champion or ""
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    playoffs["champion"] = user_champ or next((by_class[c].get("champion") for c in by_class if by_class[c].get("champion")), None)
    state["playoffs"] = playoffs
    state["season_phase"] = "playoffs"
    state["standings"] = standings
    state["playoff_season_player_stats"] = season_player_stats
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    return state


def sim_playoff_round_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """In-memory variant of sim_playoff_round."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        raise ValueError("save is not in playoffs")
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    p = _ensure_playoffs_migrated(state, teams)
    if _playoffs_global_completed(p):
        raise ValueError("Playoffs already complete.")
    return _advance_playoff_one_round_state(state)


def advance_preseason_state(state: Dict[str, Any], playbook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """In-memory variant of advance_preseason."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    playbook = playbook or {}

    had_preseason_meta = (
        "preseason_stage_index" in state
        or "preseason_stages" in state
        or "preseason_scrimmages" in state
    )
    state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
    stages = state["preseason_stages"]
    state["preseason_stage_index"] = int(state.get("preseason_stage_index", 0))
    idx = state["preseason_stage_index"]

    if idx >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        return {"state": state, "phase_completed": None}

    phase_norm = str(state.get("season_phase") or "preseason").strip().lower()
    if phase_norm in ("playoffs", "offseason", "done"):
        return {"state": state, "phase_completed": None}
    if phase_norm != "preseason":
        if had_preseason_meta:
            state["season_phase"] = "preseason"
        else:
            return {"state": state, "phase_completed": None}

    current_stage = stages[idx]

    # Reuse the existing logic by calling the non-I/O blocks above in this file:
    # This is a shallow wrapper: we run the original function body by temporarily
    # inlining its stage effects via a call to the existing implementation paths.
    #
    # To keep this maintainable, call the original advance_preseason using a fake persistence layer is not an option,
    # so we replicate the core by delegating to the same stage-handling blocks through the existing code path:
    # We do this by calling the code below from the original function (copied in simplified form).

    # --- Begin: core stage effects (copied from advance_preseason) ---
    # Playbook Select
    if current_stage == "Playbook Select" and playbook:
        _apply_user_preseason_playbook_payload(state, teams, playbook)

    # Play Selection
    game_plan = playbook.get("game_plan") if isinstance(playbook, dict) else None
    if current_stage == "Play Selection":
        user_team_name = state.get("user_team")
        if user_team_name and user_team_name in teams:
            ut = teams[user_team_name]
            if game_plan:
                off_sel = game_plan.get("offensive") or {}
                def_sel = game_plan.get("defensive") or {}
                cat_display = {
                    **{c.name: c.value for c in OFFENSIVE_CATEGORIES},
                    **{c.name: c.value for c in DEFENSIVE_CATEGORIES},
                }
                for cat_name, entries in off_sel.items():
                    if entries:
                        total = sum(float(e.get("pct", 0)) for e in entries)
                        if abs(total - 100.0) > 0.01:
                            label = cat_display.get(cat_name, cat_name)
                            raise ValueError(f"Offensive category '{label}' must total 100% (got {total:.1f}%)")
                for cat_name, entries in def_sel.items():
                    if entries:
                        total = sum(float(e.get("pct", 0)) for e in entries)
                        if abs(total - 100.0) > 0.01:
                            label = cat_display.get(cat_name, cat_name)
                            raise ValueError(f"Defensive category '{label}' must total 100% (got {total:.1f}%)")
                ut.season_offensive_play_selection = {k: [(e["play_id"], float(e["pct"])) for e in v] for k, v in off_sel.items() if v}
                ut.season_defensive_play_selection = {k: [(e["play_id"], float(e["pct"])) for e in v] for k, v in def_sel.items() if v}
            else:
                if not getattr(ut, "season_offensive_play_selection", None):
                    try:
                        run_play_selection_for_team(ut)
                    except Exception:
                        pass

    if current_stage == "Play Selection Results":
        for t in teams.values():
            try:
                run_play_selection_results_for_team(t)
            except Exception:
                pass
    elif current_stage == "Position changes":
        _apply_preseason_position_changes_stage(state, teams, playbook)
    elif current_stage == "Set Depth Chart":
        depth_chart = playbook.get("depth_chart") if isinstance(playbook, dict) else None
        if depth_chart and isinstance(depth_chart, dict):
            user_team_name = state.get("user_team")
            if user_team_name and user_team_name in teams:
                ut = teams[user_team_name]
                ut.depth_chart_order = {k: [str(n) for n in v] if isinstance(v, list) else [] for k, v in depth_chart.items() if isinstance(k, str) and k.strip()}
    elif current_stage == "Set Goals":
        STAGE_GOALS = ["Winning Season", "Playoffs", "Semifinal", "State Championship", "Title Winner"]
        goals = playbook.get("goals") if isinstance(playbook, dict) else None
        if goals and isinstance(goals, dict):
            win_goal = goals.get("win_goal")
            stage_goal = goals.get("stage_goal")
            if win_goal is not None:
                win_goal = max(0, min(10, int(win_goal)))
                stage_goal = str(stage_goal or "Winning Season")
                if stage_goal not in STAGE_GOALS:
                    stage_goal = "Winning Season"
                state["season_goals"] = {"win_goal": win_goal, "stage_goal": stage_goal}
            else:
                state["season_goals"] = state.get("season_goals") or {"win_goal": 6, "stage_goal": "Winning Season"}
        else:
            state["season_goals"] = state.get("season_goals") or {"win_goal": 6, "stage_goal": "Winning Season"}
    # --- End: core stage effects ---

    state["teams"] = [team_to_dict(t) for t in teams.values()]
    state["preseason_stage_index"] = idx + 1
    if state["preseason_stage_index"] >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
    return {"state": state, "phase_completed": current_stage}


def advance_offseason_state(
    state: Dict[str, Any],
    body: Optional[Dict[str, Any]] = None,
    league_history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """In-memory variant of advance_offseason. Pass league_history for coaching carousel (stateless bundle)."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "offseason":
        raise ValueError("save is not in offseason")
    body = body or {}
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    stages: List[str] = list(state.get("offseason_stages") or OFFSEASON_UI_STAGES)
    state["offseason_stages"] = stages
    idx = int(state.get("offseason_stage_index", 0))
    if idx >= len(stages):
        raise ValueError("offseason already complete; continue from preseason")
    current = _normalize_offseason_stage_name(stages[idx])
    user_team_name = state.get("user_team")
    ut = teams.get(user_team_name) if user_team_name else None

    if current in ("Winter 1", "Winter 2"):
        winter_results = state.get("offseason_winter_training_results")
        ack_winter = bool(body.get("winter_training_ack_results"))
        if isinstance(winter_results, dict) and str(winter_results.get("stage") or "") == current and ack_winter:
            state.pop("offseason_winter_training_results", None)
        elif isinstance(winter_results, dict) and str(winter_results.get("stage") or "") == current and not ack_winter:
            raise ValueError("Review Winter training results, then press Continue again to advance.")
        else:
            ws = body.get("winter_strength_pct")
            if ws is not None and ut and ut.coach:
                ut.coach.winter_strength_pct = max(0, min(100, int(ws)))

            results_by_team: Dict[str, Any] = {}
            user_alloc_raw = body.get("winter_training_allocations")
            for name, t in teams.items():
                if name == user_team_name:
                    if isinstance(user_alloc_raw, dict):
                        alloc = normalize_winter_training_allocations(user_alloc_raw)
                    else:
                        legacy_pct = int(getattr(getattr(t, "coach", None), "winter_strength_pct", 50) or 50)
                        alloc = _winter_allocations_from_legacy_strength_pct(legacy_pct)
                else:
                    alloc = build_ai_winter_training_allocations(t)
                results_by_team[name] = run_winter_training_session(t, alloc, current)

            user_result = results_by_team.get(user_team_name) if user_team_name else None
            state["offseason_winter_training_results"] = {
                "stage": current,
                "by_team": results_by_team,
                "user_team_result": user_result,
                "resolved": True,
            }
            state["offseason_stage_index"] = idx
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            return state
    elif current == "Spring Ball":
        so = body.get("spring_offense_focus")
        sd = body.get("spring_defense_focus")
        spring_results = state.get("offseason_spring_ball_results")
        ack = bool(body.get("spring_ball_ack_results"))
        if isinstance(spring_results, dict) and ack:
            state.pop("offseason_spring_ball_results", None)
        elif isinstance(spring_results, dict) and not ack:
            raise ValueError("Review Spring Ball results, then press Continue again to advance.")
        else:
            if ut and ut.coach:
                if so is not None:
                    s = str(so).strip().lower()
                    if s in SPRING_OFFENSE_FOCUS_OPTIONS:
                        ut.coach.spring_offense_focus = s
                if sd is not None:
                    d = str(sd).strip().lower()
                    if d in SPRING_DEFENSE_FOCUS_OPTIONS:
                        ut.coach.spring_defense_focus = d

            _assign_cpu_spring_ball_focuses(teams, user_team_name)
            results_by_team: Dict[str, Any] = {}
            for name, t in teams.items():
                results_by_team[name] = run_spring_ball_development(t)

            user_result = results_by_team.get(user_team_name) if user_team_name else None
            state["offseason_spring_ball_results"] = {
                "by_team": results_by_team,
                "user_team_result": user_result,
                "resolved": True,
            }
            state["offseason_stage_index"] = idx
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            return state
    elif current == "Improvements":
        # Reuse the same logic as advance_offseason (Improvements case)
        bank = state.get("offseason_improvements_bank")
        if not isinstance(bank, dict):
            bank = {"pp_total": 0, "pp_remaining": 0, "breakdown": None, "applied": {}}
        pp_remaining = int(bank.get("pp_remaining", bank.get("pp_total", 0)) or 0)
        if ut:
            fac_to = body.get("improve_facilities_grade")
            cul_to = body.get("improve_culture_grade")
            boo_to = body.get("improve_booster_support")
            fac_from = int(getattr(ut, "facilities_grade", 5) or 5)
            cul_from = int(getattr(ut, "culture_grade", 5) or 5)
            boo_from = int(getattr(ut, "booster_support", 5) or 5)
            fac_to_i = fac_from if fac_to is None else max(1, min(10, int(fac_to)))
            cul_to_i = cul_from if cul_to is None else max(1, min(10, int(cul_to)))
            boo_to_i = boo_from if boo_to is None else max(1, min(10, int(boo_to)))
            delta_pp = 0
            delta_pp += _improvement_pp_delta(fac_from, fac_to_i)
            delta_pp += _improvement_pp_delta(cul_from, cul_to_i)
            delta_pp += _improvement_pp_delta(boo_from, boo_to_i)
            new_remaining = pp_remaining + int(delta_pp)
            if new_remaining < 0:
                raise ValueError("Not enough PP for those improvements.")
            ut.facilities_grade = fac_to_i
            ut.culture_grade = cul_to_i
            ut.booster_support = boo_to_i
            bank["pp_remaining"] = new_remaining
            bank["applied"] = {
                "facilities_grade": {"from": fac_from, "to": fac_to_i},
                "culture_grade": {"from": cul_from, "to": cul_to_i},
                "booster_support": {"from": boo_from, "to": boo_to_i},
                "pp_delta": int(delta_pp),
            }
            state["offseason_improvements_bank"] = bank
    elif current in ("Coaching carousel I", "Coaching carousel II", "Coaching carousel III"):
        lh = league_history if isinstance(league_history, dict) else {"seasons": []}
        _apply_coaching_carousel_stage(state, teams, lh, current)
    elif current == "Coach development":
        banks_cd = state.get("offseason_coach_dev_banks")
        if not isinstance(banks_cd, dict):
            banks_cd = {}
        if user_team_name and user_team_name not in banks_cd:
            legacy = state.get("offseason_coach_dev_bank")
            if isinstance(legacy, dict):
                banks_cd[user_team_name] = legacy
        for name, t in teams.items():
            coach = getattr(t, "coach", None)
            if not coach:
                continue
            b = banks_cd.get(name)
            if not isinstance(b, dict):
                b = _empty_coach_dev_bank()
                banks_cd[name] = b
            if name == user_team_name and ut and ut.coach:
                apply_coach_development(ut.coach, b, _merge_user_coach_development_body(b, body))
            elif name != user_team_name:
                apply_ai_coach_season_development(coach, b)
        if user_team_name:
            ub = banks_cd.get(user_team_name)
            if isinstance(ub, dict):
                state["offseason_coach_dev_bank"] = ub
        state["offseason_coach_dev_banks"] = banks_cd
    elif current == "Transfers I":
        payload = run_transfer_stage_1(teams, state.get("standings") or {}, current_year=max(1, int(state.get("current_year", 1))))
        state["offseason_transfer_stage_1"] = payload
        transfer_events: List[Dict[str, Any]] = []
        for i, row in enumerate(payload.get("entries") or []):
            tpl = TRANSFER_NEWS_TEMPLATES[i % 15]
            detail = _transfer_render(
                tpl,
                {
                    "PLAYER": row.get("player", "Player"),
                    "TEAM": row.get("team", "Team"),
                    "POSITION": row.get("position", "ATH"),
                    "REGION": row.get("region", "State"),
                    "DEST_TEAM": "TBD",
                },
            )
            transfer_events.append(
                {
                    "type": "transfer_portal",
                    "player": row.get("player"),
                    "team": row.get("team"),
                    "position": row.get("position"),
                    "region": row.get("region"),
                    "detail": detail,
                }
            )
        _append_transfer_news_events(state, transfer_events)
    elif current == "Transfers II":
        stage1 = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else {}
        payload = run_transfer_stage_2(
            teams,
            state.get("standings") or {},
            stage1,
            current_year=max(1, int(state.get("current_year", 1))),
        )
        state["offseason_transfer_stage_2"] = payload
        moved_entries = [r for r in list(payload.get("entries") or []) if r.get("to_team")]
        state["offseason_transfer_review"] = {
            "entries": moved_entries,
            "moved_count": len(moved_entries),
            "blocked_count": int(payload.get("blocked_count", 0) or 0),
        }
        transfer_events = []
        for i, row in enumerate(payload.get("entries") or []):
            tpl = TRANSFER_NEWS_TEMPLATES[15 + (i % 15)]
            detail = _transfer_render(
                tpl,
                {
                    "PLAYER": row.get("player", "Player"),
                    "TEAM": row.get("from_team", "Team"),
                    "POSITION": row.get("position", "ATH"),
                    "REGION": row.get("to_region", row.get("from_region", "State")),
                    "DEST_TEAM": row.get("to_team", "Team"),
                },
            )
            transfer_events.append(
                {
                    "type": "transfer_commit",
                    "player": row.get("player"),
                    "team": row.get("from_team"),
                    "to_team": row.get("to_team"),
                    "position": row.get("position"),
                    "region": row.get("to_region", row.get("from_region")),
                    "detail": detail,
                }
            )
        _append_transfer_news_events(state, transfer_events)
    elif current in ("Transfers III", "7 on 7", "Graduation", "Freshman Class", "Schedule Release"):
        pass
    elif current == "Training Results":
        before_rows: List[Dict[str, Any]] = []
        if ut:
            for p in list(ut.roster):
                before_rows.append({"name": p.name, "position": p.position, "before": calculate_player_overall(p)})
        for t in teams.values():
            run_offseason_development(t)
        deltas: List[Dict[str, Any]] = []
        if ut:
            after_roster = list(ut.roster)
            for i, p in enumerate(after_roster):
                b = int(before_rows[i]["before"]) if i < len(before_rows) else calculate_player_overall(p)
                a = calculate_player_overall(p)
                deltas.append(
                    {
                        "name": p.name,
                        "position": p.position or (before_rows[i].get("position") if i < len(before_rows) else None),
                        "before": b,
                        "after": a,
                        "delta": a - b,
                    }
                )
        state["offseason_training_results"] = {"players": deltas}

    # QoL parity with save-backed flow: Improvements also runs carousel stage I.
    if current == "Improvements":
        lh = league_history if isinstance(league_history, dict) else {"seasons": []}
        _apply_coaching_carousel_stage(state, teams, lh, "Coaching carousel I")
        state["offseason_stage_index"] = idx + 2
    else:
        state["offseason_stage_index"] = idx + 1
    if current == "Spring Ball":
        state.pop("offseason_spring_ball_results", None)
    if current in ("Winter 1", "Winter 2"):
        state.pop("offseason_winter_training_results", None)
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    new_idx = int(state["offseason_stage_index"])
    if new_idx >= len(stages):
        teams2 = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
        _finalize_offseason_to_preseason(state, teams2)
        state["teams"] = [team_to_dict(t) for t in teams2.values()]
    return state


def finish_season_state(state: Dict[str, Any], league_history: Dict[str, Any], records: Dict[str, Any]) -> Dict[str, Any]:
    """Stateless finish_season: returns updated state + updated league_history/records + recap texts."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    output_lines: List[str] = []
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
    phase_s = str(state.get("season_phase") or "").strip().lower()
    run_playoff_stats: Dict[int, Any] = {}

    if playoffs and playoffs.get("completed") and playoffs.get("champion"):
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = list(playoffs.get("bracket_results") or [])
    elif phase_s == "playoffs":
        while True:
            p = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
            if p and p.get("completed") and p.get("champion"):
                champion = str(p.get("champion") or "")
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            state = _advance_playoff_one_round_state(state)
    else:
        pool = _playoff_pool_team_names(state, teams)
        champion, bracket_results = run_playoff(teams, standings, pool, output_lines, run_playoff_stats, num_teams=8)
        runner_up = ""
        if bracket_results:
            champ_game = bracket_results[-1]
            runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]

    standings = state.get("standings") or standings
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())

    if phase_s == "playoffs" or (playoffs and playoffs.get("completed") and playoffs.get("champion")):
        season_player_stats = season_stats_map_from_jsonable(state.get("playoff_season_player_stats") or {})
    else:
        season_player_stats = season_stats_map_from_jsonable(run_playoff_stats)

    year_num = int(state.get("current_year", 1))

    team_coaches: Dict[str, str] = {}
    for name, t in teams.items():
        coach = getattr(t, "coach", None)
        team_coaches[name] = str(getattr(coach, "name", "") or "")

    def _season_team_totals(team_name: str) -> Dict[str, int]:
        totals: Dict[str, int] = {
            "total_plays": 0,
            "rush_yards": 0,
            "pass_yards": 0,
            "total_yards": 0,
            "turnovers": 0,
            "explosive_run": 0,
            "explosive_pass": 0,
            "explosives": 0,
        }
        for wk in (state.get("week_results") or []):
            for g in (wk or []):
                if not isinstance(g, dict):
                    continue
                ts = g.get("team_stats") or {}
                row = ts.get(team_name)
                if not isinstance(row, dict):
                    continue
                for k in totals:
                    try:
                        totals[k] += int(row.get(k, 0) or 0)
                    except Exception:
                        pass
        return totals

    def _team_schedule_lines(team_name: str) -> List[str]:
        out: List[str] = []
        weeks = state.get("weeks") or []
        week_results = state.get("week_results") or []
        for wi, wk in enumerate(weeks):
            for gi, sched in enumerate(wk or []):
                if not isinstance(sched, dict):
                    continue
                h = sched.get("home")
                a = sched.get("away")
                if team_name not in (h, a):
                    continue
                played = False
                hs = as_ = 0
                ot = False
                if wi < len(week_results) and gi < len(week_results[wi]):
                    r = week_results[wi][gi]
                    if isinstance(r, dict):
                        played = bool(r.get("played"))
                        hs = int(r.get("home_score", 0) or 0)
                        as_ = int(r.get("away_score", 0) or 0)
                        ot = bool(r.get("ot"))
                out.append(format_recap_schedule_line(wi, team_name, h, a, played, hs, as_, ot))
        return out

    def _postseason_label(team_name: str, br: List[Dict[str, Any]]) -> str:
        if not team_name:
            return "—"
        if team_name == champion:
            return "State Champion"
        if team_name == runner_up:
            return "Runner-up"
        best = None
        order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
        for g in br or []:
            if not isinstance(g, dict):
                continue
            if g.get("home") != team_name and g.get("away") != team_name:
                continue
            rnd = str(g.get("round") or "")
            v = order.get(rnd)
            if v and (best is None or v > best):
                best = v
        if best == 2:
            return "Semifinalist"
        if best == 1:
            return "Quarterfinalist"
        return "—"

    # Recaps stored in-memory
    season_recaps: Dict[str, str] = {}
    team_recap_files: Dict[str, str] = {}
    br_for_history = _recap_merged_bracket_results(state, list(bracket_results or []))
    for team_name in team_names:
        safe = "".join(c for c in str(team_name) if c.isalnum() or c in " _-").strip() or "team"
        rel_path = f"season_recaps/year_{year_num}/{safe}.txt"
        srow = (standings or {}).get(team_name) or {}
        w = int(srow.get("wins", 0) or 0)
        l = int(srow.get("losses", 0) or 0)
        coach_name = team_coaches.get(team_name, "") or "—"
        postseason = _postseason_label(team_name, br_for_history)
        totals = _season_team_totals(team_name)
        player_rows = [ps for ps in season_player_stats.values() if getattr(ps, "team_name", None) == team_name]
        player_rows.sort(key=lambda ps: -(getattr(ps, "pass_yds", 0) + getattr(ps, "rush_yds", 0) + getattr(ps, "rec_yds", 0)))

        lines: List[str] = []
        lines.append(f"TEAM SEASON RECAP — Year {year_num}")
        lines.append("=" * 66)
        lines.append(f"Team: {team_name}")
        lines.append(f"Coach: {coach_name}")
        lines.append(f"Record: {w}-{l}")
        lines.append(f"Postseason: {postseason}")
        lines.append("")
        lines.append("SCHEDULE")
        lines.append("-" * 66)
        sched_lines = _team_schedule_lines(team_name)
        lines.extend(sched_lines if sched_lines else ["(no schedule found)"])
        playoff_lines = recap_postseason_lines_for_team(team_name, br_for_history)
        if playoff_lines:
            lines.append("")
            lines.append("POSTSEASON")
            lines.append("-" * 66)
            lines.extend(playoff_lines)
        lines.append("")
        lines.append("TEAM STATS (regular season totals)")
        lines.append("-" * 66)
        lines.append(f"Total plays: {totals['total_plays']}")
        lines.append(f"Rush yards: {totals['rush_yards']}")
        lines.append(f"Pass yards: {totals['pass_yards']}")
        lines.append(f"Total yards: {totals['total_yards']}")
        lines.append(f"Turnovers: {totals['turnovers']}")
        lines.append(f"Explosives: {totals['explosives']} (run {totals['explosive_run']} / pass {totals['explosive_pass']})")
        lines.append("")
        lines.append("ROSTER (end of season)")
        lines.append("-" * 66)
        t = teams.get(team_name)
        roster = getattr(t, "roster", None) or []
        if roster:
            for p_obj in roster:
                try:
                    pd = player_to_dict(p_obj)
                    nm = str(pd.get("name") or "")
                    pos = str(pd.get("position") or "")
                    ovr = pd.get("overall")
                    yr = pd.get("year")
                    lines.append(f"- {nm} ({pos}) OVR {ovr} — Year {yr}")
                except Exception:
                    continue
        else:
            lines.append("(no roster found)")
        lines.append("")
        lines.append("TOP PLAYER SEASON STATS")
        lines.append("-" * 66)
        if player_rows:
            for ps in player_rows[:20]:
                total_yds = int(getattr(ps, "pass_yds", 0) + getattr(ps, "rush_yds", 0) + getattr(ps, "rec_yds", 0))
                td = int(getattr(ps, "pass_td", 0) + getattr(ps, "rush_td", 0) + getattr(ps, "rec_td", 0))
                lines.append(f"- {ps.player_name}: {total_yds} yds, {td} TD | Pass {ps.pass_yds} ({ps.comp}/{ps.att}) | Rush {ps.rush_yds} | Rec {ps.rec_yds}")
        else:
            lines.append("(no player season stats recorded)")

        season_recaps[rel_path] = "\n".join(lines).strip() + "\n"
        team_recap_files[team_name] = rel_path

    from systems.league_history import append_season_in_memory

    out_hist = append_season_in_memory(
        league_history,
        records,
        champion=champion,
        runner_up=runner_up,
        team_names=team_names,
        standings=standings,
        season_player_stats=season_player_stats,
        year=year_num,
        bracket_results=br_for_history,
        team_coaches=team_coaches,
        team_recap_files=team_recap_files,
    )
    league_history = out_hist.get("league_history") or league_history
    records = out_hist.get("records") or records

    graduation_report: Dict[str, List[Dict[str, Any]]] = {}
    for t in teams.values():
        ro = run_offseason_roster_turnover(t, league_history=league_history)
        reset_team_season_stats(t)
        graduated = ro.get("graduated") or []
        graduation_report[t.name] = [player_to_dict(p) for p in graduated]

    state["current_year"] = int(state.get("current_year", 1)) + 1
    state["season_phase"] = "offseason"
    state["current_week"] = 1
    state["offseason_stage_index"] = 0
    state["offseason_stages"] = list(OFFSEASON_UI_STAGES)
    state["offseason_graduation_report"] = graduation_report
    state["offseason_training_results"] = None
    state["offseason_winter_training_results"] = None
    user_team_awards = str(state.get("user_team") or "")
    sg_fs = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    if user_team_awards:
        try:
            pp_breakdown_fs = _season_pp_awards_for_team(
                user_team_awards,
                standings=standings,
                bracket_results=br_for_history,
                champion=champion,
                season_goals=sg_fs,
            )
            pp_total_fs = int(pp_breakdown_fs.get("pp_total", 0) or 0)
        except Exception:
            pp_breakdown_fs = None
            pp_total_fs = 0
    else:
        pp_breakdown_fs = None
        pp_total_fs = 0
    try:
        cd_banks_fs = build_offseason_coach_dev_banks_for_league(
            team_names,
            standings,
            br_for_history,
            champion,
            user_team_awards or None,
            sg_fs,
            coaches_by_team={n: getattr(t, "coach", None) for n, t in teams.items()},
            existing_banks=state.get("offseason_coach_dev_banks") if isinstance(state.get("offseason_coach_dev_banks"), dict) else None,
        )
    except Exception:
        logger.exception("coach development banks (stateless finish)")
        cd_banks_fs = {}
        for n in team_names:
            try:
                cd_banks_fs[n] = compute_coach_development_bank(
                    n,
                    standings,
                    br_for_history,
                    champion,
                    sg_fs if n == user_team_awards else None,
                    coach=getattr(teams.get(n), "coach", None),
                    existing_bank=(state.get("offseason_coach_dev_banks") or {}).get(n)
                    if isinstance(state.get("offseason_coach_dev_banks"), dict)
                    else None,
                )
            except Exception:
                cd_banks_fs[n] = _empty_coach_dev_bank()
    state["offseason_improvements_bank"] = {
        "pp_total": pp_total_fs,
        "pp_remaining": pp_total_fs,
        "breakdown": pp_breakdown_fs,
        "applied": {},
    }
    state["offseason_coach_dev_banks"] = cd_banks_fs
    state["offseason_coach_dev_bank"] = (
        cd_banks_fs.get(user_team_awards)
        if user_team_awards and isinstance(cd_banks_fs.get(user_team_awards), dict)
        else _empty_coach_dev_bank()
    )
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["preseason_stage_index"] = 0
    state["preseason_scrimmages"] = []
    state["preseason_scrimmage_opponents"] = []
    state["season_goals"] = state.get("season_goals") or []
    ensure_league_structure_in_state(state)
    wk, wr = _regular_season_week_boards(teams, state)
    state["weeks"] = wk
    state["week_results"] = wr
    state["standings"] = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    _assign_scrimmage_opponents_for_state(state)
    state.pop("playoffs", None)
    state.pop("playoff_season_player_stats", None)

    return {"state": state, "champion": champion, "league_history": league_history, "records": records, "season_recaps": season_recaps}


def advance_preseason(user_id: str, save_id: str, playbook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    playbook = playbook or {}

    # Detect dynasty saves that use preseason (avoid "repairing" legacy saves with no preseason keys).
    had_preseason_meta = (
        "preseason_stage_index" in state
        or "preseason_stages" in state
        or "preseason_scrimmages" in state
    )
    state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
    stages = state["preseason_stages"]
    state["preseason_stage_index"] = int(state.get("preseason_stage_index", 0))
    idx = state["preseason_stage_index"]

    # Finished all preseason stages — must run before phase short-circuit (fixes stuck preseason_phase + index past end).
    if idx >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
        save_state(user_id, save_id, state, save_dir)
        return {"state": state, "phase_completed": None}

    phase_norm = str(state.get("season_phase") or "preseason").strip().lower()
    if phase_norm in ("playoffs", "offseason", "done"):
        return {"state": state, "phase_completed": None}

    if phase_norm != "preseason":
        if had_preseason_meta:
            state["season_phase"] = "preseason"
        else:
            return {"state": state, "phase_completed": None}

    current_stage = stages[idx]

    # Playbook Select: apply playbook choices to user's team coach.
    if current_stage == "Playbook Select" and playbook:
        _apply_user_preseason_playbook_payload(state, teams, playbook)
        state["teams"] = [team_to_dict(t) for t in teams.values()]

    # Play Selection: either save user's game plan (percentages) or auto-populate when first entering.
    game_plan = playbook.get("game_plan") if isinstance(playbook, dict) else None
    if current_stage == "Play Selection":
        user_team_name = state.get("user_team")
        if user_team_name and user_team_name in teams:
            ut = teams[user_team_name]
            if game_plan:
                # User submitted edited percentages; validate and save.
                off_sel = game_plan.get("offensive") or {}
                def_sel = game_plan.get("defensive") or {}
                cat_display = {
                    **{c.name: c.value for c in OFFENSIVE_CATEGORIES},
                    **{c.name: c.value for c in DEFENSIVE_CATEGORIES},
                }
                for cat_name, entries in off_sel.items():
                    if entries:
                        total = sum(float(e.get("pct", 0)) for e in entries)
                        if abs(total - 100.0) > 0.01:
                            label = cat_display.get(cat_name, cat_name)
                            raise ValueError(
                                f"Offensive category '{label}' must total 100% (got {total:.1f}%)"
                            )
                for cat_name, entries in def_sel.items():
                    if entries:
                        total = sum(float(e.get("pct", 0)) for e in entries)
                        if abs(total - 100.0) > 0.01:
                            label = cat_display.get(cat_name, cat_name)
                            raise ValueError(
                                f"Defensive category '{label}' must total 100% (got {total:.1f}%)"
                            )
                # Convert to team format: { "INSIDE_RUN": [(play_id, pct), ...], ... }
                ut.season_offensive_play_selection = {
                    k: [(e["play_id"], float(e["pct"])) for e in v]
                    for k, v in off_sel.items()
                    if v
                }
                ut.season_defensive_play_selection = {
                    k: [(e["play_id"], float(e["pct"])) for e in v]
                    for k, v in def_sel.items()
                    if v
                }
                state["teams"] = [team_to_dict(t) for t in teams.values()]
            else:
                # First time entering: run auto-selection if not yet populated.
                if not getattr(ut, "season_offensive_play_selection", None):
                    try:
                        run_play_selection_for_team(ut)
                        state["teams"] = [team_to_dict(t) for t in teams.values()]
                    except Exception:
                        pass

    # Execute other preseason stage effects (skip Play Selection - handled above).
    if current_stage == "Play Selection" and not game_plan:
        pass  # Already handled above
    elif current_stage == "Play Selection":
        pass  # Game plan saved above
    elif current_stage == "Play Selection Results":
        for t in teams.values():
            try:
                run_play_selection_results_for_team(t)
            except Exception:
                pass
        state["teams"] = [team_to_dict(t) for t in teams.values()]
    elif current_stage == "Position changes":
        _apply_preseason_position_changes_stage(state, teams, playbook)
        state["teams"] = [team_to_dict(t) for t in teams.values()]
    elif current_stage == "Set Depth Chart":
        depth_chart = playbook.get("depth_chart") if isinstance(playbook, dict) else None
        if depth_chart and isinstance(depth_chart, dict):
            user_team_name = state.get("user_team")
            if user_team_name and user_team_name in teams:
                ut = teams[user_team_name]
                ut.depth_chart_order = {
                    k: [str(n) for n in v] if isinstance(v, list) else []
                    for k, v in depth_chart.items()
                    if isinstance(k, str) and k.strip()
                }
                state["teams"] = [team_to_dict(t) for t in teams.values()]
    elif current_stage == "Set Goals":
        STAGE_GOALS = ["Winning Season", "Playoffs", "Semifinal", "State Championship", "Title Winner"]
        goals = playbook.get("goals") if isinstance(playbook, dict) else None
        if goals and isinstance(goals, dict):
            win_goal = goals.get("win_goal")
            stage_goal = goals.get("stage_goal")
            if win_goal is not None:
                win_goal = max(0, min(10, int(win_goal)))
                stage_goal = str(stage_goal or "Winning Season")
                if stage_goal not in STAGE_GOALS:
                    stage_goal = "Winning Season"
                state["season_goals"] = {"win_goal": win_goal, "stage_goal": stage_goal}
            else:
                state["season_goals"] = state.get("season_goals") or {
                    "win_goal": 6,
                    "stage_goal": "Winning Season",
                }
        else:
            state["season_goals"] = state.get("season_goals") or {
                "win_goal": 6,
                "stage_goal": "Winning Season",
            }
    elif current_stage in ("Scrimmage 1", "Scrimmage 2"):
        user_team_name = state.get("user_team")
        opponents_list = state.get("preseason_scrimmage_opponents") or []
        scrim_idx = 0 if current_stage == "Scrimmage 1" else 1
        slot = opponents_list[scrim_idx] if scrim_idx < len(opponents_list) else None

        if user_team_name and user_team_name in teams and slot and slot.get("opponent") in teams:
            opponent = slot["opponent"]
            user_home = slot.get("user_home", random.random() < 0.5)
            home_team = teams[user_team_name] if user_home else teams[opponent]
            away_team = teams[opponent] if user_home else teams[user_team_name]
            try:
                result = run_scrimmage_game(home_team, away_team)
                scrimmages = state.get("preseason_scrimmages") or []
                scrimmages.append({
                    "name": current_stage,
                    "completed": True,
                    "home": result["home"],
                    "away": result["away"],
                    "home_score": result["home_score"],
                    "away_score": result["away_score"],
                    "ot": result["ot"],
                    "team_stats": result.get("team_stats", {}),
                    "player_stats": result.get("player_stats", []),
                })
                state["preseason_scrimmages"] = scrimmages
            except Exception:
                logger.exception("run_scrimmage_game failed (slotted opponent)")
                scrimmages = state.get("preseason_scrimmages") or []
                scrimmages.append({"name": current_stage, "completed": True})
                state["preseason_scrimmages"] = scrimmages
        elif user_team_name and user_team_name in teams:
            scheduled_opponents = set()
            for wk in state.get("weeks") or []:
                for g in wk or []:
                    if isinstance(g, dict):
                        h, a = g.get("home"), g.get("away")
                        if h == user_team_name and a:
                            scheduled_opponents.add(a)
                        elif a == user_team_name and h:
                            scheduled_opponents.add(h)
            eligible = [t for t in team_names if t != user_team_name and t not in scheduled_opponents]
            if not eligible:
                eligible = [t for t in team_names if t != user_team_name]
            if eligible:
                opponent = random.choice(eligible)
                user_home = random.random() < 0.5
                home_team = teams[user_team_name] if user_home else teams[opponent]
                away_team = teams[opponent] if user_home else teams[user_team_name]
                try:
                    result = run_scrimmage_game(home_team, away_team)
                    scrimmages = state.get("preseason_scrimmages") or []
                    scrimmages.append({
                        "name": current_stage,
                        "completed": True,
                        "home": result["home"],
                        "away": result["away"],
                        "home_score": result["home_score"],
                        "away_score": result["away_score"],
                        "ot": result["ot"],
                        "team_stats": result.get("team_stats", {}),
                        "player_stats": result.get("player_stats", []),
                    })
                    state["preseason_scrimmages"] = scrimmages
                except Exception:
                    logger.exception("run_scrimmage_game failed (fallback opponent)")
                    scrimmages = state.get("preseason_scrimmages") or []
                    scrimmages.append({"name": current_stage, "completed": True})
                    state["preseason_scrimmages"] = scrimmages
            else:
                scrimmages = state.get("preseason_scrimmages") or []
                scrimmages.append({"name": current_stage, "completed": True})
                state["preseason_scrimmages"] = scrimmages
        else:
            scrimmages = state.get("preseason_scrimmages") or []
            scrimmages.append({"name": current_stage, "completed": True})
            state["preseason_scrimmages"] = scrimmages

    state["preseason_stage_index"] = idx + 1
    if state["preseason_stage_index"] >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = 1

    # When entering Position changes, Set Depth Chart, or Scrimmage 1, assign both scrimmage opponents if not yet set.
    new_idx = state["preseason_stage_index"]
    if new_idx < len(stages) and stages[new_idx] in ("Position changes", "Set Depth Chart", "Scrimmage 1"):
        if not state.get("preseason_scrimmage_opponents"):
            user_team_name = state.get("user_team")
            if user_team_name:
                scheduled_opponents = set()
                for wk in state.get("weeks") or []:
                    for g in wk or []:
                        if isinstance(g, dict):
                            h, a = g.get("home"), g.get("away")
                            if h == user_team_name and a:
                                scheduled_opponents.add(a)
                            elif a == user_team_name and h:
                                scheduled_opponents.add(h)
                eligible = [t for t in team_names if t != user_team_name and t not in scheduled_opponents]
                if not eligible:
                    eligible = [t for t in team_names if t != user_team_name]
                if len(eligible) >= 2:
                    chosen = random.sample(eligible, 2)
                    state["preseason_scrimmage_opponents"] = [
                        {"opponent": chosen[0], "user_home": random.random() < 0.5},
                        {"opponent": chosen[1], "user_home": random.random() < 0.5},
                    ]
                elif len(eligible) == 1:
                    state["preseason_scrimmage_opponents"] = [
                        {"opponent": eligible[0], "user_home": random.random() < 0.5},
                        {"opponent": eligible[0], "user_home": random.random() >= 0.5},
                    ]
                else:
                    state["preseason_scrimmage_opponents"] = []

    # When entering Play Selection (e.g. from Playbook Select), run play selection for user's team.
    if new_idx < len(stages) and stages[new_idx] == "Play Selection":
        user_team_name = state.get("user_team")
        if user_team_name and user_team_name in teams:
            ut = teams[user_team_name]
            if not getattr(ut, "season_offensive_play_selection", None):
                try:
                    run_play_selection_for_team(ut)
                    state["teams"] = [team_to_dict(t) for t in teams.values()]
                except Exception:
                    pass

    # Keep schedule/reset structures ready for regular season kickoff.
    if not state.get("weeks"):
        ensure_league_structure_in_state(state)
        wk, _wr = _regular_season_week_boards(teams, state)
        state["weeks"] = wk
    if not state.get("week_results"):
        state["week_results"] = [[{"played": False, "home_score": 0, "away_score": 0, "ot": False} for _ in wk] for wk in state.get("weeks", [])]
    if not state.get("standings"):
        state["standings"] = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}

    save_state(user_id, save_id, state, save_dir)
    return {"state": state, "phase_completed": current_stage}


def _playoff_row_same_teams(home: Any, away: Any, team_a: str, team_b: str) -> bool:
    """True if this bracket row is the same two teams as a pairing (order may differ from seed home/away)."""
    h, a = str(home or ""), str(away or "")
    return (h == team_a and a == team_b) or (h == team_b and a == team_a)


def resolve_playoff_coach_matchup(state: Dict[str, Any], user_team: str) -> Optional[Tuple[str, str]]:
    """Next playoff game for the user team as (home, away) in engine order, or None if none."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    p = _ensure_playoffs_migrated(state, teams) if isinstance(state.get("playoffs"), dict) else None
    if not p or not user_team or _playoffs_global_completed(p):
        return None
    uc = p.get("user_class") or _classification_of_team(teams, user_team)
    sub = (p.get("by_class") or {}).get(uc) if isinstance(p.get("by_class"), dict) else None
    if not isinstance(sub, dict):
        return None
    if sub.get("completed"):
        return None
    seeds = sorted(sub.get("seeds") or [], key=lambda x: int(x.get("seed", 0)))
    names = [str(s["team"]) for s in seeds]
    results = list(sub.get("bracket_results") or [])
    qf = [r for r in results if r.get("round") == "Quarterfinal"]
    sf = [r for r in results if r.get("round") == "Semifinal"]
    ch = [r for r in results if r.get("round") == "Championship"]

    for g in results:
        if g.get("home") == user_team or g.get("away") == user_team:
            if g.get("winner") and g.get("winner") != user_team:
                return None

    if len(qf) < 4:
        pairings = [(0, 7), (1, 6), (2, 5), (3, 4)]
        for hi, ai in pairings:
            hn, an = names[hi], names[ai]
            if user_team not in (hn, an):
                continue
            played = any(_playoff_row_same_teams(r.get("home"), r.get("away"), hn, an) for r in qf)
            if not played:
                return (hn, an)
        return None

    if len(sf) < 2:
        qf_pairs = [(0, 7), (1, 6), (2, 5), (3, 4)]
        winners: List[str] = []
        for hi, ai in qf_pairs:
            hn, an = names[hi], names[ai]
            found = next((r for r in qf if _playoff_row_same_teams(r.get("home"), r.get("away"), hn, an)), None)
            if not found or not found.get("winner"):
                return None
            winners.append(str(found["winner"]))
        sf_pairs = [(0, 3), (1, 2)]
        for wi, wj in sf_pairs:
            wh, wa = winners[wi], winners[wj]
            if user_team not in (wh, wa):
                continue
            played = any(_playoff_row_same_teams(r.get("home"), r.get("away"), wh, wa) for r in sf)
            if not played:
                return (wh, wa)
        return None

    if not ch:
        w1 = sf[0]["winner"]
        w2 = sf[1]["winner"]
        if user_team not in (w1, w2):
            return None
        if any(r.get("round") == "Championship" for r in results):
            return None
        return (w1, w2)
    return None


def start_coach_game(
    user_id: str,
    save_id: str,
    context: str,
    scrimmage_index: Optional[int] = 0,
) -> Dict[str, Any]:
    """Start a coach-playable game. Returns game_id and matchup info."""
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        raise ValueError("user team not set or not found")

    home_team = None
    away_team = None

    if context == "scrimmage":
        opponents = state.get("preseason_scrimmage_opponents") or []
        idx = max(0, min(scrimmage_index or 0, 1))
        slot = opponents[idx] if idx < len(opponents) else None
        if not slot or slot.get("opponent") not in teams:
            raise ValueError("scrimmage opponent not set or not found")
        opponent_name = slot["opponent"]
        user_home = slot.get("user_home", True)
        if user_home:
            home_team = teams[user_team_name]
            away_team = teams[opponent_name]
        else:
            home_team = teams[opponent_name]
            away_team = teams[user_team_name]
    elif context == "week":
        week_idx = int(state.get("current_week", 1)) - 1
        weeks = state.get("weeks") or []
        if week_idx < 0 or week_idx >= len(weeks):
            raise ValueError("no game scheduled this week")
        week_games = weeks[week_idx] or []
        matchup = None
        for g in week_games:
            if isinstance(g, dict):
                h, a = g.get("home"), g.get("away")
                if h == user_team_name or a == user_team_name:
                    matchup = g
                    break
        if not matchup:
            raise ValueError("no game for user team this week")
        home_name = matchup.get("home")
        away_name = matchup.get("away")
        if home_name not in teams or away_name not in teams:
            raise ValueError("matchup teams not found")
        home_team = teams[home_name]
        away_team = teams[away_name]
    elif context == "playoff":
        phase_s = str(state.get("season_phase") or "").strip().lower()
        if phase_s != "playoffs":
            raise ValueError("playoffs have not started")
        m = resolve_playoff_coach_matchup(state, user_team_name)
        if not m:
            raise ValueError("no playoff game for your team (eliminated, complete, or waiting on other games)")
        home_team = teams[m[0]]
        away_team = teams[m[1]]
    else:
        raise ValueError("context must be 'scrimmage', 'week', or 'playoff'")

    game_id = create_game_record(save_id, home_team, away_team, user_team_name=user_team_name)
    from backend.services.game_service import get_game
    game = get_game(game_id)
    return {
        "game_id": game_id,
        "save_id": save_id,
        "home_team_name": home_team.name,
        "away_team_name": away_team.name,
        "user_team_name": user_team_name,
        "state": game_state_dict(game),
    }


def start_coach_game_state(state: Dict[str, Any], context: str, scrimmage_index: Optional[int] = 0) -> Dict[str, Any]:
    """Stateless start_coach_game: returns matchup + serialized game (no DB)."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        raise ValueError("user team not set or not found")

    home_team = None
    away_team = None

    if context == "scrimmage":
        opponents = state.get("preseason_scrimmage_opponents") or []
        idx = max(0, min(scrimmage_index or 0, 1))
        slot = opponents[idx] if idx < len(opponents) else None
        if not slot or slot.get("opponent") not in teams:
            raise ValueError("scrimmage opponent not set or not found")
        opponent_name = slot["opponent"]
        user_home = slot.get("user_home", True)
        home_team = teams[user_team_name] if user_home else teams[opponent_name]
        away_team = teams[opponent_name] if user_home else teams[user_team_name]
    elif context == "week":
        week_idx = int(state.get("current_week", 1)) - 1
        weeks = state.get("weeks") or []
        if week_idx < 0 or week_idx >= len(weeks):
            raise ValueError("no game scheduled this week")
        matchup = None
        for g in (weeks[week_idx] or []):
            if isinstance(g, dict):
                h, a = g.get("home"), g.get("away")
                if h == user_team_name or a == user_team_name:
                    matchup = g
                    break
        if not matchup:
            raise ValueError("no game for user team this week")
        home_name = matchup.get("home")
        away_name = matchup.get("away")
        if home_name not in teams or away_name not in teams:
            raise ValueError("matchup teams not found")
        home_team = teams[home_name]
        away_team = teams[away_name]
    elif context == "playoff":
        phase_s = str(state.get("season_phase") or "").strip().lower()
        if phase_s != "playoffs":
            raise ValueError("playoffs have not started")
        m = resolve_playoff_coach_matchup(state, user_team_name)
        if not m:
            raise ValueError("no playoff game for your team (eliminated, complete, or waiting on other games)")
        home_team = teams[m[0]]
        away_team = teams[m[1]]
    else:
        raise ValueError("context must be 'scrimmage', 'week', or 'playoff'")

    from backend.services.game_state import serialize_game
    from engine.game_engine import Game
    from play_single_game import sync_game_ratings
    from systems import calculate_team_ratings, calculate_turnover_profile

    game = Game()
    game.home_team_name = home_team.name
    game.away_team_name = away_team.name
    game.user_team_name = user_team_name
    home_ratings = calculate_team_ratings(home_team)
    away_ratings = calculate_team_ratings(away_team)
    home_turnover = calculate_turnover_profile(home_team)
    away_turnover = calculate_turnover_profile(away_team)
    sync_game_ratings(game, home_ratings, away_ratings, home_turnover, away_turnover)
    game.play_log_lines = []
    game.pending_pat = False
    game.apply_opening_kickoff()

    return {
        "state": state,
        "home_team_name": home_team.name,
        "away_team_name": away_team.name,
        "user_team_name": user_team_name,
        "game": serialize_game(game),
    }


def finish_coach_week_state(state: Dict[str, Any], game: Any) -> Dict[str, Any]:
    """Stateless finish_coach_week: updates week_results + standings in state using provided game object."""
    from backend.services.game_service import game_state_dict

    gs = game_state_dict(game)
    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    hs = int(gs.get("score_home", 0))
    as_ = int(gs.get("score_away", 0))
    ot = bool(gs.get("ot_winner"))

    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    standings = state.get("standings") or {}
    current_week = int(state.get("current_week", 1))
    if current_week < 1 or current_week > len(weeks):
        raise ValueError("invalid current week")
    wk_idx = current_week - 1
    wk = weeks[wk_idx]
    wk_res = week_results[wk_idx] if wk_idx < len(week_results) else []
    game_idx = None
    for gi, g in enumerate(wk):
        if isinstance(g, dict) and g.get("home") == home_name and g.get("away") == away_name:
            game_idx = gi
            break
    if game_idx is None:
        raise ValueError("game not found in current week")
    if wk_res and game_idx < len(wk_res) and _week_result_slot_played(wk_res[game_idx]):
        raise ValueError("game already recorded")

    while len(week_results) <= wk_idx:
        week_results.append([])
    while len(week_results[wk_idx]) <= game_idx:
        week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})

    team_stats = gs.get("team_stats", {}) or {}
    hs_stats = team_stats.get(home_name, {})
    as_stats = team_stats.get(away_name, {})
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    player_lines, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)
    box_lines = [
        f"FINAL: {home_name} {hs} - {away_name} {as_}{' (OT)' if ot else ''}",
        "",
        "TEAM BOX SCORE",
        "-" * 60,
        f"{home_name}: Total Yds {hs_stats.get('total_yards', 0)} | Rush {hs_stats.get('rush_yards', 0)} | Pass {hs_stats.get('pass_yards', 0)} | TO {hs_stats.get('turnovers', 0)}",
        f"{away_name}: Total Yds {as_stats.get('total_yards', 0)} | Rush {as_stats.get('rush_yards', 0)} | Pass {as_stats.get('pass_yards', 0)} | TO {as_stats.get('turnovers', 0)}",
        "",
    ]
    box_lines.extend(player_lines)
    raw_play_log = getattr(game, "play_log_lines", None) or []
    if raw_play_log:
        game_log_text = "\n".join(
            [f"GAME LOG: {home_name} vs {away_name} (Coach Played)", "=" * 60, ""]
            + [str(x) for x in raw_play_log]
        ).strip()
    else:
        game_log_text = "No detailed play-by-play recorded for this coach-played game."
    recap_lines = box_lines
    week_results[wk_idx][game_idx] = {
        "played": True,
        "home_score": hs,
        "away_score": as_,
        "ot": ot,
        "recap": "\n".join(recap_lines),
        "box_score_text": "\n".join(box_lines).strip(),
        "game_log_text": game_log_text,
        "team_stats": {
            home_name: {
                "total_plays": int(hs_stats.get("total_plays", 0) or 0),
                "rush_yards": int(hs_stats.get("rush_yards", 0) or 0),
                "pass_yards": int(hs_stats.get("pass_yards", 0) or 0),
                "total_yards": int(hs_stats.get("total_yards", 0) or 0),
                "turnovers": int(hs_stats.get("turnovers", 0) or 0),
                "explosive_run": int(hs_stats.get("explosive_run", 0) or 0),
                "explosive_pass": int(hs_stats.get("explosive_pass", 0) or 0),
                "explosives": int(hs_stats.get("explosive_run", 0) or 0) + int(hs_stats.get("explosive_pass", 0) or 0),
            },
            away_name: {
                "total_plays": int(as_stats.get("total_plays", 0) or 0),
                "rush_yards": int(as_stats.get("rush_yards", 0) or 0),
                "pass_yards": int(as_stats.get("pass_yards", 0) or 0),
                "total_yards": int(as_stats.get("total_yards", 0) or 0),
                "turnovers": int(as_stats.get("turnovers", 0) or 0),
                "explosive_run": int(as_stats.get("explosive_run", 0) or 0),
                "explosive_pass": int(as_stats.get("explosive_pass", 0) or 0),
                "explosives": int(as_stats.get("explosive_run", 0) or 0) + int(as_stats.get("explosive_pass", 0) or 0),
            },
        },
        "player_stats": player_stats_list,
    }

    for name in (home_name, away_name):
        if name not in standings:
            standings[name] = {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0}
    home_s = standings[home_name]
    away_s = standings[away_name]
    home_s["points_for"] = home_s.get("points_for", 0) + hs
    home_s["points_against"] = home_s.get("points_against", 0) + as_
    away_s["points_for"] = away_s.get("points_for", 0) + as_
    away_s["points_against"] = away_s.get("points_against", 0) + hs
    if hs > as_:
        home_s["wins"] = home_s.get("wins", 0) + 1
        away_s["losses"] = away_s.get("losses", 0) + 1
    elif as_ > hs:
        away_s["wins"] = away_s.get("wins", 0) + 1
        home_s["losses"] = home_s.get("losses", 0) + 1

    state["week_results"] = week_results
    state["standings"] = standings
    return state


def finish_coach_playoff_state(state: Dict[str, Any], game: Any) -> Dict[str, Any]:
    """Stateless finish_coach_playoff: delegates to existing logic by updating state.playoffs bracket results."""
    # Reuse existing finish_coach_playoff implementation logic by copying essential pieces.
    from backend.services.game_service import game_state_dict

    if str(state.get("season_phase") or "").strip().lower() != "playoffs":
        raise ValueError("not in playoffs")
    gs = game_state_dict(game)
    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    hs = int(gs.get("score_home", 0))
    as_ = int(gs.get("score_away", 0))
    ot = bool(gs.get("ot_winner"))
    winner = home_name if hs > as_ else away_name
    round_name = "Quarterfinal"
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    playoffs = _ensure_playoffs_migrated(state, teams)
    uc = playoffs.get("user_class") or _classification_of_team(teams, state.get("user_team"))
    sub = playoffs.setdefault("by_class", {}).setdefault(
        uc,
        {
            "num_teams": 8,
            "seeds": [],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        },
    )
    bracket_results = list(sub.get("bracket_results") or [])
    # Determine round by how many results exist
    qf_before = len([r for r in bracket_results if r.get("round") == "Quarterfinal"])
    sf_before = len([r for r in bracket_results if r.get("round") == "Semifinal"])
    if qf_before < 4:
        round_name = "Quarterfinal"
    elif sf_before < 2:
        round_name = "Semifinal"
    else:
        round_name = "Championship"

    bracket_results.append(
        {
            "round": round_name,
            "home": home_name,
            "away": away_name,
            "home_score": hs,
            "away_score": as_,
            "ot": ot,
            "winner": winner,
        }
    )
    sub["bracket_results"] = bracket_results
    if round_name == "Championship":
        sub["completed"] = True
        sub["champion"] = winner
        sub["runner_up"] = away_name if winner == home_name else home_name
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    if sub.get("completed"):
        playoffs["champion"] = sub.get("champion")
        playoffs["runner_up"] = sub.get("runner_up")
    return state


def finish_coach_scrimmage_state(state: Dict[str, Any], game: Any, scrimmage_stage: str) -> Dict[str, Any]:
    """Stateless finish_coach_scrimmage: stores result into preseason_scrimmages and advances preseason one step."""
    from backend.services.game_service import game_state_dict

    gs = game_state_dict(game)
    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    hs = int(gs.get("score_home", 0))
    as_ = int(gs.get("score_away", 0))
    ot = bool(gs.get("ot_winner"))
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    _, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)
    # Attach minimal scrimmage record (matches existing UI expectations)
    scrims = list(state.get("preseason_scrimmages") or [])
    scrims.append(
        {
            "stage": scrimmage_stage,
            "home": home_name,
            "away": away_name,
            "home_score": hs,
            "away_score": as_,
            "ot": ot,
            "played": True,
            "player_stats": player_stats_list,
        }
    )
    state["preseason_scrimmages"] = scrims
    # Move preseason forward one stage (same behavior as finish_coach_scrimmage route)
    try:
        state["preseason_stage_index"] = int(state.get("preseason_stage_index", 0)) + 1
    except Exception:
        state["preseason_stage_index"] = 1
    return state


def finish_coach_week(
    user_id: str,
    save_id: str,
    game_id: str,
) -> Dict[str, Any]:
    """Record coach-played regular-season game result and update standings.

    Does **not** advance ``current_week``. Other matchups in the same week are
    simulated when the user runs ``sim_week()`` (Continue / Sim game), which
    skips already-played games and then advances the week.
    """
    from backend.services.game_service import get_game, game_state_dict

    state, save_dir = load_state(user_id, save_id)
    game = get_game(game_id)
    gs = game_state_dict(game)

    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    hs = int(gs.get("score_home", 0))
    as_ = int(gs.get("score_away", 0))
    ot = bool(gs.get("ot_winner"))

    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    standings = state.get("standings") or {}
    current_week = int(state.get("current_week", 1))

    if current_week < 1 or current_week > len(weeks):
        raise ValueError("invalid current week")
    wk_idx = current_week - 1
    wk = weeks[wk_idx]
    wk_res = week_results[wk_idx] if wk_idx < len(week_results) else []

    game_idx = None
    for gi, g in enumerate(wk):
        if isinstance(g, dict) and g.get("home") == home_name and g.get("away") == away_name:
            game_idx = gi
            break
    if game_idx is None:
        raise ValueError("game not found in current week")

    if wk_res and game_idx < len(wk_res) and _week_result_slot_played(wk_res[game_idx]):
        raise ValueError("game already recorded")

    # ensure week_results structure
    while len(week_results) <= wk_idx:
        week_results.append([])
    while len(week_results[wk_idx]) <= game_idx:
        week_results[wk_idx].append({"played": False, "home_score": 0, "away_score": 0, "ot": False})

    team_stats = gs.get("team_stats", {}) or {}
    hs_stats = team_stats.get(home_name, {})
    as_stats = team_stats.get(away_name, {})
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    player_lines, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)
    box_lines = [
        f"FINAL: {home_name} {hs} - {away_name} {as_}{' (OT)' if ot else ''}",
        "",
        "TEAM BOX SCORE",
        "-" * 60,
        f"{home_name}: Total Yds {hs_stats.get('total_yards', 0)} | Rush {hs_stats.get('rush_yards', 0)} | Pass {hs_stats.get('pass_yards', 0)} | TO {hs_stats.get('turnovers', 0)}",
        f"{away_name}: Total Yds {as_stats.get('total_yards', 0)} | Rush {as_stats.get('rush_yards', 0)} | Pass {as_stats.get('pass_yards', 0)} | TO {as_stats.get('turnovers', 0)}",
        "",
    ]
    box_lines.extend(player_lines)
    raw_play_log = getattr(game, "play_log_lines", None) or []
    if raw_play_log:
        game_log_text = "\n".join(
            [f"GAME LOG: {home_name} vs {away_name} (Coach Played)", "=" * 60, ""]
            + [str(x) for x in raw_play_log]
        ).strip()
    else:
        game_log_text = "No detailed play-by-play recorded for this coach-played game."
    recap_lines = box_lines
    week_results[wk_idx][game_idx] = {
        "played": True,
        "home_score": hs,
        "away_score": as_,
        "ot": ot,
        "recap": "\n".join(recap_lines),
        "box_score_text": "\n".join(box_lines).strip(),
        "game_log_text": game_log_text,
        "team_stats": {
            home_name: {
                "total_plays": int(hs_stats.get("total_plays", 0) or 0),
                "rush_yards": int(hs_stats.get("rush_yards", 0) or 0),
                "pass_yards": int(hs_stats.get("pass_yards", 0) or 0),
                "total_yards": int(hs_stats.get("total_yards", 0) or 0),
                "turnovers": int(hs_stats.get("turnovers", 0) or 0),
                "explosive_run": int(hs_stats.get("explosive_run", 0) or 0),
                "explosive_pass": int(hs_stats.get("explosive_pass", 0) or 0),
                "explosives": int(hs_stats.get("explosive_run", 0) or 0) + int(hs_stats.get("explosive_pass", 0) or 0),
            },
            away_name: {
                "total_plays": int(as_stats.get("total_plays", 0) or 0),
                "rush_yards": int(as_stats.get("rush_yards", 0) or 0),
                "pass_yards": int(as_stats.get("pass_yards", 0) or 0),
                "total_yards": int(as_stats.get("total_yards", 0) or 0),
                "turnovers": int(as_stats.get("turnovers", 0) or 0),
                "explosive_run": int(as_stats.get("explosive_run", 0) or 0),
                "explosive_pass": int(as_stats.get("explosive_pass", 0) or 0),
                "explosives": int(as_stats.get("explosive_run", 0) or 0) + int(as_stats.get("explosive_pass", 0) or 0),
            },
        },
        "player_stats": player_stats_list,
    }

    # update standings
    for name in (home_name, away_name):
        if name not in standings:
            standings[name] = {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0}

    home_s = standings[home_name]
    away_s = standings[away_name]
    home_s["points_for"] = home_s.get("points_for", 0) + hs
    home_s["points_against"] = home_s.get("points_against", 0) + as_
    away_s["points_for"] = away_s.get("points_for", 0) + as_
    away_s["points_against"] = away_s.get("points_against", 0) + hs

    if hs > as_:
        home_s["wins"] = home_s.get("wins", 0) + 1
        away_s["losses"] = away_s.get("losses", 0) + 1
    elif as_ > hs:
        away_s["wins"] = away_s.get("wins", 0) + 1
        home_s["losses"] = home_s.get("losses", 0) + 1

    state["week_results"] = week_results
    state["standings"] = standings

    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


def finish_coach_playoff(user_id: str, save_id: str, game_id: str) -> Dict[str, Any]:
    """Record coach-played playoff game. Sim other games in the round with Continue (sim-round)."""
    from backend.services.game_service import get_game, game_state_dict

    state, save_dir = load_state(user_id, save_id)
    if str(state.get("season_phase") or "").strip().lower() != "playoffs":
        raise ValueError("not in playoffs")

    game = get_game(game_id)
    gs = game_state_dict(game)
    home_name = str(gs["home_team_name"])
    away_name = str(gs["away_team_name"])
    hs = int(gs.get("score_home", 0))
    as_ = int(gs.get("score_away", 0))
    ot_w = gs.get("ot_winner")

    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in (home_name, away_name):
        raise ValueError("user team must play in this game")

    expected = resolve_playoff_coach_matchup(state, user_team_name)
    if not expected:
        raise ValueError("no pending playoff game for your team")
    eh, ea = expected
    if home_name != eh or away_name != ea:
        raise ValueError("game does not match the current playoff matchup")

    teams_fm = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    playoffs = _ensure_playoffs_migrated(state, teams_fm)
    uc = playoffs.get("user_class") or _classification_of_team(teams_fm, user_team_name)
    sub = playoffs.setdefault("by_class", {}).setdefault(
        uc,
        {
            "num_teams": 8,
            "seeds": [],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        },
    )
    bracket_results = list(sub.get("bracket_results") or [])
    for g in bracket_results:
        if _playoff_row_same_teams(g.get("home"), g.get("away"), eh, ea):
            raise ValueError("this playoff game was already recorded")

    if hs > as_:
        winner = home_name
    elif as_ > hs:
        winner = away_name
    else:
        if ot_w == "home":
            winner = home_name
        elif ot_w == "away":
            winner = away_name
        else:
            raise ValueError("could not determine winner (tie without overtime result)")

    loser = away_name if winner == home_name else home_name

    qf_before = len([r for r in bracket_results if r.get("round") == "Quarterfinal"])
    sf_before = len([r for r in bracket_results if r.get("round") == "Semifinal"])
    if qf_before < 4:
        round_name = "Quarterfinal"
    elif sf_before < 2:
        round_name = "Semifinal"
    else:
        round_name = "Championship"

    standings = state.get("standings") or {}
    team_names = [t.get("name") for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")]
    for name in team_names:
        if name not in standings:
            standings[name] = {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0}

    home_s = standings[home_name]
    away_s = standings[away_name]
    home_s["points_for"] = home_s.get("points_for", 0) + hs
    home_s["points_against"] = home_s.get("points_against", 0) + as_
    away_s["points_for"] = away_s.get("points_for", 0) + as_
    away_s["points_against"] = away_s.get("points_against", 0) + hs

    if winner == home_name:
        home_s["wins"] = home_s.get("wins", 0) + 1
        away_s["losses"] = away_s.get("losses", 0) + 1
    else:
        away_s["wins"] = away_s.get("wins", 0) + 1
        home_s["losses"] = home_s.get("losses", 0) + 1

    team_stats = gs.get("team_stats", {}) or {}
    hs_stats = team_stats.get(home_name, {})
    as_stats = team_stats.get(away_name, {})
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    player_lines, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)
    box_lines = [
        f"FINAL: {home_name} {hs} - {away_name} {as_}{' (OT)' if bool(ot_w) else ''}",
        "",
        "TEAM BOX SCORE",
        "-" * 60,
        f"{home_name}: Total Yds {hs_stats.get('total_yards', 0)} | Rush {hs_stats.get('rush_yards', 0)} | Pass {hs_stats.get('pass_yards', 0)} | TO {hs_stats.get('turnovers', 0)}",
        f"{away_name}: Total Yds {as_stats.get('total_yards', 0)} | Rush {as_stats.get('rush_yards', 0)} | Pass {as_stats.get('pass_yards', 0)} | TO {as_stats.get('turnovers', 0)}",
        "",
    ]
    box_lines.extend(player_lines)
    raw_play_log = getattr(game, "play_log_lines", None) or []
    if raw_play_log:
        game_log_text = "\n".join(
            [f"GAME LOG: {home_name} vs {away_name} (Playoffs - Coach Played)", "=" * 60, ""]
            + [str(x) for x in raw_play_log]
        ).strip()
    else:
        game_log_text = "No detailed play-by-play recorded for this coach-played playoff game."

    bracket_results.append(
        {
            "round": round_name,
            "home": home_name,
            "away": away_name,
            "home_score": hs,
            "away_score": as_,
            "winner": winner,
            "box_score_text": "\n".join(box_lines).strip(),
            "game_log_text": game_log_text,
            "player_stats": player_stats_list,
        }
    )
    sub["bracket_results"] = bracket_results

    if round_name == "Championship":
        sub["completed"] = True
        sub["champion"] = winner
        sub["runner_up"] = loser
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    if sub.get("completed"):
        playoffs["champion"] = sub.get("champion")
        playoffs["runner_up"] = sub.get("runner_up")

    state["standings"] = standings
    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


def finish_coach_scrimmage(
    user_id: str,
    save_id: str,
    game_id: str,
    scrimmage_stage: str,
) -> Dict[str, Any]:
    """Record coach-played scrimmage result and advance preseason."""
    from backend.services.game_service import get_game, game_state_dict
    state, save_dir = load_state(user_id, save_id)
    game = get_game(game_id)
    gs = game_state_dict(game)

    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    _, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)

    scrimmages = state.get("preseason_scrimmages") or []
    scrimmages.append({
        "name": scrimmage_stage,
        "completed": True,
        "home": home_name,
        "away": away_name,
        "home_score": gs["score_home"],
        "away_score": gs["score_away"],
        "ot": bool(gs.get("ot_winner")),
        "team_stats": gs.get("team_stats", {}),
        "player_stats": player_stats_list,
    })
    state["preseason_scrimmages"] = scrimmages

    stages = state.get("preseason_stages") or list(PRESEASON_STAGES)
    idx = int(state.get("preseason_stage_index", 0))
    if stages[idx] == scrimmage_stage:
        state["preseason_stage_index"] = idx + 1
        if state["preseason_stage_index"] >= len(stages):
            state["season_phase"] = "regular"
            state["current_week"] = 1

    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


def _advance_playoff_one_round_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate the next playoff round in-place for every classification bracket. Used by sim_playoff_round and finish_season."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {
        n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names
    }
    sp = season_stats_map_from_jsonable(state.get("playoff_season_player_stats") or {})
    playoffs = _ensure_playoffs_migrated(state, teams)
    if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
        state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
    _ensure_all_eligible_playoff_brackets(state, teams, standings)
    playoffs = state["playoffs"]
    by_class = playoffs.setdefault("by_class", {})
    if not by_class:
        raise ValueError("No playoff brackets configured")
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict) or pdata.get("completed"):
            continue
        seeds_raw = pdata.get("seeds") or []
        if not seeds_raw:
            names_in_class = _team_names_by_classification(teams).get(cls) or []
            if len(names_in_class) < 8:
                continue
            seeded = seed_teams(names_in_class, standings, top_n=8)
            seeds_raw = [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded]
            pdata["seeds"] = seeds_raw
        seeded_sorted = sorted(seeds_raw, key=lambda x: int(x.get("seed", 0)))
        seeded_names = [str(x["team"]) for x in seeded_sorted]
        if len(seeded_names) != 8:
            continue
        bracket_results = list(pdata.get("bracket_results") or [])
        champion, done = run_next_playoff_round_8(teams, standings, seeded_names, bracket_results, sp, None)
        runner_up = ""
        if done and bracket_results:
            cg = bracket_results[-1]
            runner_up = cg["away"] if cg["winner"] == cg["home"] else cg["home"]
        pdata["num_teams"] = 8
        pdata["seeds"] = seeds_raw
        pdata["bracket_results"] = bracket_results
        pdata["completed"] = done
        pdata["champion"] = champion if done else None
        pdata["runner_up"] = runner_up if done else None
        by_class[cls] = pdata
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    uc = playoffs.get("user_class")
    if uc and uc in by_class and by_class[uc].get("completed"):
        playoffs["champion"] = by_class[uc].get("champion")
        playoffs["runner_up"] = by_class[uc].get("runner_up")
    state["standings"] = standings
    state["playoff_season_player_stats"] = sp
    return state


def finish_season(user_id: str, save_id: str) -> Dict[str, Any]:
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    output_lines: List[str] = []
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
    phase_s = str(state.get("season_phase") or "").strip().lower()
    run_playoff_stats: Dict[int, Any] = {}
    if playoffs and playoffs.get("completed") and playoffs.get("champion"):
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = list(playoffs.get("bracket_results") or [])
    elif phase_s == "playoffs":
        while True:
            p = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
            if p and p.get("completed") and p.get("champion"):
                champion = str(p.get("champion") or "")
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            state = _advance_playoff_one_round_state(state)
    else:
        pool = _playoff_pool_team_names(state, teams)
        champion, bracket_results = run_playoff(teams, standings, pool, output_lines, run_playoff_stats, num_teams=8)
        runner_up = ""
        if bracket_results:
            champ_game = bracket_results[-1]
            runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]

    standings = state.get("standings") or standings
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())

    if phase_s == "playoffs" or (playoffs and playoffs.get("completed") and playoffs.get("champion")):
        season_player_stats = season_stats_map_from_jsonable(state.get("playoff_season_player_stats") or {})
    else:
        season_player_stats = season_stats_map_from_jsonable(run_playoff_stats)

    # --- Build per-team recap files for this season (before offseason changes roster/coaches) ---
    year_num = int(state.get("current_year", 1))
    recap_dir = os.path.join(save_dir, "season_recaps", f"year_{year_num}")
    try:
        makedirs_with_path_fallback(os.path.abspath(os.path.normpath(recap_dir)))
    except Exception:
        recap_dir = os.path.join(save_dir, "season_recaps")
        try:
            makedirs_with_path_fallback(os.path.abspath(os.path.normpath(recap_dir)))
        except OSError:
            os.makedirs(recap_dir, exist_ok=True)

    # Coach names (snapshot for history table)
    team_coaches: Dict[str, str] = {}
    for name, t in teams.items():
        coach = getattr(t, "coach", None)
        team_coaches[name] = str(getattr(coach, "name", "") or "")

    # Aggregate team stats from week_results (regular season)
    def _season_team_totals(team_name: str) -> Dict[str, int]:
        totals: Dict[str, int] = {
            "total_plays": 0,
            "rush_yards": 0,
            "pass_yards": 0,
            "total_yards": 0,
            "turnovers": 0,
            "explosive_run": 0,
            "explosive_pass": 0,
            "explosives": 0,
        }
        for wk in (state.get("week_results") or []):
            for g in (wk or []):
                if not isinstance(g, dict):
                    continue
                ts = g.get("team_stats") or {}
                row = ts.get(team_name)
                if not isinstance(row, dict):
                    continue
                for k in totals:
                    try:
                        totals[k] += int(row.get(k, 0) or 0)
                    except Exception:
                        pass
        return totals

    def _team_schedule_lines(team_name: str) -> List[str]:
        out: List[str] = []
        weeks = state.get("weeks") or []
        week_results = state.get("week_results") or []
        for wi, wk in enumerate(weeks):
            for gi, sched in enumerate(wk or []):
                if not isinstance(sched, dict):
                    continue
                h = sched.get("home")
                a = sched.get("away")
                if team_name not in (h, a):
                    continue
                played = False
                hs = as_ = 0
                ot = False
                if wi < len(week_results) and gi < len(week_results[wi]):
                    r = week_results[wi][gi]
                    if isinstance(r, dict):
                        played = bool(r.get("played"))
                        hs = int(r.get("home_score", 0) or 0)
                        as_ = int(r.get("away_score", 0) or 0)
                        ot = bool(r.get("ot"))
                out.append(format_recap_schedule_line(wi, team_name, h, a, played, hs, as_, ot))
        return out

    def _postseason_label(team_name: str, br: List[Dict[str, Any]]) -> str:
        if not team_name:
            return "—"
        if team_name == champion:
            return "State Champion"
        if team_name == runner_up:
            return "Runner-up"
        # If bracket results available, infer furthest round.
        best = None
        order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
        for g in br or []:
            if not isinstance(g, dict):
                continue
            if g.get("home") != team_name and g.get("away") != team_name:
                continue
            rnd = str(g.get("round") or "")
            v = order.get(rnd)
            if v and (best is None or v > best):
                best = v
        if best == 2:
            return "Semifinalist"
        if best == 1:
            return "Quarterfinalist"
        return "—"

    # Make recap files per team. Store relative paths in history.
    team_recap_files: Dict[str, str] = {}
    br_for_history = _recap_merged_bracket_results(state, list(bracket_results or []))
    for team_name in team_names:
        safe = "".join(c for c in str(team_name) if c.isalnum() or c in " _-").strip() or "team"
        p = os.path.join(recap_dir, f"{safe}.txt")
        srow = (standings or {}).get(team_name) or {}
        w = int(srow.get("wins", 0) or 0)
        l = int(srow.get("losses", 0) or 0)
        coach_name = team_coaches.get(team_name, "") or "—"
        postseason = _postseason_label(team_name, br_for_history)
        totals = _season_team_totals(team_name)
        player_rows = [ps for ps in season_player_stats.values() if getattr(ps, "team_name", None) == team_name]
        player_rows.sort(key=lambda ps: -(getattr(ps, "pass_yds", 0) + getattr(ps, "rush_yds", 0) + getattr(ps, "rec_yds", 0)))

        lines: List[str] = []
        lines.append(f"TEAM SEASON RECAP — Year {year_num}")
        lines.append("=" * 66)
        lines.append(f"Team: {team_name}")
        lines.append(f"Coach: {coach_name}")
        lines.append(f"Record: {w}-{l}")
        lines.append(f"Postseason: {postseason}")
        lines.append("")
        lines.append("SCHEDULE")
        lines.append("-" * 66)
        sched_lines = _team_schedule_lines(team_name)
        lines.extend(sched_lines if sched_lines else ["(no schedule found)"])
        playoff_lines = recap_postseason_lines_for_team(team_name, br_for_history)
        if playoff_lines:
            lines.append("")
            lines.append("POSTSEASON")
            lines.append("-" * 66)
            lines.extend(playoff_lines)
        lines.append("")
        lines.append("TEAM STATS (regular season totals)")
        lines.append("-" * 66)
        lines.append(f"Total plays: {totals['total_plays']}")
        lines.append(f"Rush yards: {totals['rush_yards']}")
        lines.append(f"Pass yards: {totals['pass_yards']}")
        lines.append(f"Total yards: {totals['total_yards']}")
        lines.append(f"Turnovers: {totals['turnovers']}")
        lines.append(f"Explosives: {totals['explosives']} (run {totals['explosive_run']} / pass {totals['explosive_pass']})")
        lines.append("")
        lines.append("ROSTER (end of season)")
        lines.append("-" * 66)
        t = teams.get(team_name)
        roster = getattr(t, "roster", None) or []
        if roster:
            for p_obj in roster:
                try:
                    pd = player_to_dict(p_obj)
                    nm = str(pd.get("name") or "")
                    pos = str(pd.get("position") or "")
                    ovr = pd.get("overall")
                    yr = pd.get("year")
                    lines.append(f"- {nm} ({pos}) OVR {ovr} — Year {yr}")
                except Exception:
                    continue
        else:
            lines.append("(no roster found)")
        lines.append("")
        lines.append("TOP PLAYER SEASON STATS")
        lines.append("-" * 66)
        if player_rows:
            for ps in player_rows[:20]:
                total_yds = int(getattr(ps, "pass_yds", 0) + getattr(ps, "rush_yds", 0) + getattr(ps, "rec_yds", 0))
                td = int(getattr(ps, "pass_td", 0) + getattr(ps, "rush_td", 0) + getattr(ps, "rec_td", 0))
                lines.append(f"- {ps.player_name}: {total_yds} yds, {td} TD | Pass {ps.pass_yds} ({ps.comp}/{ps.att}) | Rush {ps.rush_yds} | Rec {ps.rec_yds}")
        else:
            lines.append("(no player season stats recorded)")

        try:
            with open_text_with_path_fallback(os.path.abspath(p), "w") as f:
                f.write("\n".join(lines).strip() + "\n")
            team_recap_files[team_name] = os.path.relpath(p, save_dir)
        except Exception:
            # If writing fails, just skip this team
            continue

    append_season(
        champion=champion,
        runner_up=runner_up,
        team_names=team_names,
        standings=standings,
        season_player_stats=season_player_stats,
        year=year_num,
        bracket_results=br_for_history,
        team_coaches=team_coaches,
        team_recap_files=team_recap_files,
        save_dir=save_dir,
    )

    league_history = load_league_history(league_history_path(save_dir))

    graduation_report: Dict[str, List[Dict[str, Any]]] = {}
    for t in teams.values():
        ro = run_offseason_roster_turnover(t, league_history=league_history)
        reset_team_season_stats(t)
        graduated = ro.get("graduated") or []
        graduation_report[t.name] = [player_to_dict(p) for p in graduated]

    # advance year and reset season (interactive offseason before preseason)
    state["current_year"] = int(state.get("current_year", 1)) + 1
    state["season_phase"] = "offseason"
    state["current_week"] = 1
    state["offseason_stage_index"] = 0
    state["offseason_stages"] = list(OFFSEASON_UI_STAGES)
    state["offseason_graduation_report"] = graduation_report
    state["offseason_training_results"] = None
    state["offseason_winter_training_results"] = None
    # Improvements + coach development banks (earned in the just-finished season)
    user_team_name = str(state.get("user_team") or "")
    br_flat_fin = _recap_merged_bracket_results(state, list(bracket_results or []))
    sg_fin = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    if user_team_name:
        try:
            breakdown = _season_pp_awards_for_team(
                user_team_name,
                standings=standings,
                bracket_results=br_flat_fin,
                champion=champion,
                season_goals=sg_fin,
            )
            pp_total = int(breakdown.get("pp_total", 0) or 0)
        except Exception:
            breakdown = None
            pp_total = 0
    else:
        breakdown = None
        pp_total = 0
    try:
        cd_banks = build_offseason_coach_dev_banks_for_league(
            team_names,
            standings,
            br_flat_fin,
            champion,
            user_team_name or None,
            sg_fin,
            coaches_by_team={n: getattr(t, "coach", None) for n, t in teams.items()},
            existing_banks=state.get("offseason_coach_dev_banks") if isinstance(state.get("offseason_coach_dev_banks"), dict) else None,
        )
    except Exception:
        logger.exception("coach development banks (finish_season)")
        cd_banks = {}
        for n in team_names:
            try:
                cd_banks[n] = compute_coach_development_bank(
                    n,
                    standings,
                    br_flat_fin,
                    champion,
                    sg_fin if n == user_team_name else None,
                    coach=getattr(teams.get(n), "coach", None),
                    existing_bank=(state.get("offseason_coach_dev_banks") or {}).get(n)
                    if isinstance(state.get("offseason_coach_dev_banks"), dict)
                    else None,
                )
            except Exception:
                cd_banks[n] = _empty_coach_dev_bank()
    state["offseason_improvements_bank"] = {"pp_total": pp_total, "pp_remaining": pp_total, "breakdown": breakdown, "applied": {}}
    state["offseason_coach_dev_banks"] = cd_banks
    state["offseason_coach_dev_bank"] = (
        cd_banks.get(user_team_name) if user_team_name and isinstance(cd_banks.get(user_team_name), dict) else _empty_coach_dev_bank()
    )
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["preseason_stage_index"] = 0
    state["preseason_scrimmages"] = []
    state["preseason_scrimmage_opponents"] = []
    state["season_goals"] = state.get("season_goals") or []
    ensure_league_structure_in_state(state)
    wk, wr = _regular_season_week_boards(teams, state)
    state["weeks"] = wk
    state["week_results"] = wr
    state["standings"] = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    _assign_scrimmage_opponents_for_state(state)
    state.pop("playoffs", None)
    state.pop("playoff_season_player_stats", None)

    save_state(user_id, save_id, state, save_dir)
    return {"state": state, "champion": champion}


def sim_playoff_round(user_id: str, save_id: str) -> Dict[str, Any]:
    """Simulate the next playoff round (QF, SF, or Championship) and persist bracket results."""
    state, save_dir = load_state(user_id, save_id)
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        raise ValueError("save is not in playoffs")
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    p = _ensure_playoffs_migrated(state, teams)
    if _playoffs_global_completed(p):
        # If playoffs are already done, finalize immediately so history/recaps are available now.
        return finish_season(user_id, save_id)
    state = _advance_playoff_one_round_state(state)
    # Championship just finished: finalize season now so team/coach history updates immediately.
    p_after = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    if _playoffs_global_completed(p_after):
        save_state(user_id, save_id, state, save_dir)
        return finish_season(user_id, save_id)
    save_state(user_id, save_id, state, save_dir)
    champ = state.get("playoffs", {}).get("champion")
    return {"state": state, "champion": champ}


def sim_playoffs(user_id: str, save_id: str) -> Dict[str, Any]:
    """Simulate the full 8-team playoff in one shot (only when no games have been played yet)."""
    state, save_dir = load_state(user_id, save_id)
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        raise ValueError("save is not in playoffs")
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    _ensure_playoffs_migrated(state, teams)
    if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
        state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
    _ensure_all_eligible_playoff_brackets(state, teams, standings)
    playoffs = state["playoffs"]
    if any(
        len(list(x.get("bracket_results") or [])) > 0
        for x in (playoffs.get("by_class") or {}).values()
        if isinstance(x, dict)
    ):
        raise ValueError(
            "Playoffs already in progress. Use Continue to simulate one round at a time, "
            "or load a backup from before playoff games were played."
        )
    season_player_stats: Dict[int, Any] = dict(state.get("playoff_season_player_stats") or {})
    output_lines: List[str] = []
    by_class = playoffs.setdefault("by_class", {})
    uc = playoffs.get("user_class")
    user_champ = ""
    champion = ""
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict):
            continue
        names_in_class = _team_names_by_classification(teams).get(cls) or []
        if len(names_in_class) < 8:
            continue
        pool = names_in_class
        champion, bracket_results = run_playoff(teams, standings, pool, output_lines, season_player_stats, num_teams=8)
        runner_up = ""
        if bracket_results:
            champ_game = bracket_results[-1]
            runner_up = champ_game["away"] if champ_game["winner"] == champ_game["home"] else champ_game["home"]
        seeded = seed_teams(pool, standings, top_n=8)
        pdata.update(
            {
                "num_teams": 8,
                "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
                "bracket_results": bracket_results,
                "completed": True,
                "champion": champion,
                "runner_up": runner_up,
            }
        )
        by_class[cls] = pdata
        if cls == uc:
            user_champ = champion or ""
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    playoffs["champion"] = user_champ or next((by_class[c].get("champion") for c in by_class if by_class[c].get("champion")), None)
    state["playoffs"] = playoffs
    state["season_phase"] = "playoffs"
    state["standings"] = standings
    state["playoff_season_player_stats"] = season_player_stats
    # Full playoff sim ends with playoffs complete; finalize now for immediate history updates.
    if _playoffs_global_completed(playoffs):
        save_state(user_id, save_id, state, save_dir)
        return finish_season(user_id, save_id)
    save_state(user_id, save_id, state, save_dir)
    return {"state": state, "champion": playoffs.get("champion") or champion}

