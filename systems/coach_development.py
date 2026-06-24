"""Coach development via CP-threshold allocations (offseason stage)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models.coach import Coach

COACH_DEV_SKILLS: Tuple[str, ...] = (
    "playcalling",
    "player_development",
    "community_outreach",
    "culture",
    "recruiting",
    "scheme_teach",
)

CP_ECONOMY_VERSION = 2

LEVEL_CP_THRESHOLDS: Dict[int, int] = {
    1: 0,
    2: 12,
    3: 28,
    4: 48,
    5: 72,
    6: 100,
    7: 135,
    8: 175,
    9: 220,
    10: 270,
}

LEGACY_LEVEL_CP_THRESHOLDS: Dict[int, int] = {
    1: 0,
    2: 20,
    3: 50,
    4: 90,
    5: 140,
    6: 200,
    7: 275,
    8: 350,
    9: 425,
    10: 500,
}

CREATION_BONUS_CP_DEFAULT = 60.0
CREATION_BONUS_CP_LOW_PRESTIGE = 80.0
CREATION_BONUS_LOW_PRESTIGE_MAX = 5
MIGRATION_CATCHUP_BONUS_CP = 30.0

# Legacy export compatibility for older imports.
CP_PER_SKILL_LEVEL = 2

SEASON_CP_BASE = 10.0
RECORD_CP_PER_WIN_DELTA = 2.5
LOSING_SEASON_PENALTY_CP = 6.0
GOAL_HIT_CP = 8.0
GOAL_MISS_CP = -10.0
LOYALTY_CP_PER_YEAR = 2.0
LOYALTY_CP_CAP = 10.0


def coach_skill_factor(skill_level: int) -> float:
    """Gameplay multiplier for coach skills that affect player development."""
    lv = max(1, min(10, int(skill_level or 5)))
    return 0.50 + (lv / 10.0) * 0.55


def _postseason_tier(
    team_name: str,
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
) -> str:
    if not team_name:
        return "none"
    if team_name == (champion or ""):
        return "champion"
    made = any(
        isinstance(g, dict) and (g.get("home") == team_name or g.get("away") == team_name)
        for g in (bracket_results or [])
    )
    order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
    best = 0
    for g in bracket_results or []:
        if not isinstance(g, dict):
            continue
        if g.get("home") != team_name and g.get("away") != team_name:
            continue
        best = max(best, int(order.get(str(g.get("round") or ""), 0)))
    if best >= 3:
        return "championship"
    if best >= 2:
        return "semifinal"
    if made:
        return "playoffs"
    return "none"


def _goal_evaluation(
    season_goals: Optional[Dict[str, Any]],
    wins: int,
    losses: int,
    achieved_rank: int,
) -> Tuple[bool, bool]:
    """Returns (win_goal_met, stage_goal_met)."""
    win_goal_met = True
    stage_goal_met = True
    if not isinstance(season_goals, dict):
        return True, True

    win_goal = None
    try:
        if season_goals.get("win_goal") is not None:
            win_goal = int(season_goals.get("win_goal"))
    except Exception:
        win_goal = None
    if win_goal is not None:
        win_goal_met = wins >= win_goal

    stage_goal = str(season_goals.get("stage_goal") or "").strip() or None
    if stage_goal == "Just to have fun":
        pass
    elif stage_goal:
        goal_rank = None
        if stage_goal == "Winning Season":
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
                stage_goal_met = False
            elif achieved_rank < goal_rank:
                stage_goal_met = False

    return win_goal_met, stage_goal_met


def _cp_required_for_level(level: int) -> int:
    lv = max(1, min(10, int(level)))
    return int(LEVEL_CP_THRESHOLDS.get(lv, 0))


def _level_from_allocated_cp(cp: float) -> int:
    val = float(cp or 0.0)
    level = 1
    for lv in range(1, 11):
        if val >= LEVEL_CP_THRESHOLDS[lv]:
            level = lv
        else:
            break
    return level


def _legacy_level_from_allocated_cp(cp: float) -> int:
    val = float(cp or 0.0)
    level = 1
    for lv in range(1, 11):
        if val >= LEGACY_LEVEL_CP_THRESHOLDS[lv]:
            level = lv
        else:
            break
    return level


def _normalized_allocations(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    src = raw if isinstance(raw, dict) else {}
    for sk in COACH_DEV_SKILLS:
        try:
            out[sk] = max(0.0, float(src.get(sk, 0.0) or 0.0))
        except Exception:
            out[sk] = 0.0
    return out


def _levels_from_allocations(alloc: Dict[str, float]) -> Dict[str, int]:
    return {sk: _level_from_allocated_cp(float(alloc.get(sk, 0.0) or 0.0)) for sk in COACH_DEV_SKILLS}


def _allocated_total(alloc: Dict[str, float]) -> float:
    return float(sum(float(alloc.get(sk, 0.0) or 0.0) for sk in COACH_DEV_SKILLS))


def _base_allocations_from_coach(coach: Optional[Coach]) -> Dict[str, float]:
    if coach is None:
        return {sk: 0.0 for sk in COACH_DEV_SKILLS}
    out: Dict[str, float] = {}
    for sk in COACH_DEV_SKILLS:
        lv = int(getattr(coach, sk, 5) or 5)
        out[sk] = float(_cp_required_for_level(lv))
    return out


def _postseason_bonus_from_tier(tier: str) -> float:
    return {
        "none": 0.0,
        "playoffs": 6.0,
        "semifinal": 10.0,
        "championship": 14.0,
        "champion": 20.0,
    }.get(tier, 0.0)


def _goal_change_from_flags(has_goal: bool, win_goal_met: bool, stage_goal_met: bool) -> float:
    if not has_goal:
        return 0.0
    return GOAL_HIT_CP if (win_goal_met and stage_goal_met) else GOAL_MISS_CP


def _age_modifier(age: int) -> float:
    a = int(age or 0)
    if a < 40:
        return 2.0
    if a > 60:
        return float(-1 * (a - 60))
    return 0.0


def _loyalty_bonus(coach: Optional[Coach]) -> float:
    if coach is None:
        return 0.0
    years = max(0, int(getattr(coach, "years_at_school", 0) or 0))
    return min(LOYALTY_CP_CAP, float(years * LOYALTY_CP_PER_YEAR))


def creation_bonus_cp_for_prestige(prestige: Optional[int]) -> float:
    p = int(prestige if prestige is not None else 5)
    if p <= CREATION_BONUS_LOW_PRESTIGE_MAX:
        return CREATION_BONUS_CP_LOW_PRESTIGE
    return CREATION_BONUS_CP_DEFAULT


def _loadout_card_ids(loadout: Optional[Dict[str, Any]]) -> List[str]:
    try:
        from systems.coaching_cards import loadout_card_ids

        return loadout_card_ids(loadout)
    except Exception:
        return []


def _card_ledger_from_bank(bank: Optional[Dict[str, Any]]) -> Dict[str, float]:
    if not isinstance(bank, dict):
        return {}
    raw = bank.get("card_ledger")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = max(0.0, float(v or 0.0))
        except Exception:
            continue
    return out


def _refresh_bank_totals(bank: Dict[str, Any]) -> None:
    allocations = _normalized_allocations(bank.get("allocations"))
    allocated_total = round(_allocated_total(allocations), 1)
    cp_total = max(0.0, round(float(bank.get("cp_total", 0.0) or 0.0), 1))
    bank["cp_total"] = cp_total
    bank["allocations"] = allocations
    bank["allocated_total"] = allocated_total
    bank["available_cp"] = round(cp_total - allocated_total, 1)
    bank["levels"] = _levels_from_allocations(allocations)
    bank["thresholds"] = LEVEL_CP_THRESHOLDS
    bank["cp_economy_version"] = CP_ECONOMY_VERSION


def apply_coaching_card_cp_transaction(
    bank: Dict[str, Any],
    old_loadout: Optional[Dict[str, Any]],
    new_loadout: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deduct/refund CP for a coaching-card loadout change. Mutates bank."""
    from systems.coaching_cards import compute_loadout_change_cp

    ledger = _card_ledger_from_bank(bank)
    net_cost, new_ledger, detail = compute_loadout_change_cp(old_loadout, new_loadout, ledger)
    cp_total = max(0.0, round(float(bank.get("cp_total", 0.0) or 0.0) - float(net_cost), 1))
    bank["cp_total"] = cp_total
    bank["card_ledger"] = new_ledger
    bank["last_card_cp_detail"] = detail
    _refresh_bank_totals(bank)
    return detail


