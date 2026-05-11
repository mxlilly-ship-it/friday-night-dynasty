"""
Coaching carousel: phased offseason hiring/firing (after program Improvements).
Scripts use run_carousel_full (single shot).
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from models.coach import Coach
from systems.coach_generator import generate_coach_for_team
from systems.coach_career_system import (
    PROMOTION_ACCEPT_BASE,
    _apply_scheme_change,
    _coach_success_score,
    _consider_scheme_change,
    _consecutive_losing_seasons,
    _get_playoff_teams,
    _retirement_chance,
    _seasons_since_playoff,
    _should_fire,
)
from systems.prestige_system import get_coach_skill_sum
from systems.save_system import coach_from_dict, coach_to_dict


def _random_exit_chance(coach: Coach, hot_seat: int, prestige: int) -> float:
    """
    Chance a coach steps away for non-firing reasons (burnout / life change /
    lateral move / family). Tuned so stage-1 carousel churn averages roughly
    8-12 openings per year on a ~108-team league (was ~3-4 at base 0.025).
    Pressure and age still bias the distribution upward.
    """
    chance = 0.075
    age = int(getattr(coach, "age", 50) or 50)
    if age >= 67:
        chance += 0.05
    elif age >= 62:
        chance += 0.03
    elif age >= 57:
        chance += 0.018

    # Extra churn when pressure is elevated even if not fired.
    chance += max(0.0, (float(hot_seat) - 55.0) * 0.0022)

    # Lower-prestige jobs tend to be less stable over time.
    chance += max(0.0, (5.0 - float(prestige)) * 0.0065)
    return max(0.015, min(0.28, chance))


def _standings_row_for_team(
    team_name: str,
    seasons: List[Dict[str, Any]],
    standings: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    if seasons:
        lst = seasons[-1].get("standings") or []
        sm = {s["team"]: s for s in lst if isinstance(s, dict) and s.get("team")}
        return dict(sm.get(team_name) or {})
    if standings and team_name in standings:
        s = standings[team_name]
        pf = int(s.get("points_for", 0) or 0)
        pa = int(s.get("points_against", 0) or 0)
        return {
            "wins": int(s.get("wins", 0) or 0),
            "losses": int(s.get("losses", 0) or 0),
            "points_for": pf,
            "points_against": pa,
            "point_diff": pf - pa,
        }
    return {}


def compute_hot_seat(
    team_name: str,
    seasons: List[Dict[str, Any]],
    standings_row: Dict[str, Any],
    season_goals: Optional[Dict[str, Any]],
) -> int:
    """0–100 pressure index."""
    if not seasons:
        return 0
    losing_streak = _consecutive_losing_seasons(team_name, seasons)
    playoff_drought = _seasons_since_playoff(team_name, seasons)
    score = 0
    score += min(45, losing_streak * 12)
    score += min(35, playoff_drought * 5)
    wins = int(standings_row.get("wins", 0) or 0)
    losses = int(standings_row.get("losses", 0) or 0)
    if wins + losses > 0 and losses > wins:
        score += 12
    if wins <= 2 and losses >= 8:
        score += 18
    if isinstance(season_goals, dict):
        wg = season_goals.get("win_goal")
        try:
            wgi = int(wg) if wg is not None else None
        except Exception:
            wgi = None
        if wgi is not None and wins < wgi:
            score += 15
        stg = str(season_goals.get("stage_goal") or "").strip()
        if stg and seasons:
            last = seasons[-1]
            champion = str(last.get("state_champion") or "")
            runner_up = str(last.get("runner_up") or "")
            playoff = _get_playoff_teams(last.get("standings") or [], 8)
            tier = 0
            if team_name == champion:
                tier = 4
            elif team_name == runner_up:
                tier = 3
            elif team_name in playoff:
                br = last.get("bracket_results") or []
                best = 0
                order = {"Quarterfinal": 1, "Semifinal": 2, "Championship": 3}
                for g in br:
                    if not isinstance(g, dict):
                        continue
                    if g.get("home") != team_name and g.get("away") != team_name:
                        continue
                    best = max(best, int(order.get(str(g.get("round") or ""), 0)))
                if best >= 3:
                    tier = 2
                elif best >= 2:
                    tier = 1
                else:
                    tier = 1
            need = 0
            if stg == "Winning Season":
                need = 0 if wins >= losses else 999
            elif stg == "Playoffs":
                need = 1
            elif stg == "Semifinal":
                need = 2
            elif stg == "State Championship":
                need = 3
            elif stg == "Title Winner":
                need = 4
            if need == 999:
                score += 12
            elif need > 0 and tier < need:
                score += 15
    return min(100, int(round(score)))


def _maybe_fire_coach(
    name: str,
    team: Any,
    coach: Coach,
    seasons: List[Dict[str, Any]],
    standings_row: Dict[str, Any],
    season_goals: Optional[Dict[str, Any]],
    user_team: Optional[str],
    events: List[Dict[str, Any]],
    unemployed: List[Coach],
    vacancies: List[str],
    coach_changes: Dict[str, Tuple[float, float]],
    hot_seat_by_team: Dict[str, int],
    *,
    allow_user_coach_firing: bool = True,
) -> bool:
    prestige = getattr(team, "prestige", 5) or 5
    hs = compute_hot_seat(name, seasons, standings_row, season_goals if name == user_team else None)
    coach.hot_seat = hs
    hot_seat_by_team[name] = hs
    if name == user_team and str(user_team or "") and not allow_user_coach_firing:
        return False
    # Lowered thresholds (88→78, 92→82) so year-2+ stage-1 churn also lifts a bit and
    # genuinely under-pressure coaches get axed; year-1 hot-seats top out around 30
    # (no losing streak yet) so this only matters once history accumulates.
    threshold = 78 if name == user_team else 82
    if _should_fire(name, prestige, seasons) or hs >= threshold:
        events.append(
            {
                "type": "firing",
                "team": name,
                "coach": coach.name,
                "detail": f"{name} fires {coach.name}" + (f" (hot seat {hs})" if hs >= 70 else ""),
                "hot_seat": hs,
            }
        )
        unemployed.append(coach)
        old_skill = get_coach_skill_sum(coach)
        team.coach = None
        vacancies.append(name)
        coach_changes[name] = (old_skill, 3.0)
        return True
    return False


def _pop_unemployed_user_coach(unemployed: List[Coach], user_coach_name: Optional[str]) -> Optional[Coach]:
    """Remove and return the user's coach from the unemployed list (after a firing)."""
    if not user_coach_name or not isinstance(unemployed, list):
        return None
    tgt = str(user_coach_name).strip().lower()
    if not tgt:
        return None
    for idx, c in enumerate(unemployed):
        if c and str(c.name or "").strip().lower() == tgt:
            return unemployed.pop(idx)
    return None


