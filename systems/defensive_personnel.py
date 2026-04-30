"""
Defensive formation personnel: how many DL / LB / DB are stressed on a snap,
and snap-specific defense ratings derived from the best-fitting roster players.

Blended with team baselines in the game engine so small rosters do not swing wildly.

Player pools prefer **defensive depth chart order** (slot 0 = starter, then depth),
then **roster backfill** by position fit when a group is short.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team

from systems.depth_chart import POSITION_DEPTH, build_depth_chart
from systems.team_ratings import _player_defense_contribution

# Approximate on-field counts (sum to 11) per defensive front / package.
DEFENSIVE_FORMATION_PERSONNEL: Dict[str, Tuple[int, int, int]] = {
    "4-3": (4, 3, 4),
    "3-4": (3, 4, 4),
    "Nickel": (4, 2, 5),
    "Dime": (4, 1, 6),
    "5-2": (5, 2, 4),
    "3-3 Stack": (3, 3, 5),
    "3-3 Stack 3-High": (3, 3, 5),
    "6-2": (6, 2, 3),
}


def _avg_attr(players: List[Any], attr: str, default: float = 50.0) -> float:
    if not players:
        return default
    vals = [float(getattr(p, attr, default)) for p in players]
    return sum(vals) / len(vals)


def _eligible_dl(p: Any) -> bool:
    return p.position in ("DE", "DT") or (getattr(p, "secondary_position", None) or "") in ("DE", "DT")


def _eligible_lb(p: Any) -> bool:
    return p.position == "LB" or (getattr(p, "secondary_position", None) or "") == "LB"


def _eligible_db(p: Any) -> bool:
    return p.position in ("CB", "S") or (getattr(p, "secondary_position", None) or "") in ("CB", "S")


def _dl_sort_key(p: Any) -> float:
    return (
        float(getattr(p, "pass_rush", 50))
        + float(getattr(p, "run_defense", 50))
        + float(getattr(p, "block_shedding", 50))
    ) / 3.0


def _lb_sort_key(p: Any) -> float:
    return (
        float(getattr(p, "tackling", 50))
        + float(getattr(p, "run_defense", 50))
        + float(getattr(p, "coverage", 50))
        + float(getattr(p, "pursuit", 50))
    ) / 4.0


def _db_sort_key(p: Any) -> float:
    return (
        float(getattr(p, "coverage", 50))
        + float(getattr(p, "speed", 50))
        + float(getattr(p, "football_iq", 50))
    ) / 3.0


def _top_group(roster: List[Any], pred: Callable[[Any], bool], sort_key: Callable[[Any], float], n: int) -> List[Any]:
    pool = [p for p in roster if pred(p)]
    pool.sort(key=sort_key, reverse=True)
    return pool[: max(0, n)]


def _unique_ordered(players: List[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for p in players:
        if p is None:
            continue
        k = id(p)
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _dl_depth_chain(dc: Any) -> List[Any]:
    """DE slots in depth order, then DT slots — typical fill for DL personnel."""
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("DE", 4)):
        p = dc.get_starter("DE", "defense", slot)
        if p is not None:
            chain.append(p)
    for slot in range(POSITION_DEPTH.get("DT", 3)):
        p = dc.get_starter("DT", "defense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _lb_depth_chain(dc: Any) -> List[Any]:
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("LB", 5)):
        p = dc.get_starter("LB", "defense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _db_depth_chain(dc: Any) -> List[Any]:
    """CB depth first, then safeties (matches common chart / nickel fill)."""
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("CB", 4)):
        p = dc.get_starter("CB", "defense", slot)
        if p is not None:
            chain.append(p)
    for slot in range(POSITION_DEPTH.get("S", 3)):
        p = dc.get_starter("S", "defense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _fill_from_chart_then_roster(
    need: int,
    depth_ordered: List[Any],
    roster: List[Any],
    pred: Callable[[Any], bool],
    sort_key: Callable[[Any], float],
) -> List[Any]:
    """
    Take up to ``need`` players: walk depth chart order first, then add best
    remaining roster fits (pred) not already chosen.
    """
    chosen: List[Any] = []
    seen: set[int] = set()
    for p in depth_ordered:
        if len(chosen) >= need:
            break
        if p is None or not pred(p) or id(p) in seen:
            continue
        chosen.append(p)
        seen.add(id(p))
    while len(chosen) < need:
        pool = [p for p in roster if pred(p) and id(p) not in seen]
        if not pool:
            break
        best = max(pool, key=sort_key)
        chosen.append(best)
        seen.add(id(best))
    return chosen[:need]


def _rush_metric(players: List[Any]) -> float:
    if not players:
        return 50.0
    return (
        _avg_attr(players, "pass_rush") * 0.65
        + _avg_attr(players, "blitz") * 0.20
        + _avg_attr(players, "block_shedding") * 0.15
    )


def _coverage_metric(players: List[Any]) -> float:
    if not players:
        return 50.0
    return (
        _avg_attr(players, "coverage") * 0.65
        + _avg_attr(players, "football_iq") * 0.20
        + _avg_attr(players, "speed") * 0.15
    )


def _tackle_metric(players: List[Any]) -> float:
    if not players:
        return 50.0
    return (
        _avg_attr(players, "tackling") * 0.65
        + _avg_attr(players, "pursuit") * 0.20
        + _avg_attr(players, "discipline") * 0.15
    )


def _clamp_int(v: float, lo: int = 20, hi: int = 95) -> int:
    return max(lo, min(hi, int(round(v))))


def snap_defensive_ratings(
    team: "Team",
    formation: str,
    baseline: Dict[str, int],
    *,
    mix: float = 0.62,
) -> Dict[str, int]:
    """
    Return defense / def_coverage / def_pass_rush / def_tackling for this snap,
    blending personnel-derived values with the team's normal sim baselines.

    ``baseline`` should match the keys already on ``Game`` from sync_game_ratings /
    calculate_turnover_profile + team defense composite.

    Uses ``build_depth_chart(team)`` so order respects starters and
    ``team.depth_chart_order``; any open spots use the best remaining roster fit.
    """
    key = (formation or "").strip()
    counts = DEFENSIVE_FORMATION_PERSONNEL.get(key)
    if counts is None:
        return {
            "defense": int(baseline["defense"]),
            "def_coverage": int(baseline["def_coverage"]),
            "def_pass_rush": int(baseline["def_pass_rush"]),
            "def_tackling": int(baseline["def_tackling"]),
        }

    dl_n, lb_n, db_n = counts
    roster = list(getattr(team, "roster", None) or [])
    if not roster:
        return {
            "defense": int(baseline["defense"]),
            "def_coverage": int(baseline["def_coverage"]),
            "def_pass_rush": int(baseline["def_pass_rush"]),
            "def_tackling": int(baseline["def_tackling"]),
        }

    try:
        dc = build_depth_chart(team)
    except Exception:
        dc = None

    if dc is not None:
        dl_players = _fill_from_chart_then_roster(dl_n, _dl_depth_chain(dc), roster, _eligible_dl, _dl_sort_key)
        lb_players = _fill_from_chart_then_roster(lb_n, _lb_depth_chain(dc), roster, _eligible_lb, _lb_sort_key)
        db_players = _fill_from_chart_then_roster(db_n, _db_depth_chain(dc), roster, _eligible_db, _db_sort_key)
    else:
        dl_players = _top_group(roster, _eligible_dl, _dl_sort_key, dl_n)
        lb_players = _top_group(roster, _eligible_lb, _lb_sort_key, lb_n)
        db_players = _top_group(roster, _eligible_db, _db_sort_key, db_n)

    # Pass rush: heavier weight on DL when more big bodies are on the field.
    dl_rush = _rush_metric(dl_players)
    lb_rush = _rush_metric(lb_players)
    dl_weight = max(0.48, min(0.92, 0.30 + 0.11 * max(1, len(dl_players))))
    snap_pr = dl_weight * dl_rush + (1.0 - dl_weight) * lb_rush

    # Coverage: more DBs on the field -> coverage rating tracks DB quality more.
    db_cov = _coverage_metric(db_players)
    lb_cov = _coverage_metric(lb_players)
    db_weight = max(0.40, min(0.90, 0.28 + 0.10 * max(1, len(db_players))))
    snap_cov = db_weight * db_cov + (1.0 - db_weight) * lb_cov

    on_field = dl_players + lb_players + db_players
    snap_tackle = _tackle_metric(on_field)

    if on_field:
        snap_def = sum(_player_defense_contribution(p) for p in on_field) / len(on_field)
    else:
        snap_def = float(baseline["defense"])

    snap_pr_i = _clamp_int(snap_pr)
    snap_cov_i = _clamp_int(snap_cov)
    snap_tackle_i = _clamp_int(snap_tackle)
    snap_def_i = _clamp_int(snap_def)

    m = max(0.0, min(0.85, mix))
    out: Dict[str, int] = {
        "defense": _clamp_int(m * snap_def_i + (1.0 - m) * float(baseline["defense"])),
        "def_coverage": _clamp_int(m * snap_cov_i + (1.0 - m) * float(baseline["def_coverage"])),
        "def_pass_rush": _clamp_int(m * snap_pr_i + (1.0 - m) * float(baseline["def_pass_rush"])),
        "def_tackling": _clamp_int(m * snap_tackle_i + (1.0 - m) * float(baseline["def_tackling"])),
    }
    return out


def formation_personnel_tuple(formation: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Return (DL, LB, DB) counts for a formation label, or None if unknown."""
    if not formation:
        return None
    return DEFENSIVE_FORMATION_PERSONNEL.get(str(formation).strip())
