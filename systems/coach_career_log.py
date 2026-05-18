"""
Persistent per-coach season log stored on league_save.json.

Coach profile history reads this first, then falls back to league_history standings rows
(where ``coach`` was added later and may be missing on older archives).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def norm_coach_key(name: Optional[str]) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _standings_row(standings: Dict[str, Dict[str, Any]], team: str) -> Dict[str, Any]:
    row = standings.get(team) if isinstance(standings, dict) else None
    return dict(row) if isinstance(row, dict) else {}


def append_season_to_coach_career_log(
    state: Dict[str, Any],
    *,
    year: int,
    team_coaches: Dict[str, str],
    standings: Dict[str, Dict[str, Any]],
) -> None:
    """Snapshot every HC's W-L for the season that just finished."""
    if not isinstance(state, dict):
        return
    log = state.setdefault("coach_career_log", [])
    if not isinstance(log, list):
        log = []
        state["coach_career_log"] = log
    y = int(year)
    seen: set[Tuple[int, str, str]] = set()
    for team, coach_raw in (team_coaches or {}).items():
        team_n = str(team or "").strip()
        coach_n = str(coach_raw or "").strip()
        if not team_n or not coach_n or coach_n == "—":
            continue
        key = (y, team_n, norm_coach_key(coach_n))
        if key in seen:
            continue
        seen.add(key)
        st = _standings_row(standings, team_n)
        log.append(
            {
                "year": y,
                "team": team_n,
                "coach": coach_n,
                "wins": int(st.get("wins", 0) or 0),
                "losses": int(st.get("losses", 0) or 0),
            }
        )


def rebuild_coach_career_log_from_league_history(
    state: Dict[str, Any],
    league_history: Dict[str, Any],
    *,
    merge: bool = True,
) -> bool:
    """
    Backfill career log entries from archived seasons that recorded ``coach`` on standings rows.
    Returns True if state was changed.
    """
    if not isinstance(state, dict) or not isinstance(league_history, dict):
        return False
    seasons = league_history.get("seasons") or []
    if not isinstance(seasons, list):
        return False

    existing: List[Dict[str, Any]] = []
    if merge:
        raw = state.get("coach_career_log")
        if isinstance(raw, list):
            existing = [e for e in raw if isinstance(e, dict)]

    keys = {
        (
            int(e.get("year", 0) or 0),
            str(e.get("team") or "").strip(),
            norm_coach_key(str(e.get("coach") or "")),
        )
        for e in existing
        if str(e.get("team") or "").strip() and norm_coach_key(str(e.get("coach") or ""))
    }

    changed = False
    for s in seasons:
        if not isinstance(s, dict):
            continue
        year = s.get("year")
        try:
            y = int(year)
        except (TypeError, ValueError):
            continue
        standings_list = s.get("standings") or []
        if not isinstance(standings_list, list):
            continue
        for st_row in standings_list:
            if not isinstance(st_row, dict):
                continue
            team_n = str(st_row.get("team") or "").strip()
            coach_n = str(st_row.get("coach") or "").strip()
            if not team_n or not coach_n or coach_n == "—":
                continue
            ck = (y, team_n, norm_coach_key(coach_n))
            if ck in keys:
                continue
            keys.add(ck)
            existing.append(
                {
                    "year": y,
                    "team": team_n,
                    "coach": coach_n,
                    "wins": int(st_row.get("wins", 0) or 0),
                    "losses": int(st_row.get("losses", 0) or 0),
                }
            )
            changed = True

    if changed or (not merge and existing):
        existing.sort(key=lambda e: (-int(e.get("year", 0) or 0), str(e.get("team") or "")))
        state["coach_career_log"] = existing[-500:]
        return True
    if not merge and not state.get("coach_career_log"):
        state["coach_career_log"] = []
    return changed


def coach_history_rows_from_career_log(
    coach_name: str,
    career_log: Any,
) -> List[Dict[str, Any]]:
    """Rows for one coach from ``coach_career_log`` (no postseason labels)."""
    target = norm_coach_key(coach_name)
    if not target or not isinstance(career_log, list):
        return []
    rows: List[Dict[str, Any]] = []
    for e in career_log:
        if not isinstance(e, dict):
            continue
        if norm_coach_key(str(e.get("coach") or "")) != target:
            continue
        team_n = str(e.get("team") or "").strip()
        if not team_n:
            continue
        rows.append(
            {
                "year": e.get("year"),
                "team": team_n,
                "wins": int(e.get("wins", 0) or 0),
                "losses": int(e.get("losses", 0) or 0),
                "coach": str(e.get("coach") or "").strip() or "—",
            }
        )
    rows.sort(key=lambda r: int(r.get("year", 0) or 0), reverse=True)
    return rows
