"""
Individual player game stats per game.
Tracks offense (QB: pass yds/TD, comp/att, INT; RB: rush yds/TD; WR: rec, rec yds, rec TD)
and defense (tackles, sacks, TFL, INT). Stats are attributed from play results using depth charts.
"""

import random
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from systems.depth_chart import build_depth_chart, DepthChart

if TYPE_CHECKING:
    from models.player import Player
    from models.team import Team


@dataclass
class PlayerGameStats:
    """Per-player, per-game stats. All counts default 0."""
    player_name: str = ""
    team_name: str = ""
    # Offense - QB
    pass_yds: int = 0
    pass_td: int = 0
    comp: int = 0
    att: int = 0
    int_thrown: int = 0
    # Offense - RB
    rush_yds: int = 0
    rush_td: int = 0
    # Offense - WR/TE
    rec: int = 0
    rec_yds: int = 0
    rec_td: int = 0
    # Defense
    tackles: int = 0
    sacks: int = 0
    tfl: int = 0
    interceptions: int = 0  # INT (defensive)
    # Special teams
    fg_made: int = 0
    fg_att: int = 0
    xp_made: int = 0
    xp_att: int = 0
    punts: int = 0
    punt_yards: int = 0


@dataclass
class PlayerSeasonStats:
    """Cumulative season stats for one player (same fields as PlayerGameStats)."""
    player_name: str = ""
    team_name: str = ""
    position: str = ""
    pass_yds: int = 0
    pass_td: int = 0
    comp: int = 0
    att: int = 0
    int_thrown: int = 0
    rush_yds: int = 0
    rush_td: int = 0
    rec: int = 0
    rec_yds: int = 0
    rec_td: int = 0
    tackles: int = 0
    sacks: int = 0
    tfl: int = 0
    interceptions: int = 0
    fg_made: int = 0
    fg_att: int = 0
    xp_made: int = 0
    xp_att: int = 0
    punts: int = 0
    punt_yards: int = 0


_EXTRA_STAT_FIELDS = ("fg_made", "fg_att", "xp_made", "xp_att", "punts", "punt_yards")


def season_player_stable_key(team_name: str, player_name: str) -> int:
    """Stable int key for season stats maps across save/load (name + team)."""
    return hash((str(team_name), str(player_name))) & 0x7FFFFFFFFFFFFFFF


def season_stats_map_to_jsonable(m: Dict[int, Any]) -> Dict[str, Any]:
    """Serialize player_id -> PlayerSeasonStats for JSON (league_save.json / API)."""
    out: Dict[str, Any] = {}
    for k, v in m.items():
        pid = int(k) if not isinstance(k, str) else int(k)
        key = str(pid)
        if isinstance(v, PlayerSeasonStats):
            out[key] = asdict(v)
        elif isinstance(v, dict):
            out[key] = v
        else:
            raise TypeError(f"Unexpected playoff stats value type: {type(v)}")
    return out


def season_stats_map_from_jsonable(m: Any) -> Dict[int, PlayerSeasonStats]:
    """Restore PlayerSeasonStats objects from JSON-loaded dict."""
    if not m:
        return {}
    out: Dict[int, PlayerSeasonStats] = {}
    for k, v in m.items():
        pid = int(k) if isinstance(k, str) else int(k)
        if isinstance(v, PlayerSeasonStats):
            out[pid] = v
        elif isinstance(v, dict):
            out[pid] = PlayerSeasonStats(
                player_name=str(v.get("player_name", "")),
                team_name=str(v.get("team_name", "")),
                pass_yds=int(v.get("pass_yds", 0)),
                pass_td=int(v.get("pass_td", 0)),
                comp=int(v.get("comp", 0)),
                att=int(v.get("att", 0)),
                int_thrown=int(v.get("int_thrown", 0)),
                rush_yds=int(v.get("rush_yds", 0)),
                rush_td=int(v.get("rush_td", 0)),
                rec=int(v.get("rec", 0)),
                rec_yds=int(v.get("rec_yds", 0)),
                rec_td=int(v.get("rec_td", 0)),
                tackles=int(v.get("tackles", 0)),
                sacks=int(v.get("sacks", 0)),
                tfl=int(v.get("tfl", 0)),
                interceptions=int(v.get("interceptions", 0)),
                position=str(v.get("position", "") or ""),
                fg_made=int(v.get("fg_made", 0)),
                fg_att=int(v.get("fg_att", 0)),
                xp_made=int(v.get("xp_made", 0)),
                xp_att=int(v.get("xp_att", 0)),
                punts=int(v.get("punts", 0)),
                punt_yards=int(v.get("punt_yards", 0)),
            )
    return out