def _try_user_application_hire(
    vacancy: str,
    team_by_name: Dict[str, Any],
    employed_coaches: Dict[str, Tuple[str, Coach]],
    coach_changes: Dict[str, Tuple[float, float]],
    events: List[Dict[str, Any]],
    vacancies: List[str],
    job_applications: List[str],
    user_team: str,
    hiring_team: Any,
    hiring_prestige: int,
    unemployed: List[Coach],
    user_coach_name: Optional[str],
) -> bool:
    """
    User applies to vacant HC jobs ranked in job_applications (destination schools).
    Resolved before CPU promotion logic for this vacancy.
    """
    if user_team == vacancy:
        return False
    try:
        rank = job_applications.index(vacancy)
    except ValueError:
        return False

    poach_team = team_by_name.get(user_team)
    if not poach_team:
        return False
    hired_coach = getattr(poach_team, "coach", None)
    if hired_coach is None:
        hired_coach = _pop_unemployed_user_coach(unemployed, user_coach_name)

    if hired_coach is None:
        return False

    home_prestige = getattr(poach_team, "prestige", 5) or 5
    # Earlier in the preference list modestly boosts perceived fit / AD interest.
    rank_bonus = 0.04 * max(0.0, float(len(job_applications) - rank - 1))
    accept = PROMOTION_ACCEPT_BASE + (float(hiring_prestige) - float(home_prestige)) * 0.055 + rank_bonus
    accept = max(0.14, min(0.93, accept))
    if random.random() > accept:
        return False

    poach_old_skill = get_coach_skill_sum(hired_coach)
    hiring_team.coach = hired_coach
    hired_coach.years_at_school = 0
    hired_coach.years_since_scheme_change = getattr(hired_coach, "years_since_scheme_change", 0)
    if getattr(poach_team, "coach", None) is hired_coach:
        poach_team.coach = None
    if user_team in employed_coaches:
        del employed_coaches[user_team]
    employed_coaches[vacancy] = (vacancy, hired_coach)
    new_skill = get_coach_skill_sum(hired_coach)
    old_skill = coach_changes.get(vacancy, (3.0, 3.0))[0]
    coach_changes[vacancy] = (old_skill, new_skill)
    coach_changes[user_team] = (poach_old_skill, 3.0)
    events.append(
        {
            "type": "application_hire",
            "team": vacancy,
            "coach": hired_coach.name,
            "from_school": user_team,
            "detail": f"{hired_coach.name} accepts the {vacancy} job (user application — leaves {user_team})",
        }
    )
    if user_team not in vacancies:
        vacancies.append(user_team)
    return True


