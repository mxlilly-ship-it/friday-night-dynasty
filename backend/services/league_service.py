import copy
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.storage.db import db
from backend.storage.billing import check_trial_before_year2_preseason, user_is_entitled
from backend.billing_config import billing_required
from systems.save_system import (
    get_save_dir,
    save_league,
    ensure_save_has_history_and_records,
    player_to_dict,
    team_from_dict,
    team_to_dict,
)
from systems.teams_loader import (
    build_teams_from_json,
    build_teams_from_configs,
    enrich_save_teams_from_league_json,
    load_league_config_from_json,
    playoff_system_id_from_config,
)
from systems.playoff_systems import (
    DEFAULT_PLAYOFF_SYSTEM_ID,
    PlayoffSystemConfig,
    ensure_playoff_system_in_state,
    get_playoff_system,
    get_state_playoff_system,
)
from models.coach import apply_coach_config_dict
from models.team import Team
from systems.league_metadata import (
    apply_league_metadata_to_state,
    ensure_league_metadata_in_state,
    league_metadata_from_config,
)
from systems.league_structure import (
    default_league_structure,
    ensure_league_structure_in_state,
    playoff_pool_team_names,
)
from run_season import init_season_stats, parse_scores_from_final_line, run_game_silent, run_scrimmage_game
from systems.playoff_system import (
    PLAYOFF_ROUND_PRIORITY,
    REGIONAL_ROUND_NAMES,
    _regional_state_sf_pairings,
    _teams_per_region_from_seeds,
    next_playoff_round_name,
    next_regional_round_name,
    regional_in_region_round_names,
    round_names_for_bracket,
    round_pairings_for_size,
    run_next_playoff_round,
    run_next_playoff_round_8,
    run_next_playoff_round_regional,
    run_playoff,
    seed_teams,
    seed_teams_regional,
)
from systems.league_history import (
    append_season,
    load_league_history,
    build_team_program_totals_display,
)
from systems.coach_career_log import (
    append_season_to_coach_career_log,
    coach_history_rows_from_career_log,
    norm_coach_key,
    rebuild_coach_career_log_from_league_history,
)
from systems.prestige_system import migrate_state_team_points_fields, update_prestige
from systems.program_development_system import (
    apply_program_funding_for_season,
    apply_user_program_actions,
    build_inventory_view,
    credit_equipment_pp_to_improvements_bank,
    load_equipment_catalog,
    prepare_program_development_stage,
    program_development_summary_for_team,
    run_ai_program_purchases,
)
from systems.development_system import (
    build_ai_winter_training_allocations,
    normalize_winter_training_allocations,
    run_offseason_development,
    run_spring_ball_development,
    run_winter_training_session,
)
from systems.program_pp_economics import compute_season_program_pp_awards
from systems.program_progression import (
    PILLAR_CUMULATIVE_PP_MAX,
    clamp_progress_points,
    pillar_cumulative_pp_value,
    pillar_state_from_cumulative_pp_value,
    pp_delta_for_level_change,
)
from systems.offseason_manager import reset_team_season_stats, run_offseason_roster_turnover
from systems.seven_on_seven import VALID_TOURNAMENT_TIERS, run_seven_on_seven_tournament
from systems.team_ratings import calculate_player_overall, calculate_team_ratings
from systems.program_progression import team_composite_strength
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
    LEVEL_CP_THRESHOLDS,
    CP_ECONOMY_VERSION,
    apply_ai_coach_season_development,
    apply_coach_development,
    apply_coaching_card_cp_transaction,
    build_bulk_sim_coach_dev_body,
    build_initial_coach_dev_banks_for_dynasty,
    build_offseason_coach_dev_banks_for_league,
    compute_coach_development_bank,
    migrate_state_coach_dev_banks,
)
from systems.position_changes import apply_position_changes_to_team, run_ai_position_changes_for_team
from systems.regional_titles import (
    award_regular_season_regional_titles,
    compute_regular_season_regional_champions,
)
from systems.play_selection import (
    run_play_selection_for_team,
    run_play_selection_results_for_team,
    compute_learning_summary,
    get_install_meter_meta,
    normalize_game_plan_payload_for_storage,
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
from systems.coach_email_system import (
    delete_emails,
    ensure_coach_inbox,
    generate_coach_game_touch_emails,
    generate_playoff_round_emails,
    generate_week_checklist_email,
    generate_week_sim_emails,
    mark_emails_read,
    resolve_email_choice,
)
from backend.services.game_service import create_game as create_game_record
from backend.services.game_service import game_state_dict, build_coach_postgame_box_assets
from systems.game_stats import (
    season_stats_map_from_jsonable,
    season_stats_map_to_jsonable,
    player_game_stats_map_to_json_list,
)
from systems.gameplan_presets import list_defensive_preset_catalog, list_offensive_preset_catalog
from systems.gameplan_v2 import (
    make_default_offense_plan as make_default_offense_gameplan_v2,
    make_default_defense_plan as make_default_defense_gameplan_v2,
    validate_plan as validate_gameplan_v2,
    OFFENSE_CATEGORIES as GAMEPLAN_V2_OFF_CATEGORIES,
    DEFENSE_CATEGORIES as GAMEPLAN_V2_DEF_CATEGORIES,
)
from systems.weekly_gameplan import (
    HALFTIME_TRIGGERS_DEF,
    HALFTIME_TRIGGERS_OFF,
    apply_packages_to_coach,
    attach_cpu_coach_packages_for_game,
    autofill_callsheet_from_install,
    default_side_package,
    default_team_script,
    export_full_package,
    normalize_matchup_entry,
    normalize_side_package,
    validate_side_package,
)

logger = logging.getLogger(__name__)


def _coach_sim_emails_enabled() -> bool:
    """Week sim + playoff batch coach inbox. Disable with FND_DISABLE_WEEK_SIM_EMAILS=1/true/yes."""
    v = (os.environ.get("FND_DISABLE_WEEK_SIM_EMAILS") or "").strip().lower()
    return v not in ("1", "true", "yes")


def _maybe_coach_playoff_round_emails(state: Dict[str, Any]) -> None:
    if _coach_sim_emails_enabled():
        generate_playoff_round_emails(state)


def _hydrate_coach_inbox_persist_if_needed(user_id: str, save_id: str, state: Dict[str, Any], save_dir: str) -> None:
    """Ensure ``coach_inbox`` + starter mail exists; write league_save.json if new messages were appended."""
    inbox = state.get("coach_inbox")
    n_before = 0
    if isinstance(inbox, dict) and isinstance(inbox.get("emails"), list):
        n_before = len(inbox["emails"])
    ensure_coach_inbox(state)
    _maybe_generate_week_checklist_email(state)
    inbox2 = state.get("coach_inbox")
    n_after = 0
    if isinstance(inbox2, dict) and isinstance(inbox2.get("emails"), list):
        n_after = len(inbox2["emails"])
    if n_after > n_before:
        save_state(user_id, save_id, state, save_dir)


def patch_coach_inbox_state(
    state: Dict[str, Any],
    *,
    mark_read: Optional[List[str]] = None,
    choose: Optional[Dict[str, str]] = None,
    delete: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Stateless coach inbox patch for browser/local saves."""
    inbox = ensure_coach_inbox(state)
    if mark_read:
        mark_emails_read(inbox, [str(x) for x in mark_read if x])
    if choose and isinstance(choose, dict):
        eid = choose.get("email_id")
        cid = choose.get("choice_id")
        if eid and cid:
            resolve_email_choice(inbox, str(eid), str(cid))
    if delete:
        delete_emails(inbox, [str(x) for x in delete if x])
    return state


def patch_coach_inbox(
    user_id: str,
    save_id: str,
    *,
    mark_read: Optional[List[str]] = None,
    choose: Optional[Dict[str, str]] = None,
    delete: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Mark messages read, resolve a choice, and/or delete messages; persists state."""
    state, save_dir = load_state(user_id, save_id)
    patch_coach_inbox_state(
        state,
        mark_read=mark_read,
        choose=choose,
        delete=delete,
    )
    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


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


# Round priority used to order a team's playoff games on the season recap.
# Larger value = deeper run. Sourced from systems.playoff_system so adding new
# round names (e.g. "Round of 16" / "Round of 32") only changes one place.
_RECAP_PLAYOFF_ROUND_ORDER = dict(PLAYOFF_ROUND_PRIORITY)


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


def _playoffs_inner_for_class(
    playoffs_by_class: Any, classification: str
) -> Optional[Dict[str, Any]]:
    if not isinstance(playoffs_by_class, dict) or not playoffs_by_class:
        return None
    cls = str(classification or "").strip()
    if cls in playoffs_by_class and isinstance(playoffs_by_class[cls], dict):
        return playoffs_by_class[cls]
    low = cls.lower()
    for k, v in playoffs_by_class.items():
        if str(k).strip().lower() == low and isinstance(v, dict):
            return v
    return None


def _bracket_depth_label(team_n: str, bracket_results: Any) -> str:
    """Furthest round a team reached without winning it (Quarterfinalist /
    Semifinalist / Round-of-16 finalist / Regional Finalist / etc.)."""
    order = PLAYOFF_ROUND_PRIORITY
    best_rnd: Optional[str] = None
    best_v: Optional[int] = None
    for g in bracket_results or []:
        if not isinstance(g, dict):
            continue
        if g.get("home") != team_n and g.get("away") != team_n:
            continue
        rnd = str(g.get("round") or "")
        v = order.get(rnd)
        if v and (best_v is None or v > best_v):
            best_v = v
            best_rnd = rnd
    if best_rnd == "Semifinal":
        return "Semifinalist"
    if best_rnd == "Quarterfinal":
        return "Quarterfinalist"
    if best_rnd == "Regional Final":
        return "Regional Finalist"
    if best_rnd == "Regional Semifinal":
        return "Regional Semifinalist"
    if best_rnd == "Regional Quarterfinal":
        return "Regional Quarterfinalist"
    if best_rnd and best_rnd.startswith("Round of "):
        # e.g. "Round of 16" -> "Round of 16 finalist"
        return f"{best_rnd} finalist"
    return "—"


def _postseason_label_archived(
    team_n: str, season_entry: Dict[str, Any], teams_map: Dict[str, Any]
) -> str:
    """Postseason chip for one team on a finished season row (multiclass-aware)."""
    pbc = season_entry.get("playoffs_by_class")
    cls = _classification_of_team(teams_map, team_n)
    inner = _playoffs_inner_for_class(pbc, cls) if pbc else None
    if isinstance(inner, dict):
        if team_n == inner.get("champion"):
            return "State Champion"
        if team_n == inner.get("runner_up"):
            return "Runner-up"
        return _bracket_depth_label(team_n, inner.get("bracket_results"))
    if team_n == season_entry.get("state_champion"):
        return "State Champion"
    if team_n == season_entry.get("runner_up"):
        return "Runner-up"
    playoffs = (
        season_entry.get("playoffs")
        if isinstance(season_entry.get("playoffs"), dict)
        else {}
    )
    br = playoffs.get("bracket_results") or []
    return _bracket_depth_label(team_n, br)


def _recap_postseason_line_label_for_team(
    team_n: str,
    *,
    state: Dict[str, Any],
    season_entry_top_champion: str,
    season_entry_top_runner_up: str,
    br_flat: List[Dict[str, Any]],
    teams_map: Dict[str, Any],
) -> str:
    """Postseason line for per-team recap .txt (multiclass-aware; matches archived history labels)."""
    synthetic: Dict[str, Any] = {
        "state_champion": season_entry_top_champion,
        "runner_up": season_entry_top_runner_up,
        "playoffs": {"bracket_results": list(br_flat or [])},
    }
    snap = _playoffs_by_class_snapshot(state)
    if snap:
        synthetic["playoffs_by_class"] = snap
    return _postseason_label_archived(team_n, synthetic, teams_map)


def _team_names_by_classification(teams: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for name in teams:
        c = _classification_of_team(teams, name)
        out.setdefault(c, []).append(name)
    for k in out:
        out[k] = sorted(out[k])
    return out


def _region_of_team(teams: Dict[str, Any], name: Optional[str]) -> str:
    """Region label for a team (e.g. ``"North"``, ``"East"``).

    Empty / missing region is normalized to ``""`` so callers can treat that
    as "no region info" and skip regional bucketing.  Mirrors the shape of
    :func:`_classification_of_team`.
    """
    if not name or name not in teams:
        return ""
    t = teams[name]
    if isinstance(t, dict):
        r = t.get("region")
    else:
        r = getattr(t, "region", None)
    return str(r).strip() if r is not None else ""


def _team_names_by_region_within_class(
    teams: Dict[str, Any], classification: str
) -> Dict[str, List[str]]:
    """Group team names by region for a single classification.

    Used when seeding regional brackets — each region's pool is sorted
    independently and the top-N from each region make the playoff field.
    Teams without a region are bucketed under an empty key so the caller
    can detect "this class has no region splits" and skip the regional
    seeding.
    """
    out: Dict[str, List[str]] = {}
    for name in teams:
        if _classification_of_team(teams, name) != classification:
            continue
        out.setdefault(_region_of_team(teams, name), []).append(name)
    for k in out:
        out[k] = sorted(out[k])
    return out


def _playoffs_global_completed(playoffs: Dict[str, Any]) -> bool:
    bc = playoffs.get("by_class")
    if isinstance(bc, dict) and bc:
        return all(bool(x.get("completed")) for x in bc.values() if isinstance(x, dict))
    return bool(playoffs.get("completed"))


def _sync_playoff_top_level_champion_runner(playoffs: Dict[str, Any]) -> None:
    """Stamp top-level champion/runner_up from ``by_class`` (same idea as ``sim_playoffs``).

    ``_advance_playoff_one_round_state`` used to only copy when ``user_class`` finished, so multiclass
    saves could end with ``completed`` true but a missing top-level ``champion``. That broke the
    ``finish_season`` fast-path and could spin in the playoff-advance loop — and confused clients.
    """
    if not isinstance(playoffs, dict):
        return
    bc = playoffs.get("by_class")
    if not isinstance(bc, dict) or not bc:
        return
    uc = playoffs.get("user_class")
    user_champ = ""
    user_ru = ""
    if uc and isinstance(bc.get(uc), dict):
        inner = bc[uc]
        user_champ = str(inner.get("champion") or "").strip()
        user_ru = str(inner.get("runner_up") or "").strip()
    fb_champ = ""
    fb_ru = ""
    for c in sorted(bc.keys()):
        inner = bc.get(c)
        if not isinstance(inner, dict):
            continue
        ch = str(inner.get("champion") or "").strip()
        if ch:
            fb_champ = ch
            fb_ru = str(inner.get("runner_up") or "").strip()
            break
    top_c = user_champ or fb_champ
    if top_c:
        playoffs["champion"] = top_c
    top_ru = user_ru if user_champ else fb_ru
    if top_ru:
        playoffs["runner_up"] = top_ru


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
        legacy_size = int(p.get("num_teams") or 0)
        if legacy_size < 2:
            legacy_size = int(get_state_playoff_system(state).bracket_size)
        inner = {
            "num_teams": legacy_size,
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
    """Build the postseason bracket(s) for the active playoff system.

    The bracket size, scope (per-classification vs state-wide), seeding mode
    (overall vs regional), and minimum team count come from the league's
    :class:`PlayoffSystemConfig`, so adding a new state system only requires
    registering it in ``playoff_systems.py``.
    """
    cfg = get_state_playoff_system(state)
    bracket_size = int(cfg.bracket_size)
    min_teams = int(cfg.min_teams)
    is_regional = cfg.seeding_mode == "regional"
    by_class: Dict[str, Any] = {}

    def _overall_bracket_entry(seeded) -> Dict[str, Any]:
        return {
            "num_teams": bracket_size,
            "seeds": [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        }

    def _regional_bracket_entry(seed_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "num_teams": bracket_size,
            "seeds": list(seed_dicts),
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        }

    def _build_regional_seeds_for_pool(pool_class: str) -> Optional[List[Dict[str, Any]]]:
        """Try to build a regional seed list for one classification; return
        None if any region lacks enough teams (caller falls back to overall
        seeding so the bracket still runs)."""
        regions = _team_names_by_region_within_class(teams, pool_class)
        # Drop the no-region bucket — those teams are not eligible for a
        # regional bracket because they have no region to qualify out of.
        regions = {r: ns for r, ns in regions.items() if r}
        if len(regions) < cfg.regions_per_class:
            return None
        # Pick the top ``regions_per_class`` regions by team count for stable
        # bracket layout when a class happens to have extra regions defined.
        chosen = dict(sorted(regions.items())[: cfg.regions_per_class])
        seeds = seed_teams_regional(chosen, standings, teams_per_region=cfg.teams_per_region)
        if len(seeds) != bracket_size:
            return None
        return seeds

    if cfg.per_classification:
        groups = _team_names_by_classification(teams)
        for cls, names in groups.items():
            if len(names) < min_teams:
                continue
            if is_regional:
                regional_seeds = _build_regional_seeds_for_pool(cls)
                if regional_seeds is not None:
                    by_class[cls] = _regional_bracket_entry(regional_seeds)
                    continue
                # Regional layout couldn't be built (fewer than 4 regions or
                # an under-filled region). Fall back to overall seeding for
                # this class so they still get a bracket.
            seeded = seed_teams(names, standings, top_n=bracket_size)
            by_class[cls] = _overall_bracket_entry(seeded)
    ut = state.get("user_team")
    uc = _classification_of_team(teams, ut) if ut else None
    if cfg.per_classification and uc and uc not in by_class:
        pool = _playoff_pool_team_names(state, teams)
        if len(pool) >= min_teams:
            seeded = seed_teams(pool, standings, top_n=bracket_size)
            by_class[uc] = _overall_bracket_entry(seeded)
    if not by_class:
        # Either the active system is state-wide (per_classification=False) or
        # no classification had enough teams; fall back to the full eligible pool.
        pool = _playoff_pool_team_names(state, teams)
        if len(pool) >= min_teams:
            seeded = seed_teams(pool, standings, top_n=bracket_size)
            key = uc or "UNK"
            by_class[key] = _overall_bracket_entry(seeded)
            uc = key
    return {
        "by_class": by_class,
        "user_class": uc or (next(iter(by_class)) if by_class else None),
        "completed": False,
    }


def _ensure_all_eligible_playoff_brackets(
    state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]
) -> None:
    """Ensure ``playoffs.by_class`` has a bracket for every eligible classification.

    Eligibility (bracket size + minimum team count + per-class scope) is read
    from the active :class:`PlayoffSystemConfig`, so per-classification systems
    like WV ("≥8 teams in the class") and future variants (different bracket
    sizes, single state-wide bracket) all flow through the same path.

    Idempotent: does not remove or reset brackets that already have seeds or
    any played games. Needed because legacy migration and early init only
    stored the user's class, so other classes never received a ``by_class``
    entry even when eligible.
    """
    cfg = get_state_playoff_system(state)
    bracket_size = int(cfg.bracket_size)
    min_teams = int(cfg.min_teams)
    is_regional = cfg.seeding_mode == "regional"

    playoffs = state.setdefault("playoffs", {})
    if not isinstance(playoffs, dict):
        state["playoffs"] = {}
        playoffs = state["playoffs"]
    bc = playoffs.setdefault("by_class", {})
    if cfg.per_classification:
        groups = _team_names_by_classification(teams)
        for cls, names in groups.items():
            if len(names) < min_teams:
                continue
            if cls in bc and isinstance(bc[cls], dict):
                sub = bc[cls]
                seeds = sub.get("seeds")
                br = sub.get("bracket_results") or []
                if isinstance(seeds, list) and len(seeds) >= 1:
                    continue
                if isinstance(br, list) and len(br) > 0:
                    continue
            built_regional = False
            if is_regional:
                regions = _team_names_by_region_within_class(teams, cls)
                regions = {r: ns for r, ns in regions.items() if r}
                if len(regions) >= cfg.regions_per_class:
                    chosen = dict(sorted(regions.items())[: cfg.regions_per_class])
                    seed_dicts = seed_teams_regional(
                        chosen, standings, teams_per_region=cfg.teams_per_region
                    )
                    if len(seed_dicts) == bracket_size:
                        bc[cls] = {
                            "num_teams": bracket_size,
                            "seeds": list(seed_dicts),
                            "bracket_results": [],
                            "completed": False,
                            "champion": None,
                            "runner_up": None,
                        }
                        built_regional = True
            if built_regional:
                continue
            seeded = seed_teams(names, standings, top_n=bracket_size)
            bc[cls] = {
                "num_teams": bracket_size,
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


def _reconcile_playoff_brackets_to_config(
    state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]
) -> None:
    """Align ``by_class`` bracket size with the save's ``playoff_system`` when not yet started.

    Fixes dynasties created with the legacy 8-team ``wv`` id while using a 16-team
    league file, and corrects stale ``num_teams`` before the first postseason game.
    """
    cfg = get_state_playoff_system(state)
    desired = int(cfg.bracket_size)
    min_teams = int(cfg.min_teams)
    playoffs = state.get("playoffs")
    if not isinstance(playoffs, dict):
        return
    bc = playoffs.get("by_class")
    if not isinstance(bc, dict) or not bc:
        return
    groups = _team_names_by_classification(teams)
    for cls, pdata in list(bc.items()):
        if not isinstance(pdata, dict):
            continue
        if pdata.get("completed"):
            continue
        if pdata.get("bracket_results"):
            continue
        names = groups.get(cls) or []
        if len(names) < min_teams:
            continue
        seeds = pdata.get("seeds") or []
        current = int(pdata.get("num_teams") or len(seeds) or 0)
        if current == desired and len(seeds) == desired:
            continue
        seeded = seed_teams(names, standings, top_n=desired)
        pdata["num_teams"] = desired
        pdata["seeds"] = [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded]
        bc[cls] = pdata
    playoffs["by_class"] = bc


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


def _playoffs_by_class_snapshot(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Deep copy multiclass playoff brackets for league_history (UI: per-class postseason archive)."""
    import copy

    po = state.get("playoffs")
    if not isinstance(po, dict):
        return None
    bc = po.get("by_class")
    if not isinstance(bc, dict) or not bc:
        return None
    try:
        return copy.deepcopy(bc)
    except Exception:
        return None


def _standings_for_transfer_portal(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transfer portal pressure uses the season that just ended.
    After ``finish_season``, ``state['standings']`` is reset to 0-0 for the new year — use the snapshot.
    """
    snap = state.get("offseason_transfer_snapshot_standings")
    if isinstance(snap, dict) and snap:
        return snap
    raw = state.get("standings")
    return raw if isinstance(raw, dict) else {}


def _clear_offseason_transfer_ui_state(state: Dict[str, Any]) -> None:
    for k in (
        "offseason_transfer_stage_1",
        "offseason_transfer_stage_2",
        "offseason_transfer_review",
        "offseason_transfer_stage_1_pending_review",
        "offseason_transfer_stage_2_pending_review",
    ):
        state.pop(k, None)


def _transfers_disabled(state: Dict[str, Any]) -> bool:
    return bool(state.get("transfers_disabled"))


def _disabled_transfer_stage_1_payload() -> Dict[str, Any]:
    return {
        "disabled": True,
        "entries": [],
        "selected_count": 0,
        "pool_pct": 0.0,
        "eligible_count": 0,
    }


def _disabled_transfer_stage_2_payload() -> Dict[str, Any]:
    return {
        "disabled": True,
        "entries": [],
        "moved_count": 0,
        "blocked_count": 0,
    }


def _apply_disabled_transfer_stage_2(state: Dict[str, Any]) -> None:
    payload = _disabled_transfer_stage_2_payload()
    state["offseason_transfer_stage_2"] = payload
    state["offseason_transfer_review"] = {
        "disabled": True,
        "entries": [],
        "moved_count": 0,
        "blocked_count": 0,
    }


def _transfer_stage_1_apply_news(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
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


def _transfer_stage_2_apply_news_and_review(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    state["offseason_transfer_stage_2"] = payload
    moved_entries = [r for r in list(payload.get("entries") or []) if r.get("to_team")]
    state["offseason_transfer_review"] = {
        "entries": moved_entries,
        "moved_count": len(moved_entries),
        "blocked_count": int(payload.get("blocked_count", 0) or 0),
    }
    transfer_events: List[Dict[str, Any]] = []
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


def _transfer_playoff_snapshot(state: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Champion + bracket games from the last resolved playoffs (for goal / tier evaluation in transfers)."""
    p = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    br = list(p.get("bracket_results") or [])
    if not br:
        br = _flatten_playoff_bracket_results(p)
    ch = str(p.get("champion") or "")
    if not ch:
        bc = p.get("by_class")
        if isinstance(bc, dict):
            for sub in bc.values():
                if isinstance(sub, dict) and sub.get("champion"):
                    ch = str(sub.get("champion") or "")
                    if not br:
                        br = list(sub.get("bracket_results") or [])
                    break
    return ch, br


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
    from backend.data_paths import saves_base_dir

    return saves_base_dir()


def _get_user_logo_dir(user_id: str) -> str:
    safe_user = _safe_path_segment(user_id, default="user")
    return os.path.join(_saves_base_dir(), safe_user, "_logos")


def save_dir_team_logo(save_dir: str, team_name: str, data: bytes, extension: str) -> str:
    """Write a team crest into ``save_dir/_logos/`` (multiplayer league or save folder)."""
    ext = str(extension or "").lower().strip()
    if ext not in _LOGO_EXTENSIONS:
        raise ValueError("Unsupported logo file type. Use PNG, JPG, JPEG, or WEBP.")
    if not data:
        raise ValueError("Logo file is empty.")
    safe_name = _safe_logo_name(team_name)
    logo_dir = os.path.join(save_dir, "_logos")
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


def _find_team_logo_by_stem(logo_dir: str, stem: str) -> Optional[str]:
    for ext in _LOGO_EXTENSIONS:
        plain = os.path.abspath(os.path.join(logo_dir, f"{stem}{ext}"))
        for p in io_path_candidates(plain):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                continue
    return None


def _find_team_logo_in_dir(logo_dir: str, team_name: str) -> Optional[str]:
    if not team_name or not os.path.isdir(logo_dir):
        return None
    stems_to_try: List[str] = []
    safe_name = _safe_logo_name(team_name)
    if safe_name:
        stems_to_try.append(safe_name)
    raw = str(team_name).strip()
    if raw and raw not in stems_to_try:
        stems_to_try.append(raw)
    try:
        from systems.team_asset_lookup import team_asset_name_lookup

        lookup = team_asset_name_lookup()
        norm = _normalize_name(team_name)
        for key, canonical in lookup.items():
            if _normalize_name(canonical) == norm and key != norm:
                stems_to_try.append(key)
    except Exception:
        pass
    seen: set[str] = set()
    for stem in stems_to_try:
        if stem in seen:
            continue
        seen.add(stem)
        path = _find_team_logo_by_stem(logo_dir, stem)
        if path:
            return path
    try:
        names = os.listdir(logo_dir)
    except OSError:
        return None
    for fname in names:
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in _LOGO_EXTENSIONS:
            continue
        if match_logo_filename_to_team([team_name], stem) == team_name:
            plain = os.path.abspath(os.path.join(logo_dir, fname))
            for p in io_path_candidates(plain):
                try:
                    if os.path.isfile(p):
                        return p
                except OSError:
                    continue
    return None


def get_team_logo_path(user_id: str, team_name: str, *, custom_league: bool = False) -> Optional[str]:
    if not custom_league:
        from backend.data_paths import default_logos_dir

        path = _find_team_logo_in_dir(default_logos_dir(), team_name)
        if path:
            return path
    return _find_team_logo_in_dir(_get_user_logo_dir(user_id), team_name)


def get_default_team_logo_path(team_name: str) -> Optional[str]:
    """Built-in crest from data/logos/ only (no per-user overrides)."""
    from backend.data_paths import default_logos_dir

    return _find_team_logo_in_dir(default_logos_dir(), team_name)


def default_logos_cache_version() -> int:
    """Max mtime of files in data/logos/ — for browser cache busting."""
    from backend.data_paths import default_logos_dir

    logo_dir = default_logos_dir()
    latest = 0
    try:
        for name in os.listdir(logo_dir):
            path = os.path.join(logo_dir, name)
            try:
                if os.path.isfile(path):
                    latest = max(latest, int(os.path.getmtime(path)))
            except OSError:
                continue
    except OSError:
        pass
    return latest


def _get_user_stadium_dir(user_id: str) -> str:
    safe_user = _safe_path_segment(user_id, default="user")
    return os.path.join(_saves_base_dir(), safe_user, "_stadiums")


def save_team_stadium(user_id: str, team_name: str, data: bytes, extension: str) -> str:
    """Write stadium image for ``team_name`` (same extensions as logos). Replaces any prior file for that team."""
    ext = str(extension or "").lower().strip()
    if ext not in _LOGO_EXTENSIONS:
        raise ValueError("Unsupported stadium image type. Use PNG, JPG, JPEG, or WEBP.")
    if not data:
        raise ValueError("Stadium file is empty.")
    safe_name = _safe_logo_name(team_name)
    stadium_dir = _get_user_stadium_dir(user_id)
    stadium_dir_abs = os.path.abspath(os.path.normpath(stadium_dir))
    try:
        makedirs_with_path_fallback(stadium_dir_abs)
    except OSError:
        os.makedirs(stadium_dir, exist_ok=True)
    for old_ext in _LOGO_EXTENSIONS:
        unlink_if_exists_any(os.path.abspath(os.path.join(stadium_dir, f"{safe_name}{old_ext}")))
    out_plain = os.path.abspath(os.path.join(stadium_dir, f"{safe_name}{ext}"))
    f = open_binary_with_path_fallback(out_plain, "wb")
    try:
        f.write(data)
        return f.name
    finally:
        f.close()


def get_team_stadium_path(user_id: str, team_name: str) -> Optional[str]:
    safe_name = _safe_logo_name(team_name)
    stadium_dir = _get_user_stadium_dir(user_id)
    for ext in _LOGO_EXTENSIONS:
        plain = os.path.abspath(os.path.join(stadium_dir, f"{safe_name}{ext}"))
        for p in io_path_candidates(plain):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                continue
    return None


def _get_user_helmet_dir(user_id: str) -> str:
    safe_user = _safe_path_segment(user_id, default="user")
    return os.path.join(_saves_base_dir(), safe_user, "_helmets")


def save_team_helmet(user_id: str, team_name: str, data: bytes, extension: str) -> str:
    """Write helmet image for ``team_name`` (same extensions as logos). Replaces any prior file for that team."""
    ext = str(extension or "").lower().strip()
    if ext not in _LOGO_EXTENSIONS:
        raise ValueError("Unsupported helmet image type. Use PNG, JPG, JPEG, or WEBP.")
    if not data:
        raise ValueError("Helmet file is empty.")
    safe_name = _safe_logo_name(team_name)
    helmet_dir = _get_user_helmet_dir(user_id)
    helmet_dir_abs = os.path.abspath(os.path.normpath(helmet_dir))
    try:
        makedirs_with_path_fallback(helmet_dir_abs)
    except OSError:
        os.makedirs(helmet_dir, exist_ok=True)
    for old_ext in _LOGO_EXTENSIONS:
        unlink_if_exists_any(os.path.abspath(os.path.join(helmet_dir, f"{safe_name}{old_ext}")))
    out_plain = os.path.abspath(os.path.join(helmet_dir, f"{safe_name}{ext}"))
    f = open_binary_with_path_fallback(out_plain, "wb")
    try:
        f.write(data)
        return f.name
    finally:
        f.close()


def get_team_helmet_path(user_id: str, team_name: str) -> Optional[str]:
    safe_name = _safe_logo_name(team_name)
    helmet_dir = _get_user_helmet_dir(user_id)
    for ext in _LOGO_EXTENSIONS:
        plain = os.path.abspath(os.path.join(helmet_dir, f"{safe_name}{ext}"))
        for p in io_path_candidates(plain):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                continue
    return None


JERSEY_KINDS = ("home", "away", "alternate")


def _normalize_jersey_kind(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("alt", "alternate", "alternates", "alt-jersey", "alt_jersey"):
        return "alternate"
    if s in ("away", "road", "visitor", "visitors"):
        return "away"
    return "home"


def _get_user_jersey_dir(user_id: str) -> str:
    safe_user = _safe_path_segment(user_id, default="user")
    return os.path.join(_saves_base_dir(), safe_user, "_jerseys")


def save_team_jersey(user_id: str, team_name: str, kind: str, data: bytes, extension: str) -> str:
    """Write home/away/alternate jersey image for ``team_name``."""
    ext = str(extension or "").lower().strip()
    if ext not in _LOGO_EXTENSIONS:
        raise ValueError("Unsupported jersey image type. Use PNG, JPG, JPEG, or WEBP.")
    if not data:
        raise ValueError("Jersey file is empty.")
    jersey_kind = _normalize_jersey_kind(kind)
    safe_name = _safe_logo_name(team_name)
    team_dir = os.path.abspath(os.path.normpath(os.path.join(_get_user_jersey_dir(user_id), safe_name)))
    try:
        makedirs_with_path_fallback(team_dir)
    except OSError:
        os.makedirs(team_dir, exist_ok=True)
    for old_ext in _LOGO_EXTENSIONS:
        unlink_if_exists_any(os.path.abspath(os.path.join(team_dir, f"{jersey_kind}{old_ext}")))
    out_plain = os.path.abspath(os.path.join(team_dir, f"{jersey_kind}{ext}"))
    f = open_binary_with_path_fallback(out_plain, "wb")
    try:
        f.write(data)
        return f.name
    finally:
        f.close()


def get_team_jersey_path(user_id: str, team_name: str, kind: str) -> Optional[str]:
    jersey_kind = _normalize_jersey_kind(kind)
    safe_name = _safe_logo_name(team_name)
    team_dir = os.path.abspath(os.path.normpath(os.path.join(_get_user_jersey_dir(user_id), safe_name)))
    for ext in _LOGO_EXTENSIONS:
        plain = os.path.abspath(os.path.join(team_dir, f"{jersey_kind}{ext}"))
        for p in io_path_candidates(plain):
            try:
                if os.path.isfile(p):
                    return p
            except OSError:
                continue
    return None


def _stem_variants_for_logo_match(stem: str) -> List[str]:
    """Try filename stems with common suffixes stripped (e.g. Martinsburg_logo → Martinsburg)."""
    return _stem_variants_for_asset_match(stem, ())


def _stem_variants_for_asset_match(stem: str, extra_suffixes: tuple = ()) -> List[str]:
    stem = str(stem or "").strip()
    if not stem:
        return []
    variants: List[str] = [stem]
    suffixes = ("_logo", "-logo", "_LOGO", "-LOGO", " logo") + tuple(extra_suffixes)
    for suffix in suffixes:
        if len(stem) > len(suffix) and stem.lower().endswith(suffix.lower()):
            variants.append(stem[: -len(suffix)].strip())
    out: List[str] = []
    seen = set()
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _match_filename_stem_to_team(teams: List[str], filename_stem: str, extra_suffixes: tuple = ()) -> Optional[str]:
    by_norm: Dict[str, str] = {}
    for t in teams:
        name = str(t or "").strip()
        if not name:
            continue
        by_norm[_normalize_name(name)] = name
    for stem in _stem_variants_for_asset_match(filename_stem, extra_suffixes):
        stem_norm = _normalize_name(stem)
        if stem_norm and stem_norm in by_norm:
            return by_norm[stem_norm]
    return None


def match_logo_filename_to_team(teams: List[str], filename_stem: str) -> Optional[str]:
    hit = _match_filename_stem_to_team(teams, filename_stem, ())
    if hit:
        return hit
    from systems.team_asset_lookup import team_asset_name_lookup

    lookup = team_asset_name_lookup()
    by_norm: Dict[str, str] = {}
    for t in teams:
        name = str(t or "").strip()
        if not name:
            continue
        by_norm[_normalize_name(name)] = name
    for stem in _stem_variants_for_logo_match(filename_stem):
        key = _normalize_name(stem)
        if not key:
            continue
        canonical = lookup.get(key)
        if not canonical:
            continue
        cn = _normalize_name(canonical)
        if cn in by_norm:
            return by_norm[cn]
    return None


def match_stadium_filename_to_team(teams: List[str], filename_stem: str) -> Optional[str]:
    return _match_filename_stem_to_team(
        teams,
        filename_stem,
        ("_stadium", "-stadium", "_field", "-field", " stadium"),
    )


def match_helmet_filename_to_team(teams: List[str], filename_stem: str) -> Optional[str]:
    return _match_filename_stem_to_team(
        teams,
        filename_stem,
        ("_helmet", "-helmet", " helmet"),
    )


def match_jersey_filename_to_team(teams: List[str], filename_stem: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (team_name, jersey_kind) parsed from filename stem, or (None, None)."""
    stem = str(filename_stem or "").strip()
    if not stem:
        return None, None
    kind_suffixes = (
        ("_alternate", "alternate"),
        ("-alternate", "alternate"),
        ("_alt", "alternate"),
        ("-alt", "alternate"),
        (" alternate", "alternate"),
        ("_away", "away"),
        ("-away", "away"),
        (" away", "away"),
        ("_road", "away"),
        ("-road", "away"),
        ("_home", "home"),
        ("-home", "home"),
        (" home", "home"),
        ("_jersey", "home"),
        ("-jersey", "home"),
        (" jersey", "home"),
    )
    for suffix, kind in kind_suffixes:
        if len(stem) > len(suffix) and stem.lower().endswith(suffix.lower()):
            team_stem = stem[: -len(suffix)].strip()
            team = _match_filename_stem_to_team(teams, team_stem, ())
            if team:
                return team, kind
    team = match_logo_filename_to_team(teams, stem)
    if team:
        return team, "home"
    return None, None


PRESEASON_STAGES: List[str] = [
    "Playbook Select",
    "Play Selection",
    "Play Selection Results",
    "Position changes",
    "Set Depth Chart",
    "Scrimmage 1",
    "Scrimmage 2",
    "Home Game Themes",
    "Set Goals",
]


def normalize_preseason_stages(state: Dict[str, Any]) -> bool:
    """Insert new preseason stages into in-progress saves (by stage name)."""
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase not in ("preseason", "regular"):
        return False
    canonical = list(PRESEASON_STAGES)
    current = list(state.get("preseason_stages") or [])
    if current == canonical:
        return False
    raw_idx = int(state.get("preseason_stage_index", 0))
    if current:
        idx = max(0, min(raw_idx, len(current) - 1))
        old_stage = str(current[idx] or "").strip()
    else:
        old_stage = None
    state["preseason_stages"] = canonical
    if old_stage and old_stage in canonical:
        state["preseason_stage_index"] = canonical.index(old_stage)
    else:
        state["preseason_stage_index"] = max(0, min(raw_idx, len(canonical) - 1))
    return True


def _apply_home_game_themes_from_playbook(
    state: Dict[str, Any],
    team_names: List[str],
    user_team_name: Optional[str],
    playbook: Dict[str, Any],
) -> None:
    from systems.home_game_themes import apply_user_home_game_themes, assign_ai_home_game_themes

    ut = str(user_team_name or "").strip()
    mp = is_multiplayer_league_state(state)
    raw = playbook.get("home_game_themes")
    if ut:
        if isinstance(raw, list):
            apply_user_home_game_themes(state, ut, raw, set_global_confirmed=not mp)
            if mp:
                confirmed = state.get("home_game_themes_confirmed_teams")
                if not isinstance(confirmed, dict):
                    confirmed = {}
                confirmed[ut] = True
                state["home_game_themes_confirmed_teams"] = confirmed
                state.pop("home_game_themes_user_confirmed", None)
        elif bool(playbook.get("home_game_themes_ack")):
            if mp:
                confirmed = state.get("home_game_themes_confirmed_teams")
                if not isinstance(confirmed, dict):
                    confirmed = {}
                confirmed[ut] = True
                state["home_game_themes_confirmed_teams"] = confirmed
            else:
                state["home_game_themes_user_confirmed"] = True
    if mp:
        return
    seed = int(state.get("current_year", 1) or 1) * 7919 + hash(ut) % 100_000
    assign_ai_home_game_themes(state, team_names, ut or None, rng=random.Random(seed))


def finalize_multiplayer_home_game_themes(state: Dict[str, Any], team_names: List[str]) -> None:
    """Commissioner advance: CPU themes for schools without human picks."""
    from systems.home_game_themes import assign_ai_home_game_themes

    if not is_multiplayer_league_state(state):
        return
    seed = int(state.get("current_year", 1) or 1) * 7919 + len(team_names)
    assign_ai_home_game_themes(state, team_names, user_team=None, rng=random.Random(seed))
    state.pop("home_game_themes_user_confirmed", None)


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
    "Program Development",
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
    "Coaching carousel IV",
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
    if compact in ("programdevelopment", "programdev", "programbuilder"):
        return "Program Development"
    if compact in ("coachingcarouseliv", "coachingcarousel4"):
        return "Coaching carousel IV"
    if compact in ("transfers", "transfer"):
        return "Transfers I"
    if compact in ("transfersi", "transferi", "transferstage1"):
        return "Transfers I"
    if compact in ("transfersii", "transferii", "transferstage2"):
        return "Transfers II"
    if compact in ("transfersiii", "transferiii", "transferstage3", "transferreview"):
        return "Transfers III"
    if compact in ("coachingcarouseli", "coachingcarousel1"):
        return "Coaching carousel I"
    if compact in ("coachingcarouselii", "coachingcarousel2"):
        return "Coaching carousel II"
    if compact in ("coachingcarouseliii", "coachingcarousel3"):
        return "Coaching carousel III"
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


def _clamp_program_grade(raw: Any, fallback: int) -> int:
    """1–10 inclusive; survives bad client/API input without raising."""
    try:
        n = int(raw) if raw is not None else int(fallback)
    except (TypeError, ValueError):
        try:
            n = int(fallback)
        except (TypeError, ValueError):
            n = 5
    return max(1, min(10, n))


def _improvement_pp_delta(from_level: int, to_level: int) -> int:
    """PP delta for integer-only grade change (matches ``pp_delta_for_level_change`` cost table)."""
    return pp_delta_for_level_change(int(from_level or 1), int(to_level or 1))


def _normalize_team_program_pillars(ut: Team) -> None:
    """Collapse illegal grade/progress pairs into canonical cumulative form."""
    for gk, pk in (
        ("facilities_grade", "facilities_progress_pts"),
        ("culture_grade", "culture_progress_pts"),
        ("booster_support", "boosters_progress_pts"),
    ):
        lv = _clamp_program_grade(getattr(ut, gk, None), 5)
        pt = clamp_progress_points(getattr(ut, pk, 0))
        v = pillar_cumulative_pp_value(lv, pt)
        nlv, npt = pillar_state_from_cumulative_pp_value(v)
        setattr(ut, gk, nlv)
        setattr(ut, pk, npt)
    if hasattr(ut, "_clamp_values"):
        ut._clamp_values()


def _resolve_offseason_improvement_pillar(
    body: Dict[str, Any],
    ut: Team,
    *,
    grade_attr: str,
    pts_attr: str,
    cumulative_key: str,
    grade_body_key: str,
    pts_body_key: str,
) -> Tuple[int, int, int, int]:
    from_lv = _clamp_program_grade(getattr(ut, grade_attr, None), 5)
    from_pts = clamp_progress_points(getattr(ut, pts_attr, 0))
    raw_c = body.get(cumulative_key)
    if raw_c is not None:
        try:
            tv = max(0, min(int(PILLAR_CUMULATIVE_PP_MAX), int(raw_c)))
        except (TypeError, ValueError):
            tv = pillar_cumulative_pp_value(from_lv, from_pts)
        to_lv, to_pts = pillar_state_from_cumulative_pp_value(tv)
        return from_lv, from_pts, to_lv, to_pts
    raw_g = body.get(grade_body_key)
    to_lv = from_lv if raw_g is None else _clamp_program_grade(raw_g, from_lv)
    raw_p = body.get(pts_body_key)
    if raw_p is not None:
        to_pts = clamp_progress_points(raw_p)
    else:
        to_pts = from_pts
    v = pillar_cumulative_pp_value(to_lv, to_pts)
    to_lv, to_pts = pillar_state_from_cumulative_pp_value(v)
    return from_lv, from_pts, to_lv, to_pts


def _pillars_at_program_floor(ff: int, fp: int, cf: int, cp: int, bf: int, bp: int) -> bool:
    """True when facilities, culture, and boosters are at minimum (grade 1, no progress)."""
    return (
        pillar_cumulative_pp_value(ff, fp) == 0
        and pillar_cumulative_pp_value(cf, cp) == 0
        and pillar_cumulative_pp_value(bf, bp) == 0
    )


def _ensure_improvements_bank_equipment_pp(state: Dict[str, Any], ut: Optional[Team]) -> None:
    """Credit annual PP from owned program equipment into the user Improvements bank."""
    if ut is None:
        return
    bank = state.get("offseason_improvements_bank")
    if not isinstance(bank, dict):
        bank = {"pp_total": 0, "pp_remaining": 0, "breakdown": None, "applied": {}}
        state["offseason_improvements_bank"] = bank
    cy = int(state.get("current_year") or 0)
    credit_equipment_pp_to_improvements_bank(bank, ut, current_year=cy)


def _apply_user_team_program_improvements(ut: Team, bank: Dict[str, Any], body: Dict[str, Any]) -> None:
    """Spend flex PP bank on the three program pillars (grades + partial progress)."""
    pp_remaining = int(bank.get("pp_remaining", bank.get("pp_total", 0)) or 0)
    ff0, fp0, ff1, fp1 = _resolve_offseason_improvement_pillar(
        body,
        ut,
        grade_attr="facilities_grade",
        pts_attr="facilities_progress_pts",
        cumulative_key="improve_facilities_cumulative_pp",
        grade_body_key="improve_facilities_grade",
        pts_body_key="improve_facilities_progress_pts",
    )
    cf0, cp0, cf1, cp1 = _resolve_offseason_improvement_pillar(
        body,
        ut,
        grade_attr="culture_grade",
        pts_attr="culture_progress_pts",
        cumulative_key="improve_culture_cumulative_pp",
        grade_body_key="improve_culture_grade",
        pts_body_key="improve_culture_progress_pts",
    )
    bf0, bp0, bf1, bp1 = _resolve_offseason_improvement_pillar(
        body,
        ut,
        grade_attr="booster_support",
        pts_attr="boosters_progress_pts",
        cumulative_key="improve_boosters_cumulative_pp",
        grade_body_key="improve_booster_support",
        pts_body_key="improve_boosters_progress_pts",
    )
    delta_pp = (
        pillar_cumulative_pp_value(ff0, fp0)
        - pillar_cumulative_pp_value(ff1, fp1)
        + pillar_cumulative_pp_value(cf0, cp0)
        - pillar_cumulative_pp_value(cf1, cp1)
        + pillar_cumulative_pp_value(bf0, bp0)
        - pillar_cumulative_pp_value(bf1, bp1)
    )
    new_remaining = pp_remaining + int(delta_pp)
    if new_remaining < 0 and body.get("_bulk_cpu_pp_clamp"):
        ff1, cf1, bf1 = _bulk_enforce_improvement_pp_budget(ff0, cf0, bf0, ff1, cf1, bf1, pp_remaining)
        fp1 = cp1 = bp1 = 0
        delta_pp = (
            pillar_cumulative_pp_value(ff0, fp0)
            - pillar_cumulative_pp_value(ff1, fp1)
            + pillar_cumulative_pp_value(cf0, cp0)
            - pillar_cumulative_pp_value(cf1, cp1)
            + pillar_cumulative_pp_value(bf0, bp0)
            - pillar_cumulative_pp_value(bf1, bp1)
        )
        new_remaining = pp_remaining + int(delta_pp)
    if new_remaining < 0:
        # Bad seasons can leave a PP deficit while all pillars are already at grade 1 — nothing left to downgrade.
        if _pillars_at_program_floor(ff1, fp1, cf1, cp1, bf1, bp1):
            new_remaining = 0
        else:
            raise ValueError("Not enough PP for those improvements.")

    ut.facilities_grade = ff1
    ut.facilities_progress_pts = fp1
    ut.culture_grade = cf1
    ut.culture_progress_pts = cp1
    ut.booster_support = bf1
    ut.boosters_progress_pts = bp1
    _normalize_team_program_pillars(ut)

    bank["pp_remaining"] = new_remaining
    bank["applied"] = {
        "facilities_grade": {"from": ff0, "to": int(ut.facilities_grade), "from_pts": fp0, "to_pts": int(ut.facilities_progress_pts)},
        "culture_grade": {"from": cf0, "to": int(ut.culture_grade), "from_pts": cp0, "to_pts": int(ut.culture_progress_pts)},
        "booster_support": {"from": bf0, "to": int(ut.booster_support), "from_pts": bp0, "to_pts": int(ut.boosters_progress_pts)},
        "pp_delta": int(delta_pp),
    }


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
    # Determine furthest round reached from bracket results.
    best = 0
    order = PLAYOFF_ROUND_PRIORITY
    champ_v = order.get("Championship", 0)
    semi_v = order.get("Semifinal", 0)
    for g in bracket_results or []:
        if not isinstance(g, dict):
            continue
        if g.get("home") != team_name and g.get("away") != team_name:
            continue
        rnd = str(g.get("round") or "")
        best = max(best, int(order.get(rnd, 0)))
    if best >= champ_v:
        return "championship"
    if best >= semi_v:
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
    weeks: Optional[Any] = None,
    week_results: Optional[Any] = None,
) -> Dict[str, Any]:
    """Season-end Improvements PP (see ``systems.program_pp_economics`` constants + docstring)."""

    tier = _postseason_tier_for_team(team_name, standings, bracket_results, champion)
    return compute_season_program_pp_awards(
        team_name=team_name,
        standings=standings,
        bracket_results=bracket_results,
        champion=champion,
        season_goals=season_goals,
        weeks=weeks,
        week_results=week_results,
        postseason_tier=tier,
    )


def _ensure_user_coach_and_firing_defaults(state: Dict[str, Any]) -> None:
    """Backfill user_coach_name / league option flags for older league_save.json files."""
    if "allow_user_coach_firing" not in state:
        state["allow_user_coach_firing"] = False
    else:
        state["allow_user_coach_firing"] = bool(state.get("allow_user_coach_firing"))
    if "transfers_disabled" not in state:
        state["transfers_disabled"] = False
    else:
        state["transfers_disabled"] = bool(state.get("transfers_disabled"))
    ucn = state.get("user_coach_name")
    if isinstance(ucn, str) and ucn.strip():
        state["user_coach_name"] = ucn.strip()
        return
    ut = state.get("user_team")
    for t in state.get("teams") or []:
        if isinstance(t, dict) and t.get("name") == ut:
            c = t.get("coach")
            if isinstance(c, dict):
                nm = str(c.get("name") or "").strip()
                if nm:
                    state["user_coach_name"] = nm
            break


def _carousel_opts_from_state(state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    allow_fire = bool(state.get("allow_user_coach_firing", False))
    raw = state.get("user_coach_name")
    ucn = str(raw).strip() if isinstance(raw, str) else None
    return allow_fire, ucn if ucn else None


def _refresh_user_scheme_change_notice(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    user_team: Optional[str],
    current_year: int,
) -> None:
    """Persist offseason reminder: league does not auto-edit the human coach's preferred schemes."""
    from systems.coach_career_system import build_user_scheme_change_notice

    ut = str(user_team or "").strip()
    if not ut or ut not in teams:
        state.pop("user_scheme_change_notice", None)
        return
    coach = getattr(teams[ut], "coach", None)
    if not coach:
        state.pop("user_scheme_change_notice", None)
        return
    notice = build_user_scheme_change_notice(coach, int(current_year))
    if notice:
        state["user_scheme_change_notice"] = notice
    else:
        state.pop("user_scheme_change_notice", None)


def _coach_name_normalized_key(raw: Optional[Any]) -> str:
    """Lowercase + collapse internal whitespace for stable coach-name comparisons."""
    s = str(raw or "").strip()
    if not s:
        return ""
    return " ".join(s.lower().split())


def _sync_user_team_with_saved_coach(state: Dict[str, Any], teams: Dict[str, Team]) -> None:
    """Point user_team at the school employing the saved user coach (after carousel moves)."""
    raw = state.get("user_coach_name")
    if not (isinstance(raw, str) and raw.strip()):
        return
    key = _coach_name_normalized_key(raw)
    if not key:
        return
    for name, tm in teams.items():
        coach = getattr(tm, "coach", None)
        if coach and _coach_name_normalized_key(getattr(coach, "name", None)) == key:
            state["user_team"] = name
            return


def _sync_user_team_from_carousel_events(state: Dict[str, Any], events: List[Any]) -> None:
    """Set ``user_team`` from carousel hire events when the user's coach moved schools.

    Complements :func:`_sync_user_team_with_saved_coach` (team scan) when names match loosely
    or when the scan would otherwise miss an ``application_hire`` / ``promotion``.
    """
    _, ukey = _carousel_opts_from_state(state)
    ulow = _coach_name_normalized_key(ukey)
    if not ulow:
        return
    team_names = {str(t.get("name")) for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")}
    for ev in reversed(list(events or [])):
        if not isinstance(ev, dict):
            continue
        if _coach_name_normalized_key(ev.get("coach")) != ulow:
            continue
        et = str(ev.get("type") or "").strip().lower()
        if et in ("application_hire", "promotion"):
            dest = str(ev.get("team") or "").strip()
            if dest and dest in team_names:
                state["user_team"] = dest
                return


def _repair_user_team_from_serialized_teams(state: Dict[str, Any]) -> None:
    """If ``user_coach_name`` is employed at a school other than ``user_team``, fix the pointer.

    Repairs saves written before carousel hire events updated ``user_team`` (e.g. after an
    application hire to a new school while ``user_team`` still named the old program).
    """
    raw = state.get("user_coach_name")
    if not (isinstance(raw, str) and raw.strip()):
        return
    key = _coach_name_normalized_key(raw)
    if not key:
        return
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        c = t.get("coach")
        if not isinstance(c, dict):
            continue
        if _coach_name_normalized_key(c.get("name")) != key:
            continue
        nm = str(t.get("name") or "").strip()
        if nm:
            state["user_team"] = nm
            return


def _refresh_user_coach_unemployed_flag(state: Dict[str, Any]) -> None:
    """True when ``user_coach_name`` is set but no serialized team lists that coach as HC."""
    raw = state.get("user_coach_name")
    if not (isinstance(raw, str) and raw.strip()):
        state.pop("user_coach_unemployed", None)
        return
    key = _coach_name_normalized_key(raw)
    if not key:
        state.pop("user_coach_unemployed", None)
        return
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        c = t.get("coach")
        if not isinstance(c, dict):
            continue
        if _coach_name_normalized_key(c.get("name")) == key:
            state.pop("user_coach_unemployed", None)
            return
    state["user_coach_unemployed"] = True


def _award_program_funding_for_all_teams(
    teams: Dict[str, Any],
    standings: Dict[str, Any],
    *,
    current_year: int,
) -> None:
    """Season-review funding deposit for every program."""
    for name, team in teams.items():
        st = standings.get(name) if isinstance(standings, dict) else None
        if not isinstance(st, dict):
            st = {}
        wins = int(st.get("wins", getattr(team, "wins", 0) or 0) or 0)
        losses = int(st.get("losses", getattr(team, "losses", 0) or 0) or 0)
        apply_program_funding_for_season(team, wins=wins, losses=losses, current_year=current_year)


def _ensure_program_development_inventory_aged(state: Dict[str, Any], teams: Dict[str, Any]) -> None:
    cy = int(state.get("current_year", 1) or 1)
    if int(state.get("program_development_prepared_year") or 0) == cy:
        return
    expired_rows: List[Dict[str, Any]] = []
    for team in teams.values():
        summary = prepare_program_development_stage(team)
        for row in summary.get("expired") or []:
            if isinstance(row, dict):
                expired_rows.append(row)
    state["program_development_prepared_year"] = cy
    if expired_rows:
        state["program_development_last_expired"] = expired_rows[-20:]


def _apply_program_development_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    body: Dict[str, Any],
) -> None:
    _ensure_program_development_inventory_aged(state, teams)
    user_team_name = str(state.get("user_team") or "").strip()
    cy = int(state.get("current_year", 1) or 1)
    ut = teams.get(user_team_name) if user_team_name else None
    raw_actions = body.get("program_development_actions")
    if ut and isinstance(raw_actions, list) and raw_actions:
        apply_user_program_actions(ut, raw_actions, current_year=cy)
    for name, t in teams.items():
        if name == user_team_name:
            continue
        run_ai_program_purchases(t, current_year=cy)


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
    """After interactive offseason: enter preseason (play selection is configured in preseason UI)."""
    if _repair_missing_cross_region_schedule_planning(state):
        return
    user_team_name = state.get("user_team")
    ut = teams.get(user_team_name) if user_team_name else None
    if ut:
        ut.season_offensive_play_selection = None
        ut.season_defensive_play_selection = None
    for t in teams.values():
        reset_team_season_stats(t)
    state["season_phase"] = "preseason"
    state["preseason_stage_index"] = 0
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["current_week"] = 1
    state["preseason_scrimmages"] = []
    _assign_scrimmage_opponents_for_state(state)
    state.pop("offseason_stage_index", None)
    state.pop("offseason_stages", None)
    state.pop("offseason_training_results", None)
    state.pop("offseason_graduation_report", None)
    state.pop("offseason_coach_dev_bank", None)
    state.pop("offseason_coach_dev_banks", None)
    state.pop("offseason_spring_ball_results", None)
    state.pop("offseason_7on7_results", None)
    state.pop("multiplayer_7on7_by_team", None)
    state.pop("offseason_winter_training_results", None)
    state.pop("offseason_winter_history", None)
    state.pop("offseason_spring_history", None)
    state.pop("offseason_coach_carousel", None)
    state.pop("offseason_coach_carousel_last_events", None)
    state.pop("offseason_coach_carousel_hot_seat", None)
    state.pop("offseason_coaching_changes_summary", None)
    state.pop("offseason_carousel_job_applications", None)
    state.pop("offseason_transfer_snapshot_standings", None)
    _clear_offseason_transfer_ui_state(state)


def _empty_coach_dev_bank() -> Dict[str, Any]:
    return {
        "cp_total": 0.0,
        "allocated_total": 0.0,
        "available_cp": 0.0,
        "allocations": {sk: 0.0 for sk in COACH_DEV_SKILLS},
        "levels": {sk: 1 for sk in COACH_DEV_SKILLS},
        "thresholds": dict(LEVEL_CP_THRESHOLDS),
        "card_ledger": {},
        "cp_economy_version": CP_ECONOMY_VERSION,
        "breakdown": None,
        "applied": None,
    }


def _apply_coach_dev_stage_for_team(
    coach: Any,
    bank: Dict[str, Any],
    *,
    body: Optional[Dict[str, Any]] = None,
    is_user: bool = False,
) -> None:
    if coach is None or not isinstance(bank, dict):
        return
    from systems.coaching_cards import ai_select_coaching_cards, apply_loadout_to_coach, get_coach_loadout

    if is_user:
        from systems.coaching_cards import normalize_loadout

        if body and "coaching_cards" in body:
            old_loadout = get_coach_loadout(coach)
            new_loadout = normalize_loadout(body.get("coaching_cards"))
            apply_coaching_card_cp_transaction(bank, old_loadout, new_loadout)
            apply_loadout_to_coach(coach, new_loadout)
        apply_coach_development(coach, bank, _merge_user_coach_development_body(bank, body))
        return

    if not is_user:
        old_loadout = get_coach_loadout(coach)
        try:
            new_loadout = ai_select_coaching_cards(coach, getattr(coach, "coaching_cards", None))
            apply_coaching_card_cp_transaction(bank, old_loadout, new_loadout)
            apply_loadout_to_coach(coach, new_loadout)
        except Exception:
            pass
    apply_ai_coach_season_development(coach, bank)


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


def _merge_carousel_job_applications(state: Dict[str, Any], body: Optional[Dict[str, Any]]) -> None:
    """Persist user's ranked HC job preferences from the offseason advance POST body."""
    if not isinstance(body, dict):
        return
    if "carousel_job_applications" not in body:
        return
    raw = body.get("carousel_job_applications")
    team_names = {str(t.get("name")) for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")}
    out: List[str] = []
    if isinstance(raw, list):
        for x in raw:
            s = str(x).strip() if x is not None else ""
            if s and s in team_names and s not in out:
                out.append(s)
                if len(out) >= 12:
                    break
    state["offseason_carousel_job_applications"] = out


def _annotate_carousel_events_for_user(
    events: List[Any],
    *,
    user_team: Optional[str],
    user_coach_name: Optional[str],
) -> List[Dict[str, Any]]:
    """Tag carousel rows for UI/news. Falls back if an older coach_carousel module lacks the helper."""
    try:
        from systems.coach_carousel import annotate_carousel_events_for_user

        return annotate_carousel_events_for_user(
            events,
            user_team=user_team,
            user_coach_name=user_coach_name,
        )
    except ImportError:
        ut = str(user_team or "").strip()
        ucn = str(user_coach_name or "").strip().lower()
        out: List[Dict[str, Any]] = []
        for raw in events or []:
            if not isinstance(raw, dict):
                continue
            ev = dict(raw)
            team = str(ev.get("team") or "").strip()
            coach_key = " ".join(str(ev.get("coach") or "").strip().lower().split())
            is_user_coach = bool(ucn and coach_key == ucn)
            is_user_team = bool(ut and team == ut)
            ev["is_user_coach"] = is_user_coach
            ev["is_user_team"] = is_user_team
            typ = str(ev.get("type") or "").strip().lower()
            ev["affects_user_program"] = is_user_coach and (
                is_user_team
                or typ
                in (
                    "application_hire",
                    "promotion",
                    "firing",
                    "resignation",
                    "retirement",
                    "user_scheme_reminder",
                )
            )
            out.append(ev)
        return out


def _apply_coaching_carousel_churn(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    league_history: Dict[str, Any],
) -> None:
    """Engine step 1: retire/resign/fire only; establishes carousel persist for UI round I."""
    from systems.coach_carousel import run_coach_carousel_step

    _ensure_user_coach_and_firing_defaults(state)
    sg = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    ut = state.get("user_team")
    carousel_year = max(1, int(state.get("current_year", 1)))
    state.pop("offseason_carousel_job_applications", None)
    state.pop("offseason_coaching_changes_summary", None)
    allow_fire, user_coach_key = _carousel_opts_from_state(state)
    persist, events, _cc, hs = run_coach_carousel_step(
        teams,
        league_history,
        state.get("standings"),
        1,
        None,
        ut,
        sg,
        carousel_year,
        None,
        allow_user_coach_firing=allow_fire,
        user_coach_name=user_coach_key,
    )
    _sync_user_team_with_saved_coach(state, teams)
    state["offseason_coach_carousel"] = persist
    state["offseason_coach_carousel_last_events"] = _annotate_carousel_events_for_user(
        (events or [])[-40:],
        user_team=ut,
        user_coach_name=user_coach_key,
    )
    state["offseason_coach_carousel_hot_seat"] = hs or {}


def _apply_coaching_carousel_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    league_history: Dict[str, Any],
    step_name: str,
    body: Optional[Dict[str, Any]] = None,
) -> None:
    """Run carousel hiring rounds (engine steps 2–4); step III UI runs final engine step with schemes + prestige."""
    from systems.coach_carousel import build_carousel_season_archive, run_coach_carousel_step

    _ensure_user_coach_and_firing_defaults(state)
    _merge_carousel_job_applications(state, body)

    sg = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    ut = state.get("user_team")
    carousel_year = max(1, int(state.get("current_year", 1)))
    job_apps = list(state.get("offseason_carousel_job_applications") or [])
    step_map = {"Coaching carousel I": 2, "Coaching carousel II": 3, "Coaching carousel III": 4}
    step = step_map[step_name]
    persist_in = state.get("offseason_coach_carousel")
    if persist_in is None:
        raise ValueError("Coaching carousel state is missing; reload your save or continue from Improvements.")

    allow_fire, user_coach_key = _carousel_opts_from_state(state)
    persist, events, cc, hs = run_coach_carousel_step(
        teams,
        league_history,
        state.get("standings"),
        step,
        persist_in,
        ut,
        sg,
        carousel_year,
        job_apps,
        allow_user_coach_firing=allow_fire,
        user_coach_name=user_coach_key,
    )
    _sync_user_team_with_saved_coach(state, teams)
    _sync_user_team_from_carousel_events(state, events)
    state["offseason_coach_carousel"] = persist
    state["offseason_coach_carousel_last_events"] = _annotate_carousel_events_for_user(
        (events or [])[-40:],
        user_team=ut,
        user_coach_name=user_coach_key,
    )
    state["offseason_coach_carousel_hot_seat"] = hs or {}
    if step == 4:
        _refresh_user_scheme_change_notice(state, teams, ut, carousel_year)
        update_prestige(teams, league_history, coach_changes=cc, coach_turnover_only=True)
        season_year = max(1, int(state.get("current_year", 1)) - 1)
        ch = list(state.get("coaching_history") or [])
        archive = build_carousel_season_archive(season_year, list(events or []), dict(hs or {}))
        ch.append(
            {
                "year": season_year,
                "events": list(events or []),
                "hot_seat_by_team": dict(hs or {}),
                "carousel_summary": archive,
            }
        )
        state["coaching_history"] = ch[-100:]
        state["offseason_coaching_changes_summary"] = archive
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
    normalize_offseason_stages(state)
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
            _archive_winter_training_session(state)
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
            return _attach_league_history_to_result(save_dir, {"state": state})

    elif current == "Spring Ball":
        so = body.get("spring_offense_focus")
        sd = body.get("spring_defense_focus")
        spring_results = state.get("offseason_spring_ball_results")
        ack = bool(body.get("spring_ball_ack_results"))
        if isinstance(spring_results, dict) and ack:
            _archive_spring_ball_session(state)
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
        if ut:
            _ensure_improvements_bank_equipment_pp(state, ut)
            bank = state.get("offseason_improvements_bank")
            if not isinstance(bank, dict):
                bank = {"pp_total": 0, "pp_remaining": 0, "breakdown": None, "applied": {}}
            _apply_user_team_program_improvements(ut, bank, body)
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
                _apply_coach_dev_stage_for_team(ut.coach, b, body=body, is_user=True)
            elif name != user_team_name:
                _apply_coach_dev_stage_for_team(coach, b, is_user=False)
        if user_team_name:
            ub = banks_cd.get(user_team_name)
            if isinstance(ub, dict):
                state["offseason_coach_dev_bank"] = ub
        state["offseason_coach_dev_banks"] = banks_cd

    elif current == "Program Development":
        _apply_program_development_stage(state, teams, body)

    elif current in ("Coaching carousel I", "Coaching carousel II", "Coaching carousel III"):
        lh = load_league_history(league_history_path(save_dir))
        _apply_coaching_carousel_stage(state, teams, lh, current, body)

    elif current == "Coaching carousel IV":
        pass

    elif current == "Transfers I":
        pending = bool(state.get("offseason_transfer_stage_1_pending_review"))
        ack = bool(body.get("transfer_stage_1_ack_results"))
        st_xfer = _standings_for_transfer_portal(state)
        stage1_existing = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else None

        if pending:
            if not ack:
                raise ValueError("Review the transfer portal entrants, then press Continue again to lock and advance.")
            state.pop("offseason_transfer_stage_1_pending_review", None)
        elif isinstance(stage1_existing, dict) and stage1_existing.get("entries") is not None:
            pass
        else:
            if _transfers_disabled(state):
                state["offseason_transfer_stage_1"] = _disabled_transfer_stage_1_payload()
            else:
                tph, tbr = _transfer_playoff_snapshot(state)
                sg_tr = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
                payload = run_transfer_stage_1(
                    teams,
                    st_xfer,
                    current_year=max(1, int(state.get("current_year", 1))),
                    season_goals=sg_tr,
                    user_team=str(state.get("user_team") or "") or None,
                    bracket_results=tbr,
                    champion=tph,
                )
                state["offseason_transfer_stage_1"] = payload
                _transfer_stage_1_apply_news(state, payload)
                state["offseason_transfer_stage_1_pending_review"] = True
                state["offseason_stage_index"] = idx
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                save_state(user_id, save_id, state, save_dir)
                return _attach_league_history_to_result(save_dir, {"state": state})
    elif current == "Transfers II":
        pending = bool(state.get("offseason_transfer_stage_2_pending_review"))
        ack = bool(body.get("transfer_stage_2_ack_results"))
        st_xfer = _standings_for_transfer_portal(state)
        stage2_existing = state.get("offseason_transfer_stage_2") if isinstance(state.get("offseason_transfer_stage_2"), dict) else None

        if pending:
            if not ack:
                raise ValueError("Review transfer commitments, then press Continue again to advance.")
            state.pop("offseason_transfer_stage_2_pending_review", None)
        elif isinstance(stage2_existing, dict) and (
            stage2_existing.get("entries") is not None or stage2_existing.get("moved_count") is not None
        ):
            pass
        else:
            if _transfers_disabled(state):
                _apply_disabled_transfer_stage_2(state)
            else:
                stage1 = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else {}
                payload = run_transfer_stage_2(
                    teams,
                    st_xfer,
                    stage1,
                    current_year=max(1, int(state.get("current_year", 1))),
                )
                _transfer_stage_2_apply_news_and_review(state, payload)
                state["offseason_transfer_stage_2_pending_review"] = True
                state["offseason_stage_index"] = idx
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                save_state(user_id, save_id, state, save_dir)
                return _attach_league_history_to_result(save_dir, {"state": state})
    elif current == "7 on 7":
        seven_results = state.get("offseason_7on7_results")
        ack = bool(body.get("seven_on_seven_ack_results"))
        tier_raw = body.get("seven_on_seven_tournament")
        if isinstance(seven_results, dict) and ack:
            state.pop("offseason_7on7_results", None)
        elif isinstance(seven_results, dict) and not ack:
            raise ValueError("Review 7-on-7 tournament results, then press Continue again to advance.")
        else:
            tier = str(tier_raw or "").strip().lower()
            if tier not in VALID_TOURNAMENT_TIERS:
                raise ValueError("Choose a 7-on-7 tournament (Area, Regional, or State), then press Continue.")
            payload = run_seven_on_seven_tournament(teams, str(user_team_name or ""), tier)
            state["offseason_7on7_results"] = payload
            state["offseason_stage_index"] = idx
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            save_state(user_id, save_id, state, save_dir)
            return _attach_league_history_to_result(save_dir, {"state": state})
    elif current in ("Transfers III", "Graduation"):
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
        user_equipment_training: Optional[Dict[str, Any]] = None
        from systems.coaching_cards import platinum_breakthrough_eligible_player_names

        eligible_before = platinum_breakthrough_eligible_player_names(ut) if ut else []
        for t in teams.values():
            dev_summary = run_offseason_development(t)
            if ut and t.name == ut.name:
                user_equipment_training = dev_summary
        deltas: List[Dict[str, Any]] = []
        if ut:
            deltas = _training_player_rows_from_development(
                ut,
                before_rows,
                (user_equipment_training or {}).get("player_reports") if isinstance(user_equipment_training, dict) else None,
            )
            _attach_platinum_breakthrough_training_metadata(deltas, user_equipment_training, eligible_before)
        training_payload: Dict[str, Any] = {"players": deltas, "breakthrough_eligible": eligible_before}
        if user_equipment_training:
            from systems.program_equipment_effects import summarize_equipment_for_training_ui

            training_payload["equipment"] = {
                "by_item": user_equipment_training.get("by_item") or [],
                "item_count": int(user_equipment_training.get("item_count") or 0),
                "equipment_points_applied": int(user_equipment_training.get("equipment_points_applied") or 0),
                "ui_rows": summarize_equipment_for_training_ui(user_equipment_training),
            }
        state["offseason_training_results"] = training_payload

    elif current == "Freshman Class":
        pass

    elif current == "Schedule Release":
        pass

    # Carousel churn (retire/fire) runs when leaving Improvements, then Coaching carousel I is first interactive round.
    if current == "Improvements":
        lh = load_league_history(league_history_path(save_dir))
        _apply_coaching_carousel_churn(state, teams, lh)

    state["offseason_stage_index"] = idx + 1
    new_idx = int(state["offseason_stage_index"])
    if new_idx < len(stages) and _normalize_offseason_stage_name(stages[new_idx]) == "Program Development":
        _ensure_program_development_inventory_aged(state, teams)
    if new_idx < len(stages) and _normalize_offseason_stage_name(stages[new_idx]) == "Improvements":
        _ensure_improvements_bank_equipment_pp(state, ut)
    if current == "Spring Ball":
        state.pop("offseason_spring_ball_results", None)
    if current == "7 on 7":
        state.pop("offseason_7on7_results", None)
    if current in ("Winter 1", "Winter 2"):
        state.pop("offseason_winter_training_results", None)
    state["teams"] = [team_to_dict(t) for t in teams.values()]

    new_idx = int(state["offseason_stage_index"])
    if new_idx >= len(stages):
        check_trial_before_year2_preseason(user_id)
        teams2 = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
        _finalize_offseason_to_preseason(state, teams2)
        state["teams"] = [team_to_dict(t) for t in teams2.values()]

    save_state(user_id, save_id, state, save_dir)
    return _attach_league_history_to_result(save_dir, {"state": state})


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
    allow_user_coach_firing: bool = False,
    transfers_disabled: bool = False,
) -> Dict[str, Any]:
    provided_rows = None
    league_cfg: Dict[str, Any] = {}
    if isinstance(teams_data, dict):
        league_cfg = teams_data
        maybe_rows = teams_data.get("teams")
        if isinstance(maybe_rows, list):
            provided_rows = [r for r in maybe_rows if isinstance(r, dict)]
    if provided_rows is not None:
        teams = build_teams_from_configs(provided_rows, generate_roster=True, two_way_chance=0.55, assign_coaches=True)
        # Pull the playoff system from the caller-provided league config so an
        # in-app league editor can pick a non-default system. Falls back to WV.
        playoff_system_id = playoff_system_id_from_config(league_cfg)
    else:
        teams = build_teams_from_json(generate_roster=True, two_way_chance=0.55, assign_coaches=True)
        # Read the league JSON header (currently data/teams.json) for its
        # ``playoff_system`` field so the save records which postseason
        # structure it should use. Falls back to the default if missing.
        league_cfg = load_league_config_from_json()
        playoff_system_id = playoff_system_id_from_config(league_cfg)
    league_meta = league_metadata_from_config(league_cfg)
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
    stub_state: Dict[str, Any] = {"league_structure": ls, "user_team": user_team}
    planning_info = _schedule_planning_info_for_user(teams, user_team)
    if planning_info:
        weeks: List[List[Dict[str, str]]] = []
        week_results: List[List[Dict[str, Any]]] = []
    else:
        weeks, week_results = _regular_season_week_boards(teams, stub_state)
    standings = {name: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for name in team_names}

    uc = teams[user_team].coach
    user_coach_name = str(uc.name).strip() if uc and getattr(uc, "name", None) else None

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
        user_coach_name=user_coach_name,
        allow_user_coach_firing=bool(allow_user_coach_firing),
        transfers_disabled=bool(transfers_disabled),
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

    # New dynasties: schedule planning when cross-region picks required, else preseason.
    state, _save_dir = load_state(user_id, save_id)
    if planning_info:
        state["season_phase"] = "schedule_planning"
        state["schedule_planning_info"] = planning_info
        state.pop("weeks", None)
        state.pop("week_results", None)
    else:
        state["season_phase"] = "preseason"
    state["current_week"] = 1
    state["preseason_stages"] = list(PRESEASON_STAGES)
    state["preseason_stage_index"] = 0
    state["season_goals"] = state.get("season_goals") or []
    _sync_user_cross_region_slot_count(state)
    # Stamp the chosen postseason structure on the save state so the rest of
    # the app can branch on it without re-reading the league JSON. Persists
    # for the life of this save (immutable across the dynasty for now).
    state["playoff_system"] = playoff_system_id
    state["custom_league_json"] = provided_rows is not None
    ensure_playoff_system_in_state(state)
    apply_league_metadata_to_state(state, league_meta)
    ensure_league_metadata_in_state(state)
    state["offseason_coach_dev_banks"] = build_initial_coach_dev_banks_for_dynasty(teams)
    user_bank = state["offseason_coach_dev_banks"].get(user_team)
    if isinstance(user_bank, dict):
        state["offseason_coach_dev_bank"] = user_bank
    save_state(user_id, save_id, state, _save_dir)

    return {"save_id": save_id}


def _reconcile_saves_from_disk(user_id: str, coach_match_key: Optional[str] = None) -> None:
    """
    After a deploy wipes the SQLite index, re-register saves that still exist on disk.
    When coach_match_key is set (login username), also claim legacy folders under other user ids
    whose league_save.json user_coach_name matches.
    """
    import json
    import uuid as _uuid

    base = _saves_base_dir()
    if not _safe_isdir(base):
        return

    now = int(time.time())
    safe_user = _safe_path_segment(user_id, default="user")

    def _read_save_name(save_dir: str) -> Optional[str]:
        jplain = _league_save_plain_path(save_dir)
        try:
            with open_text_with_path_fallback(jplain, "r") as f:
                data = json.load(f)
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        name = str(data.get("save_name") or "").strip()
        return name or None

    def _coach_key_from_dir(save_dir: str) -> str:
        jplain = _league_save_plain_path(save_dir)
        try:
            with open_text_with_path_fallback(jplain, "r") as f:
                data = json.load(f)
        except Exception:
            return ""
        if not isinstance(data, dict):
            return ""
        return _coach_name_normalized_key(data.get("user_coach_name"))

    with db() as conn:
        rows = conn.execute(
            "SELECT save_name FROM saves WHERE user_id=?",
            (user_id,),
        ).fetchall()
        known_names = {str(r["save_name"]) for r in rows}

        def _register_dir(save_dir: str) -> None:
            nonlocal known_names
            if not _has_league_save_file(save_dir):
                return
            save_name = _read_save_name(save_dir)
            if not save_name or save_name in known_names:
                return
            save_id = str(_uuid.uuid4())
            try:
                updated_at = int(os.path.getmtime(_league_save_plain_path(save_dir)))
            except OSError:
                updated_at = now
            conn.execute(
                """
                INSERT INTO saves (id, user_id, save_name, save_dir, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                """,
                (save_id, user_id, save_name, save_dir, now, updated_at),
            )
            known_names.add(save_name)

        user_root = os.path.join(base, safe_user)
        if _safe_isdir(user_root):
            try:
                for entry in sorted(os.listdir(user_root)):
                    if entry == "_logos":
                        continue
                    cand = os.path.join(user_root, entry)
                    if _safe_isdir(cand):
                        _register_dir(cand)
            except OSError:
                pass

        if coach_match_key:
            try:
                top_entries = sorted(os.listdir(base))
            except OSError:
                top_entries = []
            for other_uid in top_entries:
                if other_uid in (safe_user, "_logos"):
                    continue
                other_root = os.path.join(base, other_uid)
                if not _safe_isdir(other_root):
                    continue
                try:
                    sub_entries = sorted(os.listdir(other_root))
                except OSError:
                    continue
                for entry in sub_entries:
                    if entry == "_logos":
                        continue
                    cand = os.path.join(other_root, entry)
                    if not _safe_isdir(cand) or not _has_league_save_file(cand):
                        continue
                    if _coach_key_from_dir(cand) != coach_match_key:
                        continue
                    _register_dir(cand)


def list_saves(user_id: str) -> List[Dict[str, Any]]:
    coach_key: Optional[str] = None
    with db() as conn:
        urow = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if urow and urow["username"]:
            coach_key = _coach_name_normalized_key(urow["username"])
    _reconcile_saves_from_disk(user_id, coach_match_key=coach_key or None)
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


def build_scrimmage_opponents_for_team(
    team_name: str,
    team_names: List[str],
    weeks: Any,
    *,
    exclude_opponents: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    """Pick two scrimmage opponents for one team (non-conference, not on regular-season schedule)."""
    if not team_name or team_name not in team_names:
        return []
    blocked = set(exclude_opponents or set())
    scheduled_opponents = set()
    for wk in weeks or []:
        for g in wk or []:
            if isinstance(g, dict):
                h, a = g.get("home"), g.get("away")
                if h == team_name and a:
                    scheduled_opponents.add(a)
                elif a == team_name and h:
                    scheduled_opponents.add(h)
    eligible = [t for t in team_names if t != team_name and t not in scheduled_opponents]
    if not eligible:
        eligible = [t for t in team_names if t != team_name]
    preferred = [t for t in eligible if t not in blocked]
    pick_from = preferred if len(preferred) >= 2 else (preferred if preferred else eligible)
    if len(pick_from) >= 2:
        chosen = random.sample(pick_from, 2)
        return [
            {"opponent": chosen[0], "user_home": random.random() < 0.5},
            {"opponent": chosen[1], "user_home": random.random() < 0.5},
        ]
    if len(pick_from) == 1:
        return [
            {"opponent": pick_from[0], "user_home": random.random() < 0.5},
            {"opponent": pick_from[0], "user_home": random.random() >= 0.5},
        ]
    return []


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
    state["preseason_scrimmage_opponents"] = build_scrimmage_opponents_for_team(
        user_team_name,
        team_names,
        state.get("weeks"),
    )
    return True


def apply_team_program_totals_to_serialized_team_rows(
    seasons: List[Dict[str, Any]],
    teams_rows: Optional[List[Any]] = None,
    *,
    state: Optional[Dict[str, Any]] = None,
) -> None:
    """Write program totals from season entries onto serialized team dicts (mutates in place)."""
    rows = teams_rows
    if rows is None and state is not None:
        rows = state.get("teams")
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        nm = row.get("name")
        if not nm:
            continue
        persisted_reg = int(row.get("regional_championships", 0) or 0)
        bundle = build_team_program_totals_display(nm, seasons, persisted_reg)
        row["program_wins"] = bundle["program_wins"]
        row["program_losses"] = bundle["program_losses"]
        row["playoff_appearances"] = bundle["playoff_appearances"]
        row["championships"] = bundle["state_championships"]
        row["regional_championships"] = bundle["regional_championships"]


def apply_team_program_totals_from_history_to_state(save_dir: str, state: Dict[str, Any]) -> None:
    """Align program totals on each serialized team dict with league_history.json on disk."""
    hist = load_league_history(league_history_path(save_dir))
    seasons = hist.get("seasons") or []
    apply_team_program_totals_to_serialized_team_rows(seasons, state=state)


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
    if normalize_preseason_stages(state):
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

    # Align program wins/losses, titles, playoff counts on each team with league_history.json (fixes stale file rows).
    apply_team_program_totals_from_history_to_state(save_dir, state)
    if _sync_derived_save_fields(state, save_dir):
        save_state(user_id, save_id, state, save_dir)

    try:
        hist = load_league_history(league_history_path(save_dir))
        if rebuild_coach_career_log_from_league_history(state, hist, merge=True):
            save_state(user_id, save_id, state, save_dir)
    except Exception:
        pass

    _hydrate_coach_inbox_persist_if_needed(user_id, save_id, state, save_dir)

    if _finalize_cross_region_schedule_state(state):
        save_state(user_id, save_id, state, save_dir)

    league_history_payload: Dict[str, Any] = {"seasons": []}
    try:
        league_history_payload = load_league_history(league_history_path(save_dir))
    except Exception:
        pass

    return {
        "save_id": row["id"],
        "save_name": row["save_name"],
        "state": state,
        "league_history": league_history_payload,
    }


def _get_save_row(user_id: str, save_id: str) -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, save_name, save_dir FROM saves WHERE id=? AND user_id=?",
            (save_id, user_id),
        ).fetchone()
    if not row:
        raise ValueError("save not found")
    return {"save_id": row["id"], "save_name": row["save_name"], "save_dir": row["save_dir"]}


def _backfill_last_completed_standings(state: Dict[str, Any], save_dir: str) -> None:
    """Populate ``state['last_completed_standings']`` for old saves missing the snapshot.

    Pulls the most recent archived season from league_history.json so the UI can show
    last season's record across non-regular phases instead of the freshly-reset 0-0
    standings. No-op when the snapshot is already present or no archives exist.
    """
    if isinstance(state.get("last_completed_standings"), dict) and state["last_completed_standings"]:
        return
    try:
        hist = load_league_history(league_history_path(save_dir))
    except Exception:
        return
    seasons = hist.get("seasons") or []
    if not isinstance(seasons, list) or not seasons:
        return
    latest = max(
        (s for s in seasons if isinstance(s, dict)),
        key=lambda s: int(s.get("year") or s.get("season") or 0),
        default=None,
    )
    if not isinstance(latest, dict):
        return
    standings_list = latest.get("standings") or []
    if not isinstance(standings_list, list) or not standings_list:
        return
    snap: Dict[str, Dict[str, int]] = {}
    for r in standings_list:
        if not isinstance(r, dict):
            continue
        team = str(r.get("team") or "").strip()
        if not team:
            continue
        snap[team] = {
            "wins": int(r.get("wins", 0) or 0),
            "losses": int(r.get("losses", 0) or 0),
            "points_for": int(r.get("points_for", 0) or 0),
            "points_against": int(r.get("points_against", 0) or 0),
        }
    if snap:
        state["last_completed_standings"] = snap
        year_val = latest.get("year")
        if year_val is not None:
            try:
                state["last_completed_year"] = int(year_val)
            except (TypeError, ValueError):
                pass


def _repair_missing_archived_season(state: Dict[str, Any], save_dir: str) -> bool:
    """Backfill league_history.json when offseason started without append_season (legacy / skipped UI)."""
    try:
        lcy = int(state.get("last_completed_year") or 0)
    except (TypeError, ValueError):
        return False
    if lcy <= 0:
        return False
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase in ("regular", "playoffs", "season_summary"):
        return False
    try:
        hist = load_league_history(league_history_path(save_dir))
    except Exception:
        return False
    seasons = hist.get("seasons") or []
    if any(isinstance(s, dict) and int(s.get("year") or 0) == lcy for s in seasons):
        return False
    snap_all = state.get("last_completed_standings")
    if not isinstance(snap_all, dict) or not snap_all:
        return False
    team_names = [
        str(t.get("name"))
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    ]
    if not team_names:
        return False

    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    champion = str(playoffs.get("champion") or "").strip() or "—"
    runner_up = str(playoffs.get("runner_up") or "").strip() or "—"
    br_flat = _flatten_playoff_bracket_results(playoffs) if playoffs else []
    p_bc = _playoffs_by_class_snapshot(state)
    team_coaches: Dict[str, str] = {}
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        nm = str(t.get("name") or "")
        coach = t.get("coach")
        if nm and isinstance(coach, dict):
            team_coaches[nm] = str(coach.get("name") or "")

    try:
        append_season(
            champion=champion,
            runner_up=runner_up,
            team_names=team_names,
            standings=snap_all,
            season_player_stats={},
            year=lcy,
            bracket_results=br_flat,
            team_coaches=team_coaches,
            playoffs_by_class=p_bc,
            save_dir=save_dir,
        )
        append_season_to_coach_career_log(
            state,
            year=lcy,
            team_coaches=team_coaches,
            standings=snap_all,
        )
        teams_map = {
            t["name"]: team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        hist2 = load_league_history(league_history_path(save_dir))
        update_prestige(teams_map, hist2)
        state["teams"] = [team_to_dict(t) for t in teams_map.values()]
        return True
    except Exception:
        logger.exception("repair missing archived season")
        return False


def _ensure_prestige_from_archived_season(state: Dict[str, Any], save_dir: str) -> bool:
    """Apply season-end TP from league_history when archive ran but TP was never written to the save file."""
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase not in ("offseason", "preseason", "season_summary"):
        return False
    try:
        lcy = int(state.get("last_completed_year") or 0)
    except (TypeError, ValueError):
        return False
    if lcy <= 0:
        return False
    if int(state.get("prestige_applied_for_year") or 0) == lcy:
        return False
    try:
        hist = load_league_history(league_history_path(save_dir))
    except Exception:
        return False
    seasons = [s for s in (hist.get("seasons") or []) if isinstance(s, dict)]
    if not seasons or not any(int(s.get("year") or 0) == lcy for s in seasons):
        return False
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    if not teams:
        return False
    update_prestige(teams, hist)
    state["prestige_applied_for_year"] = lcy
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    return True


def _repair_playoffs_complete_to_season_summary(state: Dict[str, Any], save_dir: str) -> bool:
    """
    When playoffs are globally complete but the save never advanced to season_summary
    (client skipped finish, or legacy state), archive the year and open the summary hub.
    """
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase != "playoffs":
        return False
    playoffs = state.get("playoffs")
    if not isinstance(playoffs, dict) or not _playoffs_global_completed(playoffs):
        return False
    _sync_playoff_top_level_champion_runner(playoffs)
    try:
        cy = int(state.get("current_year", 1))
    except (TypeError, ValueError):
        cy = 1
    try:
        hist = load_league_history(league_history_path(save_dir))
    except Exception:
        return False
    seasons = hist.get("seasons") or []
    already_archived = any(isinstance(s, dict) and int(s.get("year") or 0) == cy for s in seasons)

    if already_archived:
        _set_season_summary_phase(state)
        teams = {
            t["name"]: team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        if teams:
            update_prestige(teams, hist)
            state["prestige_applied_for_year"] = cy
            state["teams"] = [team_to_dict(t) for t in teams.values()]
        return True

    champion = str(playoffs.get("champion") or "").strip() or "—"
    runner_up = str(playoffs.get("runner_up") or "").strip() or "—"
    standings = state.get("standings") or {}
    team_names = [
        str(t.get("name"))
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    ]
    if not team_names:
        return False
    team_coaches: Dict[str, str] = {}
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        nm = str(t.get("name") or "")
        coach = t.get("coach")
        if nm and isinstance(coach, dict):
            team_coaches[nm] = str(coach.get("name") or "")
    br_flat = _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs))
    season_player_stats = season_stats_map_from_jsonable(state.get("playoff_season_player_stats") or {})
    p_bc = _playoffs_by_class_snapshot(state)
    regional_champions = compute_regular_season_regional_champions(state)
    try:
        append_season(
            champion=champion,
            runner_up=runner_up,
            team_names=team_names,
            standings=standings,
            season_player_stats=season_player_stats,
            year=cy,
            bracket_results=br_flat,
            team_coaches=team_coaches,
            playoffs_by_class=p_bc,
            regional_champions=regional_champions,
            save_dir=save_dir,
        )
        append_season_to_coach_career_log(
            state,
            year=cy,
            team_coaches=team_coaches,
            standings=standings,
        )
        teams = {
            t["name"]: team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        hist2 = load_league_history(league_history_path(save_dir))
        update_prestige(teams, hist2)
        state["prestige_applied_for_year"] = cy
        _set_season_summary_phase(state)
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        try:
            state["last_completed_standings"] = copy.deepcopy(standings)
        except Exception:
            state["last_completed_standings"] = {
                str(k): dict(v) if isinstance(v, dict) else v for k, v in dict(standings or {}).items()
            }
        state["last_completed_year"] = cy
        return True
    except Exception:
        logger.exception("repair playoffs complete to season_summary")
        return False


def finalize_season_to_summary_for_save_dir(state: Dict[str, Any], save_dir: str) -> Dict[str, Any]:
    """Archive a playoffs-complete season on disk and enter season_summary (multiplayer commish)."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        return state
    playoffs = state.get("playoffs")
    if not isinstance(playoffs, dict) or not _playoffs_global_completed(playoffs):
        return state
    _sync_playoff_top_level_champion_runner(playoffs)
    if not _repair_playoffs_complete_to_season_summary(state, save_dir):
        raise ValueError(
            "Playoffs are complete but the season could not be archived. "
            "Open Run league and use Finish season, or try Sim week again after a refresh."
        )
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    team_names = list(teams.keys())
    year_num = int(state.get("current_year", 1) or 1)
    if teams and int(state.get("program_funding_awarded_year") or 0) != year_num:
        standings = state.get("standings") or {}
        _award_program_funding_for_all_teams(teams, standings, current_year=year_num)
        state["program_funding_awarded_year"] = year_num
        state["teams"] = [team_to_dict(t) for t in teams.values()]
    if team_names:
        try:
            from systems.home_game_themes import compute_league_home_theme_summaries

            state["home_theme_season_rewards"] = compute_league_home_theme_summaries(state, team_names)
        except Exception:
            pass
    return state


def _sync_derived_save_fields(state: Dict[str, Any], save_dir: str) -> bool:
    """Migrate TP fields, repair missing archives, and apply prestige from history. Returns True if state changed."""
    changed = False
    if migrate_state_team_points_fields(state):
        changed = True
    teams_for_migrate: Dict[str, Any] = {}
    try:
        for row in state.get("teams") or []:
            if isinstance(row, dict) and row.get("name"):
                teams_for_migrate[str(row["name"])] = team_from_dict(row)
    except Exception:
        teams_for_migrate = {}
    if migrate_state_coach_dev_banks(state, teams_for_migrate):
        changed = True
    if _repair_playoffs_complete_to_season_summary(state, save_dir):
        changed = True
    if _repair_missing_archived_season(state, save_dir):
        changed = True
        apply_team_program_totals_from_history_to_state(save_dir, state)
        changed = True
    if _ensure_prestige_from_archived_season(state, save_dir):
        changed = True
    if enrich_save_teams_from_league_json(state):
        changed = True
    return changed


def load_state(user_id: str, save_id: str) -> Tuple[Dict[str, Any], str]:
    row = _get_save_row(user_id, save_id)
    import json

    save_name = row["save_name"]
    stored_dir = str(row["save_dir"] or "")
    save_dir = _resolve_save_directory(user_id, save_name, stored_dir)

    with open_text_with_path_fallback(_league_save_plain_path(save_dir), "r") as f:
        state = json.load(f)
    _ensure_user_coach_and_firing_defaults(state)
    _repair_user_team_from_serialized_teams(state)
    _refresh_user_coach_unemployed_flag(state)
    normalize_offseason_stages(state)
    normalize_preseason_stages(state)
    ensure_league_structure_in_state(state)
    # Migration: legacy saves predate the playoff_system field. Stamp the
    # default (WV) so callers can always read a valid id from state.
    ensure_playoff_system_in_state(state)
    ensure_league_metadata_in_state(state)
    if str(state.get("league_id") or "").strip().lower() == "wv_3class":
        if state.get("playoff_system") in (None, "", "wv"):
            state["playoff_system"] = "wv16"

    _migrate_save_dir_if_changed(user_id, save_id, save_dir, stored_dir)
    apply_team_program_totals_from_history_to_state(save_dir, state)
    _backfill_last_completed_standings(state, save_dir)
    if _finalize_cross_region_schedule_state(state):
        save_state(user_id, save_id, state, save_dir)
    elif _sync_derived_save_fields(state, save_dir):
        save_state(user_id, save_id, state, save_dir)
    try:
        hist = load_league_history(league_history_path(save_dir))
        rebuild_coach_career_log_from_league_history(state, hist, merge=True)
    except Exception:
        pass
    _hydrate_coach_inbox_persist_if_needed(user_id, save_id, state, save_dir)
    return state, save_dir


def _begin_playoffs_phase(state: Dict[str, Any], teams: Dict[str, Any], standings: Dict[str, Any]) -> None:
    """Enter playoffs and init brackets (no regional awards — those mutate state['teams'] separately)."""
    state["season_phase"] = "playoffs"
    state["playoff_season_player_stats"] = {}
    _ensure_playoffs_migrated(state, teams)
    if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
        state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
    _ensure_all_eligible_playoff_brackets(state, teams, standings)
    _reconcile_playoff_brackets_to_config(state, teams, standings)


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
    _refresh_user_coach_unemployed_flag(state)
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


def _archive_winter_training_session(state: Dict[str, Any]) -> None:
    """Keep Winter 1/2 player rows after user acknowledges results (Option 5 report)."""
    wr = state.get("offseason_winter_training_results")
    if not isinstance(wr, dict):
        return
    utr = wr.get("user_team_result")
    if not isinstance(utr, dict):
        return
    hist = state.get("offseason_winter_history")
    if not isinstance(hist, list):
        hist = []
    hist.append({"stage": str(wr.get("stage") or ""), "user_team_result": utr})
    state["offseason_winter_history"] = hist


def _archive_spring_ball_session(state: Dict[str, Any]) -> None:
    sr = state.get("offseason_spring_ball_results")
    if not isinstance(sr, dict):
        return
    utr = sr.get("user_team_result")
    if isinstance(utr, dict):
        state["offseason_spring_history"] = utr


def _training_player_rows_from_development(
    ut: Any,
    before_rows: List[Dict[str, Any]],
    player_reports: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Merge OVR snapshots with per-attribute training payload for the user team."""
    from systems.team_ratings import calculate_player_overall

    report_by_name: Dict[str, Dict[str, Any]] = {}
    for rep in player_reports or []:
        if isinstance(rep, dict) and rep.get("name"):
            report_by_name[str(rep["name"])] = rep

    out: List[Dict[str, Any]] = []
    after_roster = list(getattr(ut, "roster", []) or [])
    for i, p in enumerate(after_roster):
        name = getattr(p, "name", None) or (before_rows[i].get("name") if i < len(before_rows) else None)
        if not name:
            continue
        rep = report_by_name.get(str(name))
        if rep:
            out.append(
                {
                    "name": str(name),
                    "position": rep.get("position") or getattr(p, "position", None),
                    "before": int(rep.get("before", 0)),
                    "after": int(rep.get("after", 0)),
                    "delta": int(rep.get("delta", 0)),
                    "attributes": rep.get("attributes") if isinstance(rep.get("attributes"), dict) else {},
                }
            )
            continue
        b = int(before_rows[i]["before"]) if i < len(before_rows) else int(calculate_player_overall(p))
        a = int(calculate_player_overall(p))
        out.append(
            {
                "name": str(name),
                "position": getattr(p, "position", None) or (before_rows[i].get("position") if i < len(before_rows) else None),
                "before": b,
                "after": a,
                "delta": a - b,
                "attributes": {},
            }
        )
    return out


def _attach_platinum_breakthrough_training_metadata(
    deltas: List[Dict[str, Any]],
    user_equipment_training: Optional[Dict[str, Any]],
    eligible_before: List[str],
) -> None:
    eligible_set = {str(n) for n in eligible_before if n}
    breakthrough_by_name: Dict[str, int] = {}
    if isinstance(user_equipment_training, dict):
        extras = user_equipment_training.get("coaching_card_extras") or {}
        if isinstance(extras, dict):
            for ev in extras.get("events") or []:
                if not isinstance(ev, dict) or ev.get("type") != "platinum_breakthrough":
                    continue
                n = str(ev.get("player") or "").strip()
                if n:
                    breakthrough_by_name[n] = int(ev.get("potential_gain") or 0)
    for row in deltas:
        name = str(row.get("name") or "")
        row["platinum_breakthrough_eligible"] = name in eligible_set
        if name in breakthrough_by_name:
            row["platinum_breakthrough"] = True
            row["platinum_breakthrough_gain"] = breakthrough_by_name[name]
        else:
            row["platinum_breakthrough"] = False


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
    """In-place: scale active (non-zero) rows to ~100%; leave 0% plays at 0."""
    if not rows:
        return
    active_threshold = 0.01
    active = [r for r in rows if float(r.get("pct", 0) or 0) > active_threshold]
    if not active:
        return
    total = sum(float(r.get("pct", 0) or 0) for r in active)
    if 99.5 <= total <= 100.5:
        for r in rows:
            if float(r.get("pct", 0) or 0) <= active_threshold:
                r["pct"] = 0.0
        return
    if total <= 0:
        eq = 100.0 / len(active)
        for r in active:
            r["pct"] = eq
    else:
        for r in active:
            r["pct"] = (float(r.get("pct", 0) or 0) / total) * 100.0
    for r in rows:
        if float(r.get("pct", 0) or 0) <= active_threshold and r not in active:
            r["pct"] = 0.0


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


def _teams_map_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    teams_list = state.get("teams") or []
    teams: Dict[str, Any] = {}
    for t in teams_list:
        try:
            team_obj = team_from_dict(t) if isinstance(t, dict) else None
            if team_obj:
                teams[team_obj.name] = team_obj
        except Exception:
            continue
    return teams


def get_play_selection_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Play selection payload for game plan UI (stateless / browser saves)."""
    teams = _teams_map_from_state(state)
    user_team_name = state.get("user_team")
    if not user_team_name or user_team_name not in teams:
        return {"offensive": {}, "defensive": {}}

    team = teams[user_team_name]
    state_changed = False
    if not getattr(team, "season_offensive_play_selection", None) or not getattr(
        team, "season_defensive_play_selection", None
    ):
        try:
            run_play_selection_for_team(team)
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            state_changed = True
        except Exception:
            pass

    try:
        pb = build_playbook_for_team(team)
    except Exception:
        return {"offensive": {}, "defensive": {}}

    off_sel = getattr(team, "season_offensive_play_selection", None) or {}
    def_sel = getattr(team, "season_defensive_play_selection", None) or {}

    meta = get_install_meter_meta(team)
    out: Dict[str, Any] = {
        "offensive": _merge_offensive_playbook_for_display(pb, off_sel),
        "defensive": _merge_defensive_playbook_for_display(pb, def_sel),
        "install_meta": meta,
    }
    if state_changed:
        out["state"] = state
    return out


def get_play_selection_for_team(user_id: str, save_id: str) -> Dict[str, Any]:
    """Return user team's play selection with play names for the game plan UI."""
    try:
        state, save_dir = load_state(user_id, save_id)
    except Exception:
        return {"offensive": {}, "defensive": {}}

    out = get_play_selection_from_state(state)
    if out.get("state") is not None:
        save_state(user_id, save_id, out["state"], save_dir)
        del out["state"]
    return out


def get_play_learning_summary_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Learning summary for Play Selection Results (stateless / browser saves)."""
    teams = _teams_map_from_state(state)
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
    return get_play_learning_summary_from_state(state)


def update_depth_chart_in_state(state: Dict[str, Any], depth_chart: Dict[str, List[str]]) -> Dict[str, Any]:
    """Save user's depth chart order and return updated state (in-memory)."""
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
    return state


def update_depth_chart(user_id: str, save_id: str, depth_chart: Dict[str, List[str]]) -> Dict[str, Any]:
    """Save user's depth chart order and return updated state."""
    state, save_dir = load_state(user_id, save_id)
    state = update_depth_chart_in_state(state, depth_chart)
    save_state(user_id, save_id, state, save_dir)
    return state


def _week_result_slot_finalized(slot: Any) -> bool:
    """True when this schedule slot already has a final result (do not re-sim)."""
    if not isinstance(slot, dict):
        return False
    if slot.get("played") is True:
        return True
    if slot.get("played") is False:
        return False
    recap = str(slot.get("recap") or slot.get("box_score_text") or "")
    if recap and "FINAL:" in recap:
        return True
    return False


def _week_result_slot_played(slot: Any) -> bool:
    """Alias for callers that gate week sim / coach finish on completed slots."""
    return _week_result_slot_finalized(slot)


def _regular_week_fully_played(state: Dict[str, Any], wk_idx: int) -> bool:
    weeks = state.get("weeks") or []
    if wk_idx < 0 or wk_idx >= len(weeks):
        return False
    wk = weeks[wk_idx] or []
    if not wk:
        return False
    week_results = state.get("week_results") or []
    if wk_idx >= len(week_results):
        return False
    wk_res = week_results[wk_idx] or []
    for gi in range(len(wk)):
        if gi >= len(wk_res) or not _week_result_slot_played(wk_res[gi]):
            return False
    return True


def _maybe_generate_week_sim_emails_if_complete(state: Dict[str, Any], *, completed_week: int) -> None:
    """Append the weekly inbox batch once every slot in ``completed_week`` is final."""
    if not _coach_sim_emails_enabled():
        return
    wk_idx = int(completed_week) - 1
    if not _regular_week_fully_played(state, wk_idx):
        return
    generate_week_sim_emails(state, completed_week=int(completed_week))


def _maybe_generate_week_checklist_email(state: Dict[str, Any], *, week: Optional[int] = None) -> None:
    """Append the static Monday checklist for the active regular-season week (idempotent)."""
    generate_week_checklist_email(state, week=week)


def _apply_game_result_to_standings(
    standings: Dict[str, Dict[str, Any]],
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> None:
    for name in (home, away):
        if name not in standings:
            standings[name] = {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0}
    home_s = standings[home]
    away_s = standings[away]
    home_s["points_for"] = int(home_s.get("points_for", 0)) + int(home_score)
    home_s["points_against"] = int(home_s.get("points_against", 0)) + int(away_score)
    away_s["points_for"] = int(away_s.get("points_for", 0)) + int(away_score)
    away_s["points_against"] = int(away_s.get("points_against", 0)) + int(home_score)
    if home_score > away_score:
        home_s["wins"] = int(home_s.get("wins", 0)) + 1
        away_s["losses"] = int(away_s.get("losses", 0)) + 1
    elif away_score > home_score:
        away_s["wins"] = int(away_s.get("wins", 0)) + 1
        home_s["losses"] = int(home_s.get("losses", 0)) + 1


def _rebuild_standings_from_week_results(state: Dict[str, Any], team_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Recompute W/L and points from finalized week_results (prevents double-count on week sim)."""
    standings: Dict[str, Dict[str, Any]] = {
        n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names
    }
    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    for wi, wk in enumerate(weeks):
        if not isinstance(wk, list):
            continue
        wk_res = week_results[wi] if wi < len(week_results) else []
        for gi, g in enumerate(wk):
            if not isinstance(g, dict):
                continue
            home = g.get("home")
            away = g.get("away")
            if not home or not away:
                continue
            slot = wk_res[gi] if gi < len(wk_res) else {}
            if not _week_result_slot_finalized(slot):
                continue
            _apply_game_result_to_standings(
                standings,
                str(home),
                str(away),
                int(slot.get("home_score", 0)),
                int(slot.get("away_score", 0)),
            )
    return standings


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


def _coach_gameplan_v2_key_for_user_team(key: str, user_team: str) -> bool:
    """True when a stored matchup key belongs to the user's team (incl. bye keys)."""
    key = str(key or "").strip()
    user_team = str(user_team or "").strip()
    if not key or not user_team:
        return False
    if key.startswith("bye:week:"):
        parts = key.split(":")
        return len(parts) >= 4 and parts[3] == user_team
    matchup = ""
    if key.startswith("week:"):
        parts = key.split(":", 3)
        matchup = parts[3] if len(parts) > 3 else ""
    elif key.startswith("playoff:"):
        matchup = key.split(":", 1)[1] if ":" in key else ""
    if matchup and " vs " in matchup:
        home, away = matchup.split(" vs ", 1)
        return user_team in (home.strip(), away.strip())
    return False


def _normalize_offense_gameplan_library(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """User-imported offensive plans stored on the dynasty save."""
    raw = state.get("offense_gameplan_library")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        plan = item.get("plan")
        if not entry_id or not name or not isinstance(plan, dict):
            continue
        ok, _ = validate_gameplan_v2(plan, categories=GAMEPLAN_V2_OFF_CATEGORIES)
        if not ok:
            continue
        try:
            created_at = int(item.get("created_at") or 0)
        except Exception:
            created_at = 0
        out.append({"id": entry_id, "name": name, "plan": plan, "created_at": created_at})
    return out


def _offense_gameplan_library_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "presets": list_offensive_preset_catalog(),
        "saved": _normalize_offense_gameplan_library(state),
    }


def add_offense_to_gameplan_library_in_state(
    state: Dict[str, Any],
    *,
    name: str,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    label = str(name or "").strip()
    if not label:
        raise ValueError("Saved game plan name is required.")
    ok, errs = validate_gameplan_v2(plan, categories=GAMEPLAN_V2_OFF_CATEGORIES)
    if not ok:
        raise ValueError("Invalid OFF gameplan: " + "; ".join(errs[:10]))
    library = _normalize_offense_gameplan_library(state)
    entry = {
        "id": f"saved-{uuid.uuid4().hex[:12]}",
        "name": label,
        "plan": plan,
        "created_at": int(time.time()),
    }
    library.append(entry)
    state["offense_gameplan_library"] = library
    return entry


def delete_offense_from_gameplan_library_in_state(state: Dict[str, Any], entry_id: str) -> bool:
    target = str(entry_id or "").strip()
    if not target:
        raise ValueError("Saved game plan id is required.")
    library = _normalize_offense_gameplan_library(state)
    next_library = [e for e in library if e.get("id") != target]
    if len(next_library) == len(library):
        raise ValueError("Saved game plan not found.")
    state["offense_gameplan_library"] = next_library
    return True


def _normalize_defense_gameplan_library(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """User-imported defensive plans stored on the dynasty save."""
    raw = state.get("defense_gameplan_library")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        plan = item.get("plan")
        if not entry_id or not name or not isinstance(plan, dict):
            continue
        ok, _ = validate_gameplan_v2(plan, categories=GAMEPLAN_V2_DEF_CATEGORIES)
        if not ok:
            continue
        try:
            created_at = int(item.get("created_at") or 0)
        except Exception:
            created_at = 0
        out.append({"id": entry_id, "name": name, "plan": plan, "created_at": created_at})
    return out


def _defense_gameplan_library_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "presets": list_defensive_preset_catalog(),
        "saved": _normalize_defense_gameplan_library(state),
    }


def add_defense_to_gameplan_library_in_state(
    state: Dict[str, Any],
    *,
    name: str,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    label = str(name or "").strip()
    if not label:
        raise ValueError("Saved game plan name is required.")
    ok, errs = validate_gameplan_v2(plan, categories=GAMEPLAN_V2_DEF_CATEGORIES)
    if not ok:
        raise ValueError("Invalid DEF gameplan: " + "; ".join(errs[:10]))
    library = _normalize_defense_gameplan_library(state)
    entry = {
        "id": f"saved-{uuid.uuid4().hex[:12]}",
        "name": label,
        "plan": plan,
        "created_at": int(time.time()),
    }
    library.append(entry)
    state["defense_gameplan_library"] = library
    return entry


def delete_defense_from_gameplan_library_in_state(state: Dict[str, Any], entry_id: str) -> bool:
    target = str(entry_id or "").strip()
    if not target:
        raise ValueError("Saved game plan id is required.")
    library = _normalize_defense_gameplan_library(state)
    next_library = [e for e in library if e.get("id") != target]
    if len(next_library) == len(library):
        raise ValueError("Saved game plan not found.")
    state["defense_gameplan_library"] = next_library
    return True


def _gameplan_week_to_week_flags(state: Dict[str, Any]) -> Dict[str, bool]:
    raw = state.get("gameplan_week_to_week")
    if not isinstance(raw, dict):
        return {"offense": False, "defense": False}
    return {"offense": bool(raw.get("offense")), "defense": bool(raw.get("defense"))}


def _gameplan_last_confirmed(state: Dict[str, Any]) -> Dict[str, Any]:
    raw = state.get("gameplan_last_confirmed")
    return raw if isinstance(raw, dict) else {}


def _sync_last_confirmed_from_matchup_store(state: Dict[str, Any]) -> None:
    """Copy the current matchup's saved plans into gameplan_last_confirmed."""
    key = _coach_gameplan_v2_matchup_key(state)
    if not key:
        return
    store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
    entry = store.get(key) if isinstance(store.get(key), dict) else None
    if not isinstance(entry, dict):
        return
    last = dict(_gameplan_last_confirmed(state))
    changed = False
    off = entry.get("offense")
    if isinstance(off, dict):
        ok, _ = validate_gameplan_v2(off, categories=GAMEPLAN_V2_OFF_CATEGORIES)
        if ok:
            last["offense"] = off
            changed = True
    deff = entry.get("defense")
    if isinstance(deff, dict):
        ok, _ = validate_gameplan_v2(deff, categories=GAMEPLAN_V2_DEF_CATEGORIES)
        if ok:
            last["defense"] = deff
            changed = True
    fd = entry.get("fourth_down")
    if isinstance(fd, dict):
        last["fourth_down"] = fd
        changed = True
    if changed:
        state["gameplan_last_confirmed"] = last


def _carried_side_plan(state: Dict[str, Any], side: str, categories: List[str]) -> Optional[Dict[str, Any]]:
    """Template plan for week-to-week carry: last confirmed, else most recent matchup save."""
    last = _gameplan_last_confirmed(state)
    direct = last.get(side)
    if isinstance(direct, dict):
        ok, _ = validate_gameplan_v2(direct, categories=categories)
        if ok:
            return direct

    store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
    user_team = str(state.get("user_team") or "").strip()
    best_plan: Optional[Dict[str, Any]] = None
    best_ts = -1
    for key, entry in store.items():
        if user_team and not _coach_gameplan_v2_key_for_user_team(str(key), user_team):
            continue
        if not isinstance(entry, dict):
            continue
        plan = entry.get(side)
        if not isinstance(plan, dict):
            continue
        ok, _ = validate_gameplan_v2(plan, categories=categories)
        if not ok:
            continue
        try:
            ts = int(entry.get("updated_at") or 0)
        except Exception:
            ts = 0
        if ts >= best_ts:
            best_ts = ts
            best_plan = plan
    return best_plan


def _materialize_carried_gameplan_for_current_week(state: Dict[str, Any]) -> bool:
    """Ensure coach_gameplans_v2 has an entry for this week when carry-forward is enabled."""
    key = _coach_gameplan_v2_matchup_key(state)
    if not key:
        return False
    flags = _gameplan_week_to_week_flags(state)
    if not (flags.get("offense") or flags.get("defense")):
        return False

    store = state.get("coach_gameplans_v2")
    if not isinstance(store, dict):
        store = {}
    entry = dict(store.get(key)) if isinstance(store.get(key), dict) else {}
    changed = False

    if flags.get("offense") and not isinstance(entry.get("offense_package"), dict):
        last = _gameplan_last_confirmed(state)
        carried_pkg = last.get("offense_package")
        if isinstance(carried_pkg, dict):
            entry["offense_package"] = copy.deepcopy(carried_pkg)
            changed = True
        elif not isinstance(entry.get("offense"), dict):
            carried = _carried_side_plan(state, "offense", GAMEPLAN_V2_OFF_CATEGORIES)
            if isinstance(carried, dict):
                entry["offense"] = carried
                entry["offense_package"] = default_side_package("offense", carried)
                changed = True

    if flags.get("defense") and not isinstance(entry.get("defense_package"), dict):
        last = _gameplan_last_confirmed(state)
        carried_pkg = last.get("defense_package")
        if isinstance(carried_pkg, dict):
            entry["defense_package"] = copy.deepcopy(carried_pkg)
            changed = True
        elif not isinstance(entry.get("defense"), dict):
            carried = _carried_side_plan(state, "defense", GAMEPLAN_V2_DEF_CATEGORIES)
            if isinstance(carried, dict):
                entry["defense"] = carried
                entry["defense_package"] = default_side_package("defense", carried)
                changed = True

    if flags.get("offense") or flags.get("defense"):
        last = _gameplan_last_confirmed(state)
        if isinstance(last.get("team_script"), dict) and not isinstance(entry.get("team_script"), dict):
            entry["team_script"] = copy.deepcopy(last["team_script"])
            changed = True

    if changed:
        entry["updated_at"] = int(time.time())
        store[key] = entry
        state["coach_gameplans_v2"] = store
    return changed


def _resolved_matchup_gameplan_entry(state: Dict[str, Any]) -> Dict[str, Any]:
    """Per-matchup plans with optional week-to-week carry from last confirmed."""
    key = _coach_gameplan_v2_matchup_key(state)
    store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
    stored = store.get(key) if key and isinstance(store.get(key), dict) else {}
    entry: Dict[str, Any] = dict(stored) if isinstance(stored, dict) else {}

    flags = _gameplan_week_to_week_flags(state)

    if flags.get("offense") and not isinstance(entry.get("offense_package"), dict):
        carried = _gameplan_last_confirmed(state).get("offense_package")
        if isinstance(carried, dict):
            entry["offense_package"] = copy.deepcopy(carried)
        elif not isinstance(entry.get("offense"), dict):
            carried_grid = _carried_side_plan(state, "offense", GAMEPLAN_V2_OFF_CATEGORIES)
            if isinstance(carried_grid, dict):
                entry["offense"] = carried_grid
                entry["offense_package"] = default_side_package("offense", carried_grid)

    if flags.get("defense") and not isinstance(entry.get("defense_package"), dict):
        carried = _gameplan_last_confirmed(state).get("defense_package")
        if isinstance(carried, dict):
            entry["defense_package"] = copy.deepcopy(carried)
        elif not isinstance(entry.get("defense"), dict):
            carried_grid = _carried_side_plan(state, "defense", GAMEPLAN_V2_DEF_CATEGORIES)
            if isinstance(carried_grid, dict):
                entry["defense"] = carried_grid
                entry["defense_package"] = default_side_package("defense", carried_grid)

    ts = _gameplan_last_confirmed(state).get("team_script")
    if (flags.get("offense") or flags.get("defense")) and isinstance(ts, dict) and not isinstance(entry.get("team_script"), dict):
        entry["team_script"] = copy.deepcopy(ts)

    return normalize_matchup_entry(entry)


def _apply_gameplan_entry_to_coach(coach: Any, entry: Dict[str, Any]) -> None:
    if coach is None or not isinstance(entry, dict):
        return
    norm = normalize_matchup_entry(entry)
    apply_packages_to_coach(coach, norm)


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
    entry = _resolved_matchup_gameplan_entry(state)
    if not entry:
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
    _apply_gameplan_entry_to_coach(coach, entry)


def _installed_plays_payload(state: Dict[str, Any], side: str) -> List[Dict[str, str]]:
    """Installed play ids/names for call sheet dropdowns."""
    user = state.get("user_team")
    teams = {t.get("name"): t for t in (state.get("teams") or []) if isinstance(t, dict)}
    tdat = teams.get(user) if user else None
    if not isinstance(tdat, dict):
        return []
    team = team_from_dict(tdat)
    sel = (
        getattr(team, "season_offensive_play_selection", None)
        if side == "offense"
        else getattr(team, "season_defensive_play_selection", None)
    )
    if not isinstance(sel, dict):
        return []
    from systems.play_selection import filter_active_play_entries

    out: List[Dict[str, str]] = []
    seen: set = set()
    for entries in sel.values():
        if not isinstance(entries, list):
            continue
        for play_id, _pct in filter_active_play_entries(entries):
            pid = str(play_id)
            if pid in seen:
                continue
            seen.add(pid)
            out.append({"id": pid, "name": pid.replace("_", " ").title()})
    out.sort(key=lambda x: x["name"])
    return out


def get_coach_gameplan_v2_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the coach gameplan (OFF + DEF) for the user's next game.
    Stored inside the save so it travels with the dynasty.
    """
    _materialize_carried_gameplan_for_current_week(state)
    key = _coach_gameplan_v2_matchup_key(state)
    resolved_raw = _resolved_matchup_gameplan_entry(state)
    norm = normalize_matchup_entry(resolved_raw)

    offense_pkg = norm["offense_package"]
    defense_pkg = norm["defense_package"]
    team_script = norm["team_script"]

    # Legacy top-level grid mirrors for older clients
    offense = offense_pkg["grid"] if offense_pkg.get("gameplan_mode") == "grid" else offense_pkg.get("grid")
    defense = defense_pkg["grid"] if defense_pkg.get("gameplan_mode") == "grid" else defense_pkg.get("grid")

    ok_off, _ = validate_gameplan_v2(offense, categories=GAMEPLAN_V2_OFF_CATEGORIES)
    ok_def, _ = validate_gameplan_v2(defense, categories=GAMEPLAN_V2_DEF_CATEGORIES)
    if not ok_off:
        offense = make_default_offense_gameplan_v2()
        offense_pkg = default_side_package("offense", offense)
    if not ok_def:
        defense = make_default_defense_gameplan_v2()
        defense_pkg = default_side_package("defense", defense)

    is_bye = key is None
    phase_s = str(state.get("season_phase") or "").strip().lower()

    return {
        "matchup_key": key,
        "is_bye_week": is_bye,
        "offense": offense,
        "defense": defense,
        "offense_package": offense_pkg,
        "defense_package": defense_pkg,
        "team_script": team_script,
        "week_to_week": _gameplan_week_to_week_flags(state),
        "offense_library": _offense_gameplan_library_payload(state),
        "defense_library": _defense_gameplan_library_payload(state),
        "installed_plays_offense": _installed_plays_payload(state, "offense"),
        "installed_plays_defense": _installed_plays_payload(state, "defense"),
        "halftime_triggers_offense": [{"id": k, "label": v} for k, v in HALFTIME_TRIGGERS_OFF.items()],
        "halftime_triggers_defense": [{"id": k, "label": v} for k, v in HALFTIME_TRIGGERS_DEF.items()],
        "meta": {
            "season_phase": phase_s,
            "current_week": int(state.get("current_week", 1) or 1),
            "user_team": str(state.get("user_team") or ""),
            "gameplan_available": phase_s in ("regular", "playoffs") and not is_bye,
        },
    }


def get_coach_gameplan_v2(user_id: str, save_id: str) -> Dict[str, Any]:
    state, save_dir = load_state(user_id, save_id)
    if _materialize_carried_gameplan_for_current_week(state):
        save_state(user_id, save_id, state, save_dir)
    return get_coach_gameplan_v2_from_state(state)


def save_coach_gameplan_v2_in_state(
    state: Dict[str, Any],
    *,
    offense: Optional[Dict[str, Any]] = None,
    defense: Optional[Dict[str, Any]] = None,
    offense_package: Optional[Dict[str, Any]] = None,
    defense_package: Optional[Dict[str, Any]] = None,
    team_script: Optional[Dict[str, Any]] = None,
    fourth_down: Optional[Dict[str, Any]] = None,
    add_offense_library: Optional[Dict[str, Any]] = None,
    delete_offense_library_id: Optional[str] = None,
    add_defense_library: Optional[Dict[str, Any]] = None,
    delete_defense_library_id: Optional[str] = None,
    week_to_week_offense: Optional[bool] = None,
    week_to_week_defense: Optional[bool] = None,
    confirm_offense: Optional[bool] = None,
    confirm_defense: Optional[bool] = None,
    autofill_callsheet: Optional[bool] = None,
) -> Dict[str, Any]:
    """Save the user's coach gameplan for the next game (mutates state in memory)."""
    library_changed = False
    if add_offense_library is not None:
        if not isinstance(add_offense_library, dict):
            raise ValueError("add_offense_library must be an object with name and plan.")
        add_offense_to_gameplan_library_in_state(
            state,
            name=str(add_offense_library.get("name") or ""),
            plan=add_offense_library.get("plan") if isinstance(add_offense_library.get("plan"), dict) else {},
        )
        library_changed = True
    if delete_offense_library_id:
        delete_offense_from_gameplan_library_in_state(state, delete_offense_library_id)
        library_changed = True
    if add_defense_library is not None:
        if not isinstance(add_defense_library, dict):
            raise ValueError("add_defense_library must be an object with name and plan.")
        add_defense_to_gameplan_library_in_state(
            state,
            name=str(add_defense_library.get("name") or ""),
            plan=add_defense_library.get("plan") if isinstance(add_defense_library.get("plan"), dict) else {},
        )
        library_changed = True
    if delete_defense_library_id:
        delete_defense_from_gameplan_library_in_state(state, delete_defense_library_id)
        library_changed = True

    carry_changed = week_to_week_offense is not None or week_to_week_defense is not None
    if carry_changed:
        carry = state.get("gameplan_week_to_week")
        if not isinstance(carry, dict):
            carry = {}
        if week_to_week_offense is not None:
            carry["offense"] = bool(week_to_week_offense)
        if week_to_week_defense is not None:
            carry["defense"] = bool(week_to_week_defense)
        state["gameplan_week_to_week"] = carry

    matchup_changed = (
        offense is not None
        or defense is not None
        or offense_package is not None
        or defense_package is not None
        or team_script is not None
        or fourth_down is not None
        or confirm_offense is not None
        or confirm_defense is not None
        or autofill_callsheet
    )
    if matchup_changed:
        key = _coach_gameplan_v2_matchup_key(state)
        phase_s = str(state.get("season_phase") or "").strip().lower()
        if not key and not (phase_s in ("regular", "playoffs")):
            raise ValueError("No upcoming game found to attach a gameplan to.")
        # Bye week: practice-only updates stored on synthetic bye key
        if not key:
            user = str(state.get("user_team") or "")
            wk = int(state.get("current_week", 1) or 1)
            key = f"bye:week:{wk}:{user}"

        store = state.get("coach_gameplans_v2")
        if not isinstance(store, dict):
            store = {}

        entry = store.get(key)
        if not isinstance(entry, dict):
            entry = {}
        entry = normalize_matchup_entry(entry)

        if offense_package is not None:
            pkg = normalize_side_package(offense_package, "offense")
            ok, errs = validate_side_package(pkg, "offense")
            if not ok:
                raise ValueError("Invalid OFF package: " + "; ".join(errs[:8]))
            entry["offense_package"] = pkg
            if pkg.get("gameplan_mode") == "grid":
                entry["offense"] = pkg["grid"]
        elif offense is not None:
            ok, errs = validate_gameplan_v2(offense, categories=GAMEPLAN_V2_OFF_CATEGORIES)
            if not ok:
                raise ValueError("Invalid OFF gameplan: " + "; ".join(errs[:10]))
            op = entry.get("offense_package") if isinstance(entry.get("offense_package"), dict) else default_side_package("offense")
            op = normalize_side_package(op, "offense", offense)
            op["grid"] = offense
            entry["offense_package"] = op
            entry["offense"] = offense

        if defense_package is not None:
            pkg = normalize_side_package(defense_package, "defense")
            ok, errs = validate_side_package(pkg, "defense")
            if not ok:
                raise ValueError("Invalid DEF package: " + "; ".join(errs[:8]))
            entry["defense_package"] = pkg
            if pkg.get("gameplan_mode") == "grid":
                entry["defense"] = pkg["grid"]
        elif defense is not None:
            ok, errs = validate_gameplan_v2(defense, categories=GAMEPLAN_V2_DEF_CATEGORIES)
            if not ok:
                raise ValueError("Invalid DEF gameplan: " + "; ".join(errs[:10]))
            dp = entry.get("defense_package") if isinstance(entry.get("defense_package"), dict) else default_side_package("defense")
            dp = normalize_side_package(dp, "defense", defense)
            dp["grid"] = defense
            entry["defense_package"] = dp
            entry["defense"] = defense

        if team_script is not None and isinstance(team_script, dict):
            entry["team_script"] = {**default_team_script(), **team_script}

        if fourth_down is not None and isinstance(fourth_down, dict):
            try:
                risk = max(0, min(100, int(fourth_down.get("risk", fourth_down.get("go_for_it_max_ytg", 50)))))
            except Exception:
                risk = 50
            ts = entry.get("team_script") if isinstance(entry.get("team_script"), dict) else default_team_script()
            ts["risk"] = risk
            entry["team_script"] = ts

        if confirm_offense is not None and isinstance(entry.get("offense_package"), dict):
            entry["offense_package"]["confirmed"] = bool(confirm_offense)
        if confirm_defense is not None and isinstance(entry.get("defense_package"), dict):
            entry["defense_package"]["confirmed"] = bool(confirm_defense)

        if autofill_callsheet:
            user = state.get("user_team")
            teams = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")}
            team = teams.get(user) if user else None
            if team is not None:
                op = entry.get("offense_package") if isinstance(entry.get("offense_package"), dict) else default_side_package("offense")
                dp = entry.get("defense_package") if isinstance(entry.get("defense_package"), dict) else default_side_package("defense")
                op["callsheet"] = autofill_callsheet_from_install(team, "offense")
                dp["callsheet"] = autofill_callsheet_from_install(team, "defense")
                entry["offense_package"] = op
                entry["defense_package"] = dp

        entry["updated_at"] = int(time.time())
        store[key] = normalize_matchup_entry(entry)
        state["coach_gameplans_v2"] = store

        last = dict(_gameplan_last_confirmed(state))
        last["offense_package"] = store[key]["offense_package"]
        last["defense_package"] = store[key]["defense_package"]
        last["team_script"] = store[key]["team_script"]
        last["offense"] = store[key].get("offense")
        last["defense"] = store[key].get("defense")
        state["gameplan_last_confirmed"] = last
    elif not library_changed and not carry_changed:
        raise ValueError("Nothing to save.")

    flags = _gameplan_week_to_week_flags(state)
    if flags.get("offense") or flags.get("defense"):
        _sync_last_confirmed_from_matchup_store(state)
    _materialize_carried_gameplan_for_current_week(state)

    return get_coach_gameplan_v2_from_state(state)


def save_coach_gameplan_v2(
    user_id: str,
    save_id: str,
    *,
    offense: Optional[Dict[str, Any]] = None,
    defense: Optional[Dict[str, Any]] = None,
    offense_package: Optional[Dict[str, Any]] = None,
    defense_package: Optional[Dict[str, Any]] = None,
    team_script: Optional[Dict[str, Any]] = None,
    fourth_down: Optional[Dict[str, Any]] = None,
    add_offense_library: Optional[Dict[str, Any]] = None,
    delete_offense_library_id: Optional[str] = None,
    add_defense_library: Optional[Dict[str, Any]] = None,
    delete_defense_library_id: Optional[str] = None,
    week_to_week_offense: Optional[bool] = None,
    week_to_week_defense: Optional[bool] = None,
    confirm_offense: Optional[bool] = None,
    confirm_defense: Optional[bool] = None,
    autofill_callsheet: Optional[bool] = None,
) -> Dict[str, Any]:
    """Save the user's coach gameplan for the next game."""
    state, save_dir = load_state(user_id, save_id)
    result = save_coach_gameplan_v2_in_state(
        state,
        offense=offense,
        defense=defense,
        offense_package=offense_package,
        defense_package=defense_package,
        team_script=team_script,
        fourth_down=fourth_down,
        add_offense_library=add_offense_library,
        delete_offense_library_id=delete_offense_library_id,
        add_defense_library=add_defense_library,
        delete_defense_library_id=delete_defense_library_id,
        week_to_week_offense=week_to_week_offense,
        week_to_week_defense=week_to_week_defense,
        confirm_offense=confirm_offense,
        confirm_defense=confirm_defense,
        autofill_callsheet=autofill_callsheet,
    )
    save_state(user_id, save_id, state, save_dir)
    return result


def _team_recap_safe_filename(team_name: str) -> str:
    return "".join(c for c in str(team_name) if c.isalnum() or c in " _-").strip() or "team"


def _bracket_results_for_archived_season(
    season_entry: Dict[str, Any],
    team_name: str,
    teams_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Playoff games for recap augmentation (per-class bracket when available)."""
    pbc = season_entry.get("playoffs_by_class")
    if isinstance(pbc, dict) and pbc:
        cls = _classification_of_team(teams_map, team_name)
        inner = _playoffs_inner_for_class(pbc, cls)
        if isinstance(inner, dict):
            br = inner.get("bracket_results")
            if isinstance(br, list) and br:
                return [g for g in br if isinstance(g, dict)]
    playoffs = season_entry.get("playoffs")
    if isinstance(playoffs, dict):
        br = playoffs.get("bracket_results")
        if isinstance(br, list) and br:
            return [g for g in br if isinstance(g, dict)]
    return []


def _augment_recap_text_with_postseason(
    text: str,
    team_name: str,
    bracket_results: List[Dict[str, Any]],
) -> str:
    """Older recap files may lack POSTSEASON; inject from archived bracket_results."""
    if not text or not bracket_results:
        return text
    if "POSTSEASON" in text.upper():
        return text
    playoff_lines = recap_postseason_lines_for_team(team_name, bracket_results)
    if not playoff_lines:
        return text
    block = "\n".join(["", "POSTSEASON", "-" * 66, *playoff_lines, ""])
    marker = "TEAM STATS"
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx].rstrip() + block + "\n" + text[idx:]
    return text.rstrip() + block + "\n"


def _resolve_team_recap_file_path(
    save_dir: str,
    team_name: str,
    season_entry: Dict[str, Any],
) -> Optional[str]:
    """Absolute path to on-disk recap .txt, or None."""
    team = str(team_name or "").strip()
    if not team:
        return None
    base = os.path.abspath(save_dir)
    recaps = season_entry.get("team_recaps") if isinstance(season_entry.get("team_recaps"), dict) else {}
    rel = recaps.get(team) if isinstance(recaps.get(team), str) else None
    if rel:
        p = os.path.abspath(os.path.join(save_dir, rel))
        if p.startswith(base) and isfile_any(p):
            return p
    safe = _team_recap_safe_filename(team)
    year_num = int(season_entry.get("year", 0) or 0)
    season_num = int(season_entry.get("season", year_num) or year_num)
    candidates: List[str] = []
    if year_num:
        candidates.append(os.path.join(save_dir, "season_recaps", f"year_{year_num}", f"{safe}.txt"))
    if season_num and season_num != year_num:
        candidates.append(os.path.join(save_dir, "season_recaps", f"year_{season_num}", f"{safe}.txt"))
    candidates.append(os.path.join(save_dir, "season_recaps", f"{safe}.txt"))
    for p in candidates:
        ap = os.path.abspath(p)
        if ap.startswith(base) and isfile_any(ap):
            return ap
    recap_root = os.path.join(save_dir, "season_recaps")
    if not os.path.isdir(recap_root):
        return None
    y_tokens = {str(year_num), str(season_num)}
    try:
        for root, _dirs, files in os.walk(recap_root):
            if f"{safe}.txt" not in files:
                continue
            rel_dir = os.path.relpath(root, recap_root).replace("\\", "/")
            if any(tok in rel_dir for tok in y_tokens if tok and tok != "0"):
                ap = os.path.abspath(os.path.join(root, f"{safe}.txt"))
                if ap.startswith(base):
                    return ap
    except OSError:
        pass
    return None


def _team_has_season_recap(save_dir: str, team_name: str, season_entry: Dict[str, Any]) -> bool:
    return _resolve_team_recap_file_path(save_dir, team_name, season_entry) is not None


def _coach_display_name_for_team_in_state(state: Dict[str, Any], team: str) -> str:
    for t in state.get("teams") or []:
        if not isinstance(t, dict) or str(t.get("name") or "").strip() != team:
            continue
        coach = t.get("coach")
        if isinstance(coach, dict):
            nm = str(coach.get("name") or "").strip()
            if nm:
                return nm
        break
    return "—"


def _merge_live_and_snapshot_team_history_rows(
    state: Dict[str, Any],
    save_dir: str,
    team: str,
    rows: List[Dict[str, Any]],
    teams: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    When league_history.json is empty or missing a year, still show:
    - the in-progress season (regular / playoffs / season summary), and
    - the just-finished season from last_completed_standings (offseason+).
    """
    if not team:
        return rows
    seen_years = {int(r.get("year", 0) or 0) for r in rows if r.get("year") is not None}
    out = list(rows)
    phase = str(state.get("season_phase") or "").strip().lower()

    def _append_row(year: int, wins: int, losses: int, postseason: str, has_recap: bool) -> None:
        if year in seen_years:
            return
        seen_years.add(year)
        out.append(
            {
                "year": year,
                "wins": wins,
                "losses": losses,
                "postseason": postseason,
                "coach": _coach_display_name_for_team_in_state(state, team),
                "has_recap": has_recap,
            }
        )

    try:
        cy = int(state.get("current_year", 0) or 0)
    except (TypeError, ValueError):
        cy = 0
    if phase in ("regular", "playoffs", "season_summary") and cy:
        st = (state.get("standings") or {}).get(team)
        if isinstance(st, dict):
            wins = int(st.get("wins", 0) or 0)
            losses = int(st.get("losses", 0) or 0)
            _append_row(
                cy,
                wins,
                losses,
                _postseason_label_live(state, team, teams) if phase in ("playoffs", "season_summary") else "—",
                _team_has_season_recap(save_dir, team, {"year": cy}),
            )

    try:
        lcy = int(state.get("last_completed_year", 0) or 0)
    except (TypeError, ValueError):
        lcy = 0
    snap_all = state.get("last_completed_standings")
    snap = snap_all.get(team) if isinstance(snap_all, dict) else None
    if lcy and isinstance(snap, dict):
        season_entry = None
        try:
            hist = load_league_history(league_history_path(save_dir))
            for s in hist.get("seasons") or []:
                if isinstance(s, dict) and int(s.get("year", 0) or 0) == lcy:
                    season_entry = s
                    break
        except Exception:
            season_entry = None
        po = _postseason_label_archived(team, season_entry, teams) if season_entry else "—"
        _append_row(
            lcy,
            int(snap.get("wins", 0) or 0),
            int(snap.get("losses", 0) or 0),
            po,
            _team_has_season_recap(save_dir, team, season_entry or {"year": lcy}),
        )

    out.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    return out


def _postseason_label_live(state: Dict[str, Any], team: str, teams: Dict[str, Any]) -> str:
    """Postseason chip from in-save playoffs object (before archive)."""
    playoffs = state.get("playoffs")
    if not playoffs or not isinstance(playoffs, dict):
        return "—"
    pbc = playoffs.get("by_class")
    if pbc and isinstance(pbc, dict):
        cls = None
        t_obj = teams.get(team)
        if t_obj is not None:
            cls = getattr(t_obj, "classification", None)
        if cls and cls in pbc:
            inner = pbc[cls]
            if isinstance(inner, dict):
                if inner.get("champion") == team:
                    return "State Champion"
                if inner.get("runner_up") == team:
                    return "Runner-up"
    if playoffs.get("champion") == team:
        return "State Champion"
    if playoffs.get("runner_up") == team:
        return "Runner-up"
    return "—"


def get_team_ratings(user_id: str, save_id: str) -> Dict[str, Any]:
    """Roster-derived team ratings (offense, defense, run, pass, overall) for every team in the save."""
    state, _save_dir = load_state(user_id, save_id)
    standings = state.get("standings") if isinstance(state.get("standings"), dict) else {}
    rows: List[Dict[str, Any]] = []
    for t_dict in state.get("teams") or []:
        if not isinstance(t_dict, dict):
            continue
        name = str(t_dict.get("name") or "").strip()
        if not name:
            continue
        team = team_from_dict(t_dict)
        ratings = calculate_team_ratings(team)
        overall = int(round(team_composite_strength(ratings)))
        st = standings.get(name) if isinstance(standings, dict) else None
        st_dict = st if isinstance(st, dict) else {}
        rows.append({
            "team_name": name,
            "classification": str(t_dict.get("classification") or "").strip() or "—",
            "region": str(t_dict.get("region") or "").strip() or "—",
            "wins": int(st_dict.get("wins", 0) or 0),
            "losses": int(st_dict.get("losses", 0) or 0),
            "overall": overall,
            "offense": int(ratings.get("offense", 50)),
            "defense": int(ratings.get("defense", 50)),
            "run": int(ratings.get("run", 50)),
            "pass": int(ratings.get("pass", 50)),
        })
    rows.sort(key=lambda r: (-int(r.get("overall", 0) or 0), -int(r.get("offense", 0) or 0), str(r.get("team_name") or "")))
    return {"teams": rows}


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
        rows.append({
            "year": year,
            "wins": int(st_row.get("wins", 0) or 0),
            "losses": int(st_row.get("losses", 0) or 0),
            "postseason": _postseason_label_archived(team, s, teams),
            "coach": coach or "—",
            "has_recap": _team_has_season_recap(save_dir, team, s),
        })

    rows = _merge_live_and_snapshot_team_history_rows(state, save_dir, team, rows, teams)
    rows.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    persisted_regional = next(
        (
            int(r.get("regional_championships", 0) or 0)
            for r in (state.get("teams") or [])
            if isinstance(r, dict) and r.get("name") == team
        ),
        0,
    )
    totals = build_team_program_totals_display(team, seasons, persisted_regional)
    return {"team_name": team, "team_names": names, "history": rows, "totals": totals}


def get_coach_history(user_id: str, save_id: str, coach_name: str) -> Dict[str, Any]:
    """Season rows for every team/year this coach appears on in league_history.json."""
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    names = sorted(list(teams.keys()))
    target = norm_coach_key(coach_name)
    if not target:
        return {"coach_name": "", "team_names": names, "history": []}

    hist = load_league_history(league_history_path(save_dir))
    seasons = hist.get("seasons") or []
    rebuild_coach_career_log_from_league_history(state, hist, merge=True)

    season_by_year: Dict[int, Dict[str, Any]] = {}
    for s in seasons:
        if isinstance(s, dict):
            try:
                season_by_year[int(s.get("year", 0) or 0)] = s
            except (TypeError, ValueError):
                continue

    rows: List[Dict[str, Any]] = []
    seen: set[Tuple[int, str]] = set()

    for base in coach_history_rows_from_career_log(coach_name, state.get("coach_career_log")):
        try:
            y = int(base.get("year", 0) or 0)
        except (TypeError, ValueError):
            continue
        team_n = str(base.get("team") or "").strip()
        if not team_n:
            continue
        seen.add((y, team_n))
        season_entry = season_by_year.get(y)
        rows.append(
            {
                "year": y,
                "team": team_n,
                "wins": int(base.get("wins", 0) or 0),
                "losses": int(base.get("losses", 0) or 0),
                "postseason": _postseason_label_archived(team_n, season_entry, teams) if season_entry else "—",
                "coach": str(base.get("coach") or "").strip() or "—",
                "has_recap": _team_has_season_recap(save_dir, team_n, season_entry) if season_entry else False,
            }
        )

    for s in seasons:
        if not isinstance(s, dict):
            continue
        try:
            year = int(s.get("year", 0) or 0)
        except (TypeError, ValueError):
            continue
        standings_list = s.get("standings") or []
        if not isinstance(standings_list, list):
            continue
        for st_row in standings_list:
            if not isinstance(st_row, dict):
                continue
            c = st_row.get("coach")
            if not isinstance(c, str) or norm_coach_key(c) != target:
                continue
            team_n = str(st_row.get("team") or "")
            if not team_n or (year, team_n) in seen:
                continue
            seen.add((year, team_n))
            rows.append(
                {
                    "year": year,
                    "team": team_n,
                    "wins": int(st_row.get("wins", 0) or 0),
                    "losses": int(st_row.get("losses", 0) or 0),
                    "postseason": _postseason_label_archived(team_n, s, teams),
                    "coach": c.strip() or "—",
                    "has_recap": _team_has_season_recap(save_dir, team_n, s),
                }
            )

    rows.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    return {"coach_name": str(coach_name).strip(), "team_names": names, "history": rows}


def get_team_season_recap_text(user_id: str, save_id: str, team_name: str, year: int) -> str:
    """Load the saved recap .txt for the requested team/year (with postseason fallback from history)."""
    _state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in _state.get("teams", [])}
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
        p = _resolve_team_recap_file_path(save_dir, team, s)
        if not p:
            raise ValueError("Recap file not found")
        with open_text_with_path_fallback(os.path.abspath(p), "r") as f:
            text = f.read()
        br = _bracket_results_for_archived_season(s, team, teams)
        return _augment_recap_text_with_postseason(text, team, br)
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
    standings = _rebuild_standings_from_week_results(state, team_names)

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
                entry = _resolved_matchup_gameplan_entry(state)
                coach = getattr(teams[user_team], "coach", None)
                if coach is not None and isinstance(entry, dict) and entry:
                    prev_off = getattr(coach, "game_plan_v2_offense", None)
                    prev_def = getattr(coach, "game_plan_v2_defense", None)
                    prev_4th = getattr(coach, "fourth_down_go_for_it_max_ytg", None)
                    restore_attrs = (prev_off, prev_def, prev_4th)
                    _apply_gameplan_entry_to_coach(coach, entry)
            except Exception:
                restore_attrs = None

        try:
            attach_cpu_coach_packages_for_game(teams[home], teams[away], user_team=user_team)
        except Exception:
            pass

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
    if _coach_sim_emails_enabled():
        generate_week_sim_emails(state, completed_week=current_week)
    state["current_week"] = current_week + 1
    _materialize_carried_gameplan_for_current_week(state)
    if state["current_week"] <= len(weeks):
        _maybe_generate_week_checklist_email(state, week=int(state["current_week"]))
    if state["current_week"] > len(weeks):
        award_regular_season_regional_titles(state)
        _begin_playoffs_phase(state, teams, standings)
    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


# -------------------------
# Stateless (in-memory) simulation for browser-imported bundles
# -------------------------


def sim_week_state(
    state: Dict[str, Any],
    *,
    mp_human_teams: Optional[set[str]] = None,
    mp_submitted_teams: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """In-memory variant of sim_week: mutates and returns state (no disk I/O).

    When mp_human_teams / mp_submitted_teams are set (commissioner advance), human teams
  that did not submit are simmed with CPU autofill gameplans instead of saved prep.
    """
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

    # Stateless bundle: no GET /saves hydrate — seed coach_inbox + starter mail before week logic.
    ensure_coach_inbox(state)

    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    season_stats = init_season_stats(team_names)
    season_player_stats: Dict[int, Any] = {}

    current_week = int(state.get("current_week", 1))
    weeks = state.get("weeks") or []
    week_results = state.get("week_results") or []
    standings = _rebuild_standings_from_week_results(state, team_names)

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

        mp_mode = mp_human_teams is not None and mp_submitted_teams is not None
        human_teams = mp_human_teams or set()
        submitted_teams = mp_submitted_teams or set()
        coach_restores: List[Tuple[str, Tuple[Any, Any, Any]]] = []

        if mp_mode:
            store = state.get("coach_gameplans_v2") if isinstance(state.get("coach_gameplans_v2"), dict) else {}
            gp_key = f"week:{wk_idx + 1}:{gi}:{home} vs {away}"
            entry = store.get(gp_key) if isinstance(store.get(gp_key), dict) else {}
            for team_name in (home, away):
                if team_name not in human_teams or team_name not in submitted_teams:
                    continue
                if team_name not in teams:
                    continue
                coach = getattr(teams[team_name], "coach", None)
                if coach is None or not entry:
                    continue
                prev_off = getattr(coach, "game_plan_v2_offense", None)
                prev_def = getattr(coach, "game_plan_v2_defense", None)
                prev_4th = getattr(coach, "fourth_down_go_for_it_max_ytg", None)
                try:
                    _apply_gameplan_entry_to_coach(coach, entry)
                    coach_restores.append((team_name, (prev_off, prev_def, prev_4th)))
                except Exception:
                    pass
            cpu_teams = {
                t
                for t in (home, away)
                if t not in human_teams or t not in submitted_teams
            }
            try:
                attach_cpu_coach_packages_for_game(
                    teams[home], teams[away], cpu_teams=cpu_teams if cpu_teams else {home, away}
                )
            except Exception:
                pass
        else:
            user_team = state.get("user_team")
            restore_attrs: Optional[Tuple[Any, Any, Any]] = None
            if user_team and user_team in teams and (home == user_team or away == user_team):
                try:
                    entry = _resolved_matchup_gameplan_entry(state)
                    coach = getattr(teams[user_team], "coach", None)
                    if coach is not None and isinstance(entry, dict) and entry:
                        prev_off = getattr(coach, "game_plan_v2_offense", None)
                        prev_def = getattr(coach, "game_plan_v2_defense", None)
                        prev_4th = getattr(coach, "fourth_down_go_for_it_max_ytg", None)
                        restore_attrs = (prev_off, prev_def, prev_4th)
                        _apply_gameplan_entry_to_coach(coach, entry)
                except Exception:
                    restore_attrs = None

            try:
                attach_cpu_coach_packages_for_game(teams[home], teams[away], user_team=user_team)
            except Exception:
                pass

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

        if mp_mode:
            for team_name, (prev_off, prev_def, prev_4th) in coach_restores:
                try:
                    coach = getattr(teams.get(team_name), "coach", None)
                    if coach is not None:
                        coach.game_plan_v2_offense = prev_off
                        coach.game_plan_v2_defense = prev_def
                        coach.fourth_down_go_for_it_max_ytg = prev_4th
                except Exception:
                    pass
        else:
            user_team = state.get("user_team")
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
            "home": home,
            "away": away,
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
    if _coach_sim_emails_enabled():
        generate_week_sim_emails(state, completed_week=current_week)
    state["current_week"] = current_week + 1
    _materialize_carried_gameplan_for_current_week(state)
    entering_playoffs = state["current_week"] > len(weeks)
    if not entering_playoffs:
        _maybe_generate_week_checklist_email(state, week=int(state["current_week"]))
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
    by_class = playoffs.setdefault("by_class", {})
    uc = playoffs.get("user_class")
    user_champ = ""
    cfg = get_state_playoff_system(state)
    default_bracket_size = int(cfg.bracket_size)
    default_min_teams = int(cfg.min_teams)
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict):
            continue
        bracket_size = int(pdata.get("num_teams") or default_bracket_size)
        min_teams = max(default_min_teams, bracket_size)
        names_in_class = _team_names_by_classification(teams).get(cls) or []
        if len(names_in_class) < min_teams:
            continue
        # Seeds were populated by _init_playoffs_multiclass /
        # _ensure_all_eligible_playoff_brackets above (regional or standard).
        # The dispatcher reads them and runs the matching round-runner until
        # the bracket is fully decided.
        _simulate_full_bracket_to_completion(pdata, teams, standings, season_player_stats)
        by_class[cls] = pdata
        if cls == uc:
            user_champ = pdata.get("champion") or ""
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    playoffs["champion"] = user_champ or next((by_class[c].get("champion") for c in by_class if by_class[c].get("champion")), None)
    state["playoffs"] = playoffs
    state["season_phase"] = "playoffs"
    state["standings"] = standings
    state["playoff_season_player_stats"] = season_player_stats
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    _maybe_coach_playoff_round_emails(state)
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
    state_out = _advance_playoff_one_round_state(state)
    _maybe_coach_playoff_round_emails(state_out)
    return state_out


def _apply_preseason_scrimmage_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_names: List[str],
    current_stage: str,
) -> None:
    """Simulate scrimmage when advancing from Scrimmage 1 / Scrimmage 2 (Continue or Simulate)."""
    user_team_name = state.get("user_team")
    opponents_list = state.get("preseason_scrimmage_opponents") or []
    scrim_idx = 0 if current_stage == "Scrimmage 1" else 1
    slot = opponents_list[scrim_idx] if scrim_idx < len(opponents_list) else None

    def _append_result(result: Dict[str, Any]) -> None:
        scrimmages = state.get("preseason_scrimmages") or []
        scrimmages.append(
            {
                "name": current_stage,
                "completed": True,
                "home": result["home"],
                "away": result["away"],
                "home_score": result["home_score"],
                "away_score": result["away_score"],
                "ot": result["ot"],
                "team_stats": result.get("team_stats", {}),
                "player_stats": result.get("player_stats", []),
            }
        )
        state["preseason_scrimmages"] = scrimmages

    def _append_stub() -> None:
        scrimmages = state.get("preseason_scrimmages") or []
        scrimmages.append({"name": current_stage, "completed": True})
        state["preseason_scrimmages"] = scrimmages

    if user_team_name and user_team_name in teams and slot and slot.get("opponent") in teams:
        opponent = slot["opponent"]
        user_home = slot.get("user_home", random.random() < 0.5)
        home_team = teams[user_team_name] if user_home else teams[opponent]
        away_team = teams[opponent] if user_home else teams[user_team_name]
        try:
            _append_result(run_scrimmage_game(home_team, away_team))
        except Exception:
            logger.exception("run_scrimmage_game failed (slotted opponent)")
            _append_stub()
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
                _append_result(run_scrimmage_game(home_team, away_team))
            except Exception:
                logger.exception("run_scrimmage_game failed (fallback opponent)")
                _append_stub()
        else:
            _append_stub()
    else:
        _append_stub()


def _maybe_assign_preseason_scrimmage_opponents_on_advance(
    state: Dict[str, Any],
    team_names: List[str],
    new_idx: int,
    stages: List[str],
) -> None:
    """Assign both scrimmage opponents when entering Position changes / Set Depth Chart / Scrimmage 1."""
    if new_idx >= len(stages) or stages[new_idx] not in ("Position changes", "Set Depth Chart", "Scrimmage 1"):
        return
    if state.get("preseason_scrimmage_opponents"):
        return
    user_team_name = state.get("user_team")
    if not user_team_name:
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


_OFFSEASON_ADVANCE_ACK_KEYS = frozenset(
    {
        "winter_training_ack_results",
        "spring_ball_ack_results",
        "transfer_stage_1_ack_results",
        "transfer_stage_2_ack_results",
        "seven_on_seven_ack_results",
    }
)


def apply_coach_prep_state(state: Dict[str, Any], playbook: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Apply user-team prep for the current league stage without advancing league calendar."""
    playbook = playbook if isinstance(playbook, dict) else {}
    phase_s = str(state.get("season_phase") or "").strip().lower()
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")}
    user_team_name = state.get("user_team")
    team_names = list(teams.keys())

    if phase_s == "preseason":
        state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
        stages = state["preseason_stages"]
        idx = int(state.get("preseason_stage_index", 0))
        if idx >= len(stages):
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            return state
        current_stage = stages[idx]
        if current_stage == "Playbook Select" and playbook:
            _apply_user_preseason_playbook_payload(state, teams, playbook)
            # Multiplayer: keep playbooks editable until the commissioner advances this stage.
            if is_multiplayer_league_state(state) and user_team_name and user_team_name in teams:
                coach = teams[user_team_name].coach
                if coach is not None:
                    coach.last_preferred_playbook_change_year = 0
        game_plan = playbook.get("game_plan") if isinstance(playbook, dict) else None
        if current_stage == "Play Selection":
            if user_team_name and user_team_name in teams:
                ut = teams[user_team_name]
                if game_plan:
                    off_sel = game_plan.get("offensive") or {}
                    def_sel = game_plan.get("defensive") or {}
                    off_stored, def_stored = normalize_game_plan_payload_for_storage(off_sel, def_sel)
                    ut.season_offensive_play_selection = off_stored
                    ut.season_defensive_play_selection = def_stored
            for t in teams.values():
                try:
                    run_play_selection_results_for_team(t)
                except Exception:
                    pass
        elif current_stage == "Position changes":
            _apply_preseason_position_changes_stage(state, teams, playbook)
        elif current_stage == "Set Depth Chart":
            depth_chart = playbook.get("depth_chart") if isinstance(playbook, dict) else None
            if depth_chart and isinstance(depth_chart, dict) and user_team_name and user_team_name in teams:
                ut = teams[user_team_name]
                ut.depth_chart_order = {
                    k: [str(n) for n in v] if isinstance(v, list) else []
                    for k, v in depth_chart.items()
                    if isinstance(k, str) and k.strip()
                }
        elif current_stage == "Set Goals":
            goals = playbook.get("goals") if isinstance(playbook, dict) else None
            if goals and isinstance(goals, dict):
                win_goal = goals.get("win_goal")
                stage_goal = goals.get("stage_goal")
                if win_goal is not None:
                    STAGE_GOALS = [
                        "Just to have fun",
                        "Winning Season",
                        "Playoffs",
                        "Semifinal",
                        "State Championship",
                        "Title Winner",
                    ]
                    win_goal = max(0, min(10, int(win_goal)))
                    stage_goal = str(stage_goal or "Winning Season")
                    if stage_goal not in STAGE_GOALS:
                        stage_goal = "Winning Season"
                    state["season_goals"] = {"win_goal": win_goal, "stage_goal": stage_goal}
        elif current_stage in ("Scrimmage 1", "Scrimmage 2"):
            if playbook.get("scrimmage_simulate"):
                if is_multiplayer_league_state(state):
                    raise ValueError(
                        "Scrimmage is simulated by the commissioner when the league advances."
                    )
                _ensure_scrimmage_opponents(state, team_names, user_team_name)
                _apply_preseason_scrimmage_stage(state, teams, team_names, current_stage)
            elif is_multiplayer_league_state(state) and user_team_name:
                _ensure_mp_team_scrimmage_opponents(state, user_team_name, team_names)
        elif current_stage == "Home Game Themes":
            _apply_home_game_themes_from_playbook(
                state,
                team_names,
                user_team_name,
                playbook if isinstance(playbook, dict) else {},
            )
    elif phase_s == "regular":
        depth_chart = playbook.get("depth_chart") if isinstance(playbook, dict) else None
        if depth_chart and isinstance(depth_chart, dict):
            state = update_depth_chart_in_state(state, depth_chart)
            teams = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")}
    elif phase_s == "offseason":
        body = playbook.get("offseason") if isinstance(playbook.get("offseason"), dict) else playbook
        if not isinstance(body, dict):
            body = {}
        if any(body.get(k) for k in _OFFSEASON_ADVANCE_ACK_KEYS):
            raise ValueError("That step advances the league — wait for your commissioner to sim.")
        idx_before = int(state.get("offseason_stage_index", 0))
        phase_before = str(state.get("season_phase") or "")
        snap = copy.deepcopy(state)
        try:
            advance_offseason_state(state, body, league_history={"seasons": []})
        except ValueError:
            raise
        except Exception as exc:
            state.clear()
            state.update(snap)
            raise ValueError(str(exc)) from exc
        idx_after = int(state.get("offseason_stage_index", 0))
        phase_after = str(state.get("season_phase") or "")
        if idx_after != idx_before or phase_after != phase_before:
            state.clear()
            state.update(snap)
            raise ValueError("That action would advance the league — only the commissioner can do that.")
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        return state
    elif phase_s in ("season_summary", "schedule_planning"):
        if playbook.get("cross_region_picks") is not None:
            raise ValueError("Out-of-region schedules are set by the commissioner during season summary.")

    state["teams"] = [team_to_dict(t) for t in teams.values()]
    return state


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
        _maybe_generate_week_checklist_email(state)
        return {"state": state, "phase_completed": None}

    phase_norm = str(state.get("season_phase") or "preseason").strip().lower()
    if phase_norm in ("playoffs", "offseason", "done", "season_summary"):
        return {"state": state, "phase_completed": None}
    if phase_norm != "preseason":
        if had_preseason_meta:
            state["season_phase"] = "preseason"
        else:
            return {"state": state, "phase_completed": None}

    current_stage = stages[idx]
    team_names = list(teams.keys())
    user_team_name = state.get("user_team")
    if current_stage in ("Scrimmage 1", "Scrimmage 2"):
        _ensure_scrimmage_opponents(state, team_names, user_team_name)

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
                off_stored, def_stored = normalize_game_plan_payload_for_storage(off_sel, def_sel)
                ut.season_offensive_play_selection = off_stored
                ut.season_defensive_play_selection = def_stored
            else:
                raise ValueError("Configure your game plan before continuing.")

    if current_stage == "Play Selection Results":
        for t in teams.values():
            if not getattr(t, "season_offensive_play_selection", None):
                try:
                    run_play_selection_for_team(t)
                except Exception:
                    pass
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
        STAGE_GOALS = [
            "Just to have fun",
            "Winning Season",
            "Playoffs",
            "Semifinal",
            "State Championship",
            "Title Winner",
        ]
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
    elif current_stage in ("Scrimmage 1", "Scrimmage 2"):
        if is_multiplayer_league_state(state) and not user_team_name:
            pass
        else:
            _apply_preseason_scrimmage_stage(state, teams, team_names, current_stage)
    elif current_stage == "Home Game Themes":
        _apply_home_game_themes_from_playbook(
            state,
            team_names,
            user_team_name,
            playbook if isinstance(playbook, dict) else {},
        )
        mp = is_multiplayer_league_state(state)
        commish_advance = mp and not user_team_name
        if commish_advance:
            finalize_multiplayer_home_game_themes(state, team_names)
        if not commish_advance and not bool((playbook or {}).get("home_game_themes_ack")):
            if mp:
                ut = str(user_team_name or "").strip()
                confirmed = state.get("home_game_themes_confirmed_teams") or {}
                if not (isinstance(confirmed, dict) and confirmed.get(ut)):
                    state["teams"] = [team_to_dict(t) for t in teams.values()]
                    return {"state": state, "phase_completed": None}
            else:
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                return {"state": state, "phase_completed": None}
    # --- End: core stage effects ---

    state["teams"] = [team_to_dict(t) for t in teams.values()]
    state["preseason_stage_index"] = idx + 1
    if state["preseason_stage_index"] >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = max(1, int(state.get("current_week", 1)))
        _maybe_generate_week_checklist_email(state)

    new_idx = state["preseason_stage_index"]
    _maybe_assign_preseason_scrimmage_opponents_on_advance(state, team_names, new_idx, stages)

    return {"state": state, "phase_completed": current_stage}


def advance_offseason_state(
    state: Dict[str, Any],
    body: Optional[Dict[str, Any]] = None,
    league_history: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """In-memory variant of advance_offseason. Pass league_history for coaching carousel (stateless bundle)."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "offseason":
        raise ValueError("save is not in offseason")
    if _repair_missing_cross_region_schedule_planning(state):
        teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        _sync_cross_region_schedule_ui_fields(state)
        return state
    body = body or {}
    normalize_offseason_stages(state)
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
            _archive_winter_training_session(state)
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
            _archive_spring_ball_session(state)
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
        if ut:
            _ensure_improvements_bank_equipment_pp(state, ut)
        bank = state.get("offseason_improvements_bank")
        if not isinstance(bank, dict):
            bank = {"pp_total": 0, "pp_remaining": 0, "breakdown": None, "applied": {}}
        if ut:
            _apply_user_team_program_improvements(ut, bank, body)
        state["offseason_improvements_bank"] = bank
    elif current in ("Coaching carousel I", "Coaching carousel II", "Coaching carousel III"):
        lh = league_history if isinstance(league_history, dict) else {"seasons": []}
        _apply_coaching_carousel_stage(state, teams, lh, current, body)
    elif current == "Coaching carousel IV":
        pass
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
                _apply_coach_dev_stage_for_team(ut.coach, b, body=body, is_user=True)
            elif name != user_team_name:
                _apply_coach_dev_stage_for_team(coach, b, is_user=False)
        if user_team_name:
            ub = banks_cd.get(user_team_name)
            if isinstance(ub, dict):
                state["offseason_coach_dev_bank"] = ub
        state["offseason_coach_dev_banks"] = banks_cd
    elif current == "Program Development":
        _apply_program_development_stage(state, teams, body)
    elif current == "Transfers I":
        pending = bool(state.get("offseason_transfer_stage_1_pending_review"))
        ack = bool(body.get("transfer_stage_1_ack_results"))
        st_xfer = _standings_for_transfer_portal(state)
        stage1_existing = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else None

        if pending:
            if not ack:
                raise ValueError("Review the transfer portal entrants, then press Continue again to lock and advance.")
            state.pop("offseason_transfer_stage_1_pending_review", None)
        elif isinstance(stage1_existing, dict) and stage1_existing.get("entries") is not None:
            pass
        else:
            if _transfers_disabled(state):
                state["offseason_transfer_stage_1"] = _disabled_transfer_stage_1_payload()
            else:
                tph, tbr = _transfer_playoff_snapshot(state)
                sg_tr = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
                payload = run_transfer_stage_1(
                    teams,
                    st_xfer,
                    current_year=max(1, int(state.get("current_year", 1))),
                    season_goals=sg_tr,
                    user_team=str(state.get("user_team") or "") or None,
                    bracket_results=tbr,
                    champion=tph,
                )
                state["offseason_transfer_stage_1"] = payload
                _transfer_stage_1_apply_news(state, payload)
                state["offseason_transfer_stage_1_pending_review"] = True
                state["offseason_stage_index"] = idx
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                return state
    elif current == "Transfers II":
        pending = bool(state.get("offseason_transfer_stage_2_pending_review"))
        ack = bool(body.get("transfer_stage_2_ack_results"))
        st_xfer = _standings_for_transfer_portal(state)
        stage2_existing = state.get("offseason_transfer_stage_2") if isinstance(state.get("offseason_transfer_stage_2"), dict) else None

        if pending:
            if not ack:
                raise ValueError("Review transfer commitments, then press Continue again to advance.")
            state.pop("offseason_transfer_stage_2_pending_review", None)
        elif isinstance(stage2_existing, dict) and (
            stage2_existing.get("entries") is not None or stage2_existing.get("moved_count") is not None
        ):
            pass
        else:
            if _transfers_disabled(state):
                _apply_disabled_transfer_stage_2(state)
            else:
                stage1 = state.get("offseason_transfer_stage_1") if isinstance(state.get("offseason_transfer_stage_1"), dict) else {}
                payload = run_transfer_stage_2(
                    teams,
                    st_xfer,
                    stage1,
                    current_year=max(1, int(state.get("current_year", 1))),
                )
                _transfer_stage_2_apply_news_and_review(state, payload)
                state["offseason_transfer_stage_2_pending_review"] = True
                state["offseason_stage_index"] = idx
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                return state
    elif current == "7 on 7":
        mp_7on7 = _advance_multiplayer_seven_on_seven_stage(state, teams, body, idx=idx)
        if mp_7on7 == "wait_review":
            return state
        if mp_7on7 == "single_player":
            seven_results = state.get("offseason_7on7_results")
            ack = bool(body.get("seven_on_seven_ack_results"))
            tier_raw = body.get("seven_on_seven_tournament")
            if isinstance(seven_results, dict) and ack:
                state.pop("offseason_7on7_results", None)
            elif isinstance(seven_results, dict) and not ack:
                raise ValueError("Review 7-on-7 tournament results, then press Continue again to advance.")
            else:
                tier = str(tier_raw or "").strip().lower()
                if tier not in VALID_TOURNAMENT_TIERS:
                    raise ValueError("Choose a 7-on-7 tournament (Area, Regional, or State), then press Continue.")
                payload = run_seven_on_seven_tournament(teams, str(user_team_name or ""), tier)
                state["offseason_7on7_results"] = payload
                state["offseason_stage_index"] = idx
                state["teams"] = [team_to_dict(t) for t in teams.values()]
                return state
    elif current in ("Transfers III", "Graduation", "Freshman Class", "Schedule Release"):
        pass
    elif current == "Training Results":
        before_rows: List[Dict[str, Any]] = []
        if ut:
            for p in list(ut.roster):
                before_rows.append({"name": p.name, "position": p.position, "before": calculate_player_overall(p)})
        user_equipment_training: Optional[Dict[str, Any]] = None
        from systems.coaching_cards import platinum_breakthrough_eligible_player_names

        eligible_before = platinum_breakthrough_eligible_player_names(ut) if ut else []
        for t in teams.values():
            dev_summary = run_offseason_development(t)
            if ut and t.name == ut.name:
                user_equipment_training = dev_summary
        deltas: List[Dict[str, Any]] = []
        if ut:
            deltas = _training_player_rows_from_development(
                ut,
                before_rows,
                (user_equipment_training or {}).get("player_reports") if isinstance(user_equipment_training, dict) else None,
            )
            _attach_platinum_breakthrough_training_metadata(deltas, user_equipment_training, eligible_before)
        training_payload: Dict[str, Any] = {"players": deltas, "breakthrough_eligible": eligible_before}
        if user_equipment_training:
            from systems.program_equipment_effects import summarize_equipment_for_training_ui

            training_payload["equipment"] = {
                "by_item": user_equipment_training.get("by_item") or [],
                "item_count": int(user_equipment_training.get("item_count") or 0),
                "equipment_points_applied": int(user_equipment_training.get("equipment_points_applied") or 0),
                "ui_rows": summarize_equipment_for_training_ui(user_equipment_training),
            }
        state["offseason_training_results"] = training_payload

    if current == "Improvements":
        lh = league_history if isinstance(league_history, dict) else {"seasons": []}
        _apply_coaching_carousel_churn(state, teams, lh)

    state["offseason_stage_index"] = idx + 1
    new_idx = int(state["offseason_stage_index"])
    if new_idx < len(stages) and _normalize_offseason_stage_name(stages[new_idx]) == "Program Development":
        _ensure_program_development_inventory_aged(state, teams)
    if new_idx < len(stages) and _normalize_offseason_stage_name(stages[new_idx]) == "Improvements":
        _ensure_improvements_bank_equipment_pp(state, ut)
    if current == "Spring Ball":
        state.pop("offseason_spring_ball_results", None)
    if current == "7 on 7":
        state.pop("offseason_7on7_results", None)
    if current in ("Winter 1", "Winter 2"):
        state.pop("offseason_winter_training_results", None)
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    new_idx = int(state["offseason_stage_index"])
    if new_idx >= len(stages):
        check_trial_before_year2_preseason(user_id)
        teams2 = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
        _finalize_offseason_to_preseason(state, teams2)
        state["teams"] = [team_to_dict(t) for t in teams2.values()]
    return state


def finish_season_state(
    state: Dict[str, Any],
    league_history: Dict[str, Any],
    records: Dict[str, Any],
    *,
    bulk_autopilot: bool = False,
    begin_offseason: bool = False,
    cross_region_picks: Optional[Any] = None,
) -> Dict[str, Any]:
    """Stateless finish_season: returns updated state + updated league_history/records + recap texts."""
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    output_lines: List[str] = []
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
    phase_s = str(state.get("season_phase") or "").strip().lower()

    if phase_s == "schedule_planning":
        _apply_schedule_planning_picks_and_enter_offseason(
            state, teams, cross_region_picks, league_history=league_history
        )
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        _finalize_cross_region_schedule_state(state)
        return {
            "state": state,
            "league_history": league_history,
            "records": records,
            "season_recaps": {},
        }

    if phase_s == "season_summary":
        playoffs_ss = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        champion_ss = str(playoffs_ss.get("champion") or "")
        if begin_offseason or bulk_autopilot:
            br_flat_ss = _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs_ss))
            year_num_ss = int(state.get("current_year", 1))
            _apply_season_summary_offseason_begin(
                state,
                teams,
                team_names,
                standings,
                champion_ss,
                br_flat_ss,
                year_num_ss,
                league_history,
                bulk_autopilot=bulk_autopilot,
                cross_region_picks=cross_region_picks,
            )
        else:
            _sync_cross_region_schedule_ui_fields(state)
        _finalize_cross_region_schedule_state(state)
        return {
            "state": state,
            "champion": champion_ss,
            "league_history": league_history,
            "records": records,
            "season_recaps": {},
        }

    run_playoff_stats: Dict[int, Any] = {}

    if playoffs and playoffs.get("completed"):
        _sync_playoff_top_level_champion_runner(playoffs)
    if playoffs and playoffs.get("completed") and str(playoffs.get("champion") or "").strip():
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = list(playoffs.get("bracket_results") or [])
    elif phase_s == "playoffs":
        while True:
            p = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
            if p and p.get("completed"):
                _sync_playoff_top_level_champion_runner(p)
            if p and p.get("completed") and str(p.get("champion") or "").strip():
                champion = str(p.get("champion") or "")
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            if p and p.get("completed"):
                champion = ""
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            state = _advance_playoff_one_round_state(state)
    else:
        # Fallback: finish_season called from outside the playoffs phase.
        # Build the bracket(s) from scratch using the active playoff system
        # config (which may be regional) and run each to completion. Yields
        # a champion + runner_up for the user's classification.
        _ensure_playoffs_migrated(state, teams)
        if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
            state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
        _ensure_all_eligible_playoff_brackets(state, teams, standings)
        playoffs = state["playoffs"]
        by_class = playoffs.setdefault("by_class", {})
        for cls, pdata in list(by_class.items()):
            if not isinstance(pdata, dict) or pdata.get("completed"):
                continue
            _simulate_full_bracket_to_completion(pdata, teams, standings, run_playoff_stats)
            by_class[cls] = pdata
        playoffs["completed"] = _playoffs_global_completed(playoffs)
        uc = playoffs.get("user_class")
        if uc and uc in by_class:
            playoffs["champion"] = by_class[uc].get("champion")
            playoffs["runner_up"] = by_class[uc].get("runner_up")
        _sync_playoff_top_level_champion_runner(playoffs)
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = _flatten_playoff_bracket_results(playoffs)

    standings = state.get("standings") or standings
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())

    if phase_s == "playoffs" or (
        playoffs and playoffs.get("completed") and str(playoffs.get("champion") or "").strip()
    ):
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
        postseason = _recap_postseason_line_label_for_team(
            team_name,
            state=state,
            season_entry_top_champion=champion,
            season_entry_top_runner_up=runner_up,
            br_flat=br_for_history,
            teams_map=teams,
        )
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

    regional_champions = compute_regular_season_regional_champions(state)
    p_bc_snap_fs = _playoffs_by_class_snapshot(state)
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
        regional_champions=regional_champions,
        playoffs_by_class=p_bc_snap_fs,
    )
    league_history = out_hist.get("league_history") or league_history
    records = out_hist.get("records") or records
    append_season_to_coach_career_log(
        state,
        year=year_num,
        team_coaches=team_coaches,
        standings=standings,
    )
    update_prestige(teams, league_history)
    if int(state.get("program_funding_awarded_year") or 0) != int(year_num):
        _award_program_funding_for_all_teams(teams, standings, current_year=int(year_num))
        state["program_funding_awarded_year"] = int(year_num)

    from systems.home_game_themes import compute_league_home_theme_summaries

    state["home_theme_season_rewards"] = compute_league_home_theme_summaries(state, team_names)

    if not bulk_autopilot:
        _set_season_summary_phase(state)
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        if begin_offseason:
            _apply_season_summary_offseason_begin(
                state,
                teams,
                team_names,
                standings,
                champion,
                br_for_history,
                year_num,
                league_history,
                bulk_autopilot=False,
                cross_region_picks=cross_region_picks,
            )
        _finalize_cross_region_schedule_state(state)
        return {
            "state": state,
            "champion": champion,
            "league_history": league_history,
            "records": records,
            "season_recaps": season_recaps,
        }

    _apply_season_summary_offseason_begin(
        state,
        teams,
        team_names,
        standings,
        champion,
        br_for_history,
        year_num,
        league_history,
        bulk_autopilot=True,
    )
    _finalize_cross_region_schedule_state(state)

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
        _maybe_generate_week_checklist_email(state)
        save_state(user_id, save_id, state, save_dir)
        return {"state": state, "phase_completed": None}

    phase_norm = str(state.get("season_phase") or "preseason").strip().lower()
    if phase_norm in ("playoffs", "offseason", "done", "season_summary"):
        return {"state": state, "phase_completed": None}

    if phase_norm != "preseason":
        if had_preseason_meta:
            state["season_phase"] = "preseason"
        else:
            return {"state": state, "phase_completed": None}

    current_stage = stages[idx]
    user_team_name = state.get("user_team")
    if current_stage in ("Scrimmage 1", "Scrimmage 2"):
        _ensure_scrimmage_opponents(state, team_names, user_team_name)

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
                # Convert to team format: { "INSIDE_RUN": [(play_id, pct), ...], ... } — active plays only.
                off_stored, def_stored = normalize_game_plan_payload_for_storage(off_sel, def_sel)
                ut.season_offensive_play_selection = off_stored
                ut.season_defensive_play_selection = def_stored
                state["teams"] = [team_to_dict(t) for t in teams.values()]
            else:
                raise ValueError("Configure your game plan before continuing.")

    # Execute other preseason stage effects (skip Play Selection - handled above).
    if current_stage == "Play Selection":
        pass  # Game plan required above
    elif current_stage == "Play Selection Results":
        for t in teams.values():
            if not getattr(t, "season_offensive_play_selection", None):
                try:
                    run_play_selection_for_team(t)
                except Exception:
                    pass
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
        STAGE_GOALS = [
            "Just to have fun",
            "Winning Season",
            "Playoffs",
            "Semifinal",
            "State Championship",
            "Title Winner",
        ]
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
        _apply_preseason_scrimmage_stage(state, teams, team_names, current_stage)
    elif current_stage == "Home Game Themes":
        _apply_home_game_themes_from_playbook(
            state,
            team_names,
            user_team_name,
            playbook if isinstance(playbook, dict) else {},
        )
        if not bool((playbook or {}).get("home_game_themes_ack")):
            state["teams"] = [team_to_dict(t) for t in teams.values()]
            save_state(user_id, save_id, state, save_dir)
            return {"state": state, "phase_completed": None}

    state["preseason_stage_index"] = idx + 1
    if state["preseason_stage_index"] >= len(stages):
        state["season_phase"] = "regular"
        state["current_week"] = 1
        _maybe_generate_week_checklist_email(state)

    new_idx = state["preseason_stage_index"]
    _maybe_assign_preseason_scrimmage_opponents_on_advance(state, team_names, new_idx, stages)

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


def _ranking_key_for_state(state: Dict[str, Any], standings: Dict[str, Dict[str, Any]], name: str) -> Tuple[int, int]:
    """(-wins, -point_diff) for ranking a team. Mirrors playoff_system._ranking_key."""
    s = standings.get(name, {})
    return (
        -int(s.get("wins", 0)),
        -(int(s.get("points_for", 0)) - int(s.get("points_against", 0))),
    )


def _resolve_regional_user_matchup(
    sub: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    user_team: str,
) -> Optional[Tuple[str, str]]:
    """Find the user's next regional-bracket game (home, away) in slot order.

    Walks the regional bracket the same way the runner does, for any
    supported region size:
      * In-region rounds (1..N depending on ``teams_per_region``) use
        adjacent-pair pairings on the slot list.
      * State semifinal re-seeds the regional champions by overall record
        (highest vs lowest, middle vs middle).
      * Championship pairs the two state SF winners.
    """
    seeds = sorted(sub.get("seeds") or [], key=lambda x: int(x.get("seed", 0)))
    if not seeds:
        return None
    bracket_size = int(sub.get("num_teams") or len(seeds))
    if bracket_size != len(seeds):
        return None
    teams_per_region = _teams_per_region_from_seeds(seeds)
    if teams_per_region < 2 or (teams_per_region & (teams_per_region - 1)):
        return None
    names = [str(s["team"]) for s in seeds]
    results = list(sub.get("bracket_results") or [])

    # If the user team has lost any game, there's no next game for them.
    for g in results:
        if g.get("home") == user_team or g.get("away") == user_team:
            if g.get("winner") and g.get("winner") != user_team:
                return None

    # ---- In-region rounds: adjacent-pair walking on the slot list ----
    in_region_rounds = regional_in_region_round_names(teams_per_region)
    current_slots: List[str] = list(names)
    for round_name in in_region_rounds:
        pairs = [(i, i + 1) for i in range(0, len(current_slots), 2)]
        round_done = [r for r in results if r.get("round") == round_name]
        if len(round_done) < len(pairs):
            for hi, ai in pairs:
                hn, an = current_slots[hi], current_slots[ai]
                if user_team not in (hn, an):
                    continue
                played = any(
                    _playoff_row_same_teams(r.get("home"), r.get("away"), hn, an) for r in round_done
                )
                if not played:
                    return (hn, an)
            return None
        winners_this_round: List[str] = []
        for hi, ai in pairs:
            hn, an = current_slots[hi], current_slots[ai]
            found = next(
                (r for r in round_done
                 if _playoff_row_same_teams(r.get("home"), r.get("away"), hn, an)),
                None,
            )
            if not found or not found.get("winner"):
                return None
            winners_this_round.append(str(found["winner"]))
        current_slots = winners_this_round

    regional_champs = current_slots

    # ---- State SF: re-seed regional champions by overall record ----
    state_ranked = sorted(regional_champs, key=lambda n: _ranking_key_for_state(None, standings, n))  # type: ignore[arg-type]
    sf_pairs = _regional_state_sf_pairings(len(state_ranked))
    sf_done = [r for r in results if r.get("round") == "Semifinal"]
    if len(sf_done) < len(sf_pairs):
        for hi, ai in sf_pairs:
            hn, an = state_ranked[hi], state_ranked[ai]
            if user_team not in (hn, an):
                continue
            played = any(_playoff_row_same_teams(r.get("home"), r.get("away"), hn, an) for r in sf_done)
            if not played:
                return (hn, an)
        return None
    sf_winners: List[str] = []
    for hi, ai in sf_pairs:
        hn, an = state_ranked[hi], state_ranked[ai]
        found = next((r for r in sf_done if _playoff_row_same_teams(r.get("home"), r.get("away"), hn, an)), None)
        if not found or not found.get("winner"):
            return None
        sf_winners.append(str(found["winner"]))

    # ---- Championship ----
    ch_done = [r for r in results if r.get("round") == "Championship"]
    if not ch_done and len(sf_winners) >= 2:
        wh, wa = sf_winners[0], sf_winners[1]
        if user_team in (wh, wa):
            return (wh, wa)
    return None


def resolve_playoff_coach_matchup(state: Dict[str, Any], user_team: str) -> Optional[Tuple[str, str]]:
    """Next playoff game for the user team as (home, away) in engine order, or None if none.

    Works for both standard fixed brackets (any power-of-two size) and the
    regional bracket (4 regions x top 4). For standard brackets the function
    walks rounds in order, building each round's slot list from the prior
    round's recorded winners. For regional brackets it dispatches to a
    dedicated walker that knows about the in-region pairings and the
    re-seeding step at the state-semifinal stage.
    """
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    p = _ensure_playoffs_migrated(state, teams) if isinstance(state.get("playoffs"), dict) else None
    if not p or not user_team or _playoffs_global_completed(p):
        return None
    uc = p.get("user_class") or _classification_of_team(teams, user_team)
    sub = (p.get("by_class") or {}).get(uc) if isinstance(p.get("by_class"), dict) else None
    if not isinstance(sub, dict) or sub.get("completed"):
        return None

    if _bracket_is_regional(sub):
        standings = state.get("standings") or {}
        return _resolve_regional_user_matchup(sub, standings, user_team)

    seeds = sorted(sub.get("seeds") or [], key=lambda x: int(x.get("seed", 0)))
    names = [str(s["team"]) for s in seeds]
    results = list(sub.get("bracket_results") or [])
    bracket_size = int(sub.get("num_teams") or len(names) or get_state_playoff_system(state).bracket_size)
    if bracket_size <= 0 or len(names) != bracket_size:
        return None

    # Once the user team has lost a game in this bracket, there's nothing next.
    for g in results:
        if g.get("home") == user_team or g.get("away") == user_team:
            if g.get("winner") and g.get("winner") != user_team:
                return None

    round_names = round_names_for_bracket(bracket_size)
    current_slots = list(names)
    for round_name in round_names:
        pairings = round_pairings_for_size(len(current_slots))
        round_results = [r for r in results if r.get("round") == round_name]
        if len(round_results) < len(pairings):
            for hi, ai in pairings:
                hn, an = current_slots[hi], current_slots[ai]
                if user_team not in (hn, an):
                    continue
                played = any(_playoff_row_same_teams(r.get("home"), r.get("away"), hn, an) for r in round_results)
                if not played:
                    return (hn, an)
            return None
        # Round is fully recorded — collect winners in slot order to feed the next round.
        winners: List[str] = []
        for hi, ai in pairings:
            hn, an = current_slots[hi], current_slots[ai]
            found = next(
                (r for r in round_results if _playoff_row_same_teams(r.get("home"), r.get("away"), hn, an)),
                None,
            )
            if not found or not found.get("winner"):
                return None
            winners.append(str(found["winner"]))
        current_slots = winners

    return None


def start_coach_game(
    user_id: str,
    save_id: str,
    context: str,
    scrimmage_index: Optional[int] = 0,
) -> Dict[str, Any]:
    """Start a coach-playable game. Returns game_id and matchup info."""
    state, save_dir = load_state(user_id, save_id)
    if context == "scrimmage" and is_multiplayer_league_state(state):
        raise ValueError("Scrimmage is simulated by the commissioner when the league advances.")
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
    if context == "scrimmage" and is_multiplayer_league_state(state):
        raise ValueError("Scrimmage is simulated by the commissioner when the league advances.")
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
        "home": home_name,
        "away": away_name,
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

    team_names = [t.get("name") for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
    state["standings"] = _rebuild_standings_from_week_results(state, team_names)

    state["week_results"] = week_results
    ensure_coach_inbox(state)
    if _coach_sim_emails_enabled():
        generate_coach_game_touch_emails(state, home=home_name, away=away_name, hs=hs, as_=as_)
        _maybe_generate_week_sim_emails_if_complete(state, completed_week=current_week)
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
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    playoffs = _ensure_playoffs_migrated(state, teams)
    uc = playoffs.get("user_class") or _classification_of_team(teams, state.get("user_team"))
    cfg = get_state_playoff_system(state)
    sub = playoffs.setdefault("by_class", {}).setdefault(
        uc,
        {
            "num_teams": int(cfg.bracket_size),
            "seeds": [],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        },
    )
    bracket_size = int(sub.get("num_teams") or cfg.bracket_size)
    bracket_results = list(sub.get("bracket_results") or [])
    # Round name (Regional SF / Regional Final / R16 / QF / SF / Championship)
    # is derived from how many games are already recorded for the active
    # bracket. Regional brackets and standard brackets use different round
    # name sequences so we dispatch on the bracket's seed shape.
    if _bracket_is_regional(sub):
        round_name = next_regional_round_name(
            bracket_results, sub.get("seeds") or []
        )
    else:
        round_name = next_playoff_round_name(bracket_results, bracket_size)

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
    if playoffs.get("completed"):
        _sync_playoff_top_level_champion_runner(playoffs)
    _maybe_coach_playoff_round_emails(state)
    return state


def finish_coach_scrimmage_state(state: Dict[str, Any], game: Any, scrimmage_stage: str) -> Dict[str, Any]:
    """Stateless finish_coach_scrimmage: stores result into preseason_scrimmages and advances preseason one step."""
    from backend.services.game_service import game_state_dict

    gs = game_state_dict(game)
    home_name = gs["home_team_name"]
    away_name = gs["away_team_name"]
    teams_dict = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict)}
    home_team_o = teams_dict.get(home_name)
    away_team_o = teams_dict.get(away_name)
    _, player_stats_list = build_coach_postgame_box_assets(game, home_team_o, away_team_o, home_name, away_name)

    scrimmages = list(state.get("preseason_scrimmages") or [])
    scrimmages.append(
        {
            "name": scrimmage_stage,
            "completed": True,
            "home": home_name,
            "away": away_name,
            "home_score": int(gs.get("score_home", 0)),
            "away_score": int(gs.get("score_away", 0)),
            "ot": bool(gs.get("ot_winner")),
            "team_stats": gs.get("team_stats", {}),
            "player_stats": player_stats_list,
        }
    )
    state["preseason_scrimmages"] = scrimmages

    stages = state.get("preseason_stages") or list(PRESEASON_STAGES)
    idx = int(state.get("preseason_stage_index", 0))
    if idx < len(stages) and stages[idx] == scrimmage_stage:
        state["preseason_stage_index"] = idx + 1
        if state["preseason_stage_index"] >= len(stages):
            state["season_phase"] = "regular"
            state["current_week"] = 1
            _maybe_generate_week_checklist_email(state)
    team_names = [t.get("name") for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
    _maybe_assign_preseason_scrimmage_opponents_on_advance(
        state, team_names, int(state.get("preseason_stage_index", 0)), stages
    )
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
        "home": home_name,
        "away": away_name,
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

    team_names = [t.get("name") for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")]
    state["standings"] = _rebuild_standings_from_week_results(state, team_names)

    state["week_results"] = week_results

    ensure_coach_inbox(state)
    if _coach_sim_emails_enabled():
        generate_coach_game_touch_emails(state, home=home_name, away=away_name, hs=hs, as_=as_)
        _maybe_generate_week_sim_emails_if_complete(state, completed_week=current_week)
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
    cfg = get_state_playoff_system(state)
    sub = playoffs.setdefault("by_class", {}).setdefault(
        uc,
        {
            "num_teams": int(cfg.bracket_size),
            "seeds": [],
            "bracket_results": [],
            "completed": False,
            "champion": None,
            "runner_up": None,
        },
    )
    bracket_size = int(sub.get("num_teams") or cfg.bracket_size)
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

    # Round name is derived from the games already recorded against the
    # active bracket size. Regional brackets use a different round-name
    # sequence (Regional SF / Regional Final / SF / Championship) so we
    # dispatch on the bracket's seed shape.
    if _bracket_is_regional(sub):
        round_name = next_regional_round_name(
            bracket_results, sub.get("seeds") or []
        )
    else:
        round_name = next_playoff_round_name(bracket_results, bracket_size)

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
    if playoffs.get("completed"):
        _sync_playoff_top_level_champion_runner(playoffs)

    state["standings"] = standings
    _maybe_coach_playoff_round_emails(state)
    save_state(user_id, save_id, state, save_dir)
    # Mirror sim_playoff_round / sim_playoffs: archive season and land in season_summary so the hub
    # shows the year-end summary before "Begin offseason" (graduation, etc.).
    if playoffs.get("completed"):
        return finish_season(user_id, save_id)
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
            _maybe_generate_week_checklist_email(state)

    save_state(user_id, save_id, state, save_dir)
    return {"state": state}


def _bracket_is_regional(pdata: Dict[str, Any]) -> bool:
    """True if this bracket was seeded with regional metadata (the
    ``seeds[*]['region']`` key only appears on regional brackets).

    Detected from the bracket data itself rather than the active config so a
    save that switched its ``playoff_system`` mid-bracket would still finish
    the in-flight bracket using the runner it was started with.
    """
    seeds = pdata.get("seeds") if isinstance(pdata, dict) else None
    if not isinstance(seeds, list) or not seeds:
        return False
    first = seeds[0]
    return isinstance(first, dict) and bool(first.get("region"))


def _advance_one_bracket(
    pdata: Dict[str, Any],
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]],
) -> None:
    """Advance one classification bracket by exactly one round, in-place.

    Dispatches to the regional or standard fixed-bracket round runner based on
    the bracket's seed shape so callers don't need to special-case the
    playoff system. Updates ``pdata`` keys: ``bracket_results``, ``completed``,
    ``champion``, ``runner_up``.
    """
    bracket_results = list(pdata.get("bracket_results") or [])
    seeds_raw = pdata.get("seeds") or []
    bracket_size = int(pdata.get("num_teams") or len(seeds_raw))

    if _bracket_is_regional(pdata):
        # Regional runner consumes the seed dicts directly so it can read
        # the per-team region info even after a reload.
        seeded_sorted = sorted(seeds_raw, key=lambda x: int(x.get("seed", 0)))
        if len(seeded_sorted) != bracket_size:
            return
        champion, done = run_next_playoff_round_regional(
            teams, standings, seeded_sorted, bracket_results, season_player_stats, None
        )
    else:
        seeded_sorted = sorted(seeds_raw, key=lambda x: int(x.get("seed", 0)))
        seeded_names = [str(x["team"]) for x in seeded_sorted]
        if len(seeded_names) != bracket_size:
            return
        champion, done = run_next_playoff_round(
            teams, standings, seeded_names, bracket_results, season_player_stats, None
        )

    runner_up = ""
    if done and bracket_results:
        cg = bracket_results[-1]
        runner_up = cg["away"] if cg["winner"] == cg["home"] else cg["home"]
    pdata["num_teams"] = bracket_size
    pdata["bracket_results"] = bracket_results
    pdata["completed"] = done
    pdata["champion"] = champion if done else None
    pdata["runner_up"] = runner_up if done else None


def _simulate_full_bracket_to_completion(
    pdata: Dict[str, Any],
    teams: Dict[str, Any],
    standings: Dict[str, Dict[str, Any]],
    season_player_stats: Optional[Dict[int, Any]],
) -> None:
    """Advance one bracket round-by-round until a champion is crowned.

    Used by the all-at-once postseason sims (``sim_playoffs_state``,
    ``finish_season`` when called outside the playoffs phase).  log2(bracket_size)
    rounds is the upper bound; safety bound prevents an infinite loop if a
    runner ever returns ``done=False`` without recording new games.
    """
    bracket_size = int(pdata.get("num_teams") or len(pdata.get("seeds") or []) or 0)
    if bracket_size < 2:
        return
    safety = bracket_size  # generous: log2(bracket_size) rounds is the real bound
    while not pdata.get("completed") and safety > 0:
        safety -= 1
        before = len(pdata.get("bracket_results") or [])
        _advance_one_bracket(pdata, teams, standings, season_player_stats)
        after = len(pdata.get("bracket_results") or [])
        if after <= before:
            # Defensive: if the runner reported "not done" but added no games
            # we're stuck — bail rather than loop forever.
            break


def _advance_playoff_one_round_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate the next playoff round in-place for every classification bracket.

    Used by ``sim_playoff_round`` and ``finish_season``. Bracket shape (size,
    seeding mode, completion check) comes from the bracket's stored seeds /
    the active playoff system config, so 8-team / 16-team / regional systems
    all flow through one path.
    """
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
    cfg = get_state_playoff_system(state)
    default_bracket_size = int(cfg.bracket_size)
    default_min_teams = int(cfg.min_teams)
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict) or pdata.get("completed"):
            continue
        # Per-bracket size: prefer what was stored at init time (so an in-flight
        # bracket keeps its shape) and fall back to the active system config.
        bracket_size = int(pdata.get("num_teams") or default_bracket_size)
        min_teams = max(default_min_teams, bracket_size)
        seeds_raw = pdata.get("seeds") or []
        if not seeds_raw:
            names_in_class = _team_names_by_classification(teams).get(cls) or []
            if len(names_in_class) < min_teams:
                continue
            seeded = seed_teams(names_in_class, standings, top_n=bracket_size)
            seeds_raw = [{"seed": int(seed), "team": str(name)} for (seed, name) in seeded]
            pdata["seeds"] = seeds_raw
        if len(seeds_raw) != bracket_size:
            continue
        _advance_one_bracket(pdata, teams, standings, sp)
        by_class[cls] = pdata
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    if playoffs.get("completed"):
        _sync_playoff_top_level_champion_runner(playoffs)
    state["standings"] = standings
    state["playoff_season_player_stats"] = season_stats_map_to_jsonable(sp)
    return state


def _stash_pending_offseason_transition(
    state: Dict[str, Any],
    standings: Dict[str, Any],
    champion: str,
    br_flat_fin: List[Dict[str, Any]],
    year_num: int,
) -> None:
    """Hold season rollover until cross-region schedule planning is confirmed."""
    try:
        standings_snapshot = copy.deepcopy(standings)
    except Exception:
        standings_snapshot = {str(k): dict(v) if isinstance(v, dict) else v for k, v in dict(standings or {}).items()}
    state["pending_offseason_transition"] = {
        "standings": standings_snapshot,
        "champion": str(champion or ""),
        "br_flat_fin": list(br_flat_fin or []),
        "year_num": int(year_num),
    }


def _finish_season_apply_offseason_transition(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_names: List[str],
    standings: Dict[str, Any],
    champion: str,
    br_flat_fin: List[Dict[str, Any]],
    year_num: int,
    league_history: Dict[str, Any],
    *,
    defer_schedule: bool = False,
) -> None:
    """Graduation, calendar advance to offseason, PP/coach-dev banks, schedule reset — after season summary."""
    user_team_name = str(state.get("user_team") or "").strip()
    if not defer_schedule and user_team_name:
        if _redirect_to_schedule_planning_if_needed(
            state,
            teams,
            standings=standings,
            champion=champion,
            br_flat_fin=br_flat_fin,
            year_num=year_num,
            force=True,
        ):
            return

    graduation_report: Dict[str, List[Dict[str, Any]]] = {}
    for t in teams.values():
        ro = run_offseason_roster_turnover(t, league_history=league_history)
        reset_team_season_stats(t)
        graduated = ro.get("graduated") or []
        graduation_report[t.name] = [player_to_dict(p) for p in graduated]

    state["current_year"] = int(year_num) + 1
    state["season_phase"] = "offseason"
    state["current_week"] = 1
    state["offseason_stage_index"] = 0
    state["offseason_stages"] = list(OFFSEASON_UI_STAGES)
    state["offseason_graduation_report"] = graduation_report
    state["offseason_training_results"] = None
    state["offseason_winter_training_results"] = None
    state["offseason_winter_history"] = []
    state["offseason_spring_history"] = None
    user_team_name = str(state.get("user_team") or "")
    sg_fin = state.get("season_goals") if isinstance(state.get("season_goals"), dict) else None
    from systems.home_game_themes import apply_home_theme_cash_rewards, compute_league_home_theme_summaries

    theme_rewards = state.get("home_theme_season_rewards")
    if not isinstance(theme_rewards, dict):
        theme_rewards = compute_league_home_theme_summaries(state, team_names)
        state["home_theme_season_rewards"] = theme_rewards
    apply_home_theme_cash_rewards(teams, theme_rewards)
    user_theme_pp = 0
    if user_team_name and isinstance(theme_rewards.get(user_team_name), dict):
        user_theme_pp = int(theme_rewards[user_team_name].get("pp_total") or 0)
    if user_team_name:
        try:
            breakdown = _season_pp_awards_for_team(
                user_team_name,
                standings=standings,
                bracket_results=br_flat_fin,
                champion=champion,
                season_goals=sg_fin,
                weeks=state.get("weeks"),
                week_results=state.get("week_results"),
            )
            pp_total = int(breakdown.get("pp_total", 0) or 0)
        except Exception:
            breakdown = None
            pp_total = 0
    else:
        breakdown = None
        pp_total = 0
    if user_theme_pp:
        pp_total = int(pp_total) + int(user_theme_pp)
        if isinstance(breakdown, dict):
            breakdown = dict(breakdown)
            breakdown["home_theme_pp"] = int(user_theme_pp)
            breakdown["home_theme_games"] = (theme_rewards.get(user_team_name) or {}).get("games") if user_team_name else []
            breakdown["pp_total"] = int(pp_total)
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
    state.pop("home_game_themes", None)
    state.pop("home_game_themes_user_confirmed", None)
    state.pop("home_theme_season_rewards", None)
    ensure_league_structure_in_state(state)
    if not defer_schedule:
        wk, wr = _regular_season_week_boards(teams, state)
        state["weeks"] = wk
        state["week_results"] = wr
    else:
        state.pop("weeks", None)
        state.pop("week_results", None)
    try:
        state["offseason_transfer_snapshot_standings"] = copy.deepcopy(standings)
    except Exception:
        state["offseason_transfer_snapshot_standings"] = {
            str(k): dict(v) if isinstance(v, dict) else v for k, v in dict(standings or {}).items()
        }
    try:
        state["last_completed_standings"] = copy.deepcopy(standings)
    except Exception:
        state["last_completed_standings"] = {
            str(k): dict(v) if isinstance(v, dict) else v for k, v in dict(standings or {}).items()
        }
    state["last_completed_year"] = year_num
    _clear_offseason_transfer_ui_state(state)
    state["standings"] = {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    apply_team_program_totals_to_serialized_team_rows(league_history.get("seasons") or [], state=state)
    if not defer_schedule:
        _assign_scrimmage_opponents_for_state(state)
    state.pop("playoffs", None)
    state.pop("playoff_season_player_stats", None)


def _build_season_schedule_into_state(state: Dict[str, Any], teams: Dict[str, Any]) -> None:
    """Build ``weeks`` / ``week_results`` from current ``cross_region_picks`` on state."""
    wk, wr = _regular_season_week_boards(teams, state)
    state["weeks"] = wk
    state["week_results"] = wr


def _any_team_needs_cross_region_planning(teams: Dict[str, Any]) -> bool:
    """True when any program in the league has out-of-region schedule slots."""
    for name in teams:
        if _schedule_planning_info_for_user(teams, name):
            return True
    return False


def _human_teams_missing_cross_region_picks(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    human_teams: set[str],
) -> List[str]:
    """Human-controlled teams that still owe out-of-region picks."""
    missing: List[str] = []
    for team_name in sorted(human_teams):
        if not _schedule_planning_info_for_user(teams, team_name):
            continue
        if not _user_cross_region_picks_complete(state, teams, team_name):
            missing.append(team_name)
    return missing


def _merge_cross_region_picks_for_team(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_name: str,
    cross_region_picks: Any,
) -> None:
    """Validate and merge one team's out-of-region picks into shared league state."""
    from systems.schedule_planning import normalize_cross_region_picks, picks_dict_for_state

    picks = normalize_cross_region_picks(teams, team_name, cross_region_picks)
    merged: Dict[str, Any] = dict(state.get("cross_region_picks") or {})
    merged.update(picks_dict_for_state(team_name, picks))
    state["cross_region_picks"] = merged


def _auto_fill_cross_region_picks_for_teams(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    *,
    skip_teams: Optional[set[str]] = None,
) -> None:
    """Fill missing out-of-region slots (CPU teams only when skip_teams is human roster)."""
    from systems.schedule_planning import auto_random_picks, picks_dict_for_state

    skip = skip_teams or set()
    merged_picks: Dict[str, Any] = dict(state.get("cross_region_picks") or {})
    for team_name in teams:
        if team_name in skip:
            continue
        if not _schedule_planning_info_for_user(teams, team_name):
            continue
        if _user_cross_region_picks_complete(state, teams, team_name):
            continue
        merged_picks.update(picks_dict_for_state(team_name, auto_random_picks(teams, team_name)))
    state["cross_region_picks"] = merged_picks
    _build_season_schedule_into_state(state, teams)
    state.pop("schedule_planning_info", None)
    _sync_user_cross_region_slot_count(state)


def _user_cross_region_picks_complete(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    user_team: str,
) -> bool:
    """True when the user has no cross-region slots or every slot has a valid opponent."""
    from systems.schedule_planning import cross_region_slots_for_team, parse_stored_pick

    slots = cross_region_slots_for_team(teams, user_team)
    if not slots:
        return True
    picks_raw = state.get("cross_region_picks") or {}
    user_picks = picks_raw.get(user_team) if isinstance(picks_raw, dict) else None
    if not isinstance(user_picks, dict):
        return False
    by_slot = {s.slot_index: s for s in slots}
    for si, slot in by_slot.items():
        raw = user_picks.get(si)
        if raw is None:
            raw = user_picks.get(str(si))
        pick = parse_stored_pick(raw)
        if not pick.opponent or pick.opponent not in slot.eligible_teams:
            return False
    return True


def _schedule_planning_info_for_user(teams: Dict[str, Any], user_team: str) -> Optional[Dict[str, Any]]:
    from systems.schedule_planning import (
        cross_region_slots_for_team,
        cross_region_slots_to_json,
        detect_class_template,
    )
    from systems.league_structure import classification_key

    slots = cross_region_slots_for_team(teams, user_team)
    if not slots:
        return None
    t = teams.get(user_team)
    cls = classification_key(getattr(t, "classification", None) if t else None)
    tmpl = detect_class_template(teams, cls)
    in_region = tmpl.in_region_weeks if tmpl else 9
    return {
        "slot_count": len(slots),
        "in_region_games": in_region,
        "total_games": in_region + len(slots),
        "slots": cross_region_slots_to_json(slots),
    }


def _redirect_to_schedule_planning_if_needed(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    *,
    standings: Dict[str, Any],
    champion: str,
    br_flat_fin: List[Dict[str, Any]],
    year_num: int,
    force: bool = False,
) -> bool:
    """When cross-region picks are required but missing, enter schedule planning instead of offseason."""
    user_team = str(state.get("user_team") or "").strip()
    if not user_team:
        return False
    if _user_cross_region_picks_complete(state, teams, user_team):
        return False
    planning_info = _schedule_planning_info_for_user(teams, user_team)
    if not planning_info:
        return False
    _stash_pending_offseason_transition(state, standings, champion, br_flat_fin, year_num)
    state["season_phase"] = "schedule_planning"
    state.pop("cross_region_picks", None)
    state["schedule_planning_info"] = planning_info
    state.pop("weeks", None)
    state.pop("week_results", None)
    _sync_user_cross_region_slot_count(state)
    return True


def _set_season_summary_phase(state: Dict[str, Any]) -> None:
    """Enter season summary; clear prior-year out-of-region locks so the UI prompts fresh picks."""
    state["season_phase"] = "season_summary"
    state.pop("cross_region_picks", None)
    _sync_cross_region_schedule_ui_fields(state)


def _state_on_summary_or_planning_screen(state: Dict[str, Any]) -> bool:
    """True when the client may show season summary or out-of-region pick UI."""
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase in ("season_summary", "schedule_planning"):
        return True
    if phase == "playoffs":
        playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        return bool(playoffs.get("completed"))
    return False


def _sync_cross_region_schedule_ui_fields(state: Dict[str, Any]) -> None:
    """Slot count for UI hints; attach planning info when summary/planning UI needs picks."""
    ensure_league_structure_in_state(state)
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    user_team = str(state.get("user_team") or "").strip()
    info = _schedule_planning_info_for_user(teams, user_team) if user_team else None
    state["user_cross_region_slot_count"] = int(info.get("slot_count") or 0) if info else 0
    if not info or not user_team:
        return
    if _state_on_summary_or_planning_screen(state) and not _user_cross_region_picks_complete(
        state, teams, user_team
    ):
        state["schedule_planning_info"] = info
    elif str(state.get("season_phase") or "").strip().lower() == "schedule_planning":
        if not state.get("schedule_planning_info"):
            state["schedule_planning_info"] = info


def _sync_user_cross_region_slot_count(state: Dict[str, Any]) -> None:
    """Expose how many out-of-region picks the user's class requires (0 when pod-only)."""
    _sync_cross_region_schedule_ui_fields(state)


def _finalize_cross_region_schedule_state(state: Dict[str, Any]) -> bool:
    """Repair skipped planning and refresh UI-facing cross-region fields."""
    changed = _repair_missing_cross_region_schedule_planning(state)
    _sync_cross_region_schedule_ui_fields(state)
    return changed


def _ensure_schedule_planning_info_on_state(state: Dict[str, Any], teams: Dict[str, Any]) -> bool:
    """When phase is schedule_planning but info was dropped, rebuild it."""
    phase = str(state.get("season_phase") or "").strip().lower()
    if phase != "schedule_planning":
        return False
    user_team = str(state.get("user_team") or "").strip()
    if not user_team:
        return False
    if state.get("schedule_planning_info"):
        return False
    planning_info = _schedule_planning_info_for_user(teams, user_team)
    if not planning_info:
        state["season_phase"] = "season_summary"
        _sync_cross_region_schedule_ui_fields(state)
        return True
    state["schedule_planning_info"] = planning_info
    return True


def _repair_missing_cross_region_schedule_planning(state: Dict[str, Any]) -> bool:
    """Send saves that skipped out-of-region picks back to schedule planning."""
    # Multiplayer: opening schedule is shared and auto-built; never bounce one coach
    # into the single-player schedule picker (that rebuilds weeks out of order).
    if is_multiplayer_league_state(state):
        return ensure_multiplayer_opening_schedule(state)

    phase = str(state.get("season_phase") or "").strip().lower()
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    user_team = str(state.get("user_team") or "").strip()
    if not user_team or user_team not in teams:
        return False

    if _ensure_schedule_planning_info_on_state(state, teams):
        return True

    if phase == "offseason":
        if int(state.get("offseason_stage_index") or 0) != 0:
            return False
        if _user_cross_region_picks_complete(state, teams, user_team):
            return False
        planning_info = _schedule_planning_info_for_user(teams, user_team)
        if not planning_info:
            return False
        if not state.get("pending_offseason_transition"):
            playoffs_os = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
            br_flat_os = _recap_merged_bracket_results(
                state, _flatten_playoff_bracket_results(playoffs_os)
            )
            _stash_pending_offseason_transition(
                state,
                state.get("standings") or {},
                str(playoffs_os.get("champion") or ""),
                br_flat_os,
                int(state.get("current_year") or 1),
            )
        state["season_phase"] = "schedule_planning"
        state["schedule_planning_info"] = planning_info
        state.pop("weeks", None)
        state.pop("week_results", None)
        return True

    # Season summary is the intended pick screen — only repair saves that skipped planning in preseason.
    if phase != "preseason":
        return False
    if _user_cross_region_picks_complete(state, teams, user_team):
        return False
    if not _schedule_planning_info_for_user(teams, user_team):
        return False
    year_num = int(state.get("current_year") or 1)
    standings = state.get("standings") or {}
    playoffs_ps = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    champion = str(playoffs_ps.get("champion") or "")
    br_flat_ps = _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs_ps))
    return _redirect_to_schedule_planning_if_needed(
        state,
        teams,
        standings=standings,
        champion=champion,
        br_flat_fin=br_flat_ps,
        year_num=year_num,
        force=True,
    )


def _apply_schedule_planning_picks_and_enter_offseason(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    cross_region_picks: Any,
    *,
    league_history: Optional[Dict[str, Any]] = None,
) -> None:
    from systems.schedule_planning import normalize_cross_region_picks, picks_dict_for_state

    user_team = str(state.get("user_team") or "").strip()
    if not user_team:
        raise ValueError("No user team on save.")
    picks = normalize_cross_region_picks(teams, user_team, cross_region_picks)
    merged: Dict[str, Any] = dict(state.get("cross_region_picks") or {})
    merged.update(picks_dict_for_state(user_team, picks))
    state["cross_region_picks"] = merged
    _build_season_schedule_into_state(state, teams)

    already_in_offseason = isinstance(state.get("offseason_graduation_report"), dict)
    pending = state.pop("pending_offseason_transition", None)
    if isinstance(pending, dict):
        team_names = list(teams.keys())
        standings = pending.get("standings") or state.get("standings") or {}
        _finish_season_apply_offseason_transition(
            state,
            teams,
            team_names,
            standings,
            str(pending.get("champion") or ""),
            list(pending.get("br_flat_fin") or []),
            int(pending.get("year_num") or state.get("current_year") or 1),
            league_history or {"seasons": []},
            defer_schedule=False,
        )
        state["season_phase"] = "offseason"
    elif already_in_offseason:
        state["season_phase"] = "offseason"
    else:
        state["season_phase"] = "preseason"
        state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
        state["preseason_stage_index"] = int(state.get("preseason_stage_index") or 0)
    _assign_scrimmage_opponents_for_state(state)
    state.pop("schedule_planning_info", None)
    _sync_user_cross_region_slot_count(state)


def _mp_scrimmage_by_team(state: Dict[str, Any]) -> Dict[str, Any]:
    raw = state.get("multiplayer_scrimmage_by_team")
    if not isinstance(raw, dict):
        raw = {}
        state["multiplayer_scrimmage_by_team"] = raw
    return raw


def _mp_team_scrimmage_slice(state: Dict[str, Any], team_name: str) -> Dict[str, Any]:
    by_team = _mp_scrimmage_by_team(state)
    slice_ = by_team.get(team_name)
    if not isinstance(slice_, dict):
        slice_ = {}
        by_team[team_name] = slice_
    return slice_


def hydrate_mp_team_scrimmage_view(state: Dict[str, Any], team_name: str) -> None:
    """Expose one coach's scrimmage opponents/results on the working save view."""
    state.pop("preseason_scrimmage_opponents", None)
    state.pop("preseason_scrimmages", None)
    slice_ = (_mp_scrimmage_by_team(state).get(team_name) or {}) if team_name else {}
    if isinstance(slice_, dict):
        if slice_.get("opponents"):
            state["preseason_scrimmage_opponents"] = copy.deepcopy(slice_["opponents"])
        if slice_.get("scrimmages"):
            state["preseason_scrimmages"] = copy.deepcopy(slice_["scrimmages"])


def _mp_scrimmage_slot_taken_opponents(state: Dict[str, Any], scrim_idx: int, *, skip_team: str = "") -> set[str]:
    """Opponents already assigned to other teams for one scrimmage slot."""
    taken: set[str] = set()
    for team, slice_ in _mp_scrimmage_by_team(state).items():
        if team == skip_team or not isinstance(slice_, dict):
            continue
        opponents = slice_.get("opponents") or []
        if scrim_idx < len(opponents) and isinstance(opponents[scrim_idx], dict):
            opp = str(opponents[scrim_idx].get("opponent") or "").strip()
            if opp:
                taken.add(opp)
    return taken


def repair_multiplayer_scrimmage_storage(state: Dict[str, Any]) -> bool:
    """
    Multiplayer scrimmages are per-team only. Remove legacy league-wide fields that
    caused every coach to see the same matchup.
    """
    if not is_multiplayer_league_state(state):
        return False
    changed = False
    legacy_opponents = state.get("preseason_scrimmage_opponents")
    legacy_scrimmages = state.get("preseason_scrimmages")
    owner = str(state.get("user_team") or "").strip()
    if legacy_opponents or legacy_scrimmages:
        if owner:
            slice_ = _mp_team_scrimmage_slice(state, owner)
            if legacy_opponents and not slice_.get("opponents"):
                slice_["opponents"] = copy.deepcopy(legacy_opponents)
            if legacy_scrimmages and not slice_.get("scrimmages"):
                slice_["scrimmages"] = copy.deepcopy(legacy_scrimmages)
        changed = True
    if state.pop("preseason_scrimmage_opponents", None) is not None:
        changed = True
    if state.pop("preseason_scrimmages", None) is not None:
        changed = True
    if _dedupe_mp_scrimmage_opponents(state):
        changed = True
    return changed


def _dedupe_mp_scrimmage_opponents(state: Dict[str, Any]) -> bool:
    """If two teams share identical scrimmage opponent lists, re-pick for the duplicate."""
    team_names = [
        str(t.get("name") or "")
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    ]
    if not team_names:
        return False
    by_team = _mp_scrimmage_by_team(state)
    seen: Dict[str, str] = {}
    changed = False
    for team_name, slice_ in list(by_team.items()):
        if not isinstance(slice_, dict):
            continue
        opponents = slice_.get("opponents")
        if not opponents:
            continue
        signature = json.dumps(opponents, sort_keys=True)
        other = seen.get(signature)
        if other and other != team_name:
            exclude = _mp_scrimmage_slot_taken_opponents(state, 0, skip_team=team_name)
            exclude |= _mp_scrimmage_slot_taken_opponents(state, 1, skip_team=team_name)
            slice_["opponents"] = build_scrimmage_opponents_for_team(
                team_name,
                team_names,
                state.get("weeks"),
                exclude_opponents=exclude,
            )
            if slice_.get("scrimmages"):
                slice_["scrimmages"] = []
            changed = True
        else:
            seen[signature] = team_name
    return changed


def persist_mp_team_scrimmage_slice(state: Dict[str, Any], team_name: str) -> None:
    """Persist one coach's scrimmage data into the shared league save."""
    if not team_name:
        return
    slice_ = _mp_team_scrimmage_slice(state, team_name)
    if state.get("preseason_scrimmage_opponents") is not None:
        slice_["opponents"] = copy.deepcopy(state.get("preseason_scrimmage_opponents") or [])
    if state.get("preseason_scrimmages") is not None:
        slice_["scrimmages"] = copy.deepcopy(state.get("preseason_scrimmages") or [])


def _mp_7on7_by_team(state: Dict[str, Any]) -> Dict[str, Any]:
    raw = state.get("multiplayer_7on7_by_team")
    if not isinstance(raw, dict):
        raw = {}
        state["multiplayer_7on7_by_team"] = raw
    return raw


def hydrate_mp_team_7on7_view(state: Dict[str, Any], team_name: str) -> None:
    """Expose one coach's 7-on-7 tournament results on the working save view."""
    state.pop("offseason_7on7_results", None)
    if not team_name:
        return
    slice_ = _mp_7on7_by_team(state).get(team_name)
    if isinstance(slice_, dict) and isinstance(slice_.get("results"), dict):
        state["offseason_7on7_results"] = copy.deepcopy(slice_["results"])


def _run_mp_seven_on_seven_for_team(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_name: str,
    tier: str,
) -> Dict[str, Any]:
    tier_key = str(tier or "regional").strip().lower()
    if tier_key not in VALID_TOURNAMENT_TIERS:
        tier_key = "regional"
    payload = run_seven_on_seven_tournament(teams, team_name, tier_key)
    _mp_7on7_by_team(state)[team_name] = {"tier": tier_key, "results": payload}
    return payload


def _run_mp_seven_on_seven_for_all_teams(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    *,
    default_tier: str = "regional",
) -> None:
    by_team = _mp_7on7_by_team(state)
    for name in teams:
        slice_ = by_team.get(name)
        if isinstance(slice_, dict) and isinstance(slice_.get("results"), dict):
            continue
        _run_mp_seven_on_seven_for_team(state, teams, name, default_tier)


def repair_multiplayer_7on7_storage(state: Dict[str, Any]) -> bool:
    """Move legacy league-wide 7-on-7 results into per-team storage for multiplayer."""
    if not is_multiplayer_league_state(state):
        return False
    changed = False
    legacy = state.get("offseason_7on7_results")
    owner = str(state.get("user_team") or "").strip()
    if isinstance(legacy, dict) and owner:
        slice_ = _mp_7on7_by_team(state).get(owner)
        if not isinstance(slice_, dict) or not slice_.get("results"):
            _mp_7on7_by_team(state)[owner] = {
                "tier": str(legacy.get("tier") or "regional"),
                "results": copy.deepcopy(legacy),
            }
            changed = True
    if state.pop("offseason_7on7_results", None) is not None:
        changed = True
    return changed


def _advance_multiplayer_seven_on_seven_stage(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    body: Dict[str, Any],
    *,
    idx: int,
) -> str:
    """
    Multiplayer 7-on-7: coaches run/review per team; commissioner sim fills every team.
    Returns 'wait_review', 'complete', or 'single_player' (fall through to SP logic).
    """
    if not is_multiplayer_league_state(state):
        return "single_player"

    seven_results = state.get("offseason_7on7_results")
    ack = bool(body.get("seven_on_seven_ack_results"))
    tier_raw = body.get("seven_on_seven_tournament")
    user_team_name = str(state.get("user_team") or "").strip()

    if user_team_name and user_team_name in teams:
        if isinstance(seven_results, dict) and ack:
            state.pop("offseason_7on7_results", None)
            return "complete"
        if isinstance(seven_results, dict) and not ack:
            raise ValueError("Review 7-on-7 tournament results, then press Continue again to advance.")
        tier = str(tier_raw or "regional").strip().lower()
        if tier not in VALID_TOURNAMENT_TIERS:
            raise ValueError("Choose a 7-on-7 tournament (Area, Regional, or State), then press Continue.")
        payload = _run_mp_seven_on_seven_for_team(state, teams, user_team_name, tier)
        state["offseason_7on7_results"] = copy.deepcopy(payload)
        state["offseason_stage_index"] = idx
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        return "wait_review"

    # Commissioner / league-wide advance (no user_team on canonical save).
    if isinstance(seven_results, dict) and ack:
        state.pop("offseason_7on7_results", None)
    elif isinstance(seven_results, dict) and not ack:
        state.pop("offseason_7on7_results", None)
    tier = str(tier_raw or "regional").strip().lower()
    _run_mp_seven_on_seven_for_all_teams(state, teams, default_tier=tier)
    state.pop("offseason_7on7_results", None)
    return "complete"


def _ensure_mp_team_scrimmage_opponents(
    state: Dict[str, Any],
    team_name: str,
    team_names: List[str],
) -> bool:
    """Ensure a multiplayer coach has scrimmage opponents assigned (per-team store)."""
    slice_ = _mp_team_scrimmage_slice(state, team_name)
    if slice_.get("opponents"):
        hydrate_mp_team_scrimmage_view(state, team_name)
        return False
    exclude = _mp_scrimmage_slot_taken_opponents(state, 0, skip_team=team_name)
    exclude |= _mp_scrimmage_slot_taken_opponents(state, 1, skip_team=team_name)
    opponents = build_scrimmage_opponents_for_team(
        team_name,
        team_names,
        state.get("weeks"),
        exclude_opponents=exclude,
    )
    slice_["opponents"] = opponents
    if "scrimmages" not in slice_:
        slice_["scrimmages"] = []
    hydrate_mp_team_scrimmage_view(state, team_name)
    return True


def _scrimmage_stage_completed(scrimmages: List[Any], stage_name: str) -> bool:
    for row in scrimmages or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("stage") or "")
        if name != stage_name:
            continue
        if row.get("completed") is False:
            continue
        if row.get("played") is True or row.get("completed") is True:
            return True
    return False


def simulate_multiplayer_preseason_scrimmage_stage(
    state: Dict[str, Any],
    human_team_names: List[str],
    current_stage: str,
) -> None:
    """Commissioner advance: CPU-sim scrimmages for every human coach at this stage."""
    if current_stage not in ("Scrimmage 1", "Scrimmage 2"):
        return
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    team_names = list(teams.keys())
    by_team = _mp_scrimmage_by_team(state)
    scrim_idx = 0 if current_stage == "Scrimmage 1" else 1
    for team_name in human_team_names:
        if team_name not in teams:
            continue
        slice_ = _mp_team_scrimmage_slice(state, team_name)
        scrimmages = list(slice_.get("scrimmages") or [])
        if _scrimmage_stage_completed(scrimmages, current_stage):
            continue
        opponents = slice_.get("opponents")
        if not opponents:
            exclude = _mp_scrimmage_slot_taken_opponents(state, scrim_idx, skip_team=team_name)
            opponents = build_scrimmage_opponents_for_team(
                team_name,
                team_names,
                state.get("weeks"),
                exclude_opponents=exclude,
            )
            slice_["opponents"] = opponents
        work_state: Dict[str, Any] = {
            "user_team": team_name,
            "preseason_scrimmage_opponents": copy.deepcopy(opponents),
            "preseason_scrimmages": copy.deepcopy(scrimmages),
            "weeks": state.get("weeks"),
        }
        _apply_preseason_scrimmage_stage(work_state, teams, team_names, current_stage)
        slice_["opponents"] = copy.deepcopy(work_state.get("preseason_scrimmage_opponents") or opponents)
        slice_["scrimmages"] = copy.deepcopy(work_state.get("preseason_scrimmages") or scrimmages)
        by_team[team_name] = slice_
    repair_multiplayer_scrimmage_storage(state)


def is_multiplayer_league_state(state: Dict[str, Any]) -> bool:
    """True for shared online leagues (no per-coach opening schedule picker)."""
    if not isinstance(state, dict):
        return False
    if state.get("multiplayer_league"):
        return True
    mp = state.get("multiplayer")
    return isinstance(mp, dict) and bool(mp.get("league_id"))


def _auto_fill_all_cross_region_picks(state: Dict[str, Any]) -> None:
    """Fill out-of-region slots for every team and build the shared week board."""
    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    _auto_fill_cross_region_picks_for_teams(state, teams)


def ensure_multiplayer_opening_schedule(state: Dict[str, Any]) -> bool:
    """
    Multiplayer leagues never use the single-player opening schedule picker.
    Auto-build the shared schedule and start in preseason when needed.
    Returns True when state was mutated.
    """
    if not is_multiplayer_league_state(state):
        return False
    state["multiplayer_league"] = True
    phase = str(state.get("season_phase") or "").strip().lower()
    weeks = state.get("weeks")
    has_weeks = isinstance(weeks, list) and len(weeks) > 0
    # Opening dynasty only: schedule_planning before any season has been played.
    played = False
    if has_weeks:
        for wk in weeks:
            if not isinstance(wk, list):
                continue
            for g in wk:
                if isinstance(g, dict) and g.get("played"):
                    played = True
                    break
            if played:
                break
    if phase == "schedule_planning" and not played:
        _auto_fill_all_cross_region_picks(state)
        state["season_phase"] = "preseason"
        state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
        state["preseason_stage_index"] = int(state.get("preseason_stage_index") or 0)
        state["current_week"] = int(state.get("current_week") or 1)
        repair_multiplayer_scrimmage_storage(state)
        return True
    if phase == "preseason" and not has_weeks:
        teams = {
            t["name"]: team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        user_team = str(state.get("user_team") or "").strip()
        if user_team and _schedule_planning_info_for_user(teams, user_team):
            _auto_fill_all_cross_region_picks(state)
            repair_multiplayer_scrimmage_storage(state)
            return True
    return False


def advance_mp_season_summary_or_planning_state(
    state: Dict[str, Any],
    league_history: Dict[str, Any],
    *,
    human_teams: Optional[set[str]] = None,
    cross_region_picks: Optional[Any] = None,
    commish_team: str = "",
) -> str:
    """
    Multiplayer end-of-year flow: each human coach picks out-of-region games (or the
    commissioner sets them in Run league), then the commissioner advances the league.
    """
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s not in ("season_summary", "schedule_planning"):
        raise ValueError(f"Cannot advance multiplayer season end from season_phase={phase_s!r}")

    teams = {
        t["name"]: team_from_dict(t)
        for t in (state.get("teams") or [])
        if isinstance(t, dict) and t.get("name")
    }
    team_names = list(teams.keys())
    human = set(human_teams or [])

    if not _any_team_needs_cross_region_planning(teams):
        playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        champion = str(playoffs.get("champion") or "")
        br_flat = _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs))
        standings = state.get("standings") or {}
        year_num = int(state.get("current_year", 1))
        state.pop("cross_region_picks", None)
        state.pop("user_team", None)
        _finish_season_apply_offseason_transition(
            state,
            teams,
            team_names,
            standings,
            champion,
            br_flat,
            year_num,
            league_history,
            defer_schedule=False,
        )
        state["season_phase"] = "offseason"
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        return "Offseason begun"

    missing_humans = _human_teams_missing_cross_region_picks(state, teams, human)

    if missing_humans:
        raise ValueError(
            "Set out-of-region schedules for all human teams before advancing: "
            + ", ".join(missing_humans)
        )

    _auto_fill_cross_region_picks_for_teams(state, teams, skip_teams=human)

    pending = state.pop("pending_offseason_transition", None)
    if not isinstance(pending, dict):
        playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        pending = {
            "standings": state.get("standings") or {},
            "champion": str(playoffs.get("champion") or ""),
            "br_flat_fin": _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs)),
            "year_num": int(state.get("current_year", 1)),
        }

    already_in_offseason = isinstance(state.get("offseason_graduation_report"), dict)
    standings = pending.get("standings") or state.get("standings") or {}
    if isinstance(pending, dict):
        _finish_season_apply_offseason_transition(
            state,
            teams,
            team_names,
            standings,
            str(pending.get("champion") or ""),
            list(pending.get("br_flat_fin") or []),
            int(pending.get("year_num") or state.get("current_year") or 1),
            league_history,
            defer_schedule=False,
        )
        state["season_phase"] = "offseason"
    elif already_in_offseason:
        state["season_phase"] = "offseason"
    else:
        state["season_phase"] = "preseason"
        state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
        state["preseason_stage_index"] = int(state.get("preseason_stage_index") or 0)

    if is_multiplayer_league_state(state):
        repair_multiplayer_scrimmage_storage(state)
    else:
        _assign_scrimmage_opponents_for_state(state)
    state.pop("schedule_planning_info", None)
    state.pop("user_team", None)
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    return "Cross-region schedule confirmed — offseason begun"


def advance_schedule_planning_league_state(
    state: Dict[str, Any],
    *,
    league_history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Multiplayer opening: auto-fill cross-region picks for every team, then build the season schedule."""
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "schedule_planning":
        raise ValueError("save is not in schedule_planning")

    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", []) if isinstance(t, dict) and t.get("name")}
    _auto_fill_all_cross_region_picks(state)

    already_in_offseason = isinstance(state.get("offseason_graduation_report"), dict)
    pending = state.pop("pending_offseason_transition", None)
    lh = league_history if isinstance(league_history, dict) else {"seasons": []}
    if isinstance(pending, dict):
        team_names = list(teams.keys())
        standings = pending.get("standings") or state.get("standings") or {}
        _finish_season_apply_offseason_transition(
            state,
            teams,
            team_names,
            standings,
            str(pending.get("champion") or ""),
            list(pending.get("br_flat_fin") or []),
            int(pending.get("year_num") or state.get("current_year") or 1),
            lh,
            defer_schedule=False,
        )
        state["season_phase"] = "offseason"
    elif already_in_offseason:
        state["season_phase"] = "offseason"
    else:
        state["season_phase"] = "preseason"
        state["preseason_stages"] = state.get("preseason_stages") or list(PRESEASON_STAGES)
        state["preseason_stage_index"] = int(state.get("preseason_stage_index") or 0)
    if is_multiplayer_league_state(state):
        repair_multiplayer_scrimmage_storage(state)
    else:
        _assign_scrimmage_opponents_for_state(state)
    state.pop("schedule_planning_info", None)
    _sync_user_cross_region_slot_count(state)
    state["teams"] = [team_to_dict(t) for t in teams.values()]
    return state


def _apply_season_summary_offseason_begin(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_names: List[str],
    standings: Dict[str, Any],
    champion: str,
    br_flat_fin: List[Dict[str, Any]],
    year_num: int,
    league_history: Dict[str, Any],
    *,
    bulk_autopilot: bool = False,
    cross_region_picks: Optional[Any] = None,
) -> None:
    """Leave season summary: schedule planning first, or graduation/offseason when no slots / autopilot."""
    _begin_offseason_from_season_summary(
        state,
        teams,
        team_names,
        standings,
        champion,
        br_flat_fin,
        year_num,
        league_history,
        bulk_autopilot=bulk_autopilot,
    )
    if (
        not bulk_autopilot
        and cross_region_picks
        and str(state.get("season_phase") or "").strip().lower() == "schedule_planning"
    ):
        _apply_schedule_planning_picks_and_enter_offseason(
            state, teams, cross_region_picks, league_history=league_history
        )


def _begin_offseason_from_season_summary(
    state: Dict[str, Any],
    teams: Dict[str, Any],
    team_names: List[str],
    standings: Dict[str, Any],
    champion: str,
    br_flat_fin: List[Dict[str, Any]],
    year_num: int,
    league_history: Dict[str, Any],
    *,
    bulk_autopilot: bool = False,
) -> None:
    """Graduation + year advance; schedule planning when the user's class has cross-region slots."""
    from systems.schedule_planning import auto_random_picks, picks_dict_for_state

    user_team = str(state.get("user_team") or "").strip()
    planning_info = _schedule_planning_info_for_user(teams, user_team) if user_team else None

    if not bulk_autopilot:
        # Each new season requires fresh out-of-region picks — do not reuse last year's locks.
        state.pop("cross_region_picks", None)
        needs_planning = bool(planning_info)
    else:
        needs_planning = False

    if needs_planning:
        _redirect_to_schedule_planning_if_needed(
            state,
            teams,
            standings=standings,
            champion=champion,
            br_flat_fin=br_flat_fin,
            year_num=year_num,
            force=True,
        )
        return

    if planning_info and bulk_autopilot and user_team:
        state["cross_region_picks"] = picks_dict_for_state(user_team, auto_random_picks(teams, user_team))
    _finish_season_apply_offseason_transition(
        state,
        teams,
        team_names,
        standings,
        champion,
        br_flat_fin,
        year_num,
        league_history,
        defer_schedule=False,
    )


def _attach_league_history_to_result(save_dir: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Include archived seasons in API responses so the client can render League History."""
    try:
        result["league_history"] = load_league_history(league_history_path(save_dir))
    except Exception:
        result["league_history"] = {"seasons": []}
    return result


def finish_season(
    user_id: str,
    save_id: str,
    *,
    bulk_autopilot: bool = False,
    begin_offseason: bool = False,
    cross_region_picks: Optional[Any] = None,
) -> Dict[str, Any]:
    state, save_dir = load_state(user_id, save_id)
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())
    standings = state.get("standings") or {n: {"wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for n in team_names}
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s == "offseason":
        _sync_derived_save_fields(state, save_dir)
        save_state(user_id, save_id, state, save_dir)
        return _attach_league_history_to_result(save_dir, {"state": state})

    if phase_s == "schedule_planning":
        league_history_sp = load_league_history(league_history_path(save_dir))
        _apply_schedule_planning_picks_and_enter_offseason(
            state, teams, cross_region_picks, league_history=league_history_sp
        )
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        _sync_cross_region_schedule_ui_fields(state)
        save_state(user_id, save_id, state, save_dir)
        return _attach_league_history_to_result(save_dir, {"state": state})

    if phase_s == "season_summary":
        playoffs_ss = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        champion_ss = str(playoffs_ss.get("champion") or "")
        league_history_ss = load_league_history(league_history_path(save_dir))
        if league_history_ss.get("seasons"):
            update_prestige(teams, league_history_ss)
            state["prestige_applied_for_year"] = int(state.get("current_year", 1) or 1)
        _sync_cross_region_schedule_ui_fields(state)
        if begin_offseason or bulk_autopilot:
            br_flat_ss = _recap_merged_bracket_results(state, _flatten_playoff_bracket_results(playoffs_ss))
            year_num_ss = int(state.get("current_year", 1))
            _apply_season_summary_offseason_begin(
                state,
                teams,
                team_names,
                standings,
                champion_ss,
                br_flat_ss,
                year_num_ss,
                league_history_ss,
                bulk_autopilot=bulk_autopilot,
                cross_region_picks=cross_region_picks,
            )
        save_state(user_id, save_id, state, save_dir)
        return _attach_league_history_to_result(save_dir, {"state": state, "champion": champion_ss})

    output_lines: List[str] = []
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
    if playoffs and playoffs.get("completed"):
        _sync_playoff_top_level_champion_runner(playoffs)
    run_playoff_stats: Dict[int, Any] = {}
    if playoffs and playoffs.get("completed") and str(playoffs.get("champion") or "").strip():
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = list(playoffs.get("bracket_results") or [])
    elif phase_s == "playoffs":
        while True:
            p = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else None
            if p and p.get("completed"):
                _sync_playoff_top_level_champion_runner(p)
            if p and p.get("completed") and str(p.get("champion") or "").strip():
                champion = str(p.get("champion") or "")
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            if p and p.get("completed"):
                champion = ""
                runner_up = str(p.get("runner_up") or "")
                bracket_results = list(p.get("bracket_results") or [])
                break
            state = _advance_playoff_one_round_state(state)
    else:
        # Fallback: finish_season called from outside the playoffs phase.
        # Build the bracket(s) from scratch using the active playoff system
        # config (which may be regional) and run each to completion. Yields
        # a champion + runner_up for the user's classification.
        _ensure_playoffs_migrated(state, teams)
        if not isinstance(state.get("playoffs"), dict) or not (state.get("playoffs") or {}).get("by_class"):
            state["playoffs"] = _init_playoffs_multiclass(state, teams, standings)
        _ensure_all_eligible_playoff_brackets(state, teams, standings)
        playoffs = state["playoffs"]
        by_class = playoffs.setdefault("by_class", {})
        for cls, pdata in list(by_class.items()):
            if not isinstance(pdata, dict) or pdata.get("completed"):
                continue
            _simulate_full_bracket_to_completion(pdata, teams, standings, run_playoff_stats)
            by_class[cls] = pdata
        playoffs["completed"] = _playoffs_global_completed(playoffs)
        uc = playoffs.get("user_class")
        if uc and uc in by_class:
            playoffs["champion"] = by_class[uc].get("champion")
            playoffs["runner_up"] = by_class[uc].get("runner_up")
        _sync_playoff_top_level_champion_runner(playoffs)
        champion = str(playoffs.get("champion") or "")
        runner_up = str(playoffs.get("runner_up") or "")
        bracket_results = _flatten_playoff_bracket_results(playoffs)

    standings = state.get("standings") or standings
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    team_names = list(teams.keys())

    if phase_s == "playoffs" or (
        playoffs and playoffs.get("completed") and str(playoffs.get("champion") or "").strip()
    ):
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
        postseason = _recap_postseason_line_label_for_team(
            team_name,
            state=state,
            season_entry_top_champion=champion,
            season_entry_top_runner_up=runner_up,
            br_flat=br_for_history,
            teams_map=teams,
        )
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

    regional_champions = compute_regular_season_regional_champions(state)
    p_bc_snap = _playoffs_by_class_snapshot(state)
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
        regional_champions=regional_champions,
        playoffs_by_class=p_bc_snap,
        save_dir=save_dir,
    )
    append_season_to_coach_career_log(
        state,
        year=year_num,
        team_coaches=team_coaches,
        standings=standings,
    )

    league_history = load_league_history(league_history_path(save_dir))
    update_prestige(teams, league_history)
    state["prestige_applied_for_year"] = year_num
    if int(state.get("program_funding_awarded_year") or 0) != int(year_num):
        _award_program_funding_for_all_teams(teams, standings, current_year=int(year_num))
        state["program_funding_awarded_year"] = int(year_num)

    if not bulk_autopilot:
        _set_season_summary_phase(state)
        state["teams"] = [team_to_dict(t) for t in teams.values()]
        save_state(user_id, save_id, state, save_dir)
        if begin_offseason:
            league_history_chain = load_league_history(league_history_path(save_dir))
            _apply_season_summary_offseason_begin(
                state,
                teams,
                team_names,
                standings,
                champion,
                br_for_history,
                year_num,
                league_history_chain,
                bulk_autopilot=False,
                cross_region_picks=cross_region_picks,
            )
            _sync_cross_region_schedule_ui_fields(state)
            save_state(user_id, save_id, state, save_dir)
        return _attach_league_history_to_result(save_dir, {"state": state, "champion": champion})

    _apply_season_summary_offseason_begin(
        state,
        teams,
        team_names,
        standings,
        champion,
        br_for_history,
        year_num,
        league_history,
        bulk_autopilot=True,
    )

    save_state(user_id, save_id, state, save_dir)
    return _attach_league_history_to_result(save_dir, {"state": state, "champion": champion})


def sim_playoff_round(user_id: str, save_id: str) -> Dict[str, Any]:
    """Simulate the next playoff round (QF, SF, or Championship) and persist bracket results."""
    state, save_dir = load_state(user_id, save_id)
    phase_s = str(state.get("season_phase") or "").strip().lower()
    if phase_s != "playoffs":
        raise ValueError("save is not in playoffs")
    teams = {t["name"]: team_from_dict(t) for t in state.get("teams", [])}
    p = _ensure_playoffs_migrated(state, teams)
    if _playoffs_global_completed(p):
        return finish_season(user_id, save_id)
    state = _advance_playoff_one_round_state(state)
    _maybe_coach_playoff_round_emails(state)
    # Championship just finished: finalize season now so team/coach history updates immediately.
    p_after = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    if _playoffs_global_completed(p_after):
        save_state(user_id, save_id, state, save_dir)
        return finish_season(user_id, save_id)
    save_state(user_id, save_id, state, save_dir)
    champ = state.get("playoffs", {}).get("champion")
    return _attach_league_history_to_result(save_dir, {"state": state, "champion": champ})


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
    cfg = get_state_playoff_system(state)
    default_bracket_size = int(cfg.bracket_size)
    default_min_teams = int(cfg.min_teams)
    last_champion: Optional[str] = None
    for cls, pdata in list(by_class.items()):
        if not isinstance(pdata, dict):
            continue
        bracket_size = int(pdata.get("num_teams") or default_bracket_size)
        min_teams = max(default_min_teams, bracket_size)
        names_in_class = _team_names_by_classification(teams).get(cls) or []
        if len(names_in_class) < min_teams:
            continue
        # Seeds were populated by _ensure_all_eligible_playoff_brackets
        # above (regional or standard); the dispatcher reads them and runs
        # the matching round-runner until the bracket is fully decided.
        _simulate_full_bracket_to_completion(pdata, teams, standings, season_player_stats)
        by_class[cls] = pdata
        last_champion = pdata.get("champion") or last_champion
        if cls == uc:
            user_champ = pdata.get("champion") or ""
    playoffs["by_class"] = by_class
    playoffs["completed"] = _playoffs_global_completed(playoffs)
    playoffs["champion"] = user_champ or next((by_class[c].get("champion") for c in by_class if by_class[c].get("champion")), None)
    state["playoffs"] = playoffs
    state["season_phase"] = "playoffs"
    state["standings"] = standings
    state["playoff_season_player_stats"] = season_player_stats
    # Full playoff sim ends with playoffs complete; finalize now for immediate history updates.
    if _playoffs_global_completed(playoffs):
        _maybe_coach_playoff_round_emails(state)
        save_state(user_id, save_id, state, save_dir)
        return finish_season(user_id, save_id)
    _maybe_coach_playoff_round_emails(state)
    save_state(user_id, save_id, state, save_dir)
    return {"state": state, "champion": playoffs.get("champion") or last_champion or ""}


BULK_SIMULATE_SEASONS_OPTIONS: Tuple[int, ...] = (1, 5, 10, 20)


def _bulk_enforce_improvement_pp_budget(
    f0: int,
    c0: int,
    b0: int,
    f1: int,
    c1: int,
    b1: int,
    pp_remaining: int,
) -> Tuple[int, int, int]:
    """
    Ensure improvement triple matches Advance Offseason accounting exactly.
    If the plan overspends PP, walk back one grade at a time (tallest pillar first).
    """
    f = _clamp_program_grade(f1, 5)
    c = _clamp_program_grade(c1, 5)
    b = _clamp_program_grade(b1, 5)
    f0i = _clamp_program_grade(f0, 5)
    c0i = _clamp_program_grade(c0, 5)
    b0i = _clamp_program_grade(b0, 5)
    for _ in range(64):
        td = (
            _improvement_pp_delta(f0i, f)
            + _improvement_pp_delta(c0i, c)
            + _improvement_pp_delta(b0i, b)
        )
        if int(pp_remaining) + int(td) >= 0:
            return (f, c, b)
        triples: List[Tuple[int, int, str]] = [
            (f, f0i, "f"),
            (c, c0i, "c"),
            (b, b0i, "b"),
        ]
        candidates = [(cur, base, nm) for cur, base, nm in triples if cur > base]
        if not candidates:
            return (f0i, c0i, b0i)
        cur, _base, nm = max(candidates, key=lambda x: x[0])
        if nm == "f":
            f = cur - 1
        elif nm == "c":
            c = cur - 1
        else:
            b = cur - 1
    return (f0i, c0i, b0i)


def _bulk_compute_ai_improvement_targets(
    facilities: int,
    culture: int,
    booster: int,
    pp_remaining: int,
) -> Tuple[int, int, int]:
    """
    Spend improvement PP like a CPU AD: greedy cheapest marginal upgrades.

    Optional rebalance rounds if one program pillar is far above the weakest pillar,
    downgrade the highest once to refund PP toward cheaper upgrades elsewhere.
    """
    f0i = _clamp_program_grade(facilities, 5)
    c0i = _clamp_program_grade(culture, 5)
    b0i = _clamp_program_grade(booster, 5)
    f = f0i
    c = c0i
    b_s = b0i
    budget = max(0, int(pp_remaining))

    def greedy_upgrades() -> None:
        nonlocal f, c, b_s, budget
        while budget > 0:
            options: List[Tuple[int, str]] = []
            for dim, lv in [("fac", f), ("cul", c), ("boo", b_s)]:
                if lv >= 10:
                    continue
                dpp = _improvement_pp_delta(lv, lv + 1)
                if dpp >= 0:
                    continue
                cost = -int(dpp)
                if cost <= budget:
                    options.append((cost, dim))
            if not options:
                break
            options.sort(key=lambda x: x[0])
            cost, dim = options[0]
            if dim == "fac":
                f += 1
            elif dim == "cul":
                c += 1
            else:
                b_s += 1
            budget -= cost

    def try_rebalance_downgrade() -> bool:
        """Downgrade tallest pillar one level when spread is wide; refunds PP."""
        nonlocal f, c, b_s, budget
        vals = [("fac", f), ("cul", c), ("boo", b_s)]
        hi_name, hi_lv = max(vals, key=lambda x: x[1])
        lo_lv = min(x[1] for x in vals)
        if hi_lv - lo_lv < 4 or hi_lv <= 1:
            return False
        refund = _improvement_pp_delta(hi_lv, hi_lv - 1)
        if refund <= 0:
            return False
        budget += int(refund)
        if hi_name == "fac":
            f = hi_lv - 1
        elif hi_name == "cul":
            c = hi_lv - 1
        else:
            b_s = hi_lv - 1
        return True

    for _ in range(24):
        greedy_upgrades()
        if budget <= 0:
            break
        if not try_rebalance_downgrade():
            break
    greedy_upgrades()
    return _bulk_enforce_improvement_pp_budget(
        f0i,
        c0i,
        b0i,
        _clamp_program_grade(f, 5),
        _clamp_program_grade(c, 5),
        _clamp_program_grade(b_s, 5),
        int(pp_remaining),
    )


def _bulk_carousel_job_prefs_for_state(state: Dict[str, Any]) -> List[str]:
    """
    Ranked HC vacancy applications for bulk sim (higher prestige schools first).

    Only when the user's coach was fired and is unemployed — bulk sim must not silently
    move an employed head coach or create misleading \"you resigned\" carousel headlines."""
    if not state.get("user_coach_unemployed"):
        return []
    ut = str(state.get("user_team") or "").strip()
    persist = state.get("offseason_coach_carousel") if isinstance(state.get("offseason_coach_carousel"), dict) else None
    if not persist or not ut:
        return []
    vac_raw = list(persist.get("vacancies") or [])
    vac = sorted(
        {
            str(v).strip()
            for v in vac_raw
            if isinstance(v, str) and str(v).strip() and str(v).strip() != ut
        }
    )
    if not vac:
        return []
    teams_rows = [
        team_from_dict(t) for t in (state.get("teams") or []) if isinstance(t, dict) and t.get("name")
    ]
    by_name = {tm.name: tm for tm in teams_rows}

    def prestige(nm: str) -> int:
        t_obj = by_name.get(nm)
        return int(getattr(t_obj, "prestige", 5) or 5) if t_obj else 5

    vac.sort(key=lambda n: (-prestige(n), n))
    return vac[:12]


def _bulk_playoffs_bracket_started(state: Dict[str, Any]) -> bool:
    playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
    bc = playoffs.get("by_class")
    if isinstance(bc, dict):
        for sub in bc.values():
            if isinstance(sub, dict) and len(list(sub.get("bracket_results") or [])) > 0:
                return True
    return len(list(playoffs.get("bracket_results") or [])) > 0


def _bulk_cpu_offseason_advance_body(state: Dict[str, Any]) -> Dict[str, Any]:
    stages: List[str] = list(state.get("offseason_stages") or OFFSEASON_UI_STAGES)
    idx = int(state.get("offseason_stage_index", 0))
    if idx < 0 or idx >= len(stages):
        return {}
    current = _normalize_offseason_stage_name(stages[idx])
    body: Dict[str, Any] = {"_bulk_cpu_pp_clamp": True}
    if current in ("Winter 1", "Winter 2"):
        winter_results = state.get("offseason_winter_training_results")
        if (
            isinstance(winter_results, dict)
            and str(winter_results.get("stage") or "") == current
        ):
            body["winter_training_ack_results"] = True
    elif current == "Spring Ball":
        if isinstance(state.get("offseason_spring_ball_results"), dict):
            body["spring_ball_ack_results"] = True
    elif current == "7 on 7":
        if isinstance(state.get("offseason_7on7_results"), dict):
            body["seven_on_seven_ack_results"] = True
        else:
            body["seven_on_seven_tournament"] = "regional"
    elif current == "Improvements":
        teams_m = {
            str(t["name"]): team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        ut_name = state.get("user_team")
        ut_team = teams_m.get(str(ut_name or "").strip())
        if ut_team is not None:
            _ensure_improvements_bank_equipment_pp(state, ut_team)
        bank = (
            state.get("offseason_improvements_bank")
            if isinstance(state.get("offseason_improvements_bank"), dict)
            else {}
        )
        if ut_team is not None:
            pp_rem = int(bank.get("pp_remaining", bank.get("pp_total", 0)) or 0)
            fac_from = _clamp_program_grade(getattr(ut_team, "facilities_grade", None), 5)
            cul_from = _clamp_program_grade(getattr(ut_team, "culture_grade", None), 5)
            boo_from = _clamp_program_grade(getattr(ut_team, "booster_support", None), 5)
            fac_to, cul_to, boo_to = _bulk_compute_ai_improvement_targets(
                fac_from,
                cul_from,
                boo_from,
                pp_rem,
            )
            body["improve_facilities_grade"] = fac_to
            body["improve_culture_grade"] = cul_to
            body["improve_booster_support"] = boo_to
    elif current == "Coach development":
        teams_m = {
            str(t["name"]): team_from_dict(t)
            for t in (state.get("teams") or [])
            if isinstance(t, dict) and t.get("name")
        }
        ut_name = str(state.get("user_team") or "").strip()
        ut_team = teams_m.get(ut_name) if ut_name else None
        coach_o = getattr(ut_team, "coach", None) if ut_team is not None else None
        if coach_o is not None:
            banks_cd = state.get("offseason_coach_dev_banks") if isinstance(state.get("offseason_coach_dev_banks"), dict) else {}
            cd_bank = banks_cd.get(ut_name) if isinstance(banks_cd.get(ut_name), dict) else None
            if cd_bank is None:
                legacy = state.get("offseason_coach_dev_bank") if isinstance(state.get("offseason_coach_dev_bank"), dict) else None
                if isinstance(legacy, dict):
                    cd_bank = legacy
            if isinstance(cd_bank, dict):
                body.update(build_bulk_sim_coach_dev_body(coach_o, cd_bank))
    elif current in ("Coaching carousel I", "Coaching carousel II", "Coaching carousel III"):
        jp = _bulk_carousel_job_prefs_for_state(state)
        if jp:
            body["carousel_job_applications"] = jp
    elif current == "Transfers I":
        if bool(state.get("offseason_transfer_stage_1_pending_review")):
            body["transfer_stage_1_ack_results"] = True
    elif current == "Transfers II":
        if bool(state.get("offseason_transfer_stage_2_pending_review")):
            body["transfer_stage_2_ack_results"] = True
    return body


def _bulk_run_offseason_autopilot(
    user_id: str,
    save_id: str,
    *,
    max_iterations: int = 8000,
) -> None:
    for _ in range(max_iterations):
        state, _save_dir = load_state(user_id, save_id)
        if str(state.get("season_phase") or "").strip().lower() != "offseason":
            return
        advance_offseason(user_id, save_id, _bulk_cpu_offseason_advance_body(state))
    raise RuntimeError(
        "Bulk simulate seasons: offseason autopilot exceeded iteration limit — save may need manual advancement."
    )


def _bulk_run_preseason_autopilot(
    user_id: str,
    save_id: str,
    *,
    max_iterations: int = 250,
) -> None:
    for _ in range(max_iterations):
        state, _save_dir = load_state(user_id, save_id)
        ph = str(state.get("season_phase") or "").strip().lower()
        if ph == "regular":
            return
        if ph != "preseason":
            raise ValueError(
                f"Bulk simulate seasons: expected preseason phase, got {ph!r}."
            )
        advance_preseason(user_id, save_id, {})
    raise RuntimeError(
        "Bulk simulate seasons: preseason autopilot exceeded iteration limit — reload the save."
    )


def _bulk_sim_regular_until_playoffs(
    user_id: str,
    save_id: str,
    *,
    max_iterations: int = 320,
) -> None:
    for _ in range(max_iterations):
        state, _save_dir = load_state(user_id, save_id)
        ph = str(state.get("season_phase") or "").strip().lower()
        if ph == "playoffs":
            return
        if ph != "regular":
            raise ValueError(
                f"Bulk simulate seasons: expected regular season, got {ph!r}."
            )
        weeks = state.get("weeks") or []
        cw = int(state.get("current_week", 1))
        if cw > len(weeks):
            return
        sim_week(user_id, save_id)
    raise RuntimeError(
        "Bulk simulate seasons: regular season exceeded iteration limit (unexpected schedule length)."
    )


def _bulk_complete_playoffs_and_finish_season(
    user_id: str,
    save_id: str,
    *,
    max_iterations: int = 96,
) -> None:
    for _ in range(max_iterations):
        state, _save_dir = load_state(user_id, save_id)
        ph = str(state.get("season_phase") or "").strip().lower()
        if ph != "playoffs":
            return
        playoffs = state.get("playoffs") if isinstance(state.get("playoffs"), dict) else {}
        if _playoffs_global_completed(playoffs):
            finish_season(user_id, save_id, bulk_autopilot=True)
            return
        if not _bulk_playoffs_bracket_started(state):
            sim_playoffs(user_id, save_id)
        else:
            sim_playoff_round(user_id, save_id)
    raise RuntimeError(
        "Bulk simulate seasons: playoffs did not resolve — try advancing playoffs manually once."
    )


def simulate_seasons_forward(user_id: str, save_id: str, seasons: int) -> Dict[str, Any]:
    """
    Fast-forward the save by completing N full football years (remainder of current year if needed,
    then offseason autoplay, preseason autoplay, repeat). Ends at regular season Week 1 after the last year.

    Coaching carousel: firings/hires/promotions run as normal; the user's coach also submits ranked job
    preferences to open vacancies (high prestige first) so application-based moves can occur.

    Improvements: spends program points on AI-picked upgrades (and may rebalance by downgrading an
    over-built pillar to fund weaker grades). Coach development: uses the same allocation math as CPU coaches.
    """
    seasons_i = int(seasons)
    if seasons_i not in BULK_SIMULATE_SEASONS_OPTIONS:
        raise ValueError("seasons must be 1, 5, 10, or 20")
    if billing_required() and not user_is_entitled(user_id):
        raise ValueError("Multi-season fast-forward requires a full purchase.")

    for _ in range(seasons_i):
        guard = 0
        while True:
            guard += 1
            if guard > 120:
                raise RuntimeError(
                    "Bulk simulate seasons: main loop stalled — save may be in an unexpected phase."
                )
            state, _save_dir = load_state(user_id, save_id)
            phase = str(state.get("season_phase") or "").strip().lower()
            if phase == "done":
                raise ValueError(
                    "This save is archived or marked complete; bulk simulation is unavailable."
                )
            if phase in ("offseason", "preseason"):
                if phase == "offseason":
                    _bulk_run_offseason_autopilot(user_id, save_id)
                _bulk_run_preseason_autopilot(user_id, save_id)
                continue

            if phase == "regular":
                _bulk_sim_regular_until_playoffs(user_id, save_id)
                continue

            if phase == "playoffs":
                _bulk_complete_playoffs_and_finish_season(user_id, save_id)
                _bulk_run_offseason_autopilot(user_id, save_id)
                _bulk_run_preseason_autopilot(user_id, save_id)
                break

            if phase == "season_summary":
                finish_season(user_id, save_id, begin_offseason=True)
                continue

            raise ValueError(
                f"Cannot simulate seasons from season_phase={phase!r}; advance the save in-game first."
            )

    state_out, _save_dir = load_state(user_id, save_id)
    return {"state": state_out, "seasons_simulated": seasons_i}

