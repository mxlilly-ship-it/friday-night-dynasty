"""
Home game theme nights: preseason selection, win rewards (PP or program funding).

Each home team may assign a theme per regular-season home game. On a win, the
selected reward type pays out at season summary (cash applied at offseason start;
user PP rolls into the Improvements bank).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

THEME_CATALOG: Dict[str, Dict[str, Any]] = {
    # School / community
    "youth_night": {"label": "Youth Night", "pp": 150, "cash": 0, "group": "school_community"},
    "elementary_night": {"label": "Elementary Night", "pp": 0, "cash": 500, "group": "school_community"},
    "teacher_appreciation_night": {"label": "Teacher Appreciation Night", "pp": 100, "cash": 0, "group": "school_community"},
    "senior_night": {"label": "Senior Night", "pp": 200, "cash": 0, "group": "school_community"},
    "homecoming": {"label": "Homecoming", "pp": 300, "cash": 2500, "group": "school_community"},
    "spirit_night": {"label": "Spirit Night", "pp": 200, "cash": 0, "group": "school_community"},
    # Legacy / program history
    "alumni_night": {"label": "Alumni Night", "pp": 0, "cash": 2000, "group": "legacy"},
    "hall_of_fame_night": {"label": "Hall of Fame Night", "pp": 200, "cash": 0, "group": "legacy"},
    "championship_anniversary_night": {"label": "Championship Anniversary Night", "pp": 0, "cash": 1500, "group": "legacy"},
    "jersey_retirement_night": {"label": "Jersey Retirement Night", "pp": 200, "cash": 0, "group": "legacy"},
    "decade_night": {"label": "Decade Night (80s, 90s, etc.)", "pp": 100, "cash": 0, "group": "legacy"},
    "legends_night": {"label": "Legends Night", "pp": 0, "cash": 1000, "group": "legacy"},
    # Community service / honor
    "military_appreciation_night": {"label": "Military Appreciation Night", "pp": 0, "cash": 2000, "group": "community_service"},
    "first_responders_night": {"label": "First Responders Night", "pp": 300, "cash": 0, "group": "community_service"},
    "healthcare_workers_night": {"label": "Healthcare Workers Night", "pp": 200, "cash": 0, "group": "community_service"},
    "community_heroes_night": {"label": "Community Heroes Night", "pp": 200, "cash": 0, "group": "community_service"},
    "local_nonprofit_night": {"label": "Local Nonprofit Night", "pp": 0, "cash": 1500, "group": "community_service"},
    "cancer_awareness_night": {"label": "Cancer Awareness Night", "pp": 200, "cash": 0, "group": "community_service"},
    # Fan experience / atmosphere
    "white_out": {"label": "White Out", "pp": 150, "cash": 0, "group": "fan_experience"},
    "blackout": {"label": "Blackout", "pp": 150, "cash": 0, "group": "fan_experience"},
    "stripe_out": {"label": "Stripe Out", "pp": 150, "cash": 0, "group": "fan_experience"},
    "neon_night": {"label": "Neon Night", "pp": 150, "cash": 0, "group": "fan_experience"},
    "rivalry_night": {"label": "Rivalry Night", "pp": 0, "cash": 4000, "group": "fan_experience"},
}

THEME_GROUP_LABELS: Dict[str, str] = {
    "school_community": "School / community",
    "legacy": "Legacy / program history",
    "community_service": "Community service / honor",
    "fan_experience": "Fan experience / atmosphere",
}


def game_slot_key(week: int, game_index: int) -> str:
    return f"{int(week)}:{int(game_index)}"


def parse_game_slot_key(key: str) -> Optional[Tuple[int, int]]:
    parts = str(key or "").split(":", 1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None


def list_home_games_for_team(state: Dict[str, Any], team_name: str) -> List[Dict[str, Any]]:
    """Regular-season home games for ``team_name`` (week is 1-based)."""
    tn = str(team_name or "").strip()
    if not tn:
        return []
    weeks = state.get("weeks")
    if not isinstance(weeks, list):
        return []
    out: List[Dict[str, Any]] = []
    for wi, wk in enumerate(weeks):
        if not isinstance(wk, list):
            continue
        for gi, sched in enumerate(wk):
            if not isinstance(sched, dict):
                continue
            if str(sched.get("home") or "").strip() != tn:
                continue
            away = str(sched.get("away") or "").strip()
            out.append(
                {
                    "week": wi + 1,
                    "game_index": gi,
                    "opponent": away or "—",
                    "slot_key": game_slot_key(wi + 1, gi),
                }
            )
    return out


def _theme_offers_both(theme_id: str) -> bool:
    meta = THEME_CATALOG.get(theme_id) or {}
    return int(meta.get("pp") or 0) > 0 and int(meta.get("cash") or 0) > 0


def _default_reward_choice(theme_id: str) -> Optional[str]:
    meta = THEME_CATALOG.get(theme_id) or {}
    pp = int(meta.get("pp") or 0)
    cash = int(meta.get("cash") or 0)
    if pp > 0 and cash > 0:
        return None  # caller must choose
    if pp > 0:
        return "pp"
    if cash > 0:
        return "cash"
    return None


def normalize_reward_choice(theme_id: Optional[str], raw_choice: Optional[str]) -> Optional[str]:
    tid = str(theme_id or "").strip()
    if not tid or tid not in THEME_CATALOG:
        return None
    choice = str(raw_choice or "").strip().lower()
    if choice in ("pp", "cash"):
        meta = THEME_CATALOG[tid]
        if choice == "pp" and int(meta.get("pp") or 0) <= 0:
            choice = "cash" if int(meta.get("cash") or 0) > 0 else None
        if choice == "cash" and int(meta.get("cash") or 0) <= 0:
            choice = "pp" if int(meta.get("pp") or 0) > 0 else None
        return choice
    return _default_reward_choice(tid)


def _reward_amounts(theme_id: str, reward_choice: str) -> Tuple[int, int]:
    meta = THEME_CATALOG.get(theme_id) or {}
    pp = int(meta.get("pp") or 0)
    cash = int(meta.get("cash") or 0)
    if reward_choice == "pp":
        return pp, 0
    if reward_choice == "cash":
        return 0, cash
    return 0, 0


def _home_team_won(
    state: Dict[str, Any],
    *,
    week: int,
    game_index: int,
    home_team: str,
) -> Optional[bool]:
    weeks = state.get("weeks")
    results = state.get("week_results")
    if not isinstance(weeks, list) or not isinstance(results, list):
        return None
    wi = int(week) - 1
    gi = int(game_index)
    if wi < 0 or wi >= len(weeks):
        return None
    wk = weeks[wi]
    if not isinstance(wk, list) or gi < 0 or gi >= len(wk):
        return None
    sched = wk[gi]
    if not isinstance(sched, dict):
        return None
    if str(sched.get("home") or "").strip() != str(home_team or "").strip():
        return None
    row = results[wi] if wi < len(results) else None
    if not isinstance(row, list) or gi >= len(row):
        return None
    r = row[gi]
    if not isinstance(r, dict) or not r.get("played"):
        return None
    hs = int(r.get("home_score", 0) or 0)
    ascore = int(r.get("away_score", 0) or 0)
    if hs == ascore:
        return False
    return hs > ascore


def get_team_theme_entry(
    state: Dict[str, Any],
    team_name: str,
    week: int,
    game_index: int,
) -> Optional[Dict[str, Any]]:
    store = state.get("home_game_themes")
    if not isinstance(store, dict):
        return None
    team_map = store.get(str(team_name or "").strip())
    if not isinstance(team_map, dict):
        return None
    entry = team_map.get(game_slot_key(week, game_index))
    return entry if isinstance(entry, dict) else None


def theme_label_for_slot(state: Dict[str, Any], team_name: str, week: int, game_index: int) -> Optional[str]:
    entry = get_team_theme_entry(state, team_name, week, game_index)
    if not entry:
        return None
    tid = str(entry.get("theme_id") or "").strip()
    meta = THEME_CATALOG.get(tid)
    return str(meta.get("label") or tid) if meta else None


def _ensure_theme_store(state: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    raw = state.get("home_game_themes")
    if not isinstance(raw, dict):
        raw = {}
        state["home_game_themes"] = raw
    return raw  # type: ignore[return-value]


def apply_user_home_game_themes(
    state: Dict[str, Any],
    user_team: str,
    selections: Any,
) -> None:
    """Validate and persist user home-game theme picks."""
    ut = str(user_team or "").strip()
    if not ut:
        return
    home_games = list_home_games_for_team(state, ut)
    valid_slots = {g["slot_key"] for g in home_games}
    store = _ensure_theme_store(state)
    team_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(selections, list):
        for row in selections:
            if not isinstance(row, dict):
                continue
            try:
                week = int(row.get("week"))
                gi = int(row.get("game_index"))
            except (TypeError, ValueError):
                continue
            slot = game_slot_key(week, gi)
            if slot not in valid_slots:
                continue
            tid = str(row.get("theme_id") or "").strip()
            if not tid:
                continue
            if tid not in THEME_CATALOG:
                continue
            choice = normalize_reward_choice(tid, row.get("reward_choice"))
            if choice is None and _theme_offers_both(tid):
                continue
            if choice is None:
                choice = _default_reward_choice(tid)
            if choice is None:
                continue
            team_map[slot] = {"theme_id": tid, "reward_choice": choice}
    store[ut] = team_map
    state["home_game_themes_user_confirmed"] = True


def assign_ai_home_game_themes(
    state: Dict[str, Any],
    team_names: List[str],
    user_team: Optional[str],
    *,
    rng: Optional[random.Random] = None,
) -> None:
    """Fill home themes for CPU teams (and any home slots the user left blank)."""
    r = rng or random.Random()
    store = _ensure_theme_store(state)
    theme_ids = list(THEME_CATALOG.keys())
    ut = str(user_team or "").strip()
    for name in team_names:
        tn = str(name or "").strip()
        if not tn:
            continue
        home_games = list_home_games_for_team(state, tn)
        if not home_games:
            continue
        existing = store.get(tn) if isinstance(store.get(tn), dict) else {}
        team_map = dict(existing) if isinstance(existing, dict) else {}
        for g in home_games:
            slot = g["slot_key"]
            if tn == ut and slot in team_map:
                continue
            if slot in team_map and tn != ut:
                continue
            if r.random() < 0.12:
                continue  # leave blank sometimes
            tid = r.choice(theme_ids)
            meta = THEME_CATALOG[tid]
            pp = int(meta.get("pp") or 0)
            cash = int(meta.get("cash") or 0)
            if pp > 0 and cash > 0:
                choice = "cash" if r.random() < 0.45 else "pp"
            elif cash > 0:
                choice = "cash"
            else:
                choice = "pp"
            team_map[slot] = {"theme_id": tid, "reward_choice": choice}
        store[tn] = team_map


def compute_home_theme_rewards_for_team(state: Dict[str, Any], team_name: str) -> Dict[str, Any]:
    """Season-end tally for one team."""
    tn = str(team_name or "").strip()
    store = state.get("home_game_themes")
    team_map = store.get(tn) if isinstance(store, dict) else None
    if not isinstance(team_map, dict):
        team_map = {}

    pp_total = 0
    cash_total = 0
    games: List[Dict[str, Any]] = []

    for slot, entry in team_map.items():
        if not isinstance(entry, dict):
            continue
        parsed = parse_game_slot_key(slot)
        if not parsed:
            continue
        week, gi = parsed
        tid = str(entry.get("theme_id") or "").strip()
        if tid not in THEME_CATALOG:
            continue
        meta = THEME_CATALOG[tid]
        choice = normalize_reward_choice(tid, entry.get("reward_choice"))
        if choice is None:
            continue
        won = _home_team_won(state, week=week, game_index=gi, home_team=tn)
        opponent = "—"
        for g in list_home_games_for_team(state, tn):
            if g["slot_key"] == slot:
                opponent = str(g.get("opponent") or "—")
                break
        pp_amt, cash_amt = (0, 0)
        earned = False
        if won is True:
            pp_amt, cash_amt = _reward_amounts(tid, choice)
            pp_total += pp_amt
            cash_total += cash_amt
            earned = True
        games.append(
            {
                "week": week,
                "game_index": gi,
                "opponent": opponent,
                "theme_id": tid,
                "theme_label": str(meta.get("label") or tid),
                "reward_choice": choice,
                "won": won,
                "earned": earned,
                "pp": pp_amt,
                "cash": cash_amt,
            }
        )

    games.sort(key=lambda x: (int(x.get("week") or 0), int(x.get("game_index") or 0)))
    return {
        "team": tn,
        "pp_total": int(pp_total),
        "cash_total": int(cash_total),
        "games": games,
    }


def compute_league_home_theme_summaries(
    state: Dict[str, Any],
    team_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name in team_names:
        tn = str(name or "").strip()
        if tn:
            out[tn] = compute_home_theme_rewards_for_team(state, tn)
    return out


def apply_home_theme_cash_rewards(teams: Dict[str, Any], summaries: Dict[str, Dict[str, Any]]) -> None:
    for name, team in teams.items():
        row = summaries.get(name) if isinstance(summaries, dict) else None
        if not isinstance(row, dict):
            continue
        cash = int(row.get("cash_total") or 0)
        if cash <= 0:
            continue
        bal = int(getattr(team, "program_funding_balance", 0) or 0)
        team.program_funding_balance = max(0, min(250_000, bal + cash))