def _hiring_iteration(
    vacancy: str,
    team_by_name: Dict[str, Any],
    employed_coaches: Dict[str, Tuple[str, Coach]],
    seasons: List[Dict[str, Any]],
    unemployed: List[Coach],
    coach_changes: Dict[str, Tuple[float, float]],
    events: List[Dict[str, Any]],
    vacancies: List[str],
    current_year: int,
    job_applications: Optional[List[str]] = None,
    user_team: Optional[str] = None,
    user_coach_name: Optional[str] = None,
) -> None:
    hiring_team = team_by_name[vacancy]
    hiring_prestige = getattr(hiring_team, "prestige", 5) or 5
    ja = job_applications or []
    if user_team and ja and _try_user_application_hire(
        vacancy,
        team_by_name,
        employed_coaches,
        coach_changes,
        events,
        vacancies,
        ja,
        user_team,
        hiring_team,
        hiring_prestige,
        unemployed,
        user_coach_name,
    ):
        return

    candidates: List[Tuple[float, str, Coach]] = []
    for school, (_, coach) in list(employed_coaches.items()):
        if not coach:
            continue
        school_team = team_by_name.get(school)
        if not school_team:
            continue
        school_prestige = getattr(school_team, "prestige", 5) or 5
        if school_prestige >= hiring_prestige:
            continue
        success = _coach_success_score(school, seasons)
        if success < 1.0:
            continue
        accept = PROMOTION_ACCEPT_BASE + (hiring_prestige - school_prestige) * 0.05
        accept = min(0.95, accept)
        if random.random() > accept:
            continue
        candidates.append((success, school, coach))

    if candidates:
        candidates.sort(key=lambda c: -c[0])
        _, poach_school, hired_coach = candidates[0]
        poach_old_skill = get_coach_skill_sum(hired_coach)
        hiring_team.coach = hired_coach
        hired_coach.years_at_school = 0
        hired_coach.years_since_scheme_change = getattr(hired_coach, "years_since_scheme_change", 0)
        poach_team = team_by_name[poach_school]
        poach_team.coach = None
        del employed_coaches[poach_school]
        employed_coaches[vacancy] = (vacancy, hired_coach)
        new_skill = get_coach_skill_sum(hired_coach)
        old_skill = coach_changes.get(vacancy, (3.0, 3.0))[0]
        coach_changes[vacancy] = (old_skill, new_skill)
        coach_changes[poach_school] = (poach_old_skill, 3.0)
        events.append(
            {
                "type": "promotion",
                "team": vacancy,
                "coach": hired_coach.name,
                "detail": f"{hired_coach.name} leaves {poach_school} for {vacancy}",
                "from_school": poach_school,
            }
        )
        vacancies.append(poach_school)
        return

    if unemployed:
        new_coach = None
        skip = str(user_coach_name or "").strip().lower() or None
        for idx in range(len(unemployed) - 1, -1, -1):
            c = unemployed[idx]
            if skip and str(c.name or "").strip().lower() == skip:
                continue
            new_coach = unemployed.pop(idx)
            break
        if new_coach is None:
            new_coach = generate_coach_for_team(hiring_team)
            new_coach.last_preferred_playbook_change_year = max(1, int(current_year))
    else:
        new_coach = generate_coach_for_team(hiring_team)
        new_coach.last_preferred_playbook_change_year = max(1, int(current_year))
    new_coach.years_at_school = 0
    new_coach.years_since_scheme_change = 0
    hiring_team.coach = new_coach
    new_skill = get_coach_skill_sum(new_coach)
    old_skill = coach_changes.get(vacancy, (3.0, 3.0))[0]
    coach_changes[vacancy] = (old_skill, new_skill)
    events.append({"type": "hire", "team": vacancy, "coach": new_coach.name, "detail": f"{vacancy} hires {new_coach.name}"})
    employed_coaches[vacancy] = (vacancy, new_coach)


