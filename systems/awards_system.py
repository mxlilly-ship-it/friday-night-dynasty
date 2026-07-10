"""
Awards system: statewide POY / OPOY / DPOY and per-class All-State teams (1st, 2nd, HM).
Uses PlayerSeasonStats from the completed season and roster positions from save state.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from systems.game_stats import PlayerSeasonStats, season_player_stable_key

# Slots per tier (24 players): offense 13 + defense 11
ALL_STATE_SLOT_COUNTS: List[Tuple[str, int]] = [
    ("QB", 1),
    ("RB", 2),
    ("WR", 2),
    ("TE", 1),
    ("OL", 5),
    ("K", 1),
    ("P", 1),
    ("DL", 4),
    ("LB", 3),
    ("DB", 4),
]

ROSTER_TO_AWARD_POS: Dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "OL": "OL",
    "K": "K",
    "P": "P",
    "DE": "DL",
    "DT": "DL",
    "LB": "LB",
    "CB": "DB",
    "S": "DB",
}

OFFENSE_AWARD_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "OL", "K", "P"})
DEFENSE_AWARD_POSITIONS = frozenset({"DL", "LB", "DB"})


def _offensive_score(s: PlayerSeasonStats) -> Tuple[int, int]:
    total_yds = s.pass_yds + s.rush_yds + s.rec_yds
    total_td = s.pass_td + s.rush_td + s.rec_td
    return (total_yds, total_td)


def _defensive_score(s: PlayerSeasonStats) -> float:
    return float(s.tackles + s.sacks * 3 + s.interceptions * 5 + s.tfl)


def _overall_score(s: PlayerSeasonStats) -> Tuple[float, int]:
    off_yds, off_td = _offensive_score(s)
    return (off_yds + _defensive_score(s) * 2, off_td)


def _award_position_from_roster(position: str) -> Optional[str]:
    pos = str(position or "").strip().upper()
    return ROSTER_TO_AWARD_POS.get(pos)


def _infer_award_position(s: PlayerSeasonStats) -> Optional[str]:
    """Fallback when roster position missing — avoids classifying pure defenders as RB."""
    roster_pos = _award_position_from_roster(s.position)
    if roster_pos:
        return roster_pos

    pass_impact = s.pass_yds + s.pass_td * 6 if s.att >= 10 else 0
    rush_impact = s.rush_yds + s.rush_td * 6
    rec_impact = s.rec_yds + s.rec_td * 6
    def_impact = s.sacks * 3 + s.tfl * 2 + s.tackles + s.interceptions * 5

    if def_impact > 0 and def_impact >= max(pass_impact, rush_impact, rec_impact):
        if s.sacks >= max(2, s.tackles * 0.15):
            return "DL"
        if s.interceptions >= max(2, s.tackles * 0.2):
            return "DB"
        return "LB"

    if pass_impact >= rush_impact and pass_impact >= rec_impact and s.att >= 20:
        return "QB"
    if rush_impact > rec_impact and rush_impact > 0:
        return "RB"
    if rec_impact > 0:
        return "WR"
    return None


def _team_classifications_from_state(state: Optional[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not state:
        return out
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "").strip()
        if name:
            out[name] = str(t.get("classification") or "Unclassified").strip() or "Unclassified"
    return out


def _team_rush_yards_from_state(state: Optional[Dict[str, Any]]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    if not state:
        return totals
    for wk in state.get("week_results") or []:
        for g in wk or []:
            if not isinstance(g, dict) or not g.get("played"):
                continue
            ts = g.get("team_stats") or {}
            if not isinstance(ts, dict):
                continue
            for team_name, row in ts.items():
                if not isinstance(row, dict):
                    continue
                totals[str(team_name)] = totals.get(str(team_name), 0) + int(row.get("rush_yards", 0) or 0)
    return totals


def _ol_depth_slot(team_name: str, player_name: str, state: Optional[Dict[str, Any]]) -> int:
    """Lower is better (starter). Default 4 if unknown."""
    if not state:
        return 4
    for t in state.get("teams") or []:
        if not isinstance(t, dict) or str(t.get("name") or "") != team_name:
            continue
        dc = t.get("depth_chart") or {}
        off = dc.get("offense") or {}
        ol_slots = off.get("OL") or []
        for idx, slot in enumerate(ol_slots):
            if isinstance(slot, dict) and str(slot.get("name") or "") == player_name:
                return idx
        break
    return 4


def _position_score(
    s: PlayerSeasonStats,
    award_pos: str,
    *,
    team_rush_yards: Dict[str, int],
    state: Optional[Dict[str, Any]],
) -> float:
    if award_pos == "QB":
        return float(s.pass_yds + s.pass_td * 6 - s.int_thrown * 3)
    if award_pos == "RB":
        return float(s.rush_yds + s.rush_td * 6 + s.rec_yds * 0.3)
    if award_pos in ("WR", "TE"):
        return float(s.rec_yds + s.rec_td * 6 + s.rec * 0.5)
    if award_pos == "DL":
        return float(s.sacks * 3 + s.tfl * 2 + s.tackles * 0.5)
    if award_pos == "LB":
        return float(s.tackles + s.sacks * 3 + s.tfl * 2 + s.interceptions * 5)
    if award_pos == "DB":
        return float(s.interceptions * 5 + s.tackles + s.tfl)
    if award_pos == "K":
        fg_pct = (s.fg_made / s.fg_att) if s.fg_att else 0.0
        return float(s.fg_made * 3 + fg_pct * 50 + s.xp_made)
    if award_pos == "P":
        if s.punts <= 0:
            return 0.0
        avg = s.punt_yards / s.punts
        return float(avg * min(s.punts, 60))
    if award_pos == "OL":
        team_rush = float(team_rush_yards.get(s.team_name, 0))
        slot = _ol_depth_slot(s.team_name, s.player_name, state)
        return team_rush - slot * 25.0
    return 0.0


def _meets_threshold(s: PlayerSeasonStats, award_pos: str, *, honorable: bool) -> bool:
    if honorable:
        if award_pos == "OL":
            return str(s.position or "").upper() == "OL"
        return _position_score(s, award_pos, team_rush_yards={}, state=None) > 0

    if award_pos == "QB":
        return s.att >= 30 or s.pass_yds >= 150
    if award_pos == "RB":
        return s.rush_yds >= 80
    if award_pos in ("WR", "TE"):
        return s.rec >= 6 or s.rec_yds >= 50
    if award_pos == "OL":
        return str(s.position or "").upper() == "OL"
    if award_pos == "K":
        return s.fg_att >= 2 or s.xp_att >= 5
    if award_pos == "P":
        return s.punts >= 4
    if award_pos == "DL":
        return s.sacks >= 1 or s.tackles >= 8
    if award_pos == "LB":
        return s.tackles >= 12
    if award_pos == "DB":
        return s.interceptions >= 1 or s.tackles >= 10
    return False


def _apply_roster_positions(
    stats_map: Dict[int, PlayerSeasonStats],
    state: Optional[Dict[str, Any]],
) -> None:
    if not state:
        return
    roster_pos: Dict[Tuple[str, str], str] = {}
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        team_name = str(t.get("name") or "").strip()
        for p in t.get("roster") or []:
            if isinstance(p, dict):
                pname = str(p.get("name") or "").strip()
                if team_name and pname:
                    roster_pos[(team_name, pname)] = str(p.get("position") or "").strip()
    for s in stats_map.values():
        if not s.position:
            s.position = roster_pos.get((s.team_name, s.player_name), "")


def _ensure_roster_award_candidates(
    stats_map: Dict[int, PlayerSeasonStats],
    state: Optional[Dict[str, Any]],
) -> None:
    """OL / K / P may have no skill stats — still eligible from roster."""
    if not state:
        return
    for t in state.get("teams") or []:
        if not isinstance(t, dict):
            continue
        team_name = str(t.get("name") or "").strip()
        if not team_name:
            continue
        for p in t.get("roster") or []:
            if not isinstance(p, dict):
                continue
            pname = str(p.get("name") or "").strip()
            if not pname:
                continue
            roster_pos = str(p.get("position") or "").strip()
            award_pos = _award_position_from_roster(roster_pos)
            if award_pos not in ("OL", "K", "P"):
                continue
            key = season_player_stable_key(team_name, pname)
            if key not in stats_map:
                stats_map[key] = PlayerSeasonStats(
                    player_name=pname,
                    team_name=team_name,
                    position=roster_pos,
                )
            elif not stats_map[key].position:
                stats_map[key].position = roster_pos


def _player_entry_dict(
    s: PlayerSeasonStats,
    award_pos: str,
    classification: str,
    score: float,
) -> Dict[str, Any]:
    return {
        "position": award_pos,
        "name": s.player_name,
        "team": s.team_name,
        "classification": classification,
        "score": round(score, 2),
        "stats": {
            "pass_yds": s.pass_yds,
            "pass_td": s.pass_td,
            "rush_yds": s.rush_yds,
            "rush_td": s.rush_td,
            "rec_yds": s.rec_yds,
            "rec_td": s.rec_td,
            "rec": s.rec,
            "tackles": s.tackles,
            "sacks": s.sacks,
            "tfl": s.tfl,
            "interceptions": s.interceptions,
            "fg_made": s.fg_made,
            "fg_att": s.fg_att,
            "xp_made": s.xp_made,
            "punts": s.punts,
            "punt_yards": s.punt_yards,
        },
    }


def _pick_statewide_award(
    stats_map: Dict[int, PlayerSeasonStats],
    key_fn: Callable[[PlayerSeasonStats], Any],
    filter_fn: Callable[[PlayerSeasonStats], bool],
    stat_fields: List[str],
) -> Optional[Dict[str, Any]]:
    candidates = [s for s in stats_map.values() if filter_fn(s)]
    if not candidates:
        return None
    best = max(candidates, key=key_fn)
    team_class = ""
    out: Dict[str, Any] = {"name": best.player_name, "team": best.team_name, "classification": team_class}
    for f in stat_fields:
        out[f] = getattr(best, f, 0)
    return out


def _assign_players_to_positions(
    stats_map: Dict[int, PlayerSeasonStats],
    team_classifications: Dict[str, str],
    team_rush_yards: Dict[str, int],
    state: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Each player assigned to one award position (highest score among eligible roster groups).
    Returns list of dicts with player, award_pos, classification, score.
    """
    assigned: List[Dict[str, Any]] = []
    for s in stats_map.values():
        primary = _award_position_from_roster(s.position) or _infer_award_position(s)
        if not primary:
            continue
        classification = team_classifications.get(s.team_name, "Unclassified")
        best_pos = primary
        best_score = _position_score(s, primary, team_rush_yards=team_rush_yards, state=state)
        assigned.append(
            {
                "player": s,
                "award_pos": best_pos,
                "classification": classification,
                "score": best_score,
                "key": (s.player_name, s.team_name),
            }
        )
    return assigned