def player_game_stats_map_to_json_list(stats_map: Dict[int, PlayerGameStats]) -> List[Dict[str, Any]]:
    """Serialize per-game player stats for league_save week_results / API (matches frontend field names)."""
    out: List[Dict[str, Any]] = []
    for gs in stats_map.values():
        if not isinstance(gs, PlayerGameStats):
            continue
        out.append(
            {
                "player_name": gs.player_name,
                "team_name": gs.team_name,
                "pass_yds": gs.pass_yds,
                "pass_td": gs.pass_td,
                "comp": gs.comp,
                "att": gs.att,
                "int_thrown": gs.int_thrown,
                "rush_yds": gs.rush_yds,
                "rush_td": gs.rush_td,
                "rec": gs.rec,
                "rec_yds": gs.rec_yds,
                "rec_td": gs.rec_td,
                "tackles": gs.tackles,
                "sacks": gs.sacks,
                "tfl": gs.tfl,
                "interceptions": gs.interceptions,
                "fg_made": gs.fg_made,
                "fg_att": gs.fg_att,
                "xp_made": gs.xp_made,
                "xp_att": gs.xp_att,
                "punts": gs.punts,
                "punt_yards": gs.punt_yards,
            }
        )
    return out


def player_game_stats_by_id_to_json(stats_map: Dict[int, PlayerGameStats]) -> Dict[str, Any]:
    """JSON-serialize coach-mode stats on Game (player_id -> stat fields) for DB persistence."""
    return {str(pid): asdict(gs) for pid, gs in stats_map.items()}


def player_game_stats_by_id_from_json(raw: Any) -> Dict[int, PlayerGameStats]:
    """Restore coach-mode stats from Game JSON (inverse of player_game_stats_by_id_to_json)."""
    if not raw:
        return {}
    if isinstance(raw, list):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: Dict[int, PlayerGameStats] = {}
    for k, v in raw.items():
        if not isinstance(v, dict):
            continue
        try:
            pid = int(k)
        except (TypeError, ValueError):
            continue
        out[pid] = PlayerGameStats(
            player_name=str(v.get("player_name", "")),
            team_name=str(v.get("team_name", "")),
            pass_yds=int(v.get("pass_yds", 0)),
            pass_td=int(v.get("pass_td", 0)),
            comp=int(v.get("comp", 0)),
            att=int(v.get("att", 0)),
            int_thrown=int(v.get("int_thrown", 0)),
            rush_yds=int(v.get("rush_yds", 0)),
            rush_td=int(v.get("rush_td", 0)),
            rec=int(v.get("rec", 0)),
            rec_yds=int(v.get("rec_yds", 0)),
            rec_td=int(v.get("rec_td", 0)),
            tackles=int(v.get("tackles", 0)),
            sacks=int(v.get("sacks", 0)),
            tfl=int(v.get("tfl", 0)),
            interceptions=int(v.get("interceptions", 0)),
            fg_made=int(v.get("fg_made", 0)),
            fg_att=int(v.get("fg_att", 0)),
            xp_made=int(v.get("xp_made", 0)),
            xp_att=int(v.get("xp_att", 0)),
            punts=int(v.get("punts", 0)),
            punt_yards=int(v.get("punt_yards", 0)),
        )
    return out