def _rebuild_employed(teams: Dict[str, Any]) -> Dict[str, Tuple[str, Coach]]:
    return {
        name: (name, team.coach)
        for name, team in teams.items()
        if getattr(team, "coach", None)
    }


def _job_apps_open_only(vacancies: List[str], job_applications: Optional[List[str]]) -> List[str]:
    if not job_applications:
        return []
    open_set = set(vacancies)
    seen: List[str] = []
    for name in job_applications:
        if name in open_set and name not in seen:
            seen.append(name)
    return seen


def _hiring_loop(
    teams: Dict[str, Any],
    vacancies: List[str],
    unemployed: List[Coach],
    seasons: List[Dict[str, Any]],
    coach_changes: Dict[str, Tuple[float, float]],
    events: List[Dict[str, Any]],
    max_fills: Optional[int],
    current_year: int,
    *,
    job_applications: Optional[List[str]] = None,
    user_team: Optional[str] = None,
    user_coach_name: Optional[str] = None,
) -> Tuple[List[str], List[Coach]]:
    team_by_name = {name: team for name, team in teams.items()}
    employed_coaches = _rebuild_employed(teams)
    fills = 0
    vac = list(vacancies)
    while vac:
        if max_fills is not None and fills >= max_fills:
            break
        vac.sort(key=lambda v: (-(getattr(team_by_name[v], "prestige", 5) or 5), v))
        vacancy = vac.pop(0)
        # Re-evaluate prefs each iteration as the open set evolves.
        ja_eff = _job_apps_open_only(vac + [vacancy], job_applications)
        _hiring_iteration(
            vacancy,
            team_by_name,
            employed_coaches,
            seasons,
            unemployed,
            coach_changes,
            events,
            vac,
            current_year,
            ja_eff,
            user_team,
            user_coach_name,
        )
        fills += 1
        employed_coaches = _rebuild_employed(teams)
    return vac, unemployed