def _build_class_all_state(
    assigned: List[Dict[str, Any]],
    classification: str,
    team_rush_yards: Dict[str, int],
    state: Optional[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    used: set = set()
    tiers: Dict[str, List[Dict[str, Any]]] = {
        "first_team": [],
        "second_team": [],
        "honorable_mention": [],
    }
    tier_order = ("first_team", "second_team", "honorable_mention")

    for tier in tier_order:
        honorable = tier == "honorable_mention"
        for award_pos, count in ALL_STATE_SLOT_COUNTS:
            pool_strict = [
                a
                for a in assigned
                if a["classification"] == classification
                and a["award_pos"] == award_pos
                and a["key"] not in used
                and _meets_threshold(a["player"], award_pos, honorable=False)
            ]
            pool_strict.sort(key=lambda a: -a["score"])
            pool_lenient = [
                a
                for a in assigned
                if a["classification"] == classification
                and a["award_pos"] == award_pos
                and a["key"] not in used
                and a not in pool_strict
                and _meets_threshold(a["player"], award_pos, honorable=True)
            ]
            pool_lenient.sort(key=lambda a: -a["score"])
            chosen = pool_strict[:count]
            if len(chosen) < count:
                chosen.extend(pool_lenient[: count - len(chosen)])
            for a in chosen:
                used.add(a["key"])
                s = a["player"]
                tiers[tier].append(
                    _player_entry_dict(s, award_pos, classification, a["score"])
                )
    return tiers


def compute_awards(
    season_player_stats: Dict[int, PlayerSeasonStats],
    *,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute statewide POY awards and per-class All-State 1st / 2nd / Honorable Mention."""
    stats = dict(season_player_stats)
    _apply_roster_positions(stats, state)
    _ensure_roster_award_candidates(stats, state)
    team_classifications = _team_classifications_from_state(state)
    team_rush_yards = _team_rush_yards_from_state(state)

    for s in stats.values():
        if s.team_name in team_classifications:
            pass  # classifications already resolved

    poy = _pick_statewide_award(
        stats,
        _overall_score,
        lambda s: _overall_score(s) > (0, 0) or _defensive_score(s) > 0,
        [
            "pass_yds", "pass_td", "rush_yds", "rush_td", "rec_yds", "rec_td",
            "tackles", "sacks", "interceptions",
        ],
    )
    opoy = _pick_statewide_award(
        stats,
        _offensive_score,
        lambda s: _offensive_score(s) != (0, 0),
        ["pass_yds", "pass_td", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td"],
    )
    dpoy = _pick_statewide_award(
        stats,
        _defensive_score,
        lambda s: _defensive_score(s) > 0,
        ["tackles", "sacks", "tfl", "interceptions"],
    )

    for entry in (poy, opoy, dpoy):
        if entry and entry.get("team"):
            entry["classification"] = team_classifications.get(str(entry["team"]), "")

    assigned = _assign_players_to_positions(
        stats, team_classifications, team_rush_yards, state
    )
    classes = sorted({c for c in team_classifications.values() if c})
    if not classes:
        classes = sorted({a["classification"] for a in assigned if a.get("classification")})

    all_state_by_class: Dict[str, Any] = {}
    for cls in classes:
        all_state_by_class[cls] = _build_class_all_state(
            assigned, cls, team_rush_yards, state
        )

    # Backward-compatible alias: flatten first team across all classes (sorted by class)
    legacy_first: List[Dict[str, Any]] = []
    for cls in classes:
        legacy_first.extend(all_state_by_class.get(cls, {}).get("first_team", []))

    return {
        "player_of_the_year": poy,
        "offensive_player_of_the_year": opoy,
        "defensive_player_of_the_year": dpoy,
        "all_state_by_class": all_state_by_class,
        "all_state_first_team": legacy_first,
    }


def format_awards_text(awards: Dict[str, Any]) -> List[str]:
    """Format awards as readable text lines for season recaps."""
    lines: List[str] = []
    lines.append("AWARDS")
    lines.append("-" * 50)

    poy = awards.get("player_of_the_year")
    if poy:
        cls = f" [{poy.get('classification')}]" if poy.get("classification") else ""
        lines.append(f"Player of the Year: {poy['name']} ({poy['team']}){cls}")
    else:
        lines.append("Player of the Year: (none)")

    opoy = awards.get("offensive_player_of_the_year")
    if opoy:
        yds = opoy.get("pass_yds", 0) + opoy.get("rush_yds", 0) + opoy.get("rec_yds", 0)
        lines.append(f"Offensive Player of the Year: {opoy['name']} ({opoy['team']}) - {yds} total yds")
    else:
        lines.append("Offensive Player of the Year: (none)")

    dpoy = awards.get("defensive_player_of_the_year")
    if dpoy:
        parts = []
        if dpoy.get("tackles"):
            parts.append(f"{dpoy['tackles']} tack")
        if dpoy.get("sacks"):
            parts.append(f"{dpoy['sacks']} sack")
        if dpoy.get("interceptions"):
            parts.append(f"{dpoy['interceptions']} INT")
        line = f"Defensive Player of the Year: {dpoy['name']} ({dpoy['team']})"
        if parts:
            line += " - " + ", ".join(parts)
        lines.append(line)
    else:
        lines.append("Defensive Player of the Year: (none)")

    by_class = awards.get("all_state_by_class") or {}
    for cls in sorted(by_class.keys()):
        block = by_class[cls]
        if not isinstance(block, dict):
            continue
        for tier_key, tier_label in (
            ("first_team", "All-State 1st Team"),
            ("second_team", "All-State 2nd Team"),
            ("honorable_mention", "All-State Honorable Mention"),
        ):
            entries = block.get(tier_key) or []
            if not entries:
                continue
            lines.append("")
            lines.append(f"{tier_label} — {cls}")
            lines.append("-" * 30)
            for entry in entries:
                lines.append(_format_all_state_line(entry))

    if not by_class:
        lines.append("")
        lines.append("All-State 1st Team")
        lines.append("-" * 30)
        for entry in awards.get("all_state_first_team", []):
            lines.append(_format_all_state_line(entry))

    return lines


def _format_all_state_line(entry: Dict[str, Any]) -> str:
    pos = entry.get("position", "?")
    name = entry.get("name", "?")
    team = entry.get("team", "?")
    s = entry.get("stats") or {}
    if pos in ("QB", "RB", "WR", "TE"):
        yds = s.get("pass_yds", 0) + s.get("rush_yds", 0) + s.get("rec_yds", 0)
        ext = f" - {yds} yds" if yds else ""
    elif pos in ("K", "P"):
        if pos == "K":
            ext = f" - {s.get('fg_made', 0)}/{s.get('fg_att', 0)} FG"
        else:
            punts = s.get("punts", 0)
            py = s.get("punt_yards", 0)
            avg = round(py / punts, 1) if punts else 0
            ext = f" - {avg} avg ({punts} punts)"
    elif pos == "OL":
        ext = ""
    else:
        t, sa, i = s.get("tackles", 0), s.get("sacks", 0), s.get("interceptions", 0)
        ext = f" - {t} tack, {sa} sack, {i} INT" if (t or sa or i) else ""
    return f"  {pos}: {name} ({team}){ext}"


def team_awards_lines(awards: Dict[str, Any], team_name: str) -> List[str]:
    """Lines for a team recap — statewide POY and that team's All-State selections."""
    if not team_name:
        return []
    lines: List[str] = []
    tn = str(team_name).strip()

    for key, label in (
        ("player_of_the_year", "State Player of the Year"),
        ("offensive_player_of_the_year", "State Offensive POY"),
        ("defensive_player_of_the_year", "State Defensive POY"),
    ):
        entry = awards.get(key)
        if isinstance(entry, dict) and str(entry.get("team") or "") == tn:
            lines.append(f"{label}: {entry.get('name', '?')}")

    picks: List[str] = []
    by_class = awards.get("all_state_by_class") or {}
    for cls in sorted(by_class.keys()):
        block = by_class.get(cls) or {}
        if not isinstance(block, dict):
            continue
        for tier_key, tier_label in (
            ("first_team", "1st Team"),
            ("second_team", "2nd Team"),
            ("honorable_mention", "Honorable Mention"),
        ):
            for entry in block.get(tier_key) or []:
                if str(entry.get("team") or "") != tn:
                    continue
                picks.append(
                    f"- {entry.get('name', '?')} ({entry.get('position', '?')}, {cls} {tier_label})"
                )
    if picks:
        lines.append("All-State selections:")
        lines.extend(picks)
    return lines