def merge_game_stats_into_season(
    season_stats_map: Dict[int, PlayerSeasonStats],
    game_stats_map: Dict[int, PlayerGameStats],
) -> None:
    """Add one game's stats into the season totals. Updates season_stats_map in place."""
    for player_id, gs in game_stats_map.items():
        if player_id not in season_stats_map:
            season_stats_map[player_id] = PlayerSeasonStats(
                player_name=gs.player_name,
                team_name=gs.team_name,
            )
        s = season_stats_map[player_id]
        s.pass_yds += gs.pass_yds
        s.pass_td += gs.pass_td
        s.comp += gs.comp
        s.att += gs.att
        s.int_thrown += gs.int_thrown
        s.rush_yds += gs.rush_yds
        s.rush_td += gs.rush_td
        s.rec += gs.rec
        s.rec_yds += gs.rec_yds
        s.rec_td += gs.rec_td
        s.tackles += gs.tackles
        s.sacks += gs.sacks
        s.tfl += gs.tfl
        s.interceptions += gs.interceptions
        for fld in _EXTRA_STAT_FIELDS:
            setattr(s, fld, getattr(s, fld) + getattr(gs, fld))


def _absorb_stat_row_into_season(
    season_stats_map: Dict[int, PlayerSeasonStats],
    row: Dict[str, Any],
    *,
    position: str = "",
) -> None:
    """Merge one week_results / JSON player stat row into season totals."""
    player_name = str(row.get("player_name") or row.get("name") or "").strip()
    team_name = str(row.get("team_name") or row.get("team") or "").strip()
    if not player_name or not team_name:
        return
    key = season_player_stable_key(team_name, player_name)
    if key not in season_stats_map:
        season_stats_map[key] = PlayerSeasonStats(player_name=player_name, team_name=team_name)
    s = season_stats_map[key]
    if position and not s.position:
        s.position = position
    s.pass_yds += int(row.get("pass_yds", 0) or 0)
    s.pass_td += int(row.get("pass_td", 0) or 0)
    s.comp += int(row.get("comp", 0) or 0)
    s.att += int(row.get("att", 0) or 0)
    s.int_thrown += int(row.get("int_thrown", 0) or 0)
    s.rush_yds += int(row.get("rush_yds", 0) or 0)
    s.rush_td += int(row.get("rush_td", 0) or 0)
    s.rec += int(row.get("rec", 0) or 0)
    s.rec_yds += int(row.get("rec_yds", 0) or 0)
    s.rec_td += int(row.get("rec_td", 0) or 0)
    s.tackles += int(row.get("tackles", 0) or 0)
    s.sacks += int(row.get("sacks", 0) or 0)
    s.tfl += int(row.get("tfl", 0) or 0)
    s.interceptions += int(row.get("interceptions", 0) or 0)
    for fld in _EXTRA_STAT_FIELDS:
        setattr(s, fld, getattr(s, fld) + int(row.get(fld, 0) or 0))


def rebuild_season_player_stats_from_state(state: Dict[str, Any]) -> Dict[int, PlayerSeasonStats]:
    """
    Full-season player stats from regular-season week_results plus playoff rollup.
    Keys are stable per (team, player) so awards work after save/load.
    """
    roster_pos: Dict[Tuple[str, str], str] = {}
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
            if pname:
                roster_pos[(team_name, pname)] = str(p.get("position") or "").strip()

    out: Dict[int, PlayerSeasonStats] = {}
    for wk in state.get("week_results") or []:
        for g in wk or []:
            if not isinstance(g, dict) or not g.get("played"):
                continue
            for row in g.get("player_stats") or []:
                if not isinstance(row, dict):
                    continue
                pn = str(row.get("player_name") or row.get("name") or "").strip()
                tn = str(row.get("team_name") or row.get("team") or "").strip()
                pos = roster_pos.get((tn, pn), "")
                _absorb_stat_row_into_season(out, row, position=pos)

    playoff = season_stats_map_from_jsonable(state.get("playoff_season_player_stats") or {})
    for ps in playoff.values():
        key = season_player_stable_key(ps.team_name, ps.player_name)
        if key not in out:
            out[key] = PlayerSeasonStats(
                player_name=ps.player_name,
                team_name=ps.team_name,
                position=roster_pos.get((ps.team_name, ps.player_name), ps.position or ""),
            )
        dst = out[key]
        if not dst.position:
            dst.position = roster_pos.get((ps.team_name, ps.player_name), ps.position or "")
        dst.pass_yds += ps.pass_yds
        dst.pass_td += ps.pass_td
        dst.comp += ps.comp
        dst.att += ps.att
        dst.int_thrown += ps.int_thrown
        dst.rush_yds += ps.rush_yds
        dst.rush_td += ps.rush_td
        dst.rec += ps.rec
        dst.rec_yds += ps.rec_yds
        dst.rec_td += ps.rec_td
        dst.tackles += ps.tackles
        dst.sacks += ps.sacks
        dst.tfl += ps.tfl
        dst.interceptions += ps.interceptions
        for fld in _EXTRA_STAT_FIELDS:
            setattr(dst, fld, getattr(dst, fld) + getattr(ps, fld))

    for s in out.values():
        if not s.position:
            s.position = roster_pos.get((s.team_name, s.player_name), "")

    return out