def build_carousel_season_archive(
    seasons_year: int, events: List[Dict[str, Any]], hot_seat_by_team: Dict[str, int]
) -> Dict[str, Any]:
    """Compact coaching carousel recap for saves / UI (shown in postseason history)."""
    ev = list(events or [])
    counts = {
        "retirement": 0,
        "resignation": 0,
        "firing": 0,
        "hire": 0,
        "promotion": 0,
        "application_hire": 0,
        "scheme_change": 0,
    }
    bullets: List[str] = []
    stop = {"retirement", "resignation", "firing", "hire", "promotion", "application_hire", "scheme_change"}
    for e in ev:
        t = str(e.get("type") or "")
        if t in counts:
            counts[t] += 1
        if t in stop and isinstance(e.get("detail"), str) and str(e["detail"]).strip():
            bullets.append(str(e["detail"]).strip())

    headline = (
        f"Year {seasons_year}: {counts['retirement'] + counts['resignation'] + counts['firing']} openings, "
        f"{counts['hire'] + counts['promotion'] + counts['application_hire']} hires"
    )
    return {
        "year": seasons_year,
        "headline": headline,
        "counts": counts,
        "bullets": bullets[-80:],
    }


def _serialize_cc(cc: Dict[str, Tuple[float, float]]) -> Dict[str, List[float]]:
    return {k: [float(v[0]), float(v[1])] for k, v in cc.items()}