def initialize_dynasty_coach_bank(
    coach: Optional[Coach],
    *,
    prestige: Optional[int] = None,
    existing_loadout: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Opening CP bank when a dynasty is created."""
    base_alloc = _base_allocations_from_coach(coach)
    bonus = creation_bonus_cp_for_prestige(prestige)
    cp_total = round(_allocated_total(base_alloc) + bonus, 1)
    bank: Dict[str, Any] = {
        "cp_total": cp_total,
        "allocated_total": round(_allocated_total(base_alloc), 1),
        "available_cp": round(cp_total - _allocated_total(base_alloc), 1),
        "allocations": base_alloc,
        "levels": _levels_from_allocations(base_alloc),
        "thresholds": LEVEL_CP_THRESHOLDS,
        "card_ledger": {},
        "cp_economy_version": CP_ECONOMY_VERSION,
        "creation_bonus_cp": bonus,
        "breakdown": None,
        "applied": None,
    }
    if coach is not None and existing_loadout is not None:
        apply_coaching_card_cp_transaction(bank, None, existing_loadout)
    elif coach is not None:
        loadout = getattr(coach, "coaching_cards", None)
        if isinstance(loadout, dict) and _loadout_card_ids(loadout):
            apply_coaching_card_cp_transaction(bank, None, loadout)
    return bank


def build_initial_coach_dev_banks_for_dynasty(
    teams: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name, team in (teams or {}).items():
        coach = getattr(team, "coach", None)
        prestige = getattr(team, "prestige", 5)
        out[str(name)] = initialize_dynasty_coach_bank(coach, prestige=prestige)
    return out


def _remap_legacy_allocation(cp: float) -> float:
    level = _legacy_level_from_allocated_cp(cp)
    return float(_cp_required_for_level(level))


def migrate_coach_dev_bank(bank: Dict[str, Any], coach: Optional[Coach] = None) -> bool:
    """One-time migration from legacy CP economy to v2."""
    if int(bank.get("cp_economy_version", 0) or 0) >= CP_ECONOMY_VERSION:
        return False

    old_alloc = _normalized_allocations(bank.get("allocations"))
    new_alloc = {sk: _remap_legacy_allocation(float(old_alloc.get(sk, 0.0) or 0.0)) for sk in COACH_DEV_SKILLS}
    if not any(old_alloc.values()) and coach is not None:
        new_alloc = _base_allocations_from_coach(coach)

    old_total = float(bank.get("cp_total", 0.0) or 0.0)
    if old_total <= 0 and coach is not None:
        old_total = _allocated_total(_base_allocations_from_coach(coach))

    scaled_total = round(old_total * 0.45 + MIGRATION_CATCHUP_BONUS_CP, 1)
    new_allocated = round(_allocated_total(new_alloc), 1)
    if scaled_total < new_allocated:
        scaled_total = new_allocated

    bank["cp_total"] = scaled_total
    bank["allocations"] = new_alloc
    bank["card_ledger"] = _card_ledger_from_bank(bank)
    bank["cp_economy_version"] = CP_ECONOMY_VERSION
    bank["thresholds"] = LEVEL_CP_THRESHOLDS

    if coach is not None:
        loadout = getattr(coach, "coaching_cards", None)
        if isinstance(loadout, dict) and _loadout_card_ids(loadout) and not bank["card_ledger"]:
            apply_coaching_card_cp_transaction(bank, None, loadout)
        else:
            _refresh_bank_totals(bank)
    else:
        _refresh_bank_totals(bank)
    return True


def migrate_state_coach_dev_banks(state: Dict[str, Any], teams: Optional[Dict[str, Any]] = None) -> bool:
    changed = False
    banks = state.get("offseason_coach_dev_banks")
    if not isinstance(banks, dict):
        banks = {}
    team_map = teams or {}
    if not team_map:
        for row in state.get("teams") or []:
            if isinstance(row, dict) and row.get("name"):
                team_map[str(row["name"])] = row

    for name, bank in list(banks.items()):
        if not isinstance(bank, dict):
            continue
        coach = None
        t = team_map.get(name) if isinstance(team_map, dict) else None
        if t is not None:
            coach = getattr(t, "coach", None) if not isinstance(t, dict) else (t.get("coach") if isinstance(t.get("coach"), dict) else None)
        if migrate_coach_dev_bank(bank, coach=coach if hasattr(coach, "playcalling") else None):
            changed = True

    legacy = state.get("offseason_coach_dev_bank")
    if isinstance(legacy, dict):
        user_team = str(state.get("user_team") or "")
        coach = None
        ut = team_map.get(user_team) if user_team else None
        if ut is not None and hasattr(ut, "coach"):
            coach = ut.coach
        if migrate_coach_dev_bank(legacy, coach=coach):
            changed = True
            if user_team:
                banks[user_team] = legacy
            changed = True

    if changed:
        state["offseason_coach_dev_banks"] = banks
        user_team = str(state.get("user_team") or "")
        if user_team and isinstance(banks.get(user_team), dict):
            state["offseason_coach_dev_bank"] = banks[user_team]
    return changed


def compute_season_cp_change(
    team_name: str,
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    season_goals: Optional[Dict[str, Any]],
    coach: Optional[Coach] = None,
) -> Tuple[float, Dict[str, Any]]:
    srow = (standings or {}).get(team_name) or {}
    wins = int(srow.get("wins", 0) or 0)
    losses = int(srow.get("losses", 0) or 0)

    tier = _postseason_tier(team_name, standings, bracket_results, champion)
    achieved_rank = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(tier, 0)
    win_goal_met, stage_goal_met = _goal_evaluation(season_goals, wins, losses, achieved_rank)
    has_goal = isinstance(season_goals, dict) and (
        season_goals.get("win_goal") is not None or str(season_goals.get("stage_goal") or "").strip()
    )

    record_cp = (wins - losses) * RECORD_CP_PER_WIN_DELTA
    playoffs_bonus = _postseason_bonus_from_tier(tier)
    goal_change = _goal_change_from_flags(has_goal, win_goal_met, stage_goal_met)
    losing_season_penalty = LOSING_SEASON_PENALTY_CP if wins < losses else 0.0
    loyalty_bonus = _loyalty_bonus(coach)
    age_mod = _age_modifier(int(getattr(coach, "age", 35) if coach is not None else 35))

    cp_change = (
        SEASON_CP_BASE
        + record_cp
        + playoffs_bonus
        + goal_change
        + loyalty_bonus
        - losing_season_penalty
        + age_mod
    )

    breakdown = {
        "wins": wins,
        "losses": losses,
        "base_cp": SEASON_CP_BASE,
        "record_cp": record_cp,
        "postseason_tier": tier,
        "playoffs_bonus": playoffs_bonus,
        "win_goal_met": win_goal_met,
        "stage_goal_met": stage_goal_met,
        "goal_cp": goal_change,
        "loyalty_bonus": loyalty_bonus,
        "losing_season_penalty": -losing_season_penalty,
        "age_modifier": age_mod,
        "cp_change": cp_change,
    }
    return round(cp_change, 1), breakdown


def compute_coach_development_bank(
    team_name: str,
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    season_goals: Optional[Dict[str, Any]],
    coach: Optional[Coach] = None,
    existing_bank: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one team's CP bank and carry forward prior allocations."""
    cp_change, breakdown = compute_season_cp_change(
        team_name, standings, bracket_results, champion, season_goals, coach=coach
    )

    base_alloc = _base_allocations_from_coach(coach)
    base_total = round(_allocated_total(base_alloc), 1)
    prior_total = base_total
    if isinstance(existing_bank, dict):
        migrate_coach_dev_bank(existing_bank, coach=coach)
        try:
            prior_total = float(existing_bank.get("cp_total", base_total) or base_total)
        except Exception:
            prior_total = base_total
    cp_total = max(0.0, round(prior_total + cp_change, 1))

    if isinstance(existing_bank, dict) and isinstance(existing_bank.get("allocations"), dict):
        allocations = _normalized_allocations(existing_bank.get("allocations"))
        card_ledger = _card_ledger_from_bank(existing_bank)
    else:
        allocations = base_alloc
        card_ledger = {}

    allocated_total = round(_allocated_total(allocations), 1)
    available_cp = round(cp_total - allocated_total, 1)
    levels = _levels_from_allocations(allocations)

    breakdown["prior_cp_total"] = prior_total
    breakdown["wins_cp"] = breakdown.get("record_cp", 0)  # legacy UI key
    breakdown["losses_cp"] = 0.0

    return {
        "cp_total": cp_total,
        "allocated_total": allocated_total,
        "available_cp": available_cp,
        "allocations": allocations,
        "levels": levels,
        "thresholds": LEVEL_CP_THRESHOLDS,
        "card_ledger": card_ledger,
        "cp_economy_version": CP_ECONOMY_VERSION,
        "breakdown": breakdown,
        "applied": None,
    }


def build_offseason_coach_dev_banks_for_league(
    team_names: List[str],
    standings: Dict[str, Any],
    bracket_results: List[Dict[str, Any]],
    champion: str,
    user_team: Optional[str],
    season_goals: Optional[Dict[str, Any]],
    coaches_by_team: Optional[Dict[str, Coach]] = None,
    existing_banks: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """One CP bank per team. Only user team applies season goals."""
    out: Dict[str, Dict[str, Any]] = {}
    for tn in team_names:
        goals = season_goals if tn == user_team else None
        coach = (coaches_by_team or {}).get(tn) if isinstance(coaches_by_team, dict) else None
        prior = (existing_banks or {}).get(tn) if isinstance(existing_banks, dict) else None
        out[tn] = compute_coach_development_bank(tn, standings, bracket_results, champion, goals, coach=coach, existing_bank=prior)
    return out


def _ai_target_allocations(coach: Coach, cp_total: float) -> Dict[str, float]:
    """AI: fit to pool, preserving coach identity using threshold steps."""
    levels = {sk: max(1, min(10, int(getattr(coach, sk, 5) or 5))) for sk in COACH_DEV_SKILLS}

    def needed() -> float:
        return float(sum(_cp_required_for_level(levels[sk]) for sk in COACH_DEV_SKILLS))

    total = needed()
    while total > cp_total + 1e-6:
        candidates = sorted(COACH_DEV_SKILLS, key=lambda sk: (levels[sk], sk), reverse=True)
        lowered = False
        for sk in candidates:
            if levels[sk] <= 1:
                continue
            levels[sk] -= 1
            lowered = True
            break
        total = needed()
        if not lowered:
            break

    while True:
        candidates = sorted(COACH_DEV_SKILLS, key=lambda sk: (levels[sk], sk))
        raised = False
        for sk in candidates:
            lv = levels[sk]
            if lv >= 10:
                continue
            inc = _cp_required_for_level(lv + 1) - _cp_required_for_level(lv)
            if total + inc <= cp_total + 1e-6:
                levels[sk] += 1
                total += inc
                raised = True
                break
        if not raised:
            break

    return {sk: float(_cp_required_for_level(levels[sk])) for sk in COACH_DEV_SKILLS}


def apply_ai_coach_season_development(coach: Coach, bank: Dict[str, Any]) -> None:
    """CPU coaches auto-adjust threshold allocations to fit their CP pool."""
    if coach is None:
        return
    cp_total = float(bank.get("cp_total", 0.0) or 0.0)
    body = {"coach_dev_allocations": _ai_target_allocations(coach, cp_total)}
    apply_coach_development(coach, bank, body)


def build_bulk_sim_coach_dev_body(coach: Coach, bank: Dict[str, Any]) -> Dict[str, Any]:
    """Allocations POST body matching CPU coach dev logic (bulk season simulation)."""
    if coach is None or not isinstance(bank, dict):
        return {}
    cp_total = float(bank.get("cp_total", 0.0) or 0.0)
    return {"coach_dev_allocations": _ai_target_allocations(coach, cp_total)}


def apply_coach_development(coach: Coach, bank: Dict[str, Any], body: Dict[str, Any]) -> None:
    """Apply user/AI CP allocations, then derive levels from thresholds."""
    if coach is None:
        raise ValueError("Missing coach for development")
    payload = body if isinstance(body, dict) else {}
    current_alloc = _normalized_allocations(bank.get("allocations") if isinstance(bank, dict) else None)
    requested = payload.get("coach_dev_allocations")
    alloc = _normalized_allocations(requested if isinstance(requested, dict) else current_alloc)
    cp_total = float(bank.get("cp_total", 0.0) or 0.0)
    alloc_total = round(_allocated_total(alloc), 1)
    if alloc_total > cp_total + 1e-6:
        if alloc_total > 0:
            scale = cp_total / alloc_total
            alloc = {sk: round(float(alloc.get(sk, 0.0) or 0.0) * scale, 1) for sk in COACH_DEV_SKILLS}
        else:
            alloc = {sk: 0.0 for sk in COACH_DEV_SKILLS}
        alloc_total = round(_allocated_total(alloc), 1)

    levels = _levels_from_allocations(alloc)
    before = {sk: int(getattr(coach, sk, 5) or 5) for sk in COACH_DEV_SKILLS}
    for sk in COACH_DEV_SKILLS:
        setattr(coach, sk, int(levels[sk]))
    coach._clamp_skills()
    after = {sk: int(getattr(coach, sk, 5) or 5) for sk in COACH_DEV_SKILLS}

    bank["cp_total"] = round(cp_total, 1)
    bank["allocations"] = alloc
    bank["levels"] = levels
    bank["allocated_total"] = alloc_total
    bank["available_cp"] = round(cp_total - alloc_total, 1)
    bank["thresholds"] = LEVEL_CP_THRESHOLDS
    bank["cp_economy_version"] = CP_ECONOMY_VERSION
    bank["applied"] = {"before_levels": before, "after_levels": after, "allocations": dict(alloc)}