def record_pat(
    stats_map: Dict[int, PlayerGameStats],
    offense_team: "Team",
    offense_dc: DepthChart,
    pat_result: Dict[str, Any],
) -> None:
    """Attribute extra-point attempts to the kicker."""
    if not pat_result.get("pat_kick"):
        return
    kicker = _pick_offense_player(offense_dc, "K", 0)
    if kicker is None:
        return
    s = _get_or_create(stats_map, kicker, offense_team.name)
    s.xp_att += 1
    if pat_result.get("pat_success"):
        s.xp_made += 1


def record_special_teams(
    stats_map: Dict[int, PlayerGameStats],
    home_team: "Team",
    away_team: "Team",
    home_dc: DepthChart,
    away_dc: DepthChart,
    possession: str,
    result: Dict[str, Any],
) -> None:
    """Attribute punts and field goals from silent-sim 4th-down decisions."""
    if possession == "home":
        off_team, off_dc = home_team, home_dc
    else:
        off_team, off_dc = away_team, away_dc
    off_name = off_team.name

    if result.get("field_goal"):
        kicker = _pick_offense_player(off_dc, "K", 0)
        if kicker is not None:
            ks = _get_or_create(stats_map, kicker, off_name)
            ks.fg_att += 1
            if result.get("field_goal_good"):
                ks.fg_made += 1
    if result.get("punt"):
        punter = _pick_offense_player(off_dc, "P", 0)
        if punter is not None:
            ps = _get_or_create(stats_map, punter, off_name)
            dist = int(result.get("punt_distance") or 40)
            ps.punts += 1
            ps.punt_yards += dist


def _get_or_create(stats_map: Dict[int, PlayerGameStats], player: "Player", team_name: str) -> PlayerGameStats:
    key = id(player)
    if key not in stats_map:
        stats_map[key] = PlayerGameStats(player_name=player.name, team_name=team_name)
    return stats_map[key]


def _pick_offense_player(dc: DepthChart, position: str, prefer_slot: int = 0) -> Optional["Player"]:
    p = dc.get_starter(position, "offense", prefer_slot)
    if p is not None:
        return p
    return None


def _pick_receiver(dc: DepthChart) -> Optional["Player"]:
    """
    Pick a receiver for a completed pass. Spreads catches across WR1–3, TE, RB
    so multiple receivers get stats. Weights: WR1 26%, WR2 24%, WR3 18%, TE 18%, RB 14%.
    """
    candidates: List[Tuple["Player", float]] = []
    for pos, slot, weight in [
        ("WR", 0, 26), ("WR", 1, 24), ("WR", 2, 18),
        ("TE", 0, 18), ("RB", 0, 8), ("RB", 1, 6),
    ]:
        p = dc.get_starter(pos, "offense", slot)
        if p is not None:
            candidates.append((p, weight))
    if not candidates:
        return None
    players, weights = zip(*candidates)
    return random.choices(players, weights=weights, k=1)[0]


def _spread_weight_for_stat(stats_map: Dict[int, PlayerGameStats], player: "Player", base_weight: float, stat_attr: str) -> float:
    """
    Down-weight players already piling up tackles/sacks so box scores spread across the defense.
    Tuned so elite games land ~15–18 tackles / ~1–2 sacks rather than one MIKE dominating.
    """
    st = stats_map.get(id(player))
    n = int(getattr(st, stat_attr, 0) or 0) if st else 0
    if stat_attr == "sacks":
        # Stronger concentration fight (few sack events per game).
        soften = 1.0 / (2.25 + float(n) * 1.35 + (float(max(n - 1, 0)) ** 1.2) * 0.95)
        return float(base_weight) * soften
    soften = 1.0 / (2.05 + float(n) * 0.48 + (float(n) ** 1.12) * 0.28)
    return float(base_weight) * soften