def _deserialize_cc(d: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for k, v in (d or {}).items():
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            out[k] = (float(v[0]), float(v[1]))
    return out


def _synthetic_seasons_from_standings(standings: Optional[Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    When league_history has no seasons (new saves, zip bundles), firings and hot-seat logic
    would never run because _should_fire requires seasons. Build one pseudo-season from the
    live standings dict so the carousel still reacts to the year that just finished.
    """
    if not standings:
        return []
    rows: List[Dict[str, Any]] = []
    for team_name, s in standings.items():
        if not isinstance(s, dict):
            continue
        w = int(s.get("wins", 0) or 0)
        l = int(s.get("losses", 0) or 0)
        pf = int(s.get("points_for", 0) or 0)
        pa = int(s.get("points_against", 0) or 0)
        rows.append(
            {
                "team": str(team_name),
                "wins": w,
                "losses": l,
                "points_for": pf,
                "points_against": pa,
                "point_diff": pf - pa,
            }
        )
    if not rows:
        return []
    rows.sort(key=lambda r: (-int(r.get("wins", 0) or 0), -int(r.get("point_diff", 0) or 0)))
    return [
        {
            "standings": rows,
            "state_champion": "",
            "runner_up": "",
            "bracket_results": [],
        }
    ]


def _carousel_init(
    teams: Dict[str, Any],
    seasons: List[Dict[str, Any]],
    standings: Optional[Dict[str, Dict[str, Any]]],
    user_team: Optional[str],
    season_goals: Optional[Dict[str, Any]],
    *,
    allow_user_coach_firing: bool = True,
) -> Tuple[List[str], List[Coach], List[Dict[str, Any]], Dict[str, Tuple[float, float]], Dict[str, int]]:
    events: List[Dict[str, Any]] = []
    coach_changes: Dict[str, Tuple[float, float]] = {}
    hot_seat_by_team: Dict[str, int] = {}
    vacancies: List[str] = []
    unemployed: List[Coach] = []

    for team in teams.values():
        coach = getattr(team, "coach", None)
        if coach:
            coach.age = min(75, coach.age + 1)
            coach.years_at_school = getattr(coach, "years_at_school", 0) + 1
            coach.years_since_scheme_change = getattr(coach, "years_since_scheme_change", 0) + 1

    for name, team in teams.items():
        coach = getattr(team, "coach", None)
        if not coach:
            continue
        if random.random() < _retirement_chance(coach.age):
            events.append(
                {
                    "type": "retirement",
                    "team": name,
                    "coach": coach.name,
                    "detail": f"{coach.name} (age {coach.age}) retires from {name}",
                }
            )
            old_skill = get_coach_skill_sum(coach)
            team.coach = None
            vacancies.append(name)
            coach_changes[name] = (old_skill, 3.0)

    # Random voluntary exits (burnout/life change) to keep carousel turnover realistic.
    for name, team in list(teams.items()):
        coach = getattr(team, "coach", None)
        if not coach or name in vacancies:
            continue
        row = _standings_row_for_team(name, seasons, standings)
        hs = compute_hot_seat(name, seasons, row, season_goals if name == user_team else None)
        coach.hot_seat = hs
        hot_seat_by_team[name] = hs
        prestige = int(getattr(team, "prestige", 5) or 5)
        if random.random() < _random_exit_chance(coach, hs, prestige):
            events.append(
                {
                    "type": "resignation",
                    "team": name,
                    "coach": coach.name,
                    "detail": f"{coach.name} steps away from coaching at {name}",
                    "hot_seat": hs,
                }
            )
            old_skill = get_coach_skill_sum(coach)
            team.coach = None
            vacancies.append(name)
            coach_changes[name] = (old_skill, 3.0)

    for name, team in list(teams.items()):
        coach = getattr(team, "coach", None)
        if not coach or name in vacancies:
            continue
        row = _standings_row_for_team(name, seasons, standings)
        sg = season_goals if name == user_team else None
        _maybe_fire_coach(
            name,
            team,
            coach,
            seasons,
            row,
            sg,
            user_team,
            events,
            unemployed,
            vacancies,
            coach_changes,
            hot_seat_by_team,
            allow_user_coach_firing=allow_user_coach_firing,
        )

    for name, team in teams.items():
        coach = getattr(team, "coach", None)
        if not coach or name in hot_seat_by_team:
            continue
        row = _standings_row_for_team(name, seasons, standings)
        hs = compute_hot_seat(name, seasons, row, season_goals if name == user_team else None)
        coach.hot_seat = hs
        hot_seat_by_team[name] = hs

    return vacancies, unemployed, events, coach_changes, hot_seat_by_team


def run_coach_carousel_step(
    teams: Dict[str, Any],
    league_history: Optional[Dict[str, Any]],
    standings: Optional[Dict[str, Dict[str, Any]]],
    carousel_step: int,
    persisted: Optional[Dict[str, Any]],
    user_team: Optional[str],
    season_goals: Optional[Dict[str, Any]],
    current_year: int = 1,
    job_applications: Optional[List[str]] = None,
    *,
    allow_user_coach_firing: bool = True,
    user_coach_name: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Tuple[float, float]], Dict[str, int]]:
    """
    carousel_step:
      1 — churn only (retire/resign/fire + vacancy list; no hires).
      2 — hiring round one (caps by half the opening count).
      3 — hiring round two (same cap rule).
      4 — finish all hires + optional scheme changes.

    persisted: carry between advances; None only for step 1 (runs init).

    job_applications: ordered school names where the user's coach seeks an HC vacancy (applied in rounds 2–4).
    """
    from systems.league_history import load_league_history

    # Use explicit dict from caller (e.g. stateless zip) even when empty; do not treat {} as "load disk".
    if isinstance(league_history, dict):
        data = league_history
    else:
        data = load_league_history()
    seasons: List[Dict[str, Any]] = list(data.get("seasons") or [])
    if not seasons and standings:
        seasons = _synthetic_seasons_from_standings(standings)

    if persisted is None:
        vacancies, unemployed, events, coach_changes, hot_seat_by_team = _carousel_init(
            teams, seasons, standings, user_team, season_goals, allow_user_coach_firing=allow_user_coach_firing
        )
    else:
        vacancies = list(persisted.get("vacancies") or [])
        unemployed = [coach_from_dict(d) for d in (persisted.get("unemployed") or [])]
        events = list(persisted.get("events") or [])
        coach_changes = _deserialize_cc(persisted.get("coach_changes") or {})
        hot_seat_by_team = dict(persisted.get("hot_seat_by_team") or {})

    if carousel_step == 1:
        out = {
            "vacancies": vacancies,
            "unemployed": [coach_to_dict(c) for c in unemployed],
            "events": events,
            "coach_changes": _serialize_cc(coach_changes),
            "hot_seat_by_team": hot_seat_by_team,
        }
        return out, events, coach_changes, hot_seat_by_team

    if carousel_step == 2:
        n = len(vacancies)
        max_f = max(1, n // 2) if n else None
        vac, unemp = _hiring_loop(
            teams,
            vacancies,
            unemployed,
            seasons,
            coach_changes,
            events,
            max_f,
            current_year,
            job_applications=job_applications,
            user_team=user_team,
            user_coach_name=user_coach_name,
        )
        out = {
            "vacancies": vac,
            "unemployed": [coach_to_dict(c) for c in unemp],
            "events": events,
            "coach_changes": _serialize_cc(coach_changes),
            "hot_seat_by_team": hot_seat_by_team,
        }
        return out, events, coach_changes, hot_seat_by_team

    if carousel_step == 3:
        n = len(vacancies)
        max_f = max(1, n // 2) if n else None
        vac, unemp = _hiring_loop(
            teams,
            vacancies,
            unemployed,
            seasons,
            coach_changes,
            events,
            max_f,
            current_year,
            job_applications=job_applications,
            user_team=user_team,
            user_coach_name=user_coach_name,
        )
        out = {
            "vacancies": vac,
            "unemployed": [coach_to_dict(c) for c in unemp],
            "events": events,
            "coach_changes": _serialize_cc(coach_changes),
            "hot_seat_by_team": hot_seat_by_team,
        }
        return out, events, coach_changes, hot_seat_by_team

    # Step 4: finish hires + scheme
    vac, unemp = _hiring_loop(
        teams,
        vacancies,
        unemployed,
        seasons,
        coach_changes,
        events,
        None,
        current_year,
        job_applications=job_applications,
        user_team=user_team,
        user_coach_name=user_coach_name,
    )
    for team in teams.values():
        coach = getattr(team, "coach", None)
        if not coach or not _consider_scheme_change(coach):
            continue
        change_info = _apply_scheme_change(coach, current_year)
        detail = f"{coach.name} changes scheme at {team.name}"
        if "new_offensive_style" in change_info:
            detail += f" (offense: {change_info['old_offensive_style']} → {change_info['new_offensive_style']})"
        elif "new_defensive_style" in change_info:
            detail += f" (defense: {change_info['old_defensive_style']} → {change_info['new_defensive_style']})"
        elif "new_offensive_formation" in change_info:
            detail += f" (offensive playbook: {change_info['old_offensive_formation']} → {change_info['new_offensive_formation']})"
        elif "new_defensive_formation" in change_info:
            detail += f" (defensive playbook: {change_info['old_defensive_formation']} → {change_info['new_defensive_formation']})"
        evt = {"type": "scheme_change", "team": team.name, "coach": coach.name, "detail": detail}
        evt.update(change_info)
        events.append(evt)

    return None, events, coach_changes, hot_seat_by_team


def run_carousel_full(
    teams: Dict[str, Any],
    league_history: Optional[Dict[str, Any]] = None,
    standings: Optional[Dict[str, Dict[str, Any]]] = None,
    user_team: Optional[str] = None,
    season_goals: Optional[Dict[str, Any]] = None,
    *,
    current_year: int = 1,
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[float, float]]]:
    """Single-shot all four carousel engine steps (scripts / legacy callers)."""
    p: Optional[Dict[str, Any]] = None
    ev: List[Dict[str, Any]] = []
    cc: Dict[str, Tuple[float, float]] = {}
    for step in (1, 2, 3, 4):
        p, ev, cc, _hs = run_coach_carousel_step(
            teams,
            league_history,
            standings,
            step,
            p,
            user_team,
            season_goals,
            current_year,
            None,
        )
    return ev, cc
