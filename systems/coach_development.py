"""Coach development via CP-threshold allocations (offseason stage)."""

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

LEVEL_CP_THRESHOLDS: Dict[int, int] = {
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

# Legacy export compatibility for older imports.
CP_PER_SKILL_LEVEL = 2


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
    if stage_goal:
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
    return 1.0 if tier in ("playoffs", "semifinal", "championship", "champion") else 0.0


def _goal_change_from_flags(has_goal: bool, win_goal_met: bool, stage_goal_met: bool) -> float:
    if not has_goal:
        return 0.0
    return 1.0 if (win_goal_met and stage_goal_met) else -2.0


def _age_modifier(age: int) -> float:
    a = int(age or 0)
    if a < 40:
        return 1.0
    if a > 60:
        return float(-2 * (a - 60))
    return 0.0


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
    srow = (standings or {}).get(team_name) or {}
    wins = int(srow.get("wins", 0) or 0)
    losses = int(srow.get("losses", 0) or 0)

    tier = _postseason_tier(team_name, standings, bracket_results, champion)
    achieved_rank = {"none": 0, "playoffs": 1, "semifinal": 2, "championship": 3, "champion": 4}.get(tier, 0)
    win_goal_met, stage_goal_met = _goal_evaluation(season_goals, wins, losses, achieved_rank)
    has_goal = isinstance(season_goals, dict) and (
        season_goals.get("win_goal") is not None or str(season_goals.get("stage_goal") or "").strip()
    )
    playoffs_bonus = _postseason_bonus_from_tier(tier)
    goal_change = _goal_change_from_flags(has_goal, win_goal_met, stage_goal_met)
    losing_season_penalty = 2.0 if wins < losses else 0.0
    age_mod = _age_modifier(int(getattr(coach, "age", 35) if coach is not None else 35))

    cp_change = (
        (wins * 0.5)
        - (losses * 0.5)
        + playoffs_bonus
        + goal_change
        - losing_season_penalty
        + age_mod
    )

    # On first initialization (no existing bank), seed CP from current coach attributes
    # so the coach starts with a baseline that matches their created skill levels.
    base_alloc = _base_allocations_from_coach(coach)
    base_total = round(_allocated_total(base_alloc), 1)
    prior_total = base_total
    if isinstance(existing_bank, dict):
        try:
            prior_total = float(existing_bank.get("cp_total", base_total) or base_total)
        except Exception:
            prior_total = base_total
    cp_total = max(0.0, round(prior_total + cp_change, 1))

    if isinstance(existing_bank, dict) and isinstance(existing_bank.get("allocations"), dict):
        allocations = _normalized_allocations(existing_bank.get("allocations"))
    else:
        allocations = base_alloc
    allocated_total = round(_allocated_total(allocations), 1)
    available_cp = round(cp_total - allocated_total, 1)
    levels = _levels_from_allocations(allocations)

    breakdown = {
        "wins": wins,
        "losses": losses,
        "wins_cp": wins * 0.5,
        "losses_cp": -(losses * 0.5),
        "postseason_tier": tier,
        "playoffs_bonus": playoffs_bonus,
        "win_goal_met": win_goal_met,
        "stage_goal_met": stage_goal_met,
        "goal_cp": goal_change,
        "losing_season_penalty": -losing_season_penalty,
        "age_modifier": age_mod,
        "cp_change": cp_change,
        "prior_cp_total": prior_total,
    }

    return {
        "cp_total": cp_total,
        "allocated_total": allocated_total,
        "available_cp": available_cp,
        "allocations": allocations,
        "levels": levels,
        "thresholds": LEVEL_CP_THRESHOLDS,
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
        # Temporary fail-open behavior: never block offseason advancement on CP overflow.
        # Scale allocations down proportionally to fit the current CP budget.
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
    bank["applied"] = {"before_levels": before, "after_levels": after, "allocations": dict(alloc)}