def _pick_weighted_defender(
    dc: DepthChart,
    weighted_slots: List[Tuple[str, int, float]],
    stats_map: Dict[int, PlayerGameStats],
    stat_attr: str,
) -> Optional["Player"]:
    """Pick one defender from (position, depth_slot, weight) rows using spread-adjusted weights."""
    out: List[Tuple["Player", float]] = []
    for pos, slot, base_w in weighted_slots:
        if base_w <= 0:
            continue
        p = dc.get_starter(pos, "defense", slot)
        if p is None:
            continue
        w = _spread_weight_for_stat(stats_map, p, base_w, stat_attr)
        if w > 0:
            out.append((p, w))
    if not out:
        return None
    players, weights = zip(*out)
    return random.choices(players, weights=weights, k=1)[0]


def _pick_run_tackler(
    dc: DepthChart, yards: int, stats_map: Dict[int, PlayerGameStats],
) -> Optional["Player"]:
    """
    Pick tackler on run play. Spread by run distance; weights kept fairly flat so
    DL/LB/S/CB all get realistic shares (targets: most defenders <10 tkl/game, stars mid-teens).
    """
    if yards <= 4:
        weighted_slots = [
            ("DE", 0, 14), ("DE", 1, 14), ("DE", 2, 10),
            ("DT", 0, 14), ("DT", 1, 13),
            ("LB", 0, 13), ("LB", 1, 13), ("LB", 2, 10),
            ("S", 0, 10), ("S", 1, 9),
            ("CB", 0, 9), ("CB", 1, 8),
        ]
    elif yards <= 8:
        weighted_slots = [
            ("LB", 0, 14), ("LB", 1, 14), ("LB", 2, 11),
            ("S", 0, 14), ("S", 1, 13),
            ("DE", 0, 10), ("DE", 1, 9), ("DT", 0, 9), ("DT", 1, 8),
            ("CB", 0, 10), ("CB", 1, 9),
        ]
    else:
        weighted_slots = [
            ("S", 0, 16), ("S", 1, 15),
            ("CB", 0, 16), ("CB", 1, 15),
            ("LB", 0, 12), ("LB", 1, 11), ("LB", 2, 9),
            ("DE", 0, 6), ("DT", 0, 6),
        ]
    return _pick_weighted_defender(dc, weighted_slots, stats_map, "tackles")


def _pick_pass_tackler(dc: DepthChart, stats_map: Dict[int, PlayerGameStats]) -> Optional["Player"]:
    """Tackler on completed pass — flat weights across second level and perimeter."""
    weighted_slots = [
        ("CB", 0, 14), ("CB", 1, 14),
        ("S", 0, 14), ("S", 1, 13),
        ("LB", 0, 14), ("LB", 1, 13), ("LB", 2, 11),
        ("DE", 0, 11), ("DE", 1, 10),
        ("DT", 0, 10), ("DT", 1, 9),
    ]
    return _pick_weighted_defender(dc, weighted_slots, stats_map, "tackles")


def _pick_sacker(dc: DepthChart, stats_map: Dict[int, PlayerGameStats]) -> Optional["Player"]:
    """Sack credit — deliberately flat so no single EDGE hoovers ~all sacks."""
    weighted_slots = [
        ("DE", 0, 17), ("DE", 1, 17), ("DE", 2, 13),
        ("DT", 0, 16), ("DT", 1, 15),
        ("LB", 0, 16), ("LB", 1, 14), ("LB", 2, 11),
    ]
    return _pick_weighted_defender(dc, weighted_slots, stats_map, "sacks")


def _pick_interceptor(dc: DepthChart) -> Optional["Player"]:
    """Pick INT defender. CB and S."""
    candidates = [
        ("CB", 0, 28), ("CB", 1, 22), ("S", 0, 26), ("S", 1, 24),
    ]
    out: List[Tuple["Player", float]] = []
    for pos, slot, weight in candidates:
        p = dc.get_starter(pos, "defense", slot)
        if p is not None:
            out.append((p, weight))
    if not out:
        return None
    players, weights = zip(*out)
    return random.choices(players, weights=weights, k=1)[0]




