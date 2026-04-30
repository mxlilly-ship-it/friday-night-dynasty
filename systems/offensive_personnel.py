"""
Offensive formation personnel: RB / TE / WR counts on the field (with 5 OL + 1 QB),
snap run/pass ratings from those starters + depth, blended into the game engine baselines.

Counts align with docstrings in ``formation_plays.py`` for each formation label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from models.team import Team

from systems.depth_chart import POSITION_DEPTH, build_depth_chart
from systems.team_ratings import _player_pass_contribution, _player_run_contribution

# (OL on field, RB, TE, WR) — must satisfy OL + 1 QB + RB + TE + WR = 11 (OL is always 5 here).
OFFENSIVE_FORMATION_PERSONNEL: Dict[str, Tuple[int, int, int, int]] = {
    "Dual": (5, 1, 1, 3),
    "Trio": (5, 1, 0, 4),
    "Empty": (5, 0, 0, 5),
    "Pro": (5, 2, 1, 2),
    "Twins": (5, 1, 1, 3),
    "Trey Wing": (5, 1, 2, 2),
    "Wing": (5, 1, 2, 2),
    "Flexbone": (5, 3, 0, 2),
    "Double Wing": (5, 3, 2, 0),
    "Power I": (5, 3, 1, 1),
    "Wing T": (5, 3, 1, 1),
    "Doubles": (5, 1, 1, 3),
}


def _unique_ordered(players: List[Any]) -> List[Any]:
    seen: set[int] = set()
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


def _ol_depth_chain(dc: Any) -> List[Any]:
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("OL", 8)):
        p = dc.get_starter("OL", "offense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _qb_depth_chain(dc: Any) -> List[Any]:
    p = dc.get_starter("QB", "offense", 0)
    return [p] if p is not None else []


def _rb_depth_chain(dc: Any) -> List[Any]:
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("RB", 4)):
        p = dc.get_starter("RB", "offense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _te_depth_chain(dc: Any) -> List[Any]:
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("TE", 2)):
        p = dc.get_starter("TE", "offense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _wr_depth_chain(dc: Any) -> List[Any]:
    chain: List[Any] = []
    for slot in range(POSITION_DEPTH.get("WR", 6)):
        p = dc.get_starter("WR", "offense", slot)
        if p is not None:
            chain.append(p)
    return _unique_ordered(chain)


def _eligible_ol(p: Any) -> bool:
    return p.position == "OL" or (getattr(p, "secondary_position", None) or "") == "OL"


def _eligible_qb(p: Any) -> bool:
    return p.position == "QB" or (getattr(p, "secondary_position", None) or "") == "QB"


def _eligible_rb(p: Any) -> bool:
    return p.position == "RB" or (getattr(p, "secondary_position", None) or "") == "RB"


def _eligible_te(p: Any) -> bool:
    return p.position == "TE" or (getattr(p, "secondary_position", None) or "") == "TE"


def _eligible_wr(p: Any) -> bool:
    return p.position == "WR" or (getattr(p, "secondary_position", None) or "") == "WR"


def _ol_sort_key(p: Any) -> float:
    return (float(getattr(p, "run_blocking", 50)) + float(getattr(p, "pass_blocking", 50)) + float(getattr(p, "strength", 50))) / 3.0


def _qb_sort_key(p: Any) -> float:
    return (float(getattr(p, "throw_power", 50)) + float(getattr(p, "throw_accuracy", 50)) + float(getattr(p, "decisions", 50))) / 3.0


def _rb_sort_key(p: Any) -> float:
    return (
        float(getattr(p, "speed", 50))
        + float(getattr(p, "break_tackle", 50))
        + float(getattr(p, "vision", 50))
        + float(getattr(p, "ball_security", 50))
    ) / 4.0


def _te_sort_key(p: Any) -> float:
    return (float(getattr(p, "catching", 50)) + float(getattr(p, "route_running", 50)) + float(getattr(p, "run_blocking", 50))) / 3.0


def _wr_sort_key(p: Any) -> float:
    return (float(getattr(p, "catching", 50)) + float(getattr(p, "route_running", 50)) + float(getattr(p, "speed", 50))) / 3.0


def _fill_from_chart_then_roster(
    need: int,
    depth_ordered: List[Any],
    roster: List[Any],
    pred: Callable[[Any], bool],
    sort_key: Callable[[Any], float],
) -> List[Any]:
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


def _top_group(roster: List[Any], pred: Callable[[Any], bool], sort_key: Callable[[Any], float], n: int) -> List[Any]:
    pool = [p for p in roster if pred(p)]
    pool.sort(key=sort_key, reverse=True)
    return pool[: max(0, n)]


def _clamp_int(v: float, lo: int = 20, hi: int = 95) -> int:
    return max(lo, min(hi, int(round(v))))


def snap_offensive_ratings(
    team: "Team",
    formation: str,
    baseline: Dict[str, int],
    *,
    mix: float = 0.58,
) -> Dict[str, int]:
    """
    Return ``run`` and ``pass`` ratings (1–100) for this snap from on-field personnel.

    ``baseline`` uses keys ``run`` and ``pass`` (same as ``Game`` after sync_game_ratings).
    """
    key = (formation or "").strip()
    spec = OFFENSIVE_FORMATION_PERSONNEL.get(key)
    if spec is None:
        return {"run": int(baseline["run"]), "pass": int(baseline["pass"])}

    ol_n, rb_n, te_n, wr_n = spec
    roster = list(getattr(team, "roster", None) or [])
    if not roster:
        return {"run": int(baseline["run"]), "pass": int(baseline["pass"])}

    try:
        dc = build_depth_chart(team)
    except Exception:
        dc = None

    if dc is not None:
        ol_players = _fill_from_chart_then_roster(ol_n, _ol_depth_chain(dc), roster, _eligible_ol, _ol_sort_key)
        qb_list = _fill_from_chart_then_roster(1, _qb_depth_chain(dc), roster, _eligible_qb, _qb_sort_key)
        rb_players = _fill_from_chart_then_roster(rb_n, _rb_depth_chain(dc), roster, _eligible_rb, _rb_sort_key)
        te_players = _fill_from_chart_then_roster(te_n, _te_depth_chain(dc), roster, _eligible_te, _te_sort_key)
        wr_players = _fill_from_chart_then_roster(wr_n, _wr_depth_chain(dc), roster, _eligible_wr, _wr_sort_key)
    else:
        ol_players = _top_group(roster, _eligible_ol, _ol_sort_key, ol_n)
        qb_list = _top_group(roster, _eligible_qb, _qb_sort_key, 1)
        rb_players = _top_group(roster, _eligible_rb, _rb_sort_key, rb_n)
        te_players = _top_group(roster, _eligible_te, _te_sort_key, te_n)
        wr_players = _top_group(roster, _eligible_wr, _wr_sort_key, wr_n)

    on_field = ol_players + qb_list + rb_players + te_players + wr_players
    if not on_field:
        return {"run": int(baseline["run"]), "pass": int(baseline["pass"])}

    snap_run = sum(_player_run_contribution(p) for p in on_field) / len(on_field)
    snap_pass = sum(_player_pass_contribution(p) for p in on_field) / len(on_field)

    snap_run_i = _clamp_int(snap_run)
    snap_pass_i = _clamp_int(snap_pass)

    m = max(0.0, min(0.85, mix))
    return {
        "run": _clamp_int(m * snap_run_i + (1.0 - m) * float(baseline["run"])),
        "pass": _clamp_int(m * snap_pass_i + (1.0 - m) * float(baseline["pass"])),
    }


def formation_offensive_personnel_tuple(formation: Optional[str]) -> Optional[Tuple[int, int, int, int]]:
    """Return (OL, RB, TE, WR) counts for a formation label, or None if unknown."""
    if not formation:
        return None
    return OFFENSIVE_FORMATION_PERSONNEL.get(str(formation).strip())