def create_game_stats(
    home_team: "Team",
    away_team: "Team",
    home_dc: Optional[DepthChart] = None,
    away_dc: Optional[DepthChart] = None,
) -> tuple:
    """
    Create a fresh GameStats container and init zero stats for all players
    who might play (from depth charts). Returns (stats_map, home_dc, away_dc).
    stats_map: Dict[int, PlayerGameStats] keyed by id(player).
    """
    home_dc = home_dc or build_depth_chart(home_team)
    away_dc = away_dc or build_depth_chart(away_team)
    stats_map: Dict[int, PlayerGameStats] = {}

    for team, dc, team_name in [
        (home_team, home_dc, home_team.name),
        (away_team, away_dc, away_team.name),
    ]:
        for pos_list, side in [(list(dc.offense.keys()), "offense"), (list(dc.defense.keys()), "defense")]:
            for pos in pos_list:
                chart = dc.offense if side == "offense" else dc.defense
                for p in chart.get(pos, [])[:4]:
                    _get_or_create(stats_map, p, team_name)

    return (stats_map, home_dc, away_dc)


def record_play(
    stats_map: Dict[int, PlayerGameStats],
    home_team: "Team",
    away_team: "Team",
    home_dc: DepthChart,
    away_dc: DepthChart,
    possession: str,
    offense_call: str,
    result: Dict[str, Any],
) -> None:
    """
    Attribute one play to players and update stats_map.
    possession: "home" or "away" (who had the ball this play)
    offense_call: "1" = run, "2" = pass
    result: dict with yards, touchdown, sack, interception, incomplete_pass
    """
    is_run = offense_call == "1"
    yards = result.get("yards", 0)
    touchdown = result.get("touchdown", False)
    sack = result.get("sack", False)
    interception = result.get("interception", False)
    incomplete = result.get("incomplete_pass", False)
    scramble = result.get("scramble", False)

    if possession == "home":
        off_team, off_dc, def_team, def_dc = home_team, home_dc, away_team, away_dc
    else:
        off_team, off_dc, def_team, def_dc = away_team, away_dc, home_team, home_dc

    off_name = off_team.name
    def_name = def_team.name

    if is_run:
        # Run: RB gets rush_yds, rush_td; defense gets tackle (and TFL if yards < 0)
        rb = _pick_offense_player(off_dc, "RB", random.randint(0, 2))
        if rb is not None:
            s = _get_or_create(stats_map, rb, off_name)
            s.rush_yds += yards
            if touchdown:
                s.rush_td += 1
        tackler = _pick_run_tackler(def_dc, yards, stats_map)
        if tackler is not None:
            s = _get_or_create(stats_map, tackler, def_name)
            s.tackles += 1
            if yards < 0:
                s.tfl += 1
    else:
        # Pass
        qb = _pick_offense_player(off_dc, "QB", 0)
        if qb is not None:
            qb_s = _get_or_create(stats_map, qb, off_name)
            qb_s.att += 1
            if sack:
                # Sack: no completion, QB gets attempt only; defense gets sack (+ TFL)
                sacker = _pick_sacker(def_dc, stats_map)
                if sacker is not None:
                    ss = _get_or_create(stats_map, sacker, def_name)
                    ss.sacks += 1
                    ss.tfl += 1
                return
            if interception:
                qb_s.int_thrown += 1
                int_player = _pick_interceptor(def_dc)
                if int_player is not None:
                    si = _get_or_create(stats_map, int_player, def_name)
                    si.interceptions += 1
                return
            if incomplete:
                return
            # Complete pass: yards, maybe TD
            qb_s.comp += 1
            qb_s.pass_yds += yards
            if touchdown:
                qb_s.pass_td += 1
            # Receiver: spread catches across WR1–3, TE, RB (3+ receivers typically)
            recv = _pick_receiver(off_dc)
            if recv is not None:
                rs = _get_or_create(stats_map, recv, off_name)
                rs.rec += 1
                rs.rec_yds += yards
                if touchdown:
                    rs.rec_td += 1
        # Defense tackle on completion or QB scramble (treat scramble stop like run fits)
        if not interception and not sack:
            tackler = _pick_run_tackler(def_dc, yards, stats_map) if scramble else _pick_pass_tackler(def_dc, stats_map)
            if tackler is not None:
                ts = _get_or_create(stats_map, tackler, def_name)
                ts.tackles += 1


def format_game_box_score(
    stats_map: Dict[int, PlayerGameStats],
    home_team_name: str,
    away_team_name: str,
) -> List[str]:
    """Format individual player stats for one game as text lines."""
    lines = []
    lines.append("")
    lines.append("PLAYER GAME STATS")
    lines.append("-" * 50)

    for team_name in (home_team_name, away_team_name):
        lines.append(f"\n{team_name}")
        team_entries = [s for s in stats_map.values() if s.team_name == team_name]
        team_entries.sort(key=lambda s: (-(s.pass_yds + s.rush_yds + s.rec_yds), -s.tackles, s.player_name))

        # Offense
        qbs = [s for s in team_entries if s.att > 0]
        if qbs:
            lines.append("  QB:")
            for s in qbs:
                lines.append(f"    {s.player_name}: {s.comp}/{s.att} {s.pass_yds} yds, {s.pass_td} TD, {s.int_thrown} INT")

        rbs = [s for s in team_entries if s.rush_yds != 0 or s.rush_td > 0]
        if rbs:
            lines.append("  RB:")
            for s in rbs:
                lines.append(f"    {s.player_name}: {s.rush_yds} rush yds, {s.rush_td} TD")

        wrs = [s for s in team_entries if s.rec > 0 or s.rec_yds != 0 or s.rec_td > 0]
        if wrs:
            lines.append("  WR/TE:")
            for s in wrs:
                lines.append(f"    {s.player_name}: {s.rec} rec, {s.rec_yds} yds, {s.rec_td} TD")

        # Defense
        defs = [s for s in team_entries if s.tackles > 0 or s.sacks > 0 or s.tfl > 0 or s.interceptions > 0]
        if defs:
            lines.append("  Defense:")
            for s in defs:
                parts = [f"{s.player_name}:"]
                if s.tackles:
                    parts.append(f"{s.tackles} tkl")
                if s.sacks:
                    parts.append(f"{s.sacks} sk")
                if s.tfl:
                    parts.append(f"{s.tfl} TFL")
                if s.interceptions:
                    parts.append(f"{s.interceptions} INT")
                lines.append("    " + " ".join(parts))

    return lines


def format_season_player_stats(
    season_stats_map: Dict[int, PlayerSeasonStats],
    team_names_order: Optional[List[str]] = None,
    top_n: int = 5,
) -> List[str]:
    """
    Format season player stats for a separate file: league leaders then by-team.
    season_stats_map: Dict[player_id, PlayerSeasonStats] from merge_game_stats_into_season.
    team_names_order: optional list of team names for consistent ordering.
    top_n: number of league leaders per category.
    """
    lines: List[str] = []
    all_stats = list(season_stats_map.values())
    if not all_stats:
        return ["No player stats recorded this season."]

    teams = list({s.team_name for s in all_stats})
    if team_names_order:
        teams = [t for t in team_names_order if t in teams] + [t for t in teams if t not in team_names_order]

    # ---------- LEAGUE LEADERS ----------
    lines.append("=" * 60)
    lines.append("  LEAGUE LEADERS (Season)")
    lines.append("=" * 60)

    # Passing yards
    pass_yds = [s for s in all_stats if s.att > 0]
    pass_yds.sort(key=lambda s: -s.pass_yds)
    if pass_yds:
        lines.append("")
        lines.append("Passing Yards")
        lines.append("-" * 40)
        for i, s in enumerate(pass_yds[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.pass_yds} yds  ({s.comp}/{s.att}, {s.pass_td} TD, {s.int_thrown} INT)")

    # Passing TD
    if pass_yds:
        pass_td_list = sorted(pass_yds, key=lambda s: -s.pass_td)
        lines.append("")
        lines.append("Passing Touchdowns")
        lines.append("-" * 40)
        for i, s in enumerate(pass_td_list[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.pass_td} TD")

    # Rushing yards
    rush_yds = [s for s in all_stats if s.rush_yds != 0 or s.rush_td > 0]
    rush_yds.sort(key=lambda s: (-s.rush_yds, -s.rush_td))
    if rush_yds:
        lines.append("")
        lines.append("Rushing Yards")
        lines.append("-" * 40)
        for i, s in enumerate(rush_yds[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.rush_yds} yds, {s.rush_td} TD")

    # Receiving
    rec_stats = [s for s in all_stats if s.rec > 0 or s.rec_yds != 0 or s.rec_td > 0]
    rec_stats.sort(key=lambda s: (-s.rec_yds, -s.rec))
    if rec_stats:
        lines.append("")
        lines.append("Receiving Yards")
        lines.append("-" * 40)
        for i, s in enumerate(rec_stats[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.rec} rec, {s.rec_yds} yds, {s.rec_td} TD")

    # Tackles
    defs = [s for s in all_stats if s.tackles > 0]
    defs.sort(key=lambda s: -s.tackles)
    if defs:
        lines.append("")
        lines.append("Tackles")
        lines.append("-" * 40)
        for i, s in enumerate(defs[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.tackles} tkl")

    # Sacks
    sack_list = [s for s in all_stats if s.sacks > 0]
    sack_list.sort(key=lambda s: -s.sacks)
    if sack_list:
        lines.append("")
        lines.append("Sacks")
        lines.append("-" * 40)
        for i, s in enumerate(sack_list[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.sacks} sk")

    # Interceptions (defensive)
    int_list = [s for s in all_stats if s.interceptions > 0]
    int_list.sort(key=lambda s: -s.interceptions)
    if int_list:
        lines.append("")
        lines.append("Interceptions")
        lines.append("-" * 40)
        for i, s in enumerate(int_list[:top_n], 1):
            lines.append(f"  {i}. {s.player_name} ({s.team_name}): {s.interceptions} INT")

    # ---------- BY TEAM ----------
    lines.append("")
    lines.append("=" * 60)
    lines.append("  INDIVIDUAL PLAYER STATS BY TEAM")
    lines.append("=" * 60)

    for team_name in teams:
        team_entries = [s for s in all_stats if s.team_name == team_name]
        team_entries.sort(key=lambda s: (-(s.pass_yds + s.rush_yds + s.rec_yds), -s.tackles, s.player_name))

        lines.append("")
        lines.append(team_name)
        lines.append("-" * 40)

        qbs = [s for s in team_entries if s.att > 0]
        if qbs:
            lines.append("  QB:")
            for s in qbs:
                pct = (100 * s.comp / s.att) if s.att else 0
                lines.append(f"    {s.player_name}: {s.comp}/{s.att} ({pct:.1f}%) {s.pass_yds} yds, {s.pass_td} TD, {s.int_thrown} INT")

        rbs = [s for s in team_entries if s.rush_yds != 0 or s.rush_td > 0]
        if rbs:
            lines.append("  RB:")
            for s in rbs:
                lines.append(f"    {s.player_name}: {s.rush_yds} rush yds, {s.rush_td} TD")

        wrs = [s for s in team_entries if s.rec > 0 or s.rec_yds != 0 or s.rec_td > 0]
        if wrs:
            lines.append("  WR/TE:")
            for s in wrs:
                lines.append(f"    {s.player_name}: {s.rec} rec, {s.rec_yds} yds, {s.rec_td} TD")

        defs_team = [s for s in team_entries if s.tackles > 0 or s.sacks > 0 or s.tfl > 0 or s.interceptions > 0]
        if defs_team:
            lines.append("  Defense:")
            for s in defs_team:
                parts = [f"{s.player_name}:"]
                if s.tackles:
                    parts.append(f"{s.tackles} tkl")
                if s.sacks:
                    parts.append(f"{s.sacks} sk")
                if s.tfl:
                    parts.append(f"{s.tfl} TFL")
                if s.interceptions:
                    parts.append(f"{s.interceptions} INT")
                lines.append("    " + " ".join(parts))

    return lines
